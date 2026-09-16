import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path


def _install_stubs():
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    sys.modules["homeassistant.components"] = components
    homeassistant.components = components

    switch_component = types.ModuleType("homeassistant.components.switch")
    switch_component.SwitchEntity = type("SwitchEntity", (), {})
    sys.modules["homeassistant.components.switch"] = switch_component

    binary_component = types.ModuleType("homeassistant.components.binary_sensor")
    binary_component.BinarySensorEntity = type("BinarySensorEntity", (), {})
    sys.modules["homeassistant.components.binary_sensor"] = binary_component

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda func: func
    sys.modules["homeassistant.core"] = core
    homeassistant.core = core

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers
    homeassistant.helpers = helpers

    entity = types.ModuleType("homeassistant.helpers.entity")
    entity.DeviceInfo = lambda **kwargs: kwargs
    sys.modules["homeassistant.helpers.entity"] = entity

    coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    coordinator.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = coordinator


def _load_platform_modules():
    _install_stubs()
    root = Path(__file__).resolve().parents[1]
    package = types.ModuleType("custom_components")
    package.__path__ = [str(root / "custom_components")]
    sys.modules["custom_components"] = package
    savant = types.ModuleType("custom_components.savant_energy")
    savant.__path__ = [str(root / "custom_components" / "savant_energy")]
    sys.modules["custom_components.savant_energy"] = savant

    models = types.ModuleType("custom_components.savant_energy.models")
    models.get_device_model = lambda *_args, **_kwargs: "Savant Energy"
    sys.modules[models.__name__] = models

    utils = types.ModuleType("custom_components.savant_energy.utils")
    utils.calculate_dmx_uid = lambda uid: str(uid)

    async def _unused_async(*_args, **_kwargs):
        return None

    utils.async_build_managed_dmx_values = _unused_async
    utils.async_set_dmx_values = _unused_async
    sys.modules[utils.__name__] = utils

    relay_control = types.ModuleType("custom_components.savant_energy.relay_control")
    relay_control.SavantRelayController = object
    sys.modules[relay_control.__name__] = relay_control

    for module_name in (
        "custom_components.savant_energy.switch",
        "custom_components.savant_energy.binary_sensor",
    ):
        sys.modules.pop(module_name, None)
    return (
        importlib.import_module("custom_components.savant_energy.switch"),
        importlib.import_module("custom_components.savant_energy.binary_sensor"),
    )


class HubControlSafetyTests(unittest.TestCase):
    def tearDown(self):
        # Do not leak lightweight platform stubs into the independent sensor
        # bootstrap test, which imports the real utility module.
        for module_name in (
            "custom_components.savant_energy.switch",
            "custom_components.savant_energy.binary_sensor",
            "custom_components.savant_energy.utils",
            "custom_components.savant_energy.models",
            "custom_components.savant_energy.relay_control",
        ):
            sys.modules.pop(module_name, None)

    def test_hub_only_relay_measurements_create_no_switch_or_relay_status_entity(self):
        switch, binary_sensor = _load_platform_modules()
        hub_only_relay = {
            "uid": "relay::1",
            "role": "relay",
            "has_relay": False,
            "power": 42.0,
            "energy": 1.234,
            "energy_raw": 1234.0,
            "measurement_source": "hub_channel",
            "hub_match_source": "hub_exact",
        }
        coordinator = types.SimpleNamespace(
            data={"snapshot_data": {"presentDemands": [hub_only_relay]}},
            mode="current",
        )
        entry = types.SimpleNamespace(entry_id="entry", data={}, options={})
        hass = types.SimpleNamespace(data={switch.DOMAIN: {entry.entry_id: coordinator}})
        switch_entities = []
        binary_entities = []

        asyncio.run(switch.async_setup_entry(hass, entry, switch_entities.extend))
        asyncio.run(binary_sensor.async_setup_entry(hass, entry, binary_entities.extend))

        self.assertEqual(switch_entities, [])
        self.assertEqual(binary_entities, [])


if __name__ == "__main__":
    unittest.main()
