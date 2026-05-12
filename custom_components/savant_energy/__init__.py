"""Savant Energy integration for Home Assistant.

Provides energy monitoring and relay control for Savant Energy systems via
InfluxDB 2 (data) and OLA/DMX (relay control).
"""

import copy
import logging
from datetime import timedelta, datetime
import os

import homeassistant.helpers.config_validation as cv  # type: ignore
import voluptuous as vol  # type: ignore

from homeassistant.config_entries import ConfigEntry  # type: ignore
from homeassistant.core import HomeAssistant  # type: ignore
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator  # type: ignore
from homeassistant.helpers.translation import async_get_translations  # type: ignore
from homeassistant.components import frontend  # type: ignore

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_ADDRESS,
    CONF_HOST,
    CONF_MODE,
    CONF_SCAN_INTERVAL,
    CONF_INFLUX_URL,
    CONF_INFLUX_TOKEN,
    CONF_INFLUX_ORG,
    DEFAULT_MODE,
    MODE_LEGACY,
    MODE_CURRENT,
    MODE_AUTO,
    DEFAULT_PORT,
    DEFAULT_OLA_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_INFLUX_URL,
    DEFAULT_INFLUX_ORG,
)
from .current.influx_client import fetch_influx_snapshot
from .current.relay_control import SavantRelayController
from .legacy.snapshot_data import fetch_current_energy_snapshot

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ADDRESS): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

LOVELACE_CARD_FILENAME = "savant-energy-scenes-card.js"


class SavantEnergyCoordinator(DataUpdateCoordinator):
    """Coordinator for Savant Energy data updates.

    Polls InfluxDB on a configurable interval and makes the result available
    to all platform entities via self.data.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.address = entry.data.get(CONF_ADDRESS, "")
        raw_mode = entry.options.get(CONF_MODE, entry.data.get(CONF_MODE, DEFAULT_MODE))
        self.mode = MODE_LEGACY if raw_mode == MODE_AUTO else raw_mode
        self.host = entry.options.get(CONF_HOST, entry.data.get(CONF_HOST, self.address))
        self.influx_url = entry.options.get(
            CONF_INFLUX_URL,
            entry.data.get(CONF_INFLUX_URL, f"http://{self.host}:8086"),
        )
        self.influx_token = entry.options.get(
            CONF_INFLUX_TOKEN, entry.data.get(CONF_INFLUX_TOKEN, "")
        )
        self.influx_org = entry.options.get(
            CONF_INFLUX_ORG, entry.data.get(CONF_INFLUX_ORG, DEFAULT_INFLUX_ORG)
        )
        self.config_entry = entry
        self.base_scan_interval_seconds = scan_interval
        self.consecutive_failures = 0
        self.cached_present_demands: list = []
        self.last_fetch_error: dict | None = None

        self.relay_controller: SavantRelayController | None = None
        if self.mode == MODE_CURRENT:
            # Relay control only applies to current mode.
            sem_host = os.getenv("SAVANT_SEM_HOST", self.address or "192.168.1.108")
            self.relay_controller = SavantRelayController(sem_host=sem_host, sem_port=DEFAULT_PORT)

    def _hub_host_from_influx_url(self) -> str:
        """Extract hub host from InfluxDB URL (same device, different port)."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.influx_url)
            return parsed.hostname or "192.168.1.14"
        except Exception:
            return "192.168.1.14"

    def _adjust_interval(self, success: bool) -> None:
        """Back off on failure (capped at 30 s); restore on success."""
        if success:
            self.consecutive_failures = 0
            next_seconds = self.base_scan_interval_seconds
        else:
            self.consecutive_failures += 1
            next_seconds = min(
                self.base_scan_interval_seconds * (2 ** (self.consecutive_failures - 1)),
                30,
            )

        next_interval = timedelta(seconds=next_seconds)
        if self.update_interval != next_interval:
            self.update_interval = next_interval
            _LOGGER.info(
                "Savant poll interval → %d s (%s)",
                next_seconds,
                "success" if success else f"failure #{self.consecutive_failures}",
            )

    async def _async_update_data(self) -> dict:
        """Fetch latest circuit and system data from InfluxDB."""
        if self.mode == MODE_LEGACY:
            return await self._async_update_legacy_data()
        return await self._async_update_current_data()

    async def _async_update_current_data(self) -> dict:
        """Fetch latest circuit and system data from InfluxDB (>=11.2 mode)."""
        now = datetime.now()

        result = await fetch_influx_snapshot(
            self.influx_url, self.influx_token, self.influx_org
        )

        if not result.success or result.data is None:
            self._adjust_interval(success=False)
            self.last_fetch_error = {
                "type": result.error_type,
                "message": result.error_message,
                "timestamp": now.isoformat(),
            }
            _LOGGER.warning(
                "Savant InfluxDB fetch failed (%s): %s",
                result.error_type,
                result.error_message,
            )

            existing = dict(self.data) if isinstance(self.data, dict) else {}
            existing.setdefault("snapshot_data", None)
            existing["cached_present_demands"] = copy.deepcopy(self.cached_present_demands)
            existing["snapshot_status"] = {
                "ok": False,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "failure_count": self.consecutive_failures,
                "next_retry_seconds": int(self.update_interval.total_seconds()),
                "used_cached_snapshot": bool(existing.get("snapshot_data")),
            }
            return existing

        snapshot_data = result.data
        self._adjust_interval(success=True)
        self.last_fetch_error = None

        present_demands = snapshot_data.get("presentDemands", [])
        if isinstance(present_demands, list):
            self.cached_present_demands = [
                copy.deepcopy(d) for d in present_demands if isinstance(d, dict)
            ]
            
            # Build relay UID map from presentDemands (relay_uid added by influx_client.py)
            relay_uid_map = {}
            for device in present_demands:
                uid = device.get("uid")
                relay_uid = device.get("relay_uid")
                if uid and relay_uid:
                    relay_uid_map[uid] = relay_uid
            
            if relay_uid_map and self.relay_controller:
                import asyncio
                # Set relay UID map (fire and forget; not awaiting)
                asyncio.create_task(self.relay_controller.set_relay_uid_map(relay_uid_map))
                _LOGGER.debug("Updated relay controller UID map with %d entries", len(relay_uid_map))

        _LOGGER.debug(
            "InfluxDB: %d circuits, %d system channels",
            len(present_demands),
            len(snapshot_data.get("system_data", {})),
        )

        return {
            "snapshot_data": snapshot_data,
            "cached_present_demands": copy.deepcopy(self.cached_present_demands),
            "snapshot_status": {
                "ok": True,
                "error_type": None,
                "error_message": None,
                "failure_count": 0,
                "next_retry_seconds": int(self.update_interval.total_seconds()),
                "used_cached_snapshot": False,
            },
        }

    async def _async_update_legacy_data(self) -> dict:
        """Fetch legacy snapshot data (<11.2 mode)."""
        now = datetime.now()
        result = await self.hass.async_add_executor_job(
            fetch_current_energy_snapshot,
            self.address,
            DEFAULT_PORT,
        )

        if not result.success or result.data is None:
            self._adjust_interval(success=False)
            self.last_fetch_error = {
                "type": result.error_type,
                "message": result.error_message,
                "timestamp": now.isoformat(),
            }
            _LOGGER.warning(
                "Savant legacy snapshot fetch failed (%s): %s",
                result.error_type,
                result.error_message,
            )

            existing = dict(self.data) if isinstance(self.data, dict) else {}
            existing.setdefault("snapshot_data", None)
            existing["cached_present_demands"] = copy.deepcopy(self.cached_present_demands)
            existing["snapshot_status"] = {
                "ok": False,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "failure_count": self.consecutive_failures,
                "next_retry_seconds": int(self.update_interval.total_seconds()),
                "used_cached_snapshot": bool(existing.get("snapshot_data")),
            }
            return existing

        snapshot_data = result.data
        self._adjust_interval(success=True)
        self.last_fetch_error = None

        present_demands = snapshot_data.get("presentDemands", [])
        if isinstance(present_demands, list):
            self.cached_present_demands = [
                copy.deepcopy(d) for d in present_demands if isinstance(d, dict)
            ]

        return {
            "snapshot_data": snapshot_data,
            "cached_present_demands": copy.deepcopy(self.cached_present_demands),
            "snapshot_status": {
                "ok": True,
                "error_type": None,
                "error_message": None,
                "failure_count": 0,
                "next_retry_seconds": int(self.update_interval.total_seconds()),
                "used_cached_snapshot": False,
            },
        }


