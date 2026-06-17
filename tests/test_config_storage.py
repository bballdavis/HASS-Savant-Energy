import importlib.util
import sys
import types
import unittest
from pathlib import Path


def _load_config_storage_module():
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

    module_path = savant_root / "config_storage.py"
    spec = importlib.util.spec_from_file_location(
        "custom_components.savant_energy.config_storage",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ConfigStorageTests(unittest.TestCase):
    def test_stale_options_do_not_override_fresh_data(self):
        module = _load_config_storage_module()

        data = {
            module.CONF_MODE: module.MODE_CURRENT,
            module.CONF_HOST: "10.0.0.9",
            module.CONF_INFLUX_URL: "http://fresh.example:8086",
            module.CONF_INFLUX_TOKEN: "fresh-token",
            module.CONF_INFLUX_ORG: "fresh-org",
        }
        options = {
            module.CONF_INFLUX_URL: "http://stale.example:8086",
            module.CONF_INFLUX_TOKEN: "stale-token",
            module.CONF_INFLUX_ORG: "stale-org",
        }

        normalized_data, normalized_options, changed = module.normalize_entry_storage(data, options)

        self.assertTrue(changed)
        self.assertEqual(normalized_data[module.CONF_INFLUX_URL], "http://fresh.example:8086")
        self.assertEqual(normalized_data[module.CONF_INFLUX_TOKEN], "fresh-token")
        self.assertEqual(normalized_data[module.CONF_INFLUX_ORG], "fresh-org")
        self.assertNotIn(module.CONF_INFLUX_URL, normalized_options)
        self.assertNotIn(module.CONF_INFLUX_TOKEN, normalized_options)
        self.assertNotIn(module.CONF_INFLUX_ORG, normalized_options)


if __name__ == "__main__":
    unittest.main()
