import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def _install_homeassistant_stubs() -> None:
    if "voluptuous" not in sys.modules:
        voluptuous = types.ModuleType("voluptuous")

        def _schema(value):
            return value

        def _required(value, default=None):
            return value

        def _in(value):
            return value

        voluptuous.Schema = _schema
        voluptuous.Required = _required
        voluptuous.In = _in
        sys.modules["voluptuous"] = voluptuous

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    sys.modules["homeassistant"] = homeassistant

    class _ConfigFlowBase:
        def __init_subclass__(cls, **kwargs):
            return super().__init_subclass__()

        def async_abort(self, reason=None):
            return {"type": "abort", "reason": reason}

        def async_create_entry(self, title=None, data=None):
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(self, **kwargs):
            payload = {"type": "form"}
            payload.update(kwargs)
            return payload

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = _ConfigFlowBase
    config_entries.OptionsFlow = _ConfigFlowBase
    config_entries.ConfigEntry = object
    sys.modules["homeassistant.config_entries"] = config_entries
    homeassistant.config_entries = config_entries

    core = types.ModuleType("homeassistant.core")
    core.callback = lambda func: func
    core.HomeAssistant = object
    sys.modules["homeassistant.core"] = core
    homeassistant.core = core

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers
    homeassistant.helpers = helpers

    selector = types.ModuleType("homeassistant.helpers.selector")

    class _SelectSelectorMode:
        DROPDOWN = "dropdown"

    class _SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class _SelectSelector:
        def __init__(self, config):
            self.config = config

    selector.SelectSelectorMode = _SelectSelectorMode
    selector.SelectSelectorConfig = _SelectSelectorConfig
    selector.SelectSelector = _SelectSelector
    sys.modules["homeassistant.helpers.selector"] = selector
    helpers.selector = selector


def _load_config_flow_module():
    _install_homeassistant_stubs()
    repo_root = Path(__file__).resolve().parents[1]
    package_root = repo_root / "custom_components"
    savant_root = package_root / "savant_energy"

    if "custom_components" not in sys.modules:
        package = types.ModuleType("custom_components")
        package.__path__ = [str(package_root)]
        sys.modules["custom_components"] = package

    if "custom_components.savant_energy" not in sys.modules:
        package = types.ModuleType("custom_components.savant_energy")
        package.__path__ = [str(savant_root)]
        sys.modules["custom_components.savant_energy"] = package

    module_path = savant_root / "config_flow.py"
    spec = importlib.util.spec_from_file_location(
        "custom_components.savant_energy.config_flow",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeServices:
    def __init__(self):
        self.calls = []

    async def async_call(self, domain, service, data, blocking=False):
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "data": data,
                "blocking": blocking,
            }
        )


class _FakeConfigEntries:
    def __init__(self, entry):
        self._entry = entry
        self.updated_entry = None
        self.reloads = []

    def async_get_entry(self, entry_id):
        return self._entry if entry_id == self._entry.entry_id else None

    def async_update_entry(self, entry, data=None, options=None):
        self.updated_entry = types.SimpleNamespace(entry=entry, data=data, options=options)

    async def async_reload(self, entry_id):
        self.reloads.append(entry_id)


class _FakeHass:
    def __init__(self, entry):
        self.config_entries = _FakeConfigEntries(entry)
        self.services = _FakeServices()


class ConfigFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconfigure_completes_when_discovery_only_returns_warnings(self):
        module = _load_config_flow_module()

        entry = types.SimpleNamespace(
            entry_id="entry-1",
            data={
                module.CONF_MODE: module.MODE_CURRENT,
                module.CONF_ADDRESS: "192.168.1.108",
                module.CONF_HOST: "192.168.1.14",
                module.CONF_INFLUX_URL: "http://192.168.1.14:8086",
                module.CONF_INFLUX_TOKEN: "old-token",
                module.CONF_INFLUX_ORG: "old-org",
                module.CONF_CIRCUIT_MAP: {},
            },
        )
        hass = _FakeHass(entry)

        flow = module.ConfigFlow()
        flow.hass = hass
        flow.context = {"entry_id": entry.entry_id}
        flow._pending = {
            module.CONF_MODE: module.MODE_CURRENT,
            module.CONF_ADDRESS: "192.168.1.108",
            module.CONF_HOST: "192.168.1.14",
            module.CONF_INFLUX_TOKEN: "fresh-token",
            module.CONF_INFLUX_ORG: "new-org",
            module.CONF_INFLUX_AUTH_METHOD: module.DEFAULT_INFLUX_AUTH_METHOD,
            module.CONF_CIRCUIT_MAP: {"UUID-1::1": {"role": "ct_sensor"}},
        }

        discovery_result = types.SimpleNamespace(
            success=True,
            circuit_map={"UUID-1::1": {"role": "ct_sensor"}},
            warnings=[
                "Mystery Load (channel 1, type 0000) could not be matched confidently to a Savant relay UID, so it was saved as a CT/read-only sensor.",
            ],
            error_key=None,
            error_message=None,
            query_window="-2m",
        )

        with mock.patch.object(
            module,
            "discover_circuit_metadata_with_backfill",
            new=mock.AsyncMock(return_value=discovery_result),
        ):
            discovery_error = await flow._async_discover_pending_circuit_map()

        self.assertIsNone(discovery_error)
        self.assertEqual(flow._pending_circuit_map_warnings, discovery_result.warnings)
        result = await flow._async_finish_current_reconfigure(entry)

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "reconfigure_successful")
        self.assertIsNotNone(hass.config_entries.updated_entry)
        self.assertEqual(hass.config_entries.reloads, [entry.entry_id])
        create_calls = [
            call
            for call in hass.services.calls
            if call["domain"] == "persistent_notification" and call["service"] == "create"
        ]
        self.assertEqual(len(create_calls), 1)
        self.assertIn("Mystery Load", create_calls[0]["data"]["message"])
        self.assertEqual(
            create_calls[0]["data"]["notification_id"],
            module._CIRCUIT_MAP_WARNING_NOTIFICATION_ID,
        )


if __name__ == "__main__":
    unittest.main()
