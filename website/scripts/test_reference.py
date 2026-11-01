"""Regression checks for stale reference and unsupported source changes."""
from pathlib import Path
import shutil
import tempfile
import unittest

from generate_reference import ExtractionError, generate, run
import json

ROOT = Path(__file__).resolve().parents[2]


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / 'custom_components/savant_energy'
        source.mkdir(parents=True)
        for name in ('const.py', 'config_flow.py', 'api.py', 'services.yaml', 'translations/en.json'):
            dest = source / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'custom_components/savant_energy' / name, dest)

    def test_check_is_non_writing_and_detects_missing_or_stale_output(self):
        with self.assertRaisesRegex(ExtractionError, 'Stale generated'):
            run(self.root, check=True)
        self.assertFalse((self.root / 'docs').exists())
        run(self.root)
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.root / 'docs/reference/generated').glob('*.md')}
        run(self.root, check=True)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        changed = self.root / 'custom_components/savant_energy/const.py'
        changed.write_text(changed.read_text().replace('DEFAULT_SWITCH_COOLDOWN = 15', 'DEFAULT_SWITCH_COOLDOWN = 19'))
        with self.assertRaisesRegex(ExtractionError, 'options.md'):
            run(self.root, check=True)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_source_is_parsed_not_executed(self):
        source = self.root / 'custom_components/savant_energy/const.py'
        source.write_text("raise RuntimeError('must never run')\n" + source.read_text())
        self.assertEqual(set(generate(self.root)), {'services.md', 'options.md', 'setup.md', 'errors.md'})

    def test_unsupported_option_default_fails_before_writing(self):
        source = self.root / 'custom_components/savant_energy/config_flow.py'
        source.write_text(source.read_text().replace('default=_opt(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)', 'default=dynamic_default()'))
        with self.assertRaisesRegex(ExtractionError, 'Unsupported default'):
            run(self.root)
        self.assertFalse((self.root / 'docs').exists())

    def test_service_schema_drift_fails(self):
        source = self.root / 'custom_components/savant_energy/api.py'
        source.write_text(source.read_text().replace('vol.Required("relay_states"): dict', 'vol.Optional("relay_states"): dict'))
        with self.assertRaisesRegex(ExtractionError, 'required flag'):
            run(self.root)

    def test_option_label_drift_fails(self):
        source = self.root / 'custom_components/savant_energy/translations/en.json'
        labels = json.loads(source.read_text())
        labels['options']['step']['init']['data']['new_option'] = 'New option'
        source.write_text(json.dumps(labels))
        with self.assertRaisesRegex(ExtractionError, 'labels and form fields differ'):
            run(self.root)

    def test_generation_is_deterministic(self):
        self.assertEqual(generate(self.root), generate(self.root))

    def test_mode_specific_options_are_labeled(self):
        options = generate(self.root)['options.md']
        self.assertIn('| `dmx_testing_mode` | DMX Testing Mode | `false` | Boolean | Legacy |', options)
        self.assertIn('| `reprovision_ssh_key` | Refresh SSH Key And Token | `false` | Boolean | Current |', options)

    def test_changed_mode_condition_fails(self):
        source = self.root / 'custom_components/savant_energy/config_flow.py'
        source.write_text(source.read_text().replace('if current_mode:\n            fields', 'if has_key:\n            fields'))
        with self.assertRaisesRegex(ExtractionError, 'Unsupported options field composition'):
            run(self.root)

    def test_unreviewed_fields_mutation_fails(self):
        source = self.root / 'custom_components/savant_energy/config_flow.py'
        source.write_text(source.read_text().replace('        if current_mode:\n            fields', '        fields.update(extra_fields())\n        if current_mode:\n            fields'))
        with self.assertRaisesRegex(ExtractionError, 'Unsupported options field composition'):
            run(self.root)


if __name__ == '__main__':
    unittest.main()
