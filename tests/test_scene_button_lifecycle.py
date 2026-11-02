"""Scene timer cleanup, reload isolation, and in-flight storage regression tests."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/savant_energy'


def load_buttons():
    package = types.ModuleType('button_test_package')
    package.__path__ = [str(ROOT)]
    stubs = {'button_test_package': package}
    def stub(name, **attrs):
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        stubs[name] = module
    stub('homeassistant')
    stub('homeassistant.components')
    stub('homeassistant.helpers')
    stub('homeassistant.components.button', ButtonEntity=type('ButtonEntity', (), {}), ButtonDeviceClass=Mock())
    stub('homeassistant.config_entries', ConfigEntry=object)
    stub('homeassistant.const', EntityCategory=Mock())
    stub('homeassistant.core', HomeAssistant=object, callback=lambda f: f)
    stub('homeassistant.helpers.entity', DeviceInfo=dict)
    stub('homeassistant.helpers.entity_platform', AddEntitiesCallback=object)
    stub('homeassistant.helpers.entity_registry', async_get=Mock())
    stub('homeassistant.helpers.event', async_track_time_interval=Mock(side_effect=lambda *_: Mock()))
    stub('button_test_package.utils', **{name: Mock() for name in (
        'async_build_all_loads_dmx_values', 'async_build_managed_dmx_values',
        'async_set_dmx_values', 'get_dmx_api_stats')})
    stub('button_test_package.scene', SavantSceneStorage=Mock(), SavantSceneManager=Mock())
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('button_test_package.button', ROOT / 'button.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class SceneButtonLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_entry_unload_stops_timer_and_reload_gets_one_fresh_timer(self):
        module = load_buttons()
        hass = types.SimpleNamespace(data={module.DOMAIN: {'entry': object()}})
        entry = types.SimpleNamespace(entry_id='entry', async_on_unload=Mock())
        storage = types.SimpleNamespace(async_load=AsyncMock(), scenes={})
        module.SavantSceneStorage.return_value = storage
        module.SavantSceneManager.return_value = types.SimpleNamespace(storage=storage)
        with patch.object(module, 'SavantAllLoadsButton'), patch.object(module, 'SavantApiCommandLogButton'), patch.object(module, 'SavantApiStatsButton'):
            for _ in range(3):
                await module.async_setup_entry(hass, entry, Mock())
                manager = hass.data[f'{module.DOMAIN}_scene_button_managers']['entry']
                stop = manager._unsub_refresh
                cleanup = entry.async_on_unload.call_args.args[0]
                self.assertIsNone(cleanup())
                cleanup()  # Cleanup is idempotent and doesn't remove entities twice.
                stop.assert_called_once()
                self.assertEqual(hass.data[f'{module.DOMAIN}_scene_button_managers'], {})
                storage.async_load.reset_mock()
                await manager._periodic_refresh()
                storage.async_load.assert_not_awaited()
        self.assertEqual(module.async_track_time_interval.call_count, 3)

    async def test_storage_read_finishing_after_unload_cannot_add_entities(self):
        module = load_buttons()
        started, release = asyncio.Event(), asyncio.Event()
        async def load():
            started.set()
            await release.wait()
        storage = types.SimpleNamespace(async_load=load, scenes={'new': {'name': 'New'}})
        add = Mock()
        manager = module.SavantSceneButtonManager(types.SimpleNamespace(data={}), types.SimpleNamespace(storage=storage), add)
        task = asyncio.create_task(manager._periodic_refresh())
        await started.wait()
        manager.async_unload()
        release.set()
        await task
        add.assert_not_called()
        self.assertEqual(manager.buttons, {})


class AllLoadsControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_controls_block_fallback_and_failed_polls_then_recover(self):
        module = load_buttons()
        relay = {'uid': 'uuid::1', 'role': 'relay', 'has_relay': True,
                 'relay_uid': 'SEM.1', 'percentCommanded': 100}
        bulk = AsyncMock(return_value=True)
        entry = types.SimpleNamespace(data={})
        coordinator = types.SimpleNamespace(mode=module.MODE_CURRENT, config_entry=entry,
            relay_controller=types.SimpleNamespace(set_relay_states_bulk=bulk),
            data={'snapshot_status': {'ok': True}, 'snapshot_data': {
                'telemetry_schema_mode': 'channel_read_only', 'presentDemands': [relay]}})
        button = module.SavantAllLoadsButton(types.SimpleNamespace(), coordinator)
        self.assertFalse(button.available)
        await button.async_press()
        bulk.assert_not_awaited()
        coordinator.data['snapshot_data']['telemetry_schema_mode'] = 'uuid'
        coordinator.data['snapshot_status']['ok'] = False
        self.assertFalse(button.available)
        await button.async_press()
        bulk.assert_not_awaited()
        coordinator.data['snapshot_status']['ok'] = True
        entry.data[module.CONF_INFLUX_SCHEMA_MODE] = module.INFLUX_SCHEMA_CHANNEL_READ_ONLY
        self.assertFalse(button.available)
        await button.async_press()
        bulk.assert_not_awaited()
        entry.data[module.CONF_INFLUX_SCHEMA_MODE] = module.INFLUX_SCHEMA_UUID
        coordinator.data['snapshot_data']['presentDemands'].append({
            **relay, 'relay_uid': 'UNVERIFIED', 'has_relay': False})
        self.assertTrue(button.available)
        await button.async_press()
        bulk.assert_awaited_once_with({'SEM.1': 100})

    async def test_legacy_all_loads_still_uses_legacy_command_path(self):
        module = load_buttons()
        coordinator = types.SimpleNamespace(mode='legacy')
        button = module.SavantAllLoadsButton(types.SimpleNamespace(), coordinator)
        with patch.object(button, '_press_legacy', new=AsyncMock()) as legacy:
            self.assertTrue(button.available)
            await button.async_press()
            legacy.assert_awaited_once()
