"""SSH utilities for Savant Energy: key generation and token fetching."""

from __future__ import annotations

import json
import logging
import posixpath
import shlex
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

_TOKEN_PATH = (
    "/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxReadtoken"
)
_ALT_TOKEN_PATH = (
    "/data/home/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxReadtoken"
)
_SETUP_PATH = (
    "/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxsetup"
)
_TOKEN_BUNDLE_PATH = (
    "/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxtoken"
)


def _safe_ssh_error(exc: Exception, *secrets: str) -> str:
    text = str(exc)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    for marker in ("password", "token", "private", "authorization"):
        text = text.replace(marker, "[redacted]")
    return text[:240]


@dataclass(slots=True)
class InfluxTokenResolution:
    token: str
    token_path: str | None = None
    layout: str | None = None
    rpm_home: str | None = None
    authorized_keys_path: str | None = None


class SSHBootstrapStageError(RuntimeError):
    """A classified failure in one remote bootstrap stage."""

    def __init__(self, stage: str, error_key: str) -> None:
        super().__init__(stage)
        self.stage = stage
        self.error_key = error_key


@dataclass(slots=True)
class SSHBootstrapResult:
    """Structured bootstrap outcome; iteration preserves the old 3-tuple."""

    token: str | None = None
    metadata: InfluxHostMetadata | None = None
    error_key: str | None = None
    stage: str = "complete"

    def __iter__(self):
        yield self.token
        yield self.metadata
        yield self.error_key


@dataclass(slots=True)
class InfluxHostMetadata:
    """Metadata found on the Savant host that can identify the Influx org."""

    org_id: str | None = None
    org_name: str | None = None
    bucket_name: str | None = None
    auth_org_id: str | None = None
    source_files: tuple[str, ...] = ()


def _read_remote_text(client, path: str) -> str:
    stdin, stdout, stderr = client.exec_command(f"cat {shlex.quote(path)}")
    status = stdout.channel.recv_exit_status()
    text = stdout.read().decode("utf-8", errors="ignore").strip()
    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if status != 0:
        _LOGGER.debug("SSH read stage failed for %s with exit status %s", path, status)
        return ""
    if text:
        return text
    if err:
        _LOGGER.debug("SSH read from %s returned no text", path)
    return ""


def _resolve_remote_influx_read_token(client) -> str:
    return _resolve_remote_influx_read_token_details(client).token


def _rpm_home_from_token_path(token_path: str) -> str | None:
    rpm_home, separator, _suffix = token_path.partition("/GNUstep/")
    if separator and rpm_home.endswith("/RPM") and rpm_home.startswith("/"):
        return rpm_home
    return None


def _resolve_remote_influx_read_token_details(client) -> InfluxTokenResolution:
    for path in (_TOKEN_PATH, _ALT_TOKEN_PATH):
        token = _read_remote_text(client, path)
        if token:
            layout = _rpm_home_from_token_path(path)
            return InfluxTokenResolution(token, path, layout, layout, f"{layout}/.ssh/authorized_keys")

    stdin, stdout, stderr = client.exec_command(
        f"find / -type f -path {shlex.quote('*/InfluxDB2/.influxReadtoken')} "
        "-print 2>/dev/null | head -n 1"
    )
    status = stdout.channel.recv_exit_status()
    candidate = stdout.read().decode("utf-8", errors="ignore").strip().splitlines()
    if candidate:
        token_path = candidate[0]
        token = _read_remote_text(client, token_path)
        rpm_home = _rpm_home_from_token_path(token_path)
        return InfluxTokenResolution(
            token,
            token_path,
            rpm_home,
            rpm_home,
            f"{rpm_home}/.ssh/authorized_keys" if rpm_home else None,
        )

    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if status != 0 or err:
        _LOGGER.debug("SSH find for Influx token path returned no match (exit status %s)", status)
    return InfluxTokenResolution("")


def _metadata_paths(resolution: InfluxTokenResolution) -> tuple[str, str]:
    root = (
        posixpath.dirname(resolution.token_path)
        if resolution.token_path
        else posixpath.dirname(_TOKEN_PATH)
    )
    return f"{root}/.influxsetup", f"{root}/.influxtoken"


