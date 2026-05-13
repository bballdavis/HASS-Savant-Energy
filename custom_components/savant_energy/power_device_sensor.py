"""Power, current, voltage, and energy sensor entities for Savant Energy.

Data comes from InfluxDB via the coordinator. Key units:
  power   — Watts (InfluxDB stores W directly; no scaling needed)
  current — Amperes
  voltage — Volts
  energy  — kWh (influx_client converts from mWh)
"""

import logging

from homeassistant.components.sensor import (  # type: ignore
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore

from .const import DOMAIN, MANUFACTURER
from .models import get_device_model
from .utils import slugify

_LOGGER = logging.getLogger(__name__)


def _device_info(device: dict, dmx_uid: str) -> DeviceInfo:
    """Build DeviceInfo using base_uid for A/B device grouping."""
    base_uid = device.get("base_uid", device["uid"])
    return DeviceInfo(
        identifiers={(DOMAIN, base_uid)},
        name=device["name"],
        serial_number=dmx_uid,
        manufacturer=MANUFACTURER,
        model=get_device_model(device.get("capacity", 0)),
    )


class EnergyDeviceSensor(CoordinatorEntity, SensorEntity):
    """Measurement sensor for a single field on a Savant circuit.

    Handles power (W), current (A), and voltage (V).
    """

    def __init__(self, coordinator, device: dict, sensor_type: str, unique_id: str, dmx_uid: str):
        super().__init__(coordinator)
        self._device = device
        self._sensor_type = sensor_type
        self._attr_unique_id = unique_id
        self._attr_device_info = _device_info(device, dmx_uid)
        self._attr_native_unit_of_measurement = _unit_for(sensor_type)
        self._dmx_uid = dmx_uid
        self._slug_name = slugify(device["name"])

    # --- Dynamic name (picks up renames from coordinator) ---

    @property
    def _live_name(self) -> str:
        device = self._find_device()
        return device["name"] if device else self._device["name"]

    @property
    def name(self) -> str:
        return f"{self._live_name} {self._sensor_type.capitalize()}"

    # --- Coordinator lookup helpers ---

    def _find_device(self) -> dict | None:
        snapshot = (self.coordinator.data or {}).get("snapshot_data") or {}
        uid = self._device["uid"]
        for d in (snapshot.get("presentDemands") or []):
            if d.get("uid") == uid:
                return d
        return None

    # --- SensorEntity properties ---

    @property
    def state_class(self) -> SensorStateClass:
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self) -> SensorDeviceClass | None:
        match self._sensor_type:
            case "power":
                return SensorDeviceClass.POWER
            case "voltage":
                return SensorDeviceClass.VOLTAGE
            case "current":
                return SensorDeviceClass.CURRENT
            case _:
                return None

    @property
    def native_value(self) -> float | None:
        device = self._find_device()
        if device is None:
            return None
        value = device.get(self._sensor_type)
        if value is None:
            return None
        try:
            # Power, current, and voltage are all already in their native units
            # from influx_client (W, A, V). No scaling required.
            numeric_value = float(value)
            mode = self.coordinator.config_entry.data.get("mode", "legacy")
            if self._sensor_type == "power" and mode == "legacy":
                # Legacy snapshot power has historically been represented in kW.
                return round(numeric_value * 1000.0, 3)
            return round(numeric_value, 3)
        except (ValueError, TypeError):
            _LOGGER.error(
                "Invalid %s value %r for circuit %s",
                self._sensor_type,
                value,
                self._device["uid"],
            )
            return None

    @property
    def icon(self) -> str:
        match self._sensor_type:
            case "voltage":
                return "mdi:flash"
            case "power":
                return "mdi:lightning-bolt"
            case "current":
                return "mdi:current-ac"
            case _:
                return "mdi:gauge"

    @property
    def available(self) -> bool:
        device = self._find_device()
        return device is not None and self._sensor_type in device

    @property
    def device_info(self) -> DeviceInfo:
        device = self._find_device()
        if device:
            return _device_info(device, self._dmx_uid)
        return _device_info(self._device, self._dmx_uid)


class IndividualLoadEnergySensor(CoordinatorEntity, SensorEntity):
    """Cumulative energy sensor sourced directly from the SEM hardware counter.

    The InfluxDB 'energy' field is the physical accumulator on the SEM module,
    stored in mWh and converted to kWh by influx_client. It is monotonically
    increasing and does not need integration or state restoration — the hardware
    is the authoritative source across restarts.
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_icon = "mdi:lightning-bolt-circle"
    _attr_native_unit_of_measurement = "kWh"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, device: dict, unique_id: str, dmx_uid: str):
        super().__init__(coordinator)
        self._device = device
        self._dmx_uid = dmx_uid
        self._attr_unique_id = unique_id
        self._attr_device_info = _device_info(device, dmx_uid)

    @property
    def _live_name(self) -> str:
        device = self._find_device()
        return device["name"] if device else self._device["name"]

    @property
    def name(self) -> str:
        return f"{self._live_name} Energy"

    def _find_device(self) -> dict | None:
        snapshot = (self.coordinator.data or {}).get("snapshot_data") or {}
        uid = self._device["uid"]
        for d in (snapshot.get("presentDemands") or []):
            if d.get("uid") == uid:
                return d
        return None

    @property
    def native_value(self) -> float | None:
        device = self._find_device()
        if device is None:
            return None
        value = device.get("energy")
        if value is None:
            return None
        try:
            return round(float(value), 6)
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        return self._find_device() is not None

    @property
    def device_info(self) -> DeviceInfo:
        device = self._find_device()
        if device:
            return _device_info(device, self._dmx_uid)
        return _device_info(self._device, self._dmx_uid)


# --- Helpers ---

def _unit_for(sensor_type: str) -> str | None:
    match sensor_type:
        case "power":
            return "W"
        case "voltage":
            return "V"
        case "current":
            return "A"
        case _:
            return None
