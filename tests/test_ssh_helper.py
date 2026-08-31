import asyncio
import importlib.util
import sys
import shlex
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest import mock


class _FakeStream:
    def __init__(self, payload: str = "", status: int = 0) -> None:
        self._payload = payload.encode("utf-8")
        self.channel = SimpleNamespace(recv_exit_status=lambda: status)

    def read(self) -> bytes:
        payload = self._payload
        self._payload = b""
        return payload


class _FakeChannel:
    def __init__(self) -> None:
        self.exit_code = 0

    def recv_exit_status(self) -> int:
        return self.exit_code


class _FakeSSHClient:
    def __init__(self, command_map):
        self.command_map = dict(command_map)
        self.commands = []
        self.closed = False
        self.channel = _FakeChannel()

    def set_missing_host_key_policy(self, *_args, **_kwargs):
        return None

    def connect(self, **_kwargs):
        return None

    def close(self):
        self.closed = True

    def exec_command(self, command):
        self.commands.append(command)
        if command.startswith("cat "):
            path = shlex.split(command)[1]
            return (
                None,
                _FakeStream(self.command_map.get(("cat", path), "")),
                _FakeStream(""),
            )
        if command.startswith("find "):
            return (
                None,
                _FakeStream(self.command_map.get(("find",), "")),
                _FakeStream(""),
            )
        if command.startswith("mkdir ") or command.startswith("python3 "):
            command_type = "mkdir" if command.startswith("mkdir ") else "python3"
            status = self.command_map.get(("status", command_type), 0)
            return (
                None,
                _FakeStream("", status),
                _FakeStream(""),
            )
        raise AssertionError(f"Unexpected command: {command}")


class _FakeEd25519Key:
    def __init__(self, file_obj) -> None:
        self.file_obj = file_obj


class _FakeHass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


class _BytesSftpFile:
    def __init__(self, storage, path, mode, fail_write=False, fail_truncate=False):
        self.storage, self.path, self.mode, self.fail_write, self.fail_truncate = storage, path, mode, fail_write, fail_truncate
        self.buffer = storage.get(path, b"") if "r" in mode or "a" in mode else b""
    def __enter__(self):
        if "r" in self.mode and self.path not in self.storage:
            raise OSError("missing")
        return self
    def __exit__(self, *_args):
        if any(flag in self.mode for flag in ("w", "a", "+")):
            self.storage[self.path] = self.buffer
    def read(self): return self.buffer
    def write(self, value):
        if self.fail_write: raise OSError("write failed")
        self.buffer = self.buffer + value
    def truncate(self, size):
        if self.fail_truncate: raise OSError("truncate failed")
        self.buffer = self.buffer[:size]


class _BytesSftp:
    def __init__(self, storage, fail_write=False, fail_truncate=False):
        self.storage, self.fail_write, self.fail_truncate, self.rename_calls = storage, fail_write, fail_truncate, 0
    def open(self, path, mode): return _BytesSftpFile(self.storage, path, mode, self.fail_write and "a" in mode, self.fail_truncate and "+" in mode)
    def chmod(self, *_args): return None
    def remove(self, path): self.storage.pop(path, None)
    def rename(self, *_args): self.rename_calls += 1; raise AssertionError("rename must not be called")
    def close(self): return None


