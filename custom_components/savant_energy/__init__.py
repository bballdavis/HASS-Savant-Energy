"""
Integration for Savant Energy.
Provides Home Assistant integration for Savant relay and energy monitoring devices.
"""

import copy
import logging
from datetime import timedelta, datetime
import os
import traceback

import homeassistant.helpers.config_validation as cv  # type: ignore
import voluptuous as vol  # type: ignore

from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator  # type: ignore
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry  # type: ignore
from homeassistant.helpers.translation import async_get_translations  # type: ignore
from homeassistant.components import frontend  # type: ignore

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_OLA_PORT,
)
from .snapshot_data import fetch_current_energy_snapshot
from .utils import async_get_all_dmx_status, DMX_CACHE_SECONDS # type: ignore

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ADDRESS): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Optional(CONF_SCAN_INTERVAL, default=15): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Lovelace card file information
LOVELACE_CARD_FILENAME = "savant-energy-scenes-card.js"


class SavantEnergyCoordinator(DataUpdateCoordinator):
    """
    Coordinator for Savant Energy data updates.
    Handles periodic polling of the Savant controller for energy and relay status data.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """
        Initialize the coordinator.
        Args:
            hass: Home Assistant instance
            entry: ConfigEntry for this integration
        """
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, 15)
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.address = entry.data[CONF_ADDRESS]
        self.port = entry.data[CONF_PORT]
        self.config_entry = entry  # Store config entry directly
        self.base_scan_interval_seconds = scan_interval
        self.consecutive_snapshot_failures = 0
        self.cached_present_demands = []
        self.last_snapshot_error = None
        self.dmx_data = {}  # Mapping of channel -> status (for debugging)
        self.dmx_last_update = None

    def _set_snapshot_update_interval(self, success: bool) -> None:
        """Adjust polling interval with capped backoff while snapshot retrieval is unhealthy."""
        if success:
            self.consecutive_snapshot_failures = 0
            next_interval_seconds = self.base_scan_interval_seconds
        else:
            self.consecutive_snapshot_failures += 1
            next_interval_seconds = min(
                max(
                    self.base_scan_interval_seconds,
                    self.base_scan_interval_seconds * (2 ** (self.consecutive_snapshot_failures - 1)),
                ),
                30,
            )

        next_interval = timedelta(seconds=next_interval_seconds)
        if self.update_interval != next_interval:
            self.update_interval = next_interval
            _LOGGER.info(
                "Updated Savant snapshot poll interval to %s seconds after %s",
                next_interval_seconds,
                "successful refresh" if success else "snapshot failure",
            )

    async def _async_update_data(self):
        """
        Fetch data from the Savant controller and update DMX status (for debugging).
        Returns a dict with snapshot_data and dmx_data.
        Ensures proper error handling and logging to diagnose data issues.
        """
        try:
            # Get snapshot data from energy controller
            snapshot_result = await self.hass.async_add_executor_job(
                fetch_current_energy_snapshot, self.address, self.port
            )

            if not snapshot_result.success or snapshot_result.data is None:
                self._set_snapshot_update_interval(success=False)
                self.last_snapshot_error = {
                    "type": snapshot_result.error_type,
                    "message": snapshot_result.error_message,
                    "raw_excerpt": snapshot_result.raw_excerpt,
                    "timestamp": now.isoformat(),
                }
                _LOGGER.warning(
                    "Savant snapshot refresh failed (%s): %s%s",
                    snapshot_result.error_type,
                    snapshot_result.error_message,
                    f" | sample: {snapshot_result.raw_excerpt}" if snapshot_result.raw_excerpt else "",
                )

                existing_data = dict(self.data) if isinstance(self.data, dict) else {}
                existing_data.setdefault("snapshot_data", None)
                existing_data["dmx_data"] = self.dmx_data
                existing_data["cached_present_demands"] = copy.deepcopy(self.cached_present_demands)
                existing_data["snapshot_status"] = {
                    "ok": False,
                    "error_type": snapshot_result.error_type,
                    "error_message": snapshot_result.error_message,
                    "raw_excerpt": snapshot_result.raw_excerpt,
                    "failure_count": self.consecutive_snapshot_failures,
                    "next_retry_seconds": int(self.update_interval.total_seconds()),
                    "used_cached_snapshot": bool(existing_data.get("snapshot_data")),
                }
                return existing_data

            snapshot_data = snapshot_result.data
            self._set_snapshot_update_interval(success=True)
            self.last_snapshot_error = None

            present_demands = snapshot_data.get("presentDemands", [])
            if isinstance(present_demands, list):
                self.cached_present_demands = [
                    copy.deepcopy(device)
                    for device in present_demands
                    if isinstance(device, dict)
                ]

            # Check if we have valid device data to report for debugging
            if "presentDemands" in snapshot_data:
                device_count = len(snapshot_data["presentDemands"])
                _LOGGER.info(f"Retrieved {device_count} devices in presentDemands")

                # Debug log each device found for troubleshooting
                for index, device in enumerate(snapshot_data["presentDemands"]):
                    has_uid = "uid" in device
                    has_name = "name" in device
                    has_percent = "percentCommanded" in device
                    if not all([has_uid, has_name, has_percent]):
                        _LOGGER.warning(
                            f"Incomplete device data: uid={has_uid}, name={has_name}, percentCommanded={has_percent}. Device: {device}"
                        )
                    _LOGGER.debug(
                        "Boot device[%d]: uid=%s name=%s channel=%s percentCommanded=%s power=%s voltage=%s capacity=%s",
                        index,
                        device.get("uid"),
                        device.get("name"),
                        device.get("channel"),
                        device.get("percentCommanded"),
                        device.get("power"),
                        device.get("voltage"),
                        device.get("capacity"),
                    )

            # Update DMX status for debugging if cache expired
            now = datetime.now()
            if (
                not self.dmx_last_update
                or (now - self.dmx_last_update).total_seconds() > DMX_CACHE_SECONDS
            ):
                _LOGGER.debug("Updating DMX status data due to expired cache")
                ola_port = self.config_entry.data.get("ola_port", DEFAULT_OLA_PORT)
                self.dmx_data = {}
                self.dmx_last_update = now

            return {
                "snapshot_data": snapshot_data,
                "dmx_data": self.dmx_data,
                "cached_present_demands": copy.deepcopy(self.cached_present_demands),
                "snapshot_status": {
                    "ok": True,
                    "error_type": None,
                    "error_message": None,
                    "raw_excerpt": None,
                    "failure_count": 0,
                    "next_retry_seconds": int(self.update_interval.total_seconds()),
                    "used_cached_snapshot": False,
                },
            }
        except Exception as exc:
            _LOGGER.error(f"Error updating data: {exc}")
            raise


async def _async_register_frontend_resource(hass: HomeAssistant) -> None:
    """
    Register the custom Lovelace card using Home Assistant's proper frontend system.
    This is the correct way to register custom cards that other integrations use.
    """
    try:
        # Register the static path for serving the card file
        card_path = os.path.join(os.path.dirname(__file__), LOVELACE_CARD_FILENAME)
        
        # Use Home Assistant's HTTP component to register static path
        # This serves the file at /local/savant_energy/savant-energy-scenes-card.js
        local_path = f"/local/{DOMAIN}"
        
        # Try the new method first (HA 2024.7+)
        try:
            from homeassistant.components.http import StaticPathConfig # type: ignore
            await hass.http.async_register_static_paths([
                StaticPathConfig(local_path, os.path.dirname(__file__), True)
            ])
            resource_url = f"{local_path}/{LOVELACE_CARD_FILENAME}"
            _LOGGER.info(f"Registered static path for card using new method: {resource_url}")
        except (ImportError, AttributeError):
            # Fallback to legacy method
            hass.http.register_static_path(local_path, os.path.dirname(__file__), True)
            resource_url = f"{local_path}/{LOVELACE_CARD_FILENAME}"
            _LOGGER.info(f"Registered static path for card using legacy method: {resource_url}")
        
        # Register the JavaScript resource with Home Assistant's frontend
        frontend.add_extra_js_url(hass, resource_url)
        _LOGGER.info(f"Successfully registered Lovelace card resource: {resource_url}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to register frontend resource: {e}")
        _LOGGER.exception("Full traceback:")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Savant Energy component from yaml configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Savant Energy from a config entry."""
    # Preload translations for the domain, making them available for UI flows and other parts of the integration
    await async_get_translations(hass, hass.config.language, DOMAIN)

    # Check for disable_scene_builder option
    disable_scene_builder = entry.options.get(
        "disable_scene_builder", entry.data.get("disable_scene_builder", False)
    )

    # Create coordinator and proceed with normal setup
    coordinator = SavantEnergyCoordinator(hass, entry)

    # Get initial data before setting up platforms
    _LOGGER.info("Fetching initial data from Savant Energy controller")
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    if coordinator.data is None or not coordinator.data.get("snapshot_data"):
        _LOGGER.warning(
            "Initial data fetch failed or returned no data - entities may be unavailable"
        )

    # Use PLATFORMS from const.py
    _LOGGER.info("Setting up Savant Energy platforms")
    setup_platforms = list(PLATFORMS)  # Make a copy to avoid modifying the original
    if not disable_scene_builder:
        setup_platforms.append("scene")

    await hass.config_entries.async_forward_entry_setups(entry, setup_platforms)

    # Register frontend resource after platforms are set up
    if not disable_scene_builder:
        await _async_register_frontend_resource(hass)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Use the same platform logic as in setup
    disable_scene_builder = entry.options.get(
        "disable_scene_builder", entry.data.get("disable_scene_builder", False)
    )

    unload_platforms = list(PLATFORMS)
    if not disable_scene_builder:
        unload_platforms.append("scene")

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, unload_platforms
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Handle options update by reloading the config entry.
    """
    await hass.config_entries.async_reload(entry.entry_id)


# All classes and functions are now documented for clarity and open source maintainability.
