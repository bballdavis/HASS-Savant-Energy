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
LEGACY_FEED_NOTIFICATION_ID = f"{DOMAIN}_legacy_feed_unavailable"


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
        self._legacy_feed_notification_key: tuple[str | None, str | None] | None = None

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

            notification_key = (result.error_type, result.error_message)
            if notification_key != self._legacy_feed_notification_key:
                self._legacy_feed_notification_key = notification_key
                await self._async_notify_legacy_feed_unavailable(
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
        if self._legacy_feed_notification_key is not None:
            await self._async_dismiss_legacy_feed_notification()
            self._legacy_feed_notification_key = None

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

    async def _async_notify_legacy_feed_unavailable(
        self,
        error_type: str | None,
        error_message: str | None,
    ) -> None:
        """Notify the user that the legacy PBC feed is unavailable."""
        pbc_ip = self.address or "the configured PBC"
        message = (
            f"Savant Energy could not reach the legacy feed at {pbc_ip}. "
            f"Check that the PBC IP is correct. If this Savant Host system has been upgraded recently (>11.2), "
            f"open the integration and run Reconfigure to switch to the newer setup path."
        )
        if error_type or error_message:
            message = (
                f"{message} Last error: {error_type or 'unknown'}: {error_message or 'no details available'}."
            )

        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "Savant Energy Legacy Feed Unavailable",
                "message": message,
                "notification_id": LEGACY_FEED_NOTIFICATION_ID,
            },
            blocking=True,
        )

    async def _async_dismiss_legacy_feed_notification(self) -> None:
        """Dismiss the legacy feed notification once the feed is healthy again."""
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": LEGACY_FEED_NOTIFICATION_ID},
            blocking=True,
        )


async def _async_remove_dmx_address_sensors(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove any DMX address sensor entities left over from a previous legacy-mode install."""
    from homeassistant.helpers.entity_registry import async_get as async_get_er  # type: ignore

    er = async_get_er(hass)
    stale = [
        reg.entity_id
        for reg in er.entities.values()
        if reg.config_entry_id == entry.entry_id
        and reg.unique_id.endswith("_dmx_address")
    ]
    for entity_id in stale:
        er.async_remove(entity_id)
        _LOGGER.info("Removed stale DMX address sensor (current mode): %s", entity_id)


async def _async_remove_stale_circuit_entities(
    hass: HomeAssistant, entry: ConfigEntry, coordinator
) -> None:
    """Remove orphaned circuit entities and devices from previous integration versions.

    The old power_device_sensor.py used the full circuit uid (e.g. "001AAE17329B.0")
    as the HA device identifier.  The current version uses base_uid ("001AAE17329B") to
    group both A/B slots of a relay module under one HA device.  This leaves a stale
    device entry per circuit slot in the device registry.

    On the entity side, if the uid format ever differs between legacy TCP mode and
    InfluxDB mode, entity unique_ids also change and orphaned entities accumulate.

    Safe to run every startup — only removes entries whose embedded uid/base_uid is
    genuinely absent from the live snapshot.
    """
    from homeassistant.helpers.entity_registry import async_get as async_get_er  # type: ignore
    from homeassistant.helpers.device_registry import async_get as async_get_dr  # type: ignore

    snapshot_data = (coordinator.data or {}).get("snapshot_data") or {}
    demands = snapshot_data.get("presentDemands", [])
    if not demands:
        _LOGGER.debug("Skipping stale entity/device cleanup — snapshot has no circuits yet")
        return

    # Use only legacy_uid as the stable entity identifier going forward.
    # For relay-controlled circuits this is the MAC-based hex UID (e.g. "001AAE17329B.0")
    # which matches entity unique_ids from legacy TCP mode, preserving history.
    # For CT-monitored circuits (no SEM relay) it falls back to the InfluxDB UUID since
    # those never existed in legacy mode.
    # UUID-based entries for relay circuits (created during the mode transition) are
    # intentionally NOT included here so the cleanup removes them.
    current_uids: set[str] = {d["legacy_uid"] for d in demands if d.get("legacy_uid")}
    current_base_uids: set[str] = {d["legacy_base_uid"] for d in demands if d.get("legacy_base_uid")}

    er = async_get_er(hass)

    # --- Entity cleanup ---
    # Patterns: SavantEnergy_{uid}_{suffix}  and  savant_energy_{uid}_breaker
    sensor_suffixes = (
        "_power", "_current", "_voltage", "_energy", "_dmx_address", "_relay_status"
    )
    stale_entity_ids: list[str] = []
    for reg in er.entities.values():
        if reg.config_entry_id != entry.entry_id:
            continue
        uid_str = reg.unique_id
        for suffix in sensor_suffixes:
            if uid_str.startswith("SavantEnergy_") and uid_str.endswith(suffix):
                embedded = uid_str[len("SavantEnergy_") : -len(suffix)]
                if embedded not in current_uids:
                    stale_entity_ids.append(reg.entity_id)
                break
        else:
            breaker_prefix = f"{DOMAIN}_"
            if uid_str.startswith(breaker_prefix) and uid_str.endswith("_breaker"):
                embedded = uid_str[len(breaker_prefix) : -len("_breaker")]
                if embedded not in current_uids:
                    stale_entity_ids.append(reg.entity_id)

    for entity_id in stale_entity_ids:
        er.async_remove(entity_id)
        _LOGGER.info("Removed stale circuit entity: %s", entity_id)
    if stale_entity_ids:
        _LOGGER.info("Stale entity cleanup: removed %d orphaned entities", len(stale_entity_ids))

    # --- Device cleanup ---
    # Active devices use base_uid as identifier.  Old devices used the full uid with
    # suffix (e.g. "001AAE17329B.0") which is NOT a valid base_uid and is no longer
    # referenced by any entity after the entity cleanup above.
    _always_keep = {"savant_energy_hub", "savant_energy_controller"}
    dr = async_get_dr(hass)
    for device in list(dr.devices.values()):
        for id_tuple in device.identifiers:
            if not id_tuple or id_tuple[0] != DOMAIN or len(id_tuple) < 2:
                continue
            identifier = id_tuple[1]
            if identifier in _always_keep:
                break
            if str(identifier).startswith("savant_") and "_scene" in str(identifier):
                break
            # Keep active circuit devices (base_uid match)
            if identifier in current_base_uids:
                break
            # Anything else belonging to this integration is a stale device.
            # Only remove if truly empty (no entities still attached).
            attached = [e for e in er.entities.values() if e.device_id == device.id]
            if not attached:
                dr.async_remove_device(device.id)
                _LOGGER.info(
                    "Removed orphaned device: %s (identifier=%s)", device.name or device.id, identifier
                )
            break


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

    if coordinator.mode == MODE_CURRENT:
        await _async_remove_dmx_address_sensors(hass, entry)

    # Clean up orphaned circuit entities and devices from previous installs
    # (e.g. after a uid format change between legacy and current mode).
    await _async_remove_stale_circuit_entities(hass, entry, coordinator)

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
