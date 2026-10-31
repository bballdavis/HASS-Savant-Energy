"""Frontend ownership, reload, and legacy resource regression tests."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/savant_energy'


def load_frontend():
    package = types.ModuleType('frontend_test_package')
    package.__path__ = [str(ROOT)]
    ha = types.ModuleType('homeassistant')
    components = types.ModuleType('homeassistant.components')
    frontend = types.ModuleType('homeassistant.components.frontend')
    frontend.add_extra_js_url = Mock()
    components.frontend = frontend
    http = types.ModuleType('homeassistant.components.http')
    http.StaticPathConfig = lambda *args: args
    stubs = {'frontend_test_package': package, 'homeassistant': ha,
             'homeassistant.components': components, 'homeassistant.components.frontend': frontend,
             'homeassistant.components.http': http}
    with patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location('frontend_test_package.frontend', ROOT / 'frontend.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, frontend, stubs


def hass_for(urls=()):
    resources = types.SimpleNamespace(async_get_info=AsyncMock(),
        async_items=lambda: [{'url': url} for url in urls])
    return types.SimpleNamespace(data={'lovelace': types.SimpleNamespace(resources=resources)},
        http=types.SimpleNamespace(async_register_static_paths=AsyncMock(), register_static_path=Mock()))


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def test_bundled_card_and_alias_are_registered_with_cache_version(self):
        module, frontend, stubs = load_frontend()
        hass = hass_for()
        with patch.dict(sys.modules, stubs):
            await module.async_register_frontend_resource(hass)
        urls = [c.args[1] for c in frontend.add_extra_js_url.call_args_list]
        self.assertEqual(urls, [f'/local/savant_energy/Savant-Card.js?v={module.CARD_VERSION}',
                               f'/local/savant_energy/savant-energy-scenes-card.js?v={module.CARD_VERSION}'])
        paths = hass.http.async_register_static_paths.call_args.args[0]
        self.assertEqual(paths[0][1], str(ROOT / 'www'))

    async def test_external_hacs_resource_retains_ownership(self):
        module, frontend, stubs = load_frontend()
        hass = hass_for(['/hacsfiles/Savant-Card/Savant-Card.js?hacstag=123'])
        with patch.dict(sys.modules, stubs):
            await module.async_register_frontend_resource(hass)
        self.assertEqual(frontend.add_extra_js_url.call_count, 1)
        self.assertIn('savant-energy-scenes-card.js?v=', frontend.add_extra_js_url.call_args.args[1])

    async def test_reload_and_multiple_entries_do_not_register_static_path_twice(self):
        import asyncio
        module, frontend, stubs = load_frontend()
        hass = hass_for()
        with patch.dict(sys.modules, stubs):
            await asyncio.gather(*(module.async_register_frontend_resource(hass) for _ in range(3)))
        hass.http.async_register_static_paths.assert_awaited_once()

    async def test_removing_external_resource_then_reload_switches_to_bundled(self):
        module, frontend, stubs = load_frontend()
        hass = hass_for(['/local/community/Savant-Card/Savant-Card.js?v=1'])
        with patch.dict(sys.modules, stubs):
            await module.async_register_frontend_resource(hass)
            frontend.add_extra_js_url.reset_mock()
            hass.data['lovelace'].resources.async_items = lambda: []
            await module.async_register_frontend_resource(hass)
        self.assertIn('/Savant-Card.js?v=', frontend.add_extra_js_url.call_args_list[0].args[1])
        hass.http.async_register_static_paths.assert_awaited_once()

    async def test_registry_failure_does_not_inject_duplicate_implementation(self):
        module, frontend, stubs = load_frontend()
        hass = hass_for()
        hass.data['lovelace'].resources.async_get_info.side_effect = RuntimeError('registry unavailable')
        with patch.dict(sys.modules, stubs), self.assertLogs(module._LOGGER, level='ERROR'):
            await module.async_register_frontend_resource(hass)
        frontend.add_extra_js_url.assert_not_called()

    async def test_legacy_static_api_is_supported(self):
        module, frontend, stubs = load_frontend()
        del stubs['homeassistant.components.http'].StaticPathConfig
        hass = hass_for()
        with patch.dict(sys.modules, stubs):
            await module.async_register_frontend_resource(hass)
        hass.http.register_static_path.assert_called_once()
        hass.http.async_register_static_paths.assert_not_called()
