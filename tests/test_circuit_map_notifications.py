import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _install_homeassistant_stubs() -> None:
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda value, **kwargs: value
    voluptuous.Required = lambda value, **kwargs: value
    voluptuous.Optional = lambda value, **kwargs: value
    voluptuous.ALLOW_EXTRA = object()
    sys.modules["voluptuous"] = voluptuous

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    sys.modules["homeassistant.config_entries"] = config_entries

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    sys.modules["homeassistant.core"] = core

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers

    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = str
    config_validation.positive_int = int
    sys.modules["homeassistant.helpers.config_validation"] = config_validation

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")

    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, name, update_interval):
            self.hass = hass
            self.update_interval = update_interval

    update_coordinator.DataUpdateCoordinator = _DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

    translation = types.ModuleType("homeassistant.helpers.translation")

    async def _async_get_translations(*args, **kwargs):
        return {}

    translation.async_get_translations = _async_get_translations
    sys.modules["homeassistant.helpers.translation"] = translation

    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    sys.modules["homeassistant.components"] = components
    frontend = types.ModuleType("homeassistant.components.frontend")
    sys.modules["homeassistant.components.frontend"] = frontend
    components.frontend = frontend


def _load_integration_module():
    _install_homeassistant_stubs()
    repo_root = Path(__file__).resolve().parents[1]
    package_root = repo_root / "custom_components"
    savant_root = package_root / "savant_energy"

    package = types.ModuleType("custom_components")
    package.__path__ = [str(package_root)]
    sys.modules["custom_components"] = package
    savant_package = types.ModuleType("custom_components.savant_energy")
    savant_package.__path__ = [str(savant_root)]
    sys.modules["custom_components.savant_energy"] = savant_package

    module_name = "custom_components.savant_energy.integration_under_test"
    spec = importlib.util.spec_from_file_location(module_name, savant_root / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append((domain, service, data, blocking))


class CircuitMapNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_each_mismatch_once_and_clears_when_healthy(self):
        module = _load_integration_module()
        coordinator = object.__new__(module.SavantEnergyCoordinator)
        coordinator.hass = types.SimpleNamespace(services=_FakeServices())
        coordinator._circuit_map_mismatch_fingerprint = None
        coordinator._circuit_map_status_initialized = False

        first_mismatch = {
            "unknown_circuit_keys": ["UUID-1::1"],
            "unknown_circuits": [
                {
                    "circuit_key": "UUID-1::1",
                    "display_name": "A/C",
                    "channel": "1",
                    "type": "0074",
                }
            ],
            "missing_circuit_keys": [],
        }
        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            await coordinator._async_handle_circuit_map_status(first_mismatch)
            await coordinator._async_handle_circuit_map_status(first_mismatch)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(len(coordinator.hass.services.calls), 1)
        self.assertIn("A/C (channel 1, type 0074)", coordinator.hass.services.calls[0][2]["message"])

        changed_mismatch = {**first_mismatch, "unknown_circuit_keys": ["UUID-1::1", "UUID-2::2"]}
        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            await coordinator._async_handle_circuit_map_status(changed_mismatch)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(len(coordinator.hass.services.calls), 2)

        await coordinator._async_handle_circuit_map_status(
            {"unknown_circuit_keys": [], "unknown_circuits": [], "missing_circuit_keys": []}
        )
        await coordinator._async_handle_circuit_map_status(
            {"unknown_circuit_keys": [], "unknown_circuits": [], "missing_circuit_keys": []}
        )
        self.assertEqual(len(coordinator.hass.services.calls), 3)
        self.assertEqual(coordinator.hass.services.calls[-1][1], "dismiss")

        with self.assertLogs(module._LOGGER.name, level="WARNING") as logs:
            await coordinator._async_handle_circuit_map_status(first_mismatch)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(len(coordinator.hass.services.calls), 4)


if __name__ == "__main__":
    unittest.main()
