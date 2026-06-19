import importlib.util
import sys
from pathlib import Path
import unittest


def _load_ssh_helper_module():
    module_path = Path(__file__).resolve().parents[1] / "custom_components" / "savant_energy" / "ssh_helper.py"
    spec = importlib.util.spec_from_file_location("savant_energy_ssh_helper", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SshHelperTests(unittest.TestCase):
    def test_build_influx_host_metadata_parses_real_host_shape(self):
        module = _load_ssh_helper_module()

        setup_text = """{
  "username": "localHub",
  "password": "!XuW+K&gO6s_hGt@",
  "org": "Racepoint Energy",
  "bucket": "localHub"
}"""
        token_text = """{
  "org": {
    "id": "912133f25b21b958",
    "name": "Racepoint Energy"
  },
  "bucket": {
    "name": "localHub",
    "orgID": "912133f25b21b958"
  },
  "auth": {
    "orgID": "912133f25b21b958"
  }
}"""

        metadata = module._build_influx_host_metadata(setup_text, token_text)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.org_id, "912133f25b21b958")
        self.assertEqual(metadata.org_name, "Racepoint Energy")
        self.assertEqual(metadata.bucket_name, "localHub")
        self.assertEqual(metadata.auth_org_id, "912133f25b21b958")


if __name__ == "__main__":
    unittest.main()