class _BytesClient:
    def __init__(self, storage, fail_write=False, fail_truncate=False, reject_key=False):
        self.sftp = _BytesSftp(storage, fail_write, fail_truncate)
        self.reject_key = reject_key
    def set_missing_host_key_policy(self, *_args, **_kwargs): return None
    def connect(self, **kwargs):
        if self.reject_key and kwargs.get("pkey") is not None:
            raise RuntimeError("key rejected")
    def close(self): return None
    def exec_command(self, command):
        if command.startswith("printf "): return None, _FakeStream("/data/home/RPM"), _FakeStream("")
        if command.startswith("mkdir "): return None, _FakeStream(""), _FakeStream("")
        raise AssertionError(command)
    def open_sftp(self): return self.sftp


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

    def test_resolve_remote_influx_read_token_primary(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient(
            {
                ("cat", module._TOKEN_PATH): "primary-token\n",
            }
        )

        token = module._resolve_remote_influx_read_token(fake_client)

        self.assertEqual(token, "primary-token")
        self.assertEqual(fake_client.commands[0], f"cat {shlex.quote(module._TOKEN_PATH)}")
        self.assertFalse(any(cmd.startswith("find ") for cmd in fake_client.commands))

    def test_resolve_remote_influx_read_token_alternate(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient(
            {
                ("cat", module._TOKEN_PATH): "",
                ("cat", module._ALT_TOKEN_PATH): "alternate-token\n",
            }
        )

        token = module._resolve_remote_influx_read_token(fake_client)

        self.assertEqual(token, "alternate-token")
        self.assertIn(f"cat {shlex.quote(module._ALT_TOKEN_PATH)}", fake_client.commands)
        self.assertFalse(any(cmd.startswith("find ") for cmd in fake_client.commands))

    def test_resolve_remote_influx_read_token_find(self):
        module = _load_ssh_helper_module()
        found = "/data/home/Some User/other/InfluxDB2/.influxReadtoken"
        fake_client = _FakeSSHClient(
            {
                ("cat", module._TOKEN_PATH): "",
                ("cat", module._ALT_TOKEN_PATH): "",
                ("find",): f"{found}\n",
                ("cat", found): "found-token\n",
            }
        )

        token = module._resolve_remote_influx_read_token(fake_client)

        self.assertEqual(token, "found-token")
        self.assertEqual(
            fake_client.commands[2],
            "find / -type f -path '*/InfluxDB2/.influxReadtoken' -print 2>/dev/null | sort -u | head -n 8",
        )
        self.assertEqual(fake_client.commands[3], f"cat {shlex.quote(found)}")

    def test_resolve_remote_influx_read_token_exhausted_lookup(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient(
            {
                ("cat", module._TOKEN_PATH): "",
                ("cat", module._ALT_TOKEN_PATH): "",
                ("find",): "",
            }
        )

        token = module._resolve_remote_influx_read_token(fake_client)

        self.assertEqual(token, "")
        self.assertEqual(len(fake_client.commands), 3)
        self.assertEqual(
            fake_client.commands[2],
            "find / -type f -path '*/InfluxDB2/.influxReadtoken' -print 2>/dev/null | sort -u | head -n 8",
        )

    def test_resolve_details_preserves_home_layout_and_key_path(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient({
            ("cat", module._TOKEN_PATH): "",
            ("cat", module._ALT_TOKEN_PATH): "home-token\n",
        })

        result = module._resolve_remote_influx_read_token_details(fake_client)

        self.assertEqual(result.token, "home-token")
        self.assertEqual(result.layout, "/data/home/RPM")
        self.assertEqual(result.authorized_keys_path, "/data/home/RPM/.ssh/authorized_keys")

    def test_token_candidates_keep_the_first_deterministic_path_per_token(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient({
            ("cat", module._TOKEN_PATH): "same-token\n",
            ("cat", module._ALT_TOKEN_PATH): "same-token\n",
            ("find",): "",
        })
        candidates = module._resolve_remote_influx_read_token_candidates(fake_client)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].token_path, module._TOKEN_PATH)

    def test_bootstrap_result_exposes_stage_while_unpacking_legacy_shape(self):
        module = _load_ssh_helper_module()
        result = module.SSHBootstrapResult(token="t", stage="complete")

        token, metadata, error = result

        self.assertEqual((token, metadata, error), ("t", None, None))
        self.assertEqual(result.stage, "complete")

    def test_ssh_bootstrap_worker_uses_shared_resolver(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient({})
        fake_paramiko = SimpleNamespace(
            SSHClient=lambda: fake_client,
            AutoAddPolicy=lambda: None,
            Ed25519Key=_FakeEd25519Key,
        )

        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            with mock.patch.object(module, "_resolve_remote_influx_read_token", return_value="bootstrap-token") as resolver:
                with mock.patch.object(module, "_read_remote_text", return_value=""):
                    token, metadata, error = module._ssh_bootstrap_worker(
                        "example.com", "user", "pass", "ssh-rsa key"
                    )

        self.assertEqual(token, "bootstrap-token")
        self.assertIsNone(metadata)
        self.assertIsNone(error)
        resolver.assert_called_once_with(fake_client)

    def test_ssh_bootstrap_reports_key_install_stage(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient({("status", "python3"): 1})
        fake_paramiko = SimpleNamespace(
            SSHClient=lambda: fake_client,
            AutoAddPolicy=lambda: None,
            Ed25519Key=_FakeEd25519Key,
        )

        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            result = module._ssh_bootstrap_worker(
                "example.com", "user", "pass", "ssh-rsa key"
            )

        self.assertEqual(result.error_key, "ssh_key_install_failed")
        self.assertEqual(result.stage, "authorized_keys")

    def test_ssh_fetch_worker_uses_shared_resolver(self):
        module = _load_ssh_helper_module()
        fake_client = _FakeSSHClient({})
        fake_paramiko = SimpleNamespace(
            SSHClient=lambda: fake_client,
            AutoAddPolicy=lambda: None,
            Ed25519Key=_FakeEd25519Key,
        )

        resolution = module.InfluxTokenResolution("key-token")
        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            with mock.patch.object(module, "_read_influx_token_candidates", return_value=[module.InfluxTokenCandidate(resolution)]) as resolver:
                    token, metadata = module._ssh_fetch_influx_bundle_with_key_worker(
                        "example.com", "user", "key"
                    )

        self.assertEqual(token, "key-token")
        self.assertIsNone(metadata)
        resolver.assert_called_once_with(fake_client)

    def test_authorized_keys_rollback_preserves_raw_crlf_and_no_final_newline(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        original = b"ssh-ed25519 old\xff comment\r\nssh-rsa final"
        storage = {path: original}
        client = _BytesClient(storage)
        _, added = module._install_authorized_key(client, "RPM", "ssh-ed25519 managed savant_energy_ha")
        self.assertTrue(added)
        append = client._savant_energy_authorized_key_append
        self.assertTrue(module._remove_authorized_key(client, append))
        self.assertEqual(storage[path], original)
        self.assertEqual(client.sftp.rename_calls, 0)

    def test_authorized_keys_rollback_removes_new_file_and_keeps_concurrent_change(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        storage = {}
        client = _BytesClient(storage)
        _, added = module._install_authorized_key(client, "RPM", "ssh-ed25519 managed savant_energy_ha")
        self.assertTrue(added)
        append = client._savant_energy_authorized_key_append
        self.assertTrue(module._remove_authorized_key(client, append))
        self.assertNotIn(path, storage)

        storage = {path: b"ssh-rsa other\n"}
        client = _BytesClient(storage)
        _, added = module._install_authorized_key(client, "RPM", "ssh-ed25519 managed savant_energy_ha")
        self.assertTrue(added)
        append = client._savant_energy_authorized_key_append
        storage[path] += b"ssh-rsa concurrent\n"
        self.assertFalse(module._remove_authorized_key(client, append))
        self.assertTrue(storage[path].endswith(b"ssh-rsa concurrent\n"))
        self.assertEqual(client.sftp.rename_calls, 0)

    def test_rollback_truncate_failure_never_erases_existing_keys(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        original = b"ssh-rsa first\nssh-ed25519 second\xff\n"
        storage = {path: original}
        client = _BytesClient(storage)
        _, added = module._install_authorized_key(client, "RPM", "ssh-ed25519 managed savant_energy_ha")
        self.assertTrue(added)
        append = client._savant_energy_authorized_key_append
        client.sftp.fail_truncate = True
        with self.assertRaisesRegex(OSError, "truncate failed"):
            module._remove_authorized_key(client, append)
        self.assertTrue(storage[path].startswith(original))
        self.assertTrue(storage[path].endswith(append.suffix))

    def test_authorized_key_write_failure_does_not_use_rename(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        client = _BytesClient({path: b"ssh-rsa prior\n"}, fail_write=True)
        with self.assertRaises(module._SSHInstallError):
            module._install_authorized_key(client, "RPM", "ssh-ed25519 managed savant_energy_ha")
        self.assertEqual(client.sftp.rename_calls, 0)

    def test_worker_rolls_back_after_post_append_chmod_or_reread_failure(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        public_key = "ssh-ed25519 managed savant_energy_ha"

        def run(password_client, verify_client):
            clients = iter((password_client, verify_client))
            fake_paramiko = SimpleNamespace(
                SSHClient=lambda: next(clients), AutoAddPolicy=lambda: None, Ed25519Key=_FakeEd25519Key
            )
            with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
                return module._ssh_install_and_verify_key_worker(
                    "host", "RPM", "password", "private", public_key, "token"
                )

        original = b"ssh-rsa original\xff\r\n"
        password = _BytesClient({path: original})
        password.sftp.chmod = mock.Mock(side_effect=[OSError("chmod failed"), None])
        self.assertEqual(run(password, _BytesClient(password.sftp.storage, reject_key=True)), "ssh_key_install_failed")
        self.assertEqual(password.sftp.storage[path], original)

        password = _BytesClient({path: original})
        open_remote = password.sftp.open
        reads = 0
        def fail_second_read(remote_path, mode):
            nonlocal reads
            if mode == "rb":
                reads += 1
                if reads == 2:
                    raise OSError("reread failed")
            return open_remote(remote_path, mode)
        password.sftp.open = fail_second_read
        self.assertEqual(run(password, _BytesClient(password.sftp.storage, reject_key=True)), "ssh_key_install_failed")
        self.assertEqual(password.sftp.storage[path], original)

    def test_worker_rolls_back_after_key_login_rejection(self):
        module = _load_ssh_helper_module()
        path = "/data/home/RPM/.ssh/authorized_keys"
        original = b"ssh-rsa original\n"
        password = _BytesClient({path: original})
        verify = _BytesClient(password.sftp.storage, reject_key=True)
        clients = iter((password, verify))
        fake_paramiko = SimpleNamespace(
            SSHClient=lambda: next(clients), AutoAddPolicy=lambda: None, Ed25519Key=_FakeEd25519Key
        )
        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            error = module._ssh_install_and_verify_key_worker(
                "host", "RPM", "password", "private", "ssh-ed25519 managed savant_energy_ha", "token"
            )
        self.assertEqual(error, "ssh_key_verify_failed")
        self.assertEqual(password.sftp.storage[path], original)
        self.assertEqual(password.sftp.rename_calls, 0)

    def test_async_bootstrap_rejects_unusable_installed_key(self):
        module = _load_ssh_helper_module()

        with mock.patch.object(module, "generate_ed25519_keypair", return_value=("private", "public")):
            with mock.patch.object(
                module,
                "_ssh_bootstrap_worker",
                return_value=module.SSHBootstrapResult(token="password-token"),
            ):
                with mock.patch.object(
                    module,
                    "_ssh_fetch_influx_bundle_with_key_worker",
                    return_value=(None, None),
                ):
                    result = asyncio.run(
                        module.async_ssh_bootstrap(
                            _FakeHass(), "example.com", "user", "pass"
                        )
                    )

        self.assertEqual(result, (None, None, None, "ssh_key_verify_failed"))

    def test_async_prepare_bootstrap_reads_before_any_install(self):
        module = _load_ssh_helper_module()
        with mock.patch.object(module, "generate_ed25519_keypair", return_value=("private", "public")), mock.patch.object(
            module,
            "_ssh_read_influx_bundle_with_password_worker",
            return_value=("token", None, None),
        ) as reader, mock.patch.object(module, "_ssh_install_and_verify_key_worker") as installer:
            result = asyncio.run(
                module.async_ssh_prepare_bootstrap(_FakeHass(), "example.com", "user", "pass")
            )

        self.assertEqual(result, ("private", "public", "token", None, None))
        reader.assert_called_once_with("example.com", "user", "pass")
        installer.assert_not_called()

    def test_key_verification_failure_rolls_back_only_new_authorized_key(self):
        module = _load_ssh_helper_module()
        auth_path = "/data/home/RPM/.ssh/authorized_keys"
        public_key = "ssh-ed25519 new-key savant_energy_ha"
        storage = {auth_path: b"ssh-ed25519 existing-key existing\n"}
        clients = iter((_BytesClient(storage), _BytesClient(storage, reject_key=True)))
        fake_paramiko = SimpleNamespace(
            SSHClient=lambda: next(clients),
            AutoAddPolicy=lambda: None,
            Ed25519Key=_FakeEd25519Key,
        )

        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            result = module._ssh_install_and_verify_key_worker(
                "example.com", "user", "pass", "private", public_key, "token"
            )

        self.assertEqual(result, "ssh_key_verify_failed")
        self.assertEqual(storage[auth_path], b"ssh-ed25519 existing-key existing\n")


if __name__ == "__main__":
    unittest.main()