def _safe_load_json(text: str) -> dict:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _build_influx_host_metadata(setup_text: str, token_text: str) -> InfluxHostMetadata | None:
    setup_data = _safe_load_json(setup_text)
    token_data = _safe_load_json(token_text)
    if not setup_data and not token_data:
        return None

    org_block = token_data.get("org") if isinstance(token_data.get("org"), dict) else {}
    bucket_block = token_data.get("bucket") if isinstance(token_data.get("bucket"), dict) else {}
    auth_block = token_data.get("auth") if isinstance(token_data.get("auth"), dict) else {}

    org_id = (
        str(org_block.get("id", "")).strip()
        or str(auth_block.get("orgID", "")).strip()
        or str(bucket_block.get("orgID", "")).strip()
        or str(setup_data.get("orgID", "")).strip()
    )
    org_name = str(org_block.get("name", "")).strip() or str(setup_data.get("org", "")).strip()
    bucket_name = str(bucket_block.get("name", "")).strip() or str(setup_data.get("bucket", "")).strip()
    auth_org_id = str(auth_block.get("orgID", "")).strip()

    if not any((org_id, org_name, bucket_name, auth_org_id)):
        return None

    source_files = tuple(path for path in (_SETUP_PATH, _TOKEN_BUNDLE_PATH) if path)
    return InfluxHostMetadata(
        org_id=org_id or None,
        org_name=org_name or None,
        bucket_name=bucket_name or None,
        auth_org_id=auth_org_id or None,
        source_files=source_files,
    )


def generate_ed25519_keypair() -> tuple[str, str]:
    """Return (private_key_pem, public_key_openssh) for a new Ed25519 key pair."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )

    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
    ).decode()
    public_openssh = (
        private_key.public_key()
        .public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH)
        .decode()
        .strip()
        + " savant_energy_ha"
    )
    return private_pem, public_openssh


def _ssh_bootstrap_worker(
    host: str, username: str, password: str, public_key_line: str
) -> tuple[str | None, InfluxHostMetadata | None, str | None]:
    """Blocking: install public key via password auth, then read the influx token."""
    try:
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception as exc:
        _LOGGER.warning("paramiko unavailable: %s", exc)
        return SSHBootstrapResult(error_key="ssh_unavailable", stage="dependency")

    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, password=password, timeout=10)

        # Ensure .ssh dir exists and has correct perms.
        def checked(command: str, stage: str, error_key: str) -> tuple[str, str]:
            _stdin, out, err = client.exec_command(command)
            status = out.channel.recv_exit_status()
            out_text = out.read().decode("utf-8", errors="ignore").strip()
            err_text = err.read().decode("utf-8", errors="ignore").strip()
            if status != 0:
                _LOGGER.warning("SSH bootstrap stage %s failed with exit status %s", stage, status)
                raise SSHBootstrapStageError(stage, error_key)
            return out_text, err_text

        resolution = _resolve_remote_influx_read_token_details(client)
        rpm_home = resolution.rpm_home or "/data/RPM"
        auth_keys_path = resolution.authorized_keys_path or f"{rpm_home}/.ssh/authorized_keys"
        checked(
            f"mkdir -p {shlex.quote(rpm_home + '/.ssh')} && chmod 700 {shlex.quote(rpm_home + '/.ssh')}",
            "ssh_dir",
            "ssh_key_install_failed",
        )

        # Append public key idempotently using a Python one-liner to avoid shell quoting issues.
        python_cmd = f"""python3 << 'PYEOF'
key_line = {repr(public_key_line)}
auth_path = {repr(auth_keys_path)}
try:
    try:
        with open(auth_path, 'r') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    if key_line not in lines:
        with open(auth_path, 'a') as f:
            f.write(key_line + '\\n')
        import os
        os.chmod(auth_path, 0o600)
    with open(auth_path, 'r') as f:
        if key_line not in f.read().splitlines():
            raise RuntimeError('public key verification failed')
except Exception:
    raise SystemExit(1)
