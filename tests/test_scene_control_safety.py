"""Regression coverage for scene commands during channel-only telemetry."""

import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_scene_module():
    root = Path(__file__).resolve().parents[1]
    package_root = root / "custom_components"
    savant_root = package_root / "savant_energy"

    packages = {
        "custom_components": package_root,
        "custom_components.savant_energy": savant_root,
        "homeassistant": None,
        "homeassistant.components": None,
        "homeassistant.helpers": None,
    }
    for name, path in packages.items():
        package = types.ModuleType(name)
        package.__path__ = [str(path)] if path else []
        sys.modules[name] = package

    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        sys.modules[name] = module

    stub("homeassistant.config_entries", ConfigEntry=object)
    stub("homeassistant.core", HomeAssistant=object, callback=lambda function: function)
    stub("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    stub("homeassistant.helpers.storage", Store=object)
    stub("homeassistant.helpers.entity_registry", async_get=lambda _hass: None)
    stub("homeassistant.components.http", HomeAssistantView=object)
    stub("homeassistant.exceptions", HomeAssistantError=RuntimeError)
    stub("custom_components.savant_energy.api", register_scene_services=lambda *_args: None)
    stub(
        "custom_components.savant_energy.utils",
        async_build_managed_dmx_values=lambda *_args: None,
        async_set_dmx_values=lambda *_args: None,
        slugify=lambda value: value,
    )

    name = "custom_components.savant_energy.scene_control_test"
    spec = importlib.util.spec_from_file_location(name, savant_root / "scene.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SceneControlSafetyTests(unittest.TestCase):
    def test_current_scene_requires_live_uuid_relay_identity(self):
        scene_module = _load_scene_module()
        calls = []

        async def send_bulk(states):
            calls.append(states)
            return True

        relay = {
            "uid": "uuid::1", "role": "relay", "has_relay": True,
            "relay_uid": "SEM.1", "percentCommanded": 100,
        }
        state = types.SimpleNamespace(attributes={"uid": "uuid::1"})
        hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _entity_id: state))
        coordinator = types.SimpleNamespace(
            config_entry=types.SimpleNamespace(data={}),
            relay_controller=types.SimpleNamespace(set_relay_states_bulk=send_bulk),
            data={"snapshot_data": {"telemetry_schema_mode": "channel_read_only", "presentDemands": [relay]}},
        )
        manager = scene_module.SavantSceneManager(hass, coordinator, types.SimpleNamespace())
        scene = {"name": "Test scene"}
        members = {"switch.load": True}

        self.assertFalse(asyncio.run(manager._execute_scene_current(scene, members)))
        coordinator.data["snapshot_data"]["telemetry_schema_mode"] = "uuid"
        coordinator.config_entry.data[scene_module.CONF_INFLUX_SCHEMA_MODE] = scene_module.INFLUX_SCHEMA_CHANNEL_READ_ONLY
        self.assertFalse(asyncio.run(manager._execute_scene_current(scene, members)))
        coordinator.config_entry.data[scene_module.CONF_INFLUX_SCHEMA_MODE] = scene_module.INFLUX_SCHEMA_UUID
        coordinator.data["snapshot_data"]["presentDemands"] = [{**relay, "has_relay": False, "measurement_source": "hub_channel"}]
        self.assertFalse(asyncio.run(manager._execute_scene_current(scene, members)))
        self.assertEqual(calls, [])

        coordinator.data["snapshot_data"]["presentDemands"] = [relay]
        coordinator.data["snapshot_status"] = {"ok": False, "used_cached_snapshot": True}
        self.assertFalse(asyncio.run(manager._execute_scene_current(scene, members)))
        coordinator.data["snapshot_status"] = {"ok": True}
        self.assertTrue(asyncio.run(manager._execute_scene_current(scene, members)))
        self.assertEqual(calls, [{"SEM.1": 100}])


if __name__ == "__main__":
    unittest.main()
