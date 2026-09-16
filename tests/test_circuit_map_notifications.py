import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


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
    @staticmethod
    def _zero_power_snapshot(*powers, status=None):
        return {
            "presentDemands": [
                {"role": "relay", "power": power} for power in powers
            ] + [{"role": "ct_sensor", "power": 2400}],
            "circuit_map_status": status or {
                "inventory_status": "complete",
                "inventory_authoritative": True,
            },
        }

    async def _zero_power_coordinator(self, module):
        coordinator = object.__new__(module.SavantEnergyCoordinator)
        coordinator.hass = types.SimpleNamespace(services=_FakeServices())
        coordinator._zero_relay_power_pending_since = None
        coordinator._zero_relay_power_notification_active = False
        coordinator._zero_relay_power_recovery_checked = False
        return coordinator

    async def test_zero_relay_power_debounces_dedupes_and_dismisses_on_recovery(self):
        module = _load_integration_module()
        coordinator = await self._zero_power_coordinator(module)
        base = module.datetime(2026, 9, 1, 12, 0, 0)
        snapshot = self._zero_power_snapshot(0, 1e-7)

        await coordinator._async_handle_zero_relay_power(snapshot, "-2m", base)
        self.assertEqual(coordinator.hass.services.calls, [])
        await coordinator._async_handle_zero_relay_power(
            snapshot, "-2m", base + module.timedelta(seconds=59)
        )
        self.assertEqual(coordinator.hass.services.calls, [])
        await coordinator._async_handle_zero_relay_power(
            snapshot, "-2m", base + module.timedelta(seconds=60)
        )
        await coordinator._async_handle_zero_relay_power(
            snapshot, "-2m", base + module.timedelta(seconds=120)
        )
        self.assertEqual(len(coordinator.hass.services.calls), 1)
        self.assertEqual(
            coordinator.hass.services.calls[0][2]["notification_id"],
            module.ZERO_RELAY_POWER_NOTIFICATION_ID,
        )

        recovered = self._zero_power_snapshot(0, 15)
        await coordinator._async_handle_zero_relay_power(
            recovered, "-2m", base + module.timedelta(seconds=121)
        )
        self.assertEqual(len(coordinator.hass.services.calls), 2)
        self.assertEqual(coordinator.hass.services.calls[-1][1], "dismiss")

    async def test_zero_relay_power_guards_reset_pending_without_dismiss(self):
        module = _load_integration_module()
        coordinator = await self._zero_power_coordinator(module)
        base = module.datetime(2026, 9, 1, 12, 0, 0)
        valid = self._zero_power_snapshot(0, 0)
        await coordinator._async_handle_zero_relay_power(valid, "-2m", base)
        coordinator._zero_relay_power_notification_active = True
        guards = [
            (valid, "-15m"),
            (self._zero_power_snapshot(0, 0, status={"inventory_status": "partial", "inventory_authoritative": False}), "-2m"),
            (self._zero_power_snapshot(0), "-2m"),
            (self._zero_power_snapshot(0, None), "-2m"),
        ]
        for snapshot, window in guards:
            await coordinator._async_handle_zero_relay_power(snapshot, window, base + module.timedelta(seconds=60))
            self.assertIsNone(coordinator._zero_relay_power_pending_since)
        self.assertEqual(coordinator.hass.services.calls, [])

    async def test_zero_relay_power_nonzero_ct_does_not_mask_zero_relays(self):
        module = _load_integration_module()
        coordinator = await self._zero_power_coordinator(module)
        base = module.datetime(2026, 9, 1, 12, 0, 0)
        snapshot = self._zero_power_snapshot(0, 0)
        await coordinator._async_handle_zero_relay_power(snapshot, "-2m", base)
        await coordinator._async_handle_zero_relay_power(snapshot, "-2m", base + module.timedelta(seconds=60))
        self.assertEqual(len(coordinator.hass.services.calls), 1)

    async def test_zero_relay_power_reconfigure_inventory_never_alerts(self):
        module = _load_integration_module()
        coordinator = await self._zero_power_coordinator(module)
        base = module.datetime(2026, 9, 1, 12, 0, 0)
        for status in (
            {"inventory_status": "complete", "inventory_authoritative": True, "reconfigure_required": True},
            {"inventory_status": "complete", "inventory_authoritative": True, "unknown_circuit_keys": ["new"]},
        ):
            snapshot = self._zero_power_snapshot(0, 0, status=status)
            await coordinator._async_handle_zero_relay_power(snapshot, "-2m", base)
            await coordinator._async_handle_zero_relay_power(snapshot, "-2m", base + module.timedelta(seconds=60))
        self.assertEqual(coordinator.hass.services.calls, [])

    async def test_zero_relay_power_recovery_dismisses_once_after_reload(self):
        module = _load_integration_module()
        coordinator = await self._zero_power_coordinator(module)
        base = module.datetime(2026, 9, 1, 12, 0, 0)
        recovered = self._zero_power_snapshot(1, 2)
        await coordinator._async_handle_zero_relay_power(recovered, "-2m", base)
        await coordinator._async_handle_zero_relay_power(recovered, "-2m", base + module.timedelta(seconds=60))
        self.assertEqual(len(coordinator.hass.services.calls), 1)
        await coordinator._async_handle_zero_relay_power(recovered, "-2m", base + module.timedelta(seconds=120))
        self.assertEqual(len(coordinator.hass.services.calls), 1)

    async def test_connection_state_is_unchanged_when_persist_raises(self):
        module = _load_integration_module()
        coordinator = object.__new__(module.SavantEnergyCoordinator)
        coordinator.influx_token = "old-token"
        coordinator.influx_org = "old-org"
        coordinator.influx_bucket = "old-bucket"
        coordinator.ssh_private_key = "old-key"
        coordinator.config_entry = types.SimpleNamespace(data={"influx_token": "old-token"})
        def fail_update(*_args, **_kwargs):
            raise RuntimeError("storage unavailable")
        coordinator.hass = types.SimpleNamespace(config_entries=types.SimpleNamespace(async_update_entry=fail_update))
        with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
            await coordinator._async_persist_connection_state(
                token="new-token", org="new-org", bucket="new-bucket", ssh_private_key="new-key"
            )
        self.assertEqual(
            (coordinator.influx_token, coordinator.influx_org, coordinator.influx_bucket, coordinator.ssh_private_key),
            ("old-token", "old-org", "old-bucket", "old-key"),
        )

    async def test_runtime_candidate_failure_preserves_existing_connection_state(self):
        module = _load_integration_module()
        coordinator = object.__new__(module.SavantEnergyCoordinator)
        updates = []
        class _Hass:
            config_entries = types.SimpleNamespace(async_update_entry=lambda entry, data: updates.append(data))
            async def async_add_executor_job(self, _func, *_args):
                return [failed], None
        failed = types.SimpleNamespace(token="stale-token", metadata=None)
        coordinator.hass = _Hass()
        coordinator.host = "host"
        coordinator.influx_url = "http://host:8086"
        coordinator.ssh_private_key = "private"
        coordinator.sem_host = "sem"
        coordinator.influx_token = "current-token"
        coordinator.influx_org = "current-org"
        coordinator.influx_bucket = "current-bucket"
        coordinator.config_entry = types.SimpleNamespace(data={"influx_token": "current-token", "influx_org": "current-org", "influx_bucket": "current-bucket"})
        coordinator._token_refresh_in_progress = False
        coordinator._adjust_interval = lambda success: None
        with mock.patch.object(
            module, "async_discover_influx_org", new=mock.AsyncMock(return_value=types.SimpleNamespace(selected_org_id=None))
        ):
            refreshed, metadata = await coordinator._async_refresh_influx_token_and_metadata()
        self.assertFalse(refreshed)
        self.assertIsNone(metadata)
        self.assertEqual((coordinator.influx_token, coordinator.influx_org, coordinator.influx_bucket), ("current-token", "current-org", "current-bucket"))
        self.assertEqual(updates, [])

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
