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
            "find / -type f -path '*/InfluxDB2/.influxReadtoken' -print 2>/dev/null | head -n 1",
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
            "find / -type f -path '*/InfluxDB2/.influxReadtoken' -print 2>/dev/null | head -n 1",
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

        with mock.patch.dict("sys.modules", {"paramiko": fake_paramiko}):
            with mock.patch.object(module, "_resolve_remote_influx_read_token", return_value="key-token") as resolver:
                with mock.patch.object(module, "_read_remote_text", return_value=""):
                    token, metadata = module._ssh_fetch_influx_bundle_with_key_worker(
                        "example.com", "user", "key"
                    )

        self.assertEqual(token, "key-token")
        self.assertIsNone(metadata)
        resolver.assert_called_once_with(fake_client)

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


if __name__ == "__main__":
    unittest.main()
