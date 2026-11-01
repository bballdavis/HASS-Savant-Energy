"""Updater must not downgrade a reviewed pin or propose identical artifacts."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('companion_update', Path(__file__).resolve().parents[1] / 'tools/companion_update.py')
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


class CompanionUpdateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.first = self.commit('first')
        self.second = self.commit('second')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self, value):
        (self.source / 'file').write_text(value)
        self.git('add', 'file')
        self.git('commit', '-qm', value)
        return self.git('rev-parse', 'HEAD')

    def test_same_revision_keeps_pin(self):
        self.assertFalse(UPDATE.needs_build(self.source, self.second))

    def test_older_main_does_not_replace_a_pin_ahead_of_upstream(self):
        self.git('checkout', '-q', self.first)
        self.assertFalse(UPDATE.needs_build(self.source, self.second))

    def test_newer_main_is_built(self):
        self.assertTrue(UPDATE.needs_build(self.source, self.first))

    def test_diverged_history_requires_reviewable_build(self):
        self.git('checkout', '-q', self.first)
        self.commit('diverged')
        self.assertTrue(UPDATE.needs_build(self.source, self.second))

    def test_invalid_or_missing_pin_fails_closed(self):
        with self.assertRaises(ValueError):
            UPDATE.needs_build(self.source, 'main')
        with self.assertRaises(subprocess.CalledProcessError):
            UPDATE.needs_build(self.source, '0' * 40)

    def test_same_runtime_hash_does_not_propose_metadata_only_update(self):
        (self.source / 'dist').mkdir()
        (self.source / 'dist/Savant-Card.js').write_bytes(b'card')
        metadata = {'upstream_artifact_sha256': hashlib.sha256(b'card').hexdigest()}
        self.assertFalse(UPDATE.artifact_changed(self.source, metadata))
        (self.source / 'dist/Savant-Card.js').write_bytes(b'new card')
        self.assertTrue(UPDATE.artifact_changed(self.source, metadata))
