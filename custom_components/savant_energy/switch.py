"""
Switch platform for Savant Energy.
Provides relay (breaker) switch entities for each device, with cooldown logic to prevent rapid toggling.

All classes and methods are now documented for clarity and open source maintainability.
"""

import logging
import time
import math
import asyncio

from homeassistant.components.switch import SwitchEntity  # type: ignore
from homeassistant.core import HomeAssistant, callback  # type: ignore
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore

from .const import (
    DOMAIN,
    CONF_SWITCH_COOLDOWN,
    DEFAULT_SWITCH_COOLDOWN,
    MANUFACTURER,
    DEFAULT_OLA_PORT,
    CONF_DMX_TESTING_MODE,
    CONF_PENDING_CONFIRM_MULTIPLIER,
    DEFAULT_PENDING_CONFIRM_MULTIPLIER,
)
from .models import get_device_model
from .utils import calculate_dmx_uid, async_build_managed_dmx_values, async_set_dmx_values

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """
    Set up Savant Energy switch entities.
    Creates a breaker switch for each relay device, with configurable cooldown.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    cooldown = config_entry.options.get(
        CONF_SWITCH_COOLDOWN,
        config_entry.data.get(CONF_SWITCH_COOLDOWN, DEFAULT_SWITCH_COOLDOWN),
    )
    entities = []
    _LOGGER.info(f"async_setup_entry: coordinator.data = {coordinator.data is not None}")
    if coordinator.data is not None:
        snapshot_data = coordinator.data.get("snapshot_data", {})
        _LOGGER.info(f"async_setup_entry: snapshot_data exists = {bool(snapshot_data)}, has presentDemands = {'presentDemands' in snapshot_data if snapshot_data else False}")
        if (
            snapshot_data
            and isinstance(snapshot_data, dict)
            and "presentDemands" in snapshot_data
        ):
            _LOGGER.info(
                "Creating switch entities from %d presentDemands entries",
                len(snapshot_data["presentDemands"]),
            )
            for device in snapshot_data["presentDemands"]:
                entities.append(EnergyDeviceSwitch(hass, coordinator, device, cooldown))
            _LOGGER.info(f"async_setup_entry: About to add {len(entities)} switch entities")
        else:
            _LOGGER.warning("No presentDemands payload available during switch setup. snapshot_data type: %s", type(snapshot_data))
    _LOGGER.info(f"async_setup_entry: Adding {len(entities)} entities to Home Assistant")
    async_add_entities(entities)


class EnergyDeviceSwitch(CoordinatorEntity, SwitchEntity):
    """
    Representation of a Savant Energy Switch (breaker).
    Includes cooldown logic to prevent rapid toggling.
    """
    def __init__(self, hass: HomeAssistant, coordinator, device, cooldown: int):
        """
        Initialize the switch.
        Args:
            hass: Home Assistant instance
            coordinator: DataUpdateCoordinator
            device: Device dict from presentDemands
            cooldown: Minimum seconds between toggles
        """
        super().__init__(coordinator)
        self._hass = hass
        self._device = device
        self._cooldown = cooldown
        self._attr_unique_id = f"{DOMAIN}_{device['uid']}_breaker"
        self._dmx_uid = calculate_dmx_uid(device["uid"])
        self._dmx_address = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device["uid"]))},
            name=device["name"],
            manufacturer=MANUFACTURER,
            model=get_device_model(
                device.get("capacity", 0)
            ),
            serial_number=self._dmx_uid,
        )
        self._attr_extra_state_attributes = {"uid": device["uid"], "dmx_uid": self._dmx_uid}
        self._attr_is_on = self._get_relay_status_state()
        self._last_commanded_state = self._attr_is_on
        # Pending confirmation state after a user-initiated command
        self._pending_confirm = False
        self._pending_confirm_target: bool | None = None
        self._pending_confirm_task: asyncio.Task | None = None
        self._pending_confirm_expires: float | None = None
        self._last_command_time = 0.0
        self._last_command_time = 0.0
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def _current_device_name(self):
        """Get the latest device name from coordinator data by UID."""
        snapshot_data = self.coordinator.data.get("snapshot_data", {})
        if snapshot_data and "presentDemands" in snapshot_data:
            for device in snapshot_data["presentDemands"]:
                if device["uid"] == self._device["uid"]:
                    return device["name"]
        return self._device["name"]

    # Do NOT override entity_id. Home Assistant manages entity_id and expects it to be settable.
    # Only the name property is dynamic, so the UI/friendly_name updates on device rename.
    # unique_id remains stable and is used for entity tracking.
    @property
    def name(self):
        return f"{self._current_device_name} Breaker"

    def _get_relay_status_state(self) -> bool | None:
        """
        Get the state of the switch based on the relay status sensor, or None if unknown.
        """
        return self._get_relay_status_state_for_uid(self._device["uid"])

    def _get_relay_status_state_for_uid(self, device_uid: str) -> bool | None:
        """Get the relay state for a device UID from the relay status sensor."""
        for binary_sensor in self._hass.states.async_all("binary_sensor"):
            if (
                binary_sensor.attributes.get("uid") == device_uid
            ):
                if binary_sensor.state.lower() == "on":
                    return True
                elif binary_sensor.state.lower() == "off":
                    return False
                break
        return None

    async def _send_full_dmx_command(self, target_value: str):
        """
        Send a DMX command with the full state of all addresses.
        """
        dmx_states, resolved_addresses, unresolved_devices = await async_build_managed_dmx_values(
            self.coordinator,
            self._hass,
            {self._device["uid"]: target_value},
        )
        target_dmx_address = resolved_addresses.get(self._device["uid"])
        if target_dmx_address is None:
            _LOGGER.warning(f"Cannot send DMX command for {self.name}: DMX address unknown")
            return None, None

        for device_uid, device_name in unresolved_devices.items():
            if device_uid == self._device["uid"]:
                continue
            _LOGGER.debug(
                "Preserving live universe values for %s because its DMX address is unavailable",
                device_name,
            )

        ip_address = self.coordinator.config_entry.data.get("address")
        ola_port = self.coordinator.config_entry.data.get("ola_port", DEFAULT_OLA_PORT)
        dmx_testing_mode = self.coordinator.config_entry.options.get(
            CONF_DMX_TESTING_MODE,
            self.coordinator.config_entry.data.get(CONF_DMX_TESTING_MODE, False)
        )
        result = await async_set_dmx_values(ip_address, dmx_states, ola_port, dmx_testing_mode)
        success = bool(result and result.get("success"))
        if not success:
            _LOGGER.error(f"Failed to send DMX command for {self.name} at address {target_dmx_address}: {result}")
        return target_dmx_address, result

    @property
    def available(self) -> bool:
        """
        Return True if the entity is available.
        """
        snapshot_data = self.coordinator.data.get("snapshot_data", {})
        if not snapshot_data or "presentDemands" not in snapshot_data:
            return False
        relay_state = self._get_relay_status_state()
        if relay_state is None:
            return False
        return True

    @property
    def is_on(self) -> bool:
        """
        Return the state of the switch based on the relay status sensor.
        """
        if self._attr_is_on is not None:
            return self._attr_is_on
        for binary_sensor in self._hass.states.async_all("binary_sensor"):
            if (
                binary_sensor.attributes.get("uid") == self._device["uid"]
            ):
                if binary_sensor.state.lower() == "on":
                    return True
                elif binary_sensor.state.lower() == "off":
                    return False
        return False

    async def async_turn_on(self, **kwargs):
        """
        Turn the switch on.
        Implements cooldown logic to prevent rapid toggling.
        """
        now = time.monotonic()
        if now - self._last_command_time < self._cooldown:
            time_left = math.ceil(self._cooldown - (now - self._last_command_time))
            _LOGGER.debug("Cooldown active, ignoring turn_on command")
            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Action for {self._device['name']} was delayed. Please wait {time_left} seconds before trying again.",
                    "title": "Switch Action Delayed",
                    "notification_id": f"{DOMAIN}_cooldown_{self._device['uid']}",
                },
            )
            return
        if not self.is_on:
            self._last_command_time = now
            dmx_address, result = await self._send_full_dmx_command("255")
            if dmx_address is None:
                return
            _LOGGER.info(f"Turning ON {self.name} at DMX address {dmx_address}")
            if result and result.get("success"):
                # Immediately reflect the commanded state in HA and start confirmation timeout
                self._attr_is_on = True
                self._last_commanded_state = True
                self.async_write_ha_state()
                self._start_pending_confirm(True)
            else:
                _LOGGER.error(f"Failed to set DMX ON for {self.name}; not updating HA state")

    async def async_turn_off(self, **kwargs):
        """
        Turn the switch off.
        Implements cooldown logic to prevent rapid toggling.
        """
        now = time.monotonic()
        if now - self._last_command_time < self._cooldown:
            time_left = math.ceil(self._cooldown - (now - self._last_command_time))
            _LOGGER.debug("Cooldown active, ignoring turn_off command")
            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "message": f"Action for {self._device['name']} was delayed. Please wait {time_left} seconds before trying again.",
                    "title": "Switch Action Delayed",
                    "notification_id": f"{DOMAIN}_cooldown_{self._device['uid']}",
                },
            )
            return
        if self.is_on:
            self._last_command_time = now
            dmx_address, result = await self._send_full_dmx_command("0")
            if dmx_address is None:
                return
            _LOGGER.info(f"Turning OFF {self.name} at DMX address {dmx_address}")
            if result and result.get("success"):
                # Immediately reflect the commanded state in HA and start confirmation timeout
                self._attr_is_on = False
                self._last_commanded_state = False
                self.async_write_ha_state()
                self._start_pending_confirm(False)
            else:
                _LOGGER.error(f"Failed to set DMX OFF for {self.name}; not updating HA state")

    @callback
    def _handle_coordinator_update(self) -> None:
        """
        Handle updated data from the coordinator.
        """
        new_state = None
        for binary_sensor in self._hass.states.async_all("binary_sensor"):
            if (
                binary_sensor.attributes.get("uid") == self._device["uid"]
            ):
                new_state = binary_sensor.state.lower() == "on"
                break
        # If we're currently awaiting confirmation for a commanded state, suppress changes
        if self._pending_confirm:
            # If the coordinator shows the requested target state, confirm it and clear pending
            if new_state is not None and new_state == self._pending_confirm_target:
                self._cancel_pending_confirm()
                self._attr_is_on = new_state
                self._last_commanded_state = new_state
                self.async_write_ha_state()
            # Otherwise ignore coordinator updates until pending expires
            return

        if new_state is not None and new_state != self._last_commanded_state:
            self._attr_is_on = new_state
            self._last_commanded_state = new_state
            self.async_write_ha_state()

    def _start_pending_confirm(self, target: bool) -> None:
        """Start a pending confirmation period where coordinator updates are ignored until confirmed or timeout."""
        # Cancel any existing pending task
        if self._pending_confirm_task and not self._pending_confirm_task.done():
            try:
                self._pending_confirm_task.cancel()
            except Exception:
                pass
        self._pending_confirm = True
        self._pending_confirm_target = target
        # Default timeout equals configured multiplier * coordinator update interval (seconds)
        try:
            interval = self.coordinator.update_interval.total_seconds()
        except Exception:
            interval = self.coordinator.config_entry.options.get("scan_interval", self.coordinator.config_entry.data.get("scan_interval", 15))
        multiplier = float(
            self.coordinator.config_entry.options.get(
                CONF_PENDING_CONFIRM_MULTIPLIER,
                self.coordinator.config_entry.data.get(
                    CONF_PENDING_CONFIRM_MULTIPLIER, DEFAULT_PENDING_CONFIRM_MULTIPLIER
                ),
            )
        )
        timeout = float(interval) * max(1.0, multiplier)
        self._pending_confirm_expires = time.monotonic() + timeout
        self._pending_confirm_task = self._hass.async_create_task(self._pending_confirm_waiter(timeout, target))

    def _cancel_pending_confirm(self) -> None:
        """Cancel any pending confirmation period and clear state."""
        self._pending_confirm = False
        self._pending_confirm_target = None
        self._pending_confirm_expires = None
        if self._pending_confirm_task and not self._pending_confirm_task.done():
            try:
                self._pending_confirm_task.cancel()
            except Exception:
                pass
        self._pending_confirm_task = None

    async def _pending_confirm_waiter(self, timeout: float, target: bool) -> None:
        """Wait until coordinator confirms the target state or timeout and then reconcile."""
        try:
            end = time.monotonic() + float(timeout)
            # Poll frequently for coordinator updates until timeout
            while time.monotonic() < end:
                await asyncio.sleep(min(0.5, timeout))
                current = self._get_relay_status_state()
                if current is None:
                    continue
                if current == target:
                    # Confirmed by relay status
                    self._cancel_pending_confirm()
                    self._attr_is_on = target
                    self._last_commanded_state = target
                    self.async_write_ha_state()
                    return
            # Timeout reached: reconcile to current relay status
            current = self._get_relay_status_state()
            if current is not None:
                self._attr_is_on = current
                self._last_commanded_state = current
            self._cancel_pending_confirm()
            self.async_write_ha_state()
        except asyncio.CancelledError:
            return
