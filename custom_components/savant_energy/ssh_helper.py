"""SSH utilities for Savant Energy: key generation and token fetching."""

from __future__ import annotations

import json
import logging
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
_AUTH_KEYS_PATH = "/data/RPM/.ssh/authorized_keys"


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
    text = stdout.read().decode("utf-8", errors="ignore").strip()
    if text:
        return text
    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if err:
        _LOGGER.debug("SSH read from %s returned no text: %s", path, err)
    return ""


def _resolve_remote_influx_read_token(client) -> str:
    for path in (_TOKEN_PATH, _ALT_TOKEN_PATH):
        token = _read_remote_text(client, path)
        if token:
            return token

    stdin, stdout, stderr = client.exec_command(
        f"find / -type f -path {shlex.quote('*/InfluxDB2/.influxReadtoken')} "
        "-print 2>/dev/null | head -n 1"
    )
    candidate = stdout.read().decode("utf-8", errors="ignore").strip().splitlines()
    if candidate:
        return _read_remote_text(client, candidate[0])

    err = stderr.read().decode("utf-8", errors="ignore").strip()
    if err:
        _LOGGER.debug("SSH find for Influx token path returned no match; stderr: %s", err)
    return ""


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
        return None, None, "ssh_unavailable"

    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, password=password, timeout=10)

        # Ensure .ssh dir exists and has correct perms.
        _, stdout, _ = client.exec_command("mkdir -p /data/RPM/.ssh && chmod 700 /data/RPM/.ssh")
        stdout.channel.recv_exit_status()

        # Append public key idempotently using a Python one-liner to avoid shell quoting issues.
        python_cmd = f"""python3 << 'PYEOF'
key_line = {repr(public_key_line)}
auth_path = {repr(_AUTH_KEYS_PATH)}
try:
    with open(auth_path, 'r') as f:
        content = f.read()
    if key_line not in content:
        with open(auth_path, 'a') as f:
            f.write(key_line + '\\n')
        import os
        os.chmod(auth_path, 0o600)
except Exception:
    pass
PYEOF
"""
        _, stdout, _ = client.exec_command(python_cmd)
        stdout.channel.recv_exit_status()

        token = _resolve_remote_influx_read_token(client)
        if not token:
            return None, None, "ssh_token_empty"

        metadata = _build_influx_host_metadata(
            _read_remote_text(client, _SETUP_PATH),
            _read_remote_text(client, _TOKEN_BUNDLE_PATH),
        )
        if metadata:
            _LOGGER.debug(
                "SSH bootstrap metadata from %s: org_id=%s org_name=%s bucket=%s auth_org_id=%s",
                host,
                metadata.org_id or "<unset>",
                metadata.org_name or "<unset>",
                metadata.bucket_name or "<unset>",
                metadata.auth_org_id or "<unset>",
            )
        return token, metadata, None

    except Exception as exc:
        _LOGGER.warning("SSH bootstrap to %s failed: %s", host, exc)
        return None, None, "ssh_failed"
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

        token = _resolve_remote_influx_read_token(client)
        if not token:
            return None, None

        metadata = _build_influx_host_metadata(
            _read_remote_text(client, _SETUP_PATH),
            _read_remote_text(client, _TOKEN_BUNDLE_PATH),
        )
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
        _LOGGER.warning("SSH key-based token fetch from %s failed: %s", host, exc)
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
    return private_pem, token, metadata, None


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
