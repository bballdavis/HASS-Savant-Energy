"""
Sensor platform for Savant Energy.
Creates power, voltage, and DMX address sensors for each relay device.
All classes and functions are now documented for clarity and open source maintainability.
"""

import logging
import asyncio

from homeassistant.helpers.entity import DeviceInfo  # type: ignore

from .const import DOMAIN, MANUFACTURER
from .models import get_device_model
from .power_device_sensor import EnergyDeviceSensor, IndividualLoadEnergySensor
from .dmx_address_sensor import DMXAddressSensor
from .utils import calculate_dmx_uid

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """
    Set up Savant Energy sensor entities.
    Creates power, voltage, and DMX address sensors for each relay device found in presentDemands.
    """
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    power_sensors = []  # Track power sensors for utility meter creation
    dmx_address_sensors = []  # Track DMX address sensors for concurrency

    # Defensive: Only try to create entities if coordinator.data is not None
    _LOGGER.info(f"async_setup_entry: coordinator.data = {coordinator.data is not None}")
    if coordinator.data is not None:
        snapshot_data = coordinator.data.get("snapshot_data", {})
        _LOGGER.info(f"async_setup_entry: snapshot_data exists = {bool(snapshot_data)}, has presentDemands = {'presentDemands' in snapshot_data if snapshot_data else False}")
        if (
            snapshot_data
            and isinstance(snapshot_data, dict)
            and "presentDemands" in snapshot_data
        ):
            demands_list = snapshot_data["presentDemands"]
            _LOGGER.info(f"async_setup_entry: Found {len(demands_list)} presentDemands entries")
            demands_str = str(demands_list)
            _LOGGER.debug(
                "Processing presentDemands: %.50s... (total length: %d)",
                demands_str,
                len(demands_str),
            )
            for device in demands_list:
                uid = device["uid"]
                dmx_uid = calculate_dmx_uid(uid)
                _LOGGER.info(
                    "Creating sensors for Savant Serial: %s (uid: %s)", dmx_uid, uid
                )

                # Create device info once for all sensors
                device_info = DeviceInfo(
                    identifiers={(DOMAIN, str(device["uid"]))},
                    name=device["name"],
                    serial_number=dmx_uid,
                    manufacturer=MANUFACTURER,
                    model=get_device_model(device.get("capacity", 0)),
                )

                # Create power sensor
                power_sensor = EnergyDeviceSensor(
                    coordinator, device, "power", f"SavantEnergy_{uid}_power", dmx_uid
                )
                entities.append(power_sensor)
                power_sensors.append(power_sensor)

                # Create cumulative energy sensor for the Energy dashboard
                entities.append(
                    IndividualLoadEnergySensor(
                        coordinator,
                        device,
                        f"SavantEnergy_{uid}_energy",
                        dmx_uid,
                    )
                )

                # Create voltage sensor
                entities.append(
                    EnergyDeviceSensor(
                        coordinator,
                        device,
                        "voltage",
                        f"SavantEnergy_{uid}_voltage",
                        dmx_uid,
                    )
                )
                
                # Create DMX address sensor
                dmx_sensor = DMXAddressSensor(
                    coordinator,
                    device,
                    f"SavantEnergy_{uid}_dmx_address",
                    dmx_uid,
                )
                dmx_address_sensors.append(dmx_sensor)
                entities.append(dmx_sensor)

            # Add all entities at once
            _LOGGER.info(f"async_setup_entry: About to add {len(entities)} sensor entities")
            async_add_entities(entities)
            _LOGGER.info("async_setup_entry: Added %d sensor entities successfully", len(entities))

            return True
        else:
            _LOGGER.warning("No presentDemands data found in coordinator. snapshot_data type: %s, keys: %s", type(snapshot_data), list(snapshot_data.keys()) if isinstance(snapshot_data, dict) else "N/A")