PYEOF
"""
        checked(python_cmd, "authorized_keys", "ssh_key_install_failed")

        token = resolution.token or _resolve_remote_influx_read_token(client)
        if not token:
            return SSHBootstrapResult(error_key="ssh_token_empty", stage="token_read")

        setup_path, bundle_path = _metadata_paths(resolution)
        metadata = _build_influx_host_metadata(_read_remote_text(client, setup_path), _read_remote_text(client, bundle_path))
        if metadata:
            metadata.source_files = (setup_path, bundle_path)
        if metadata:
            _LOGGER.debug(
                "SSH bootstrap metadata from %s: org_id=%s org_name=%s bucket=%s auth_org_id=%s",
                host,
                metadata.org_id or "<unset>",
                metadata.org_name or "<unset>",
                metadata.bucket_name or "<unset>",
                metadata.auth_org_id or "<unset>",
            )
        return SSHBootstrapResult(token=token, metadata=metadata)

    except SSHBootstrapStageError as exc:
        _LOGGER.warning("SSH bootstrap stage %s failed for %s", exc.stage, host)
        return SSHBootstrapResult(error_key=exc.error_key, stage=exc.stage)
    except Exception as exc:
        _LOGGER.warning("SSH bootstrap to %s failed: %s", host, _safe_ssh_error(exc, password, public_key_line))
        return SSHBootstrapResult(error_key="ssh_failed", stage="bootstrap")
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def _ssh_fetch_influx_bundle_with_key_worker(
    host: str, username: str, private_key_pem: str
) -> tuple[str | None, InfluxHostMetadata | None]:
    """Blocking: connect with Ed25519 key and read the influx token bundle."""
    try:
        import io
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception as exc:
        _LOGGER.warning("paramiko unavailable: %s", exc)
        return None, None

    client = None
    try:
        pkey = paramiko.Ed25519Key(file_obj=io.StringIO(private_key_pem))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, pkey=pkey, timeout=10)

        resolution = _resolve_remote_influx_read_token_details(client)
        token = resolution.token or _resolve_remote_influx_read_token(client)
        if not token:
            return None, None

        setup_path, bundle_path = _metadata_paths(resolution)
        metadata = _build_influx_host_metadata(_read_remote_text(client, setup_path), _read_remote_text(client, bundle_path))
        if metadata:
            metadata.source_files = (setup_path, bundle_path)
        if metadata:
            _LOGGER.debug(
                "SSH key metadata from %s: org_id=%s org_name=%s bucket=%s auth_org_id=%s",
                host,
                metadata.org_id or "<unset>",
                metadata.org_name or "<unset>",
                metadata.bucket_name or "<unset>",
                metadata.auth_org_id or "<unset>",
            )
        return token, metadata

    except Exception as exc:
        _LOGGER.warning("SSH key-based token fetch from %s failed: %s", host, _safe_ssh_error(exc, private_key_pem))
        return None, None
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


async def async_ssh_bootstrap(
    hass, host: str, username: str, password: str
) -> tuple[str | None, str | None, InfluxHostMetadata | None, str | None]:
    """Generate a key pair, install the public key, and fetch the influx token."""
    try:
        private_pem, public_openssh = generate_ed25519_keypair()
    except Exception as exc:
        _LOGGER.error("Failed to generate Ed25519 key pair: %s", exc)
        return None, None, None, "keygen_failed"

    token, metadata, error_key = await hass.async_add_executor_job(
        _ssh_bootstrap_worker, host, username, password, public_openssh
    )
    if error_key:
        return None, None, None, error_key
    verified_token, verified_metadata = await hass.async_add_executor_job(
        _ssh_fetch_influx_bundle_with_key_worker, host, username, private_pem
    )
    if not verified_token:
        _LOGGER.warning("SSH key verification failed for %s after key installation", host)
        return None, None, None, "ssh_key_verify_failed"
    return private_pem, verified_token, verified_metadata or metadata, None


async def async_ssh_fetch_token_with_key(
    hass, host: str, username: str, private_key_pem: str
) -> str | None:
    """Async wrapper: connect with Ed25519 private key and return the influx token."""
    token, _metadata = await hass.async_add_executor_job(
        _ssh_fetch_influx_bundle_with_key_worker, host, username, private_key_pem
    )
    return token


async def async_ssh_fetch_influx_bundle_with_key(
    hass, host: str, username: str, private_key_pem: str
) -> tuple[str | None, InfluxHostMetadata | None]:
    """Async wrapper: return both the token and host metadata over SSH."""
    return await hass.async_add_executor_job(
        _ssh_fetch_influx_bundle_with_key_worker, host, username, private_key_pem
    )
