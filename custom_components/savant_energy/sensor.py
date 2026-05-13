"""Sensor platform for Savant Energy.

Creates per-circuit sensors (power, current, voltage, energy, DMX address) and
system-level sensors (totals, groups, battery, solar) from InfluxDB data.
"""

import logging

from homeassistant.components.sensor import (  # type: ignore
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.entity import DeviceInfo  # type: ignore
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore

from .const import DOMAIN, MANUFACTURER, MODE_CURRENT, CONF_MODE
from .models import get_device_model
from .power_device_sensor import EnergyDeviceSensor, IndividualLoadEnergySensor
from .dmx_address_sensor import DMXAddressSensor
from .utils import calculate_dmx_uid

_LOGGER = logging.getLogger(__name__)

# Hub-level channel keys → (friendly name, unit, device_class, icon)
_SYSTEM_SENSORS: dict[str, tuple[str, str, SensorDeviceClass | None, str]] = {
    # Totals
    "Energy.Total.Consumption.Power": (
        "Total Consumption", "W", SensorDeviceClass.POWER, "mdi:home-lightning-bolt"
    ),
    "Energy.Total.Feed.Power": (
        "Grid Feed", "W", SensorDeviceClass.POWER, "mdi:transmission-tower"
    ),
    "Energy.Total.Net.Power": (
        "Net Power", "W", SensorDeviceClass.POWER, "mdi:scale-balance"
    ),
    # Battery
    "Energy.Battery.Power": (
        "Battery Power", "W", SensorDeviceClass.POWER, "mdi:battery-charging"
    ),
    "Energy.Battery.StateOfCharge": (
        "Battery State of Charge", "%", SensorDeviceClass.BATTERY, "mdi:battery"
    ),
    "Energy.Battery.SecondsRemaining": (
        "Battery Time Remaining", "s", None, "mdi:timer-outline"
    ),
    "Energy.Battery.OperatingMode": (
        "Battery Operating Mode", None, None, "mdi:battery-sync"
    ),
    # Solar
    "Energy.Circuit.Solar.Power": (
        "Solar Power", "W", SensorDeviceClass.POWER, "mdi:solar-power"
    ),
    "Energy.Solar.isProducingEnergy": (
        "Solar Producing", None, None, "mdi:weather-sunny"
    ),
    # Grid
    "Energy.Grid.IsAvailable": (
        "Grid Available", None, None, "mdi:transmission-tower"
    ),
    # Load groups
    "Energy.Group.HVAC.Power": (
        "HVAC Power", "W", SensorDeviceClass.POWER, "mdi:hvac"
    ),
    "Energy.Group.Lighting.Power": (
        "Lighting Power", "W", SensorDeviceClass.POWER, "mdi:lightbulb-group"
    ),
    "Energy.Group.Appliances.Power": (
        "Appliances Power", "W", SensorDeviceClass.POWER, "mdi:toaster-oven"
    ),
    "Energy.Group.Room.Power": (
        "Room Power", "W", SensorDeviceClass.POWER, "mdi:sofa"
    ),
    "Energy.Group.Outlet.Power": (
        "Outlet Power", "W", SensorDeviceClass.POWER, "mdi:power-socket-us"
    ),
    "Energy.Group.Garage.Power": (
        "Garage Power", "W", SensorDeviceClass.POWER, "mdi:garage"
    ),
    "Energy.Group.Refrigerator.Power": (
        "Refrigerator Power", "W", SensorDeviceClass.POWER, "mdi:fridge"
    ),
    "Energy.Group.Microwave.Power": (
        "Microwave Power", "W", SensorDeviceClass.POWER, "mdi:microwave"
    ),
    "Energy.Group.Network.Power": (
        "Network Power", "W", SensorDeviceClass.POWER, "mdi:router-network"
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up all Savant Energy sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    snapshot_data = (coordinator.data or {}).get("snapshot_data", {})
    _LOGGER.info(
        "sensor setup: snapshot_data present=%s, has presentDemands=%s",
        bool(snapshot_data),
        "presentDemands" in snapshot_data if snapshot_data else False,
    )

    # --- Per-circuit entities ---
    if (
        snapshot_data
        and isinstance(snapshot_data, dict)
        and "presentDemands" in snapshot_data
    ):
        demands = snapshot_data["presentDemands"]
        _LOGGER.info("sensor setup: %d circuits found", len(demands))

        for device in demands:
            uid = device["uid"]
            dmx_uid = calculate_dmx_uid(uid)

            entities += [
                EnergyDeviceSensor(
                    coordinator, device, "power",
                    f"SavantEnergy_{uid}_power", dmx_uid,
                ),
                EnergyDeviceSensor(
                    coordinator, device, "current",
                    f"SavantEnergy_{uid}_current", dmx_uid,
                ),
                EnergyDeviceSensor(
                    coordinator, device, "voltage",
                    f"SavantEnergy_{uid}_voltage", dmx_uid,
                ),
                IndividualLoadEnergySensor(
                    coordinator, device,
                    f"SavantEnergy_{uid}_energy", dmx_uid,
                ),
                *(
                    [DMXAddressSensor(
                        coordinator, device,
                        f"SavantEnergy_{uid}_dmx_address", dmx_uid,
                    )]
                    if coordinator.mode != MODE_CURRENT
                    else []
                ),
            ]
    else:
        _LOGGER.warning(
            "sensor setup: no presentDemands — circuit sensors will not be created. "
            "snapshot_data type=%s keys=%s",
            type(snapshot_data),
            list(snapshot_data.keys()) if isinstance(snapshot_data, dict) else "N/A",
        )

    # --- System / hub-level entities ---
    for channel_key, (label, unit, dev_class, icon) in _SYSTEM_SENSORS.items():
        entities.append(
            SystemSensor(coordinator, channel_key, label, unit, dev_class, icon)
        )

    async_add_entities(entities)
    _LOGGER.info("sensor setup: added %d entities total", len(entities))
    return True


class SystemSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a hub-level aggregated channel (totals, groups, battery, solar).

    Reads from coordinator.data['snapshot_data']['system_data'][channel_key].
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        channel_key: str,
        label: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        icon: str,
    ):
        super().__init__(coordinator)
        self._channel_key = channel_key
        self._attr_name = f"Savant {label}"
        self._attr_unique_id = f"SavantEnergy_system_{channel_key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "savant_energy_hub")},
            name="Savant Energy Hub",
            manufacturer=MANUFACTURER,
            model="Savant SEM Hub",
        )

    @property
    def icon(self) -> str:
        return self._icon

    def _system_data(self) -> dict:
        snapshot = (self.coordinator.data or {}).get("snapshot_data") or {}
        return snapshot.get("system_data") or {}

    @property
    def native_value(self) -> float | None:
        value = self._system_data().get(self._channel_key)
        if value is None:
            return None
        try:
            return round(float(value), 3)
        except (ValueError, TypeError):
            return None

    @property
    def available(self) -> bool:
        return self._channel_key in self._system_data()
