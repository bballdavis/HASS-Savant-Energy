import asyncio
import sys
import types
import unittest
from pathlib import Path


def _install_stubs():
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant
    components = types.ModuleType("homeassistant.components"); components.__path__ = []
    sys.modules["homeassistant.components"] = components
    sensor = types.ModuleType("homeassistant.components.sensor")
    class SensorEntity: pass
    class RestoreSensor(SensorEntity): pass
    class SensorDeviceClass: POWER="power"; VOLTAGE="voltage"; CURRENT="current"; ENERGY="energy"; BATTERY="battery"
    class SensorStateClass: MEASUREMENT="measurement"; TOTAL_INCREASING="total_increasing"
    sensor.SensorEntity, sensor.RestoreSensor, sensor.SensorDeviceClass, sensor.SensorStateClass = SensorEntity, RestoreSensor, SensorDeviceClass, SensorStateClass
    sys.modules["homeassistant.components.sensor"] = sensor
    helpers = types.ModuleType("homeassistant.helpers"); helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity.DeviceInfo = lambda **kwargs: kwargs
    sys.modules["homeassistant.helpers.entity"] = entity
    coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    class CoordinatorEntity:
        def __init__(self, coordinator): self.coordinator = coordinator
    coordinator.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = coordinator
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = lambda *_args, **_kwargs: None
    dispatcher.async_dispatcher_connect = lambda *_args, **_kwargs: (lambda: None)
    sys.modules["homeassistant.helpers.dispatcher"] = dispatcher


def _load_sensor_module():
    _install_stubs()
    root = Path(__file__).resolve().parents[1]
    package = types.ModuleType("custom_components"); package.__path__ = [str(root / "custom_components")]
    sys.modules["custom_components"] = package
    savant = types.ModuleType("custom_components.savant_energy"); savant.__path__ = [str(root / "custom_components" / "savant_energy")]
    sys.modules["custom_components.savant_energy"] = savant
    import importlib
    return importlib.import_module("custom_components.savant_energy.sensor")


class MeasurementBootstrapTests(unittest.TestCase):
    def test_stored_identity_recreates_unavailable_measurement_entities(self):
        module = _load_sensor_module()
        shell = {
            "circuit_key": "uuid::1", "display_name": "Recovered circuit", "channel": "1",
            "legacy_uid": "relay.0", "legacy_base_uid": "relay", "role": "relay",
        }
        coordinator = types.SimpleNamespace(data={"snapshot_data": {"presentDemands": [], "inventoryDemands": []}}, mode="current")
        entry = types.SimpleNamespace(entry_id="entry", data={"circuit_map": {"uuid::1": shell}})
        hass = types.SimpleNamespace(data={module.DOMAIN: {"entry": coordinator}})
        added = []
        asyncio.run(module.async_setup_entry(hass, entry, added.extend))
        circuit_entities = [entity for entity in added if getattr(entity, "_device", {}).get("uid") == "uuid::1"]
        self.assertEqual(len(circuit_entities), 4)
        self.assertTrue(all(entity.available is False for entity in circuit_entities))