async def _async_register_frontend_resource(hass: HomeAssistant) -> None:
    """Register the custom Lovelace card with Home Assistant's frontend."""
    try:
        local_path = f"/local/{DOMAIN}"

        try:
            from homeassistant.components.http import StaticPathConfig  # type: ignore

            await hass.http.async_register_static_paths(
                [StaticPathConfig(local_path, os.path.dirname(__file__), True)]
            )
        except (ImportError, AttributeError):
            hass.http.register_static_path(local_path, os.path.dirname(__file__), True)

        resource_url = f"{local_path}/{LOVELACE_CARD_FILENAME}"
        frontend.add_extra_js_url(hass, resource_url)
        _LOGGER.info("Registered Lovelace card: %s", resource_url)
    except Exception as exc:
        _LOGGER.error("Failed to register frontend resource: %s", exc, exc_info=True)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Savant Energy from YAML (no-op; config entry only)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Savant Energy from a config entry."""
    await async_get_translations(hass, hass.config.language, DOMAIN)

    disable_scene_builder = entry.options.get(
        "disable_scene_builder", entry.data.get("disable_scene_builder", False)
    )

    coordinator = SavantEnergyCoordinator(hass, entry)

    _LOGGER.info("Fetching initial data from Savant InfluxDB")
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    if coordinator.data is None or not coordinator.data.get("snapshot_data"):
        _LOGGER.warning(
            "Initial InfluxDB fetch returned no data — entities may show as unavailable"
        )

    setup_platforms = list(PLATFORMS)
    if not disable_scene_builder:
        setup_platforms.append("scene")

    await hass.config_entries.async_forward_entry_setups(entry, setup_platforms)

    if not disable_scene_builder:
        await _async_register_frontend_resource(hass)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries by setting a default legacy mode for old installs."""
    if CONF_MODE in entry.data:
        return True

    new_data = dict(entry.data)
    new_data[CONF_MODE] = MODE_LEGACY
    hass.config_entries.async_update_entry(entry, data=new_data)
    _LOGGER.info("Migrated Savant Energy config entry %s to mode=%s", entry.entry_id, MODE_LEGACY)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    disable_scene_builder = entry.options.get(
        "disable_scene_builder", entry.data.get("disable_scene_builder", False)
    )
    unload_platforms = list(PLATFORMS)
    if not disable_scene_builder:
        unload_platforms.append("scene")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, unload_platforms)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        # Clean up relay controller if it exists
        if coordinator and getattr(coordinator, "relay_controller", None):
            try:
                await coordinator.relay_controller.disconnect()
            except Exception as exc:
                _LOGGER.warning(f"Error disconnecting relay controller: {exc}")

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload on options change."""
    await hass.config_entries.async_reload(entry.entry_id)
