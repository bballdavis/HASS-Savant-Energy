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
from .utils import calculate_dmx_uid, async_set_dmx_values, async_get_dmx_address, slugify

_LOGGER = logging.getLogger(__name__)

_last_command_time = 0.0
PENDING_CONFIRM_MULTIPLIER: int = 3  # Number of coordinator update intervals to wait before timing out


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
    # Always trigger a refresh to ensure polling starts
    await coordinator.async_request_refresh()
    if coordinator.data is not None:
        snapshot_data = coordinator.data.get("snapshot_data", {})
        if (
            snapshot_data
            and isinstance(snapshot_data, dict)
            and "presentDemands" in snapshot_data
        ):
            for device in snapshot_data["presentDemands"]:
                entities.append(EnergyDeviceSwitch(hass, coordinator, device, cooldown))
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
        self._attr_is_on = self._get_relay_status_state()
        self._last_commanded_state = self._attr_is_on
        # Pending confirmation state after a user-initiated command
        self._pending_confirm = False
        self._pending_confirm_target: bool | None = None
        self._pending_confirm_task: asyncio.Task | None = None
        self._pending_confirm_expires: float | None = None
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
        for binary_sensor in self._hass.states.async_all("binary_sensor"):
            if (
                binary_sensor.attributes.get("uid") == self._device["uid"]
            ):
                if binary_sensor.state.lower() == "on":
                    return True
                elif binary_sensor.state.lower() == "off":
                    return False
                break
        return None

    async def _get_dmx_address_from_sensor(self) -> int | None:
        """
        Try to get the DMX address from the sensor entity for this device.
        """
        dmx_address_entity_id = f"sensor.{slugify(self._current_device_name)}_dmx_address"
        alternative_entity_id = f"sensor.savant_energy_{self._device['uid']}_dmx_address"
        state = self._hass.states.get(dmx_address_entity_id)
        if not state or state.state in ('unknown', 'unavailable'):
            state = self._hass.states.get(alternative_entity_id)
        if state and state.state not in ('unknown', 'unavailable'):
            try:
                return int(state.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid DMX address in sensor {state.entity_id}: {state.state}")
        return None    

    async def _fetch_dmx_address(self) -> int | None:
        """
        Fetch DMX address from sensor only.
        """
        address = await self._get_dmx_address_from_sensor()
        if address is not None:
            return address
        _LOGGER.warning(f"No DMX address found in sensor for {self.name}")
        return None

    async def _get_all_device_dmx_states(self, target_dmx_address=None, target_value=None):
        """
        Build a dict of {dmx_address: value} for all devices using only DMX Address and Relay Status sensors.
        """
        dmx_states = {}
        max_address = 0
        dmx_address_entities = [entity for entity in self._hass.states.async_all("sensor") if entity.entity_id.endswith("_dmx_address")]

        for dmx_address_entity in dmx_address_entities:
            if dmx_address_entity.state in ("unknown", "unavailable") or not dmx_address_entity.state:
                continue
            try:
                dmx_address = int(dmx_address_entity.state)
            except (ValueError, TypeError):
                _LOGGER.warning(f"Invalid DMX address in sensor {dmx_address_entity.entity_id}: {dmx_address_entity.state}")
                continue

            entity_id = dmx_address_entity.entity_id
            device_name = None
            sensor_state = self._hass.states.get(entity_id)
            if sensor_state and sensor_state.attributes.get("friendly_name"):
                device_name = sensor_state.attributes.get("friendly_name").replace(" DMX Address", "")
            if not device_name:
                entity_name = entity_id.split(".", 1)[1].replace("_dmx_address", "")
                device_name = entity_name.replace("_", " ").title()

            relay_found = False
            relay_status_state = None
            for binary_sensor in self._hass.states.async_all("binary_sensor"):
                if binary_sensor.attributes.get("friendly_name") and f"{device_name} Relay Status" == binary_sensor.attributes.get("friendly_name"):
                    relay_status_state = binary_sensor
                    relay_found = True
                    break

            value = "255"
            if relay_found and relay_status_state and relay_status_state.state not in ("unknown", "unavailable"):
                if relay_status_state.state.lower() == "on":
                    value = "255"
                elif relay_status_state.state.lower() == "off":
                    value = "0"
                _LOGGER.debug(f"Found relay status for {device_name}: {relay_status_state.state} (using value {value})")
            else:
                _LOGGER.debug(f"No relay status found for {device_name}, defaulting to ON")

            dmx_states[dmx_address] = value
            if dmx_address > max_address:
                max_address = dmx_address

        if target_dmx_address:
            dmx_states[target_dmx_address] = target_value
            if target_dmx_address > max_address:
                max_address = target_dmx_address

        return dmx_states, max_address

    async def _send_full_dmx_command(self, target_dmx_address, target_value):
        """
        Send a DMX command with the full state of all addresses.
        """
        dmx_states, max_address = await self._get_all_device_dmx_states(target_dmx_address, target_value)
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
        return result

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
        global _last_command_time
        now = time.monotonic()
        if now - _last_command_time < self._cooldown:
            time_left = math.ceil(self._cooldown - (now - _last_command_time))
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
            _last_command_time = now
            dmx_address = await self._fetch_dmx_address()
            if dmx_address is None:
                _LOGGER.warning(f"Cannot turn on {self.name}: DMX address unknown")
                return
            _LOGGER.info(f"Turning ON {self.name} at DMX address {dmx_address}")
            result = await self._send_full_dmx_command(dmx_address, "255")
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
        global _last_command_time
        now = time.monotonic()
        if now - _last_command_time < self._cooldown:
            time_left = math.ceil(self._cooldown - (now - _last_command_time))
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
            _last_command_time = now
            dmx_address = await self._fetch_dmx_address()
            if dmx_address is None:
                _LOGGER.warning(f"Cannot turn off {self.name}: DMX address unknown")
                return
            _LOGGER.info(f"Turning OFF {self.name} at DMX address {dmx_address}")
            result = await self._send_full_dmx_command(dmx_address, "0")
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
