import importlib.util
from pathlib import Path
import unittest


def _load_influx_client_module():
    module_path = Path(__file__).resolve().parents[1] / "custom_components" / "savant_energy" / "influx_client.py"
    spec = importlib.util.spec_from_file_location("savant_energy_influx_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InfluxEnergyScalingTests(unittest.TestCase):
    def test_resolve_energy_scale_bootstraps_plausible_ct_divisor(self):
        module = _load_influx_client_module()

        energy_kwh, diagnostics = module._resolve_energy_scale(
            "tesla-ct",
            4_150_073_000_000.0,
            power_w=0.0,
            sample_seconds=15.0,
            scale_state={},
        )

        self.assertEqual(round(energy_kwh, 3), 4150.073)
        self.assertEqual(diagnostics["energy_scale_divisor"], 1_000_000_000)
        self.assertEqual(diagnostics["energy_scale_status"], "learning")

    def test_resolve_energy_scale_learns_tesla_divisor(self):
        module = _load_influx_client_module()
        state = {}
        raw_energy = 4_150_071_000_000.0

        for step in range(7):
            energy_kwh, diagnostics = module._resolve_energy_scale(
                "tesla-ct",
                raw_energy + (step * 15_000_000.0),
                power_w=3600.0,
                sample_seconds=5.0,
                scale_state=state,
            )

        self.assertEqual(round(energy_kwh, 3), 4150.161)
        self.assertEqual(diagnostics["energy_scale_divisor"], 1_000_000_000)
        self.assertEqual(diagnostics["energy_scale_status"], "locked")

    def test_classify_circuit_role_keeps_sticky_ct_without_sem(self):
        module = _load_influx_client_module()
        state = {"divisor": 1_000_000_000.0, "stable_role": "ct_sensor"}

        role, relay_uid, role_source = module._classify_circuit_role(
            "tesla-ct",
            matched_uid=None,
            sem_ok=False,
            is_ct_tagged=False,
            state=state,
        )

        self.assertEqual(role, "ct_sensor")
        self.assertIsNone(relay_uid)
        self.assertEqual(role_source, "sticky_ct")

    def test_guard_ct_energy_reading_blocks_implausible_jump(self):
        module = _load_influx_client_module()
        state = {"last_published_energy_kwh": 4150.071}

        energy_kwh, diagnostics = module._guard_ct_energy_reading(
            4_150_071.0,
            expected_delta_kwh=0.02,
            state=state,
        )

        self.assertEqual(energy_kwh, 4150.071)
        self.assertTrue(diagnostics["energy_guard_applied"])
        self.assertEqual(diagnostics["energy_guard_reason"], "jump")
        self.assertEqual(diagnostics["energy_guard_blocked_samples"], 1)


if __name__ == "__main__":
    unittest.main()