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
    async def test_stale_current_token_step_redirects_to_ssh_without_retaining_submitted_token(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {
            module.CONF_INFLUX_TOKEN: "stale-token",
            module.CONF_INFLUX_ORG: "stale-org",
            module.CONF_CIRCUIT_MAP: {"stale::1": {}},
        }

        with mock.patch.object(
            flow,
            "async_step_current_ssh",
            new=mock.AsyncMock(return_value={"type": "form", "step_id": "current_ssh"}),
        ) as ssh_step:
            result = await flow.async_step_current_token({module.CONF_INFLUX_TOKEN: "submitted-token"})

        self.assertEqual(result["step_id"], "current_ssh")
        ssh_step.assert_awaited_once()
        self.assertNotIn(module.CONF_INFLUX_TOKEN, flow._pending)
        self.assertNotIn(module.CONF_INFLUX_ORG, flow._pending)
        self.assertNotIn(module.CONF_CIRCUIT_MAP, flow._pending)
        self.assertEqual(flow._pending[module.CONF_INFLUX_AUTH_METHOD], module.AUTH_INFLUX_SSH)

    async def test_stale_reconfigure_token_step_redirects_to_ssh_without_entry_mutation(self):
        module = _load_config_flow_module()
        original_data = {
            module.CONF_MODE: module.MODE_CURRENT,
            module.CONF_INFLUX_TOKEN: "legacy-token",
            module.CONF_INFLUX_ORG: "legacy-org",
            module.CONF_INFLUX_AUTH_METHOD: "token",
        }
        entry = types.SimpleNamespace(entry_id="entry", data=dict(original_data))
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(entry)
        flow.context = {"entry_id": entry.entry_id}
        flow._pending = {module.CONF_INFLUX_TOKEN: "stale-token"}

        with mock.patch.object(
            flow,
            "async_step_reconfigure_ssh",
            new=mock.AsyncMock(return_value={"type": "form", "step_id": "reconfigure_ssh"}),
        ) as ssh_step:
            result = await flow.async_step_reconfigure_token({module.CONF_INFLUX_TOKEN: "submitted-token"})

        self.assertEqual(result["step_id"], "reconfigure_ssh")
        ssh_step.assert_awaited_once()
        self.assertNotIn(module.CONF_INFLUX_TOKEN, flow._pending)
        self.assertEqual(flow._pending[module.CONF_INFLUX_AUTH_METHOD], module.AUTH_INFLUX_SSH)
        self.assertIsNone(flow.hass.config_entries.updated_entry)
        self.assertEqual(entry.data, original_data)

    async def test_stale_current_manual_org_step_discards_input_and_restarts_ssh(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {
            module.CONF_INFLUX_TOKEN: "stale-token",
            module.CONF_INFLUX_ORG: "stale-org",
            module.CONF_INFLUX_BUCKET: "stale-bucket",
            module.CONF_CIRCUIT_MAP: {"stale::1": {}},
        }
        flow._pending_org_candidates = {"stale": object()}
        flow._pending_ssh_bootstrap = {"token": "stale-token"}

        with mock.patch.object(
            flow,
            "async_step_current_ssh",
            new=mock.AsyncMock(return_value={"type": "form", "step_id": "current_ssh"}),
        ) as ssh_step:
            result = await flow.async_step_current_org_manual(
                {module.CONF_INFLUX_ORG: "submitted-org", module.CONF_INFLUX_BUCKET: "submitted-bucket"}
            )

        self.assertEqual(result["step_id"], "current_ssh")
        ssh_step.assert_awaited_once()
        for key in (
            module.CONF_INFLUX_TOKEN,
            module.CONF_INFLUX_ORG,
            module.CONF_INFLUX_BUCKET,
            module.CONF_CIRCUIT_MAP,
        ):
            self.assertNotIn(key, flow._pending)
        self.assertEqual(flow._pending_org_candidates, {})
        self.assertIsNone(flow._pending_ssh_bootstrap)
        self.assertEqual(flow._pending[module.CONF_INFLUX_AUTH_METHOD], module.AUTH_INFLUX_SSH)

    async def test_stale_reconfigure_manual_org_step_discards_input_without_entry_mutation(self):
        module = _load_config_flow_module()
        original_data = {
            module.CONF_MODE: module.MODE_CURRENT,
            module.CONF_INFLUX_TOKEN: "legacy-token",
            module.CONF_INFLUX_ORG: "legacy-org",
            module.CONF_INFLUX_AUTH_METHOD: "token",
        }
        entry = types.SimpleNamespace(entry_id="entry", data=dict(original_data))
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(entry)
        flow.context = {"entry_id": entry.entry_id}
        flow._pending = {
            module.CONF_INFLUX_TOKEN: "stale-token",
            module.CONF_INFLUX_ORG: "stale-org",
            module.CONF_INFLUX_BUCKET: "stale-bucket",
        }
        flow._pending_ssh_bootstrap = {"token": "stale-token"}

        with mock.patch.object(
            flow,
            "async_step_reconfigure_ssh",
            new=mock.AsyncMock(return_value={"type": "form", "step_id": "reconfigure_ssh"}),
        ) as ssh_step:
            result = await flow.async_step_reconfigure_org_manual(
                {module.CONF_INFLUX_ORG: "submitted-org", module.CONF_INFLUX_BUCKET: "submitted-bucket"}
            )

        self.assertEqual(result["step_id"], "reconfigure_ssh")
        ssh_step.assert_awaited_once()
        self.assertNotIn(module.CONF_INFLUX_TOKEN, flow._pending)
        self.assertNotIn(module.CONF_INFLUX_ORG, flow._pending)
        self.assertNotIn(module.CONF_INFLUX_BUCKET, flow._pending)
        self.assertIsNone(flow._pending_ssh_bootstrap)
        self.assertIsNone(flow.hass.config_entries.updated_entry)
        self.assertEqual(entry.data, original_data)

    async def test_current_setup_routes_directly_to_ssh_without_token_selector(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}

        with mock.patch.object(
            flow,
            "async_step_current_ssh",
            new=mock.AsyncMock(return_value={"type": "form", "step_id": "current_ssh"}),
        ) as ssh_step:
            result = await flow.async_step_current_setup(
                {module.CONF_ADDRESS: "192.168.1.108", module.CONF_HOST: "192.168.1.14"}
            )

        self.assertEqual(result["step_id"], "current_ssh")
        ssh_step.assert_awaited_once()
        self.assertEqual(flow._pending[module.CONF_INFLUX_AUTH_METHOD], module.AUTH_INFLUX_SSH)

    async def test_failed_ssh_reconfigure_retains_legacy_token_entry_data(self):
        module = _load_config_flow_module()
        original_data = {
            module.CONF_MODE: module.MODE_CURRENT,
            module.CONF_ADDRESS: "192.168.1.108",
            module.CONF_HOST: "192.168.1.14",
            module.CONF_INFLUX_TOKEN: "legacy-token",
            module.CONF_INFLUX_ORG: "legacy-org",
            module.CONF_INFLUX_AUTH_METHOD: "token",
            module.CONF_SSH_PRIVATE_KEY: "",
            module.CONF_CIRCUIT_MAP: {"legacy::1": {"role": "relay"}},
        }
        entry = types.SimpleNamespace(entry_id="entry", data=dict(original_data))
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(entry)
        flow.context = {"entry_id": entry.entry_id}

        routed = await flow.async_step_reconfigure_current_host(
            {module.CONF_ADDRESS: "192.168.1.108", module.CONF_HOST: "192.168.1.14"}
        )
        self.assertEqual(routed["step_id"], "reconfigure_ssh")
        self.assertIsNone(flow.hass.config_entries.updated_entry)

        with mock.patch.object(
            module,
            "_async_safe_ssh_prepare_bootstrap_candidates",
            new=mock.AsyncMock(return_value=("", "", [], "ssh_password_auth_failed")),
        ):
            result = await flow.async_step_reconfigure_ssh({module.CONF_SSH_PASSWORD: "wrong-password"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"][module.CONF_SSH_PASSWORD], "ssh_password_auth_failed")
        self.assertIsNone(flow.hass.config_entries.updated_entry)
        self.assertEqual(entry.data, original_data)

    async def test_reconfigure_partial_discovery_preserves_complete_stored_circuit_map(self):
        module = _load_config_flow_module()
        existing_map = {"uuid::1": {"circuit_key": "uuid::1"}, "uuid::2": {"circuit_key": "uuid::2"}}
        entry = types.SimpleNamespace(entry_id="entry", data={module.CONF_CIRCUIT_MAP: existing_map})
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(entry)
        flow.context = {"entry_id": "entry"}
        flow._pending = {module.CONF_ADDRESS: "pbc", module.CONF_INFLUX_TOKEN: "token", module.CONF_INFLUX_ORG: "org"}
        flow._pending_circuit_map_warnings = []
        discovered = types.SimpleNamespace(success=True, circuit_map={"uuid::1": {"circuit_key": "uuid::1"}}, warnings=[])
        with mock.patch.object(module, "discover_circuit_metadata_with_backfill", new=mock.AsyncMock(return_value=discovered)):
            error = await flow._async_discover_pending_circuit_map()
        self.assertIsNone(error)
        self.assertEqual(flow._pending[module.CONF_CIRCUIT_MAP], existing_map)
        self.assertTrue(any("incomplete" in warning.lower() for warning in flow._pending_circuit_map_warnings))

    async def test_ssh_candidate_selection_skips_stale_primary_for_valid_alternate(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {module.CONF_ADDRESS: "192.168.1.108", module.CONF_HOST: "192.168.1.14"}
        stale = types.SimpleNamespace(token="stale", metadata=None)
        valid = types.SimpleNamespace(token="valid", metadata=None)

        async def discover_org(metadata=None):
            return ("org", None) if flow._pending[module.CONF_INFLUX_TOKEN] == "valid" else (None, "influx_auth_failed")

        with mock.patch.object(flow, "_async_safe_discover_pending_org", new=mock.AsyncMock(side_effect=discover_org)), mock.patch.object(
            flow, "_async_discover_pending_circuit_map", new=mock.AsyncMock(return_value=None)
        ) as discover_circuit:
            selected, outcome = await flow._async_select_ssh_token_candidate([stale, valid])

        self.assertIs(selected, valid)
        self.assertIsNone(outcome)
        self.assertEqual(flow._pending[module.CONF_INFLUX_TOKEN], "valid")
        discover_circuit.assert_awaited_once()

    async def test_ssh_setup_installs_key_only_after_circuit_validation(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {
            module.CONF_ADDRESS: "192.168.1.108",
            module.CONF_HOST: "192.168.1.14",
            module.CONF_INFLUX_AUTH_METHOD: module.AUTH_INFLUX_SSH,
        }
        order = []

        async def discover_circuit():
            order.append("circuit")
            return None

        async def install_key():
            order.append("install")
            flow._pending[module.CONF_SSH_PRIVATE_KEY] = "private"
            return None

        with mock.patch.object(
            module,
            "_async_safe_ssh_prepare_bootstrap_candidates",
            new=mock.AsyncMock(return_value=("private", "public", [types.SimpleNamespace(token="token", metadata=None)], None)),
        ), mock.patch.object(
            flow,
            "_async_safe_discover_pending_org",
            new=mock.AsyncMock(return_value=("org", None)),
        ), mock.patch.object(
            flow,
            "_async_discover_pending_circuit_map",
            new=discover_circuit,
        ), mock.patch.object(
            flow,
            "_async_install_pending_ssh_key",
            new=install_key,
        ):
            result = await flow.async_step_current_ssh({module.CONF_SSH_PASSWORD: "password"})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(order, ["circuit", "install"])
        self.assertEqual(result["data"][module.CONF_SSH_PRIVATE_KEY], "private")

    async def test_ssh_setup_does_not_install_key_when_circuit_validation_fails(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {
            module.CONF_ADDRESS: "192.168.1.108",
            module.CONF_HOST: "192.168.1.14",
            module.CONF_INFLUX_AUTH_METHOD: module.AUTH_INFLUX_SSH,
        }
        install_key = mock.AsyncMock(return_value=None)

        with mock.patch.object(
            module,
            "_async_safe_ssh_prepare_bootstrap_candidates",
            new=mock.AsyncMock(return_value=("private", "public", [types.SimpleNamespace(token="token", metadata=None)], None)),
        ), mock.patch.object(
            flow,
            "_async_safe_discover_pending_org",
            new=mock.AsyncMock(return_value=("org", None)),
        ), mock.patch.object(
            flow,
            "_async_discover_pending_circuit_map",
            new=mock.AsyncMock(return_value="influx_auth_failed"),
        ), mock.patch.object(
            flow,
            "_async_install_pending_ssh_key",
            new=install_key,
        ):
            result = await flow.async_step_current_ssh({module.CONF_SSH_PASSWORD: "password"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"]["base"], "influx_auth_failed")
        install_key.assert_not_awaited()
        self.assertNotIn(module.CONF_SSH_PRIVATE_KEY, flow._pending)

    async def test_ssh_org_selection_routes_install_failure_back_to_password(self):
        module = _load_config_flow_module()
        flow = module.ConfigFlow()
        flow.hass = _FakeHass(types.SimpleNamespace(entry_id="unused", data={}))
        flow.context = {}
        flow._pending = {
            module.CONF_ADDRESS: "192.168.1.108",
            module.CONF_HOST: "192.168.1.14",
            module.CONF_INFLUX_TOKEN: "token",
        }
        candidate = module.InfluxOrgCandidate(
            org_id="org",
            org_name="Org",
            circuit_count=1,
            field_names=("power",),
            total_power_w=100.0,
            last_seen=None,
            score=100,
            summary="Org",
            selected_bucket="localHub",
        )
        flow._pending_org_candidates = {"org::localHub": candidate}
        flow._remember_ssh_bootstrap("192.168.1.14", "password", "private", "public", "token")

        with mock.patch.object(
            flow,
            "_async_discover_pending_circuit_map",
            new=mock.AsyncMock(return_value=None),
        ), mock.patch.object(
            flow,
            "_async_install_pending_ssh_key",
            new=mock.AsyncMock(return_value="ssh_key_verify_failed"),
        ):
            result = await flow.async_step_current_org_select({module.CONF_INFLUX_ORG: "org::localHub"})

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "current_ssh")
        self.assertEqual(result["errors"][module.CONF_SSH_PASSWORD], "ssh_key_verify_failed")

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
        self.assertEqual(
            hass.config_entries.updated_entry.data[module.CONF_CIRCUIT_MAP],
            discovery_result.circuit_map,
        )
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
