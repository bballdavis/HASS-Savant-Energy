"""SSH utilities for Savant Energy: key generation and token fetching."""

from __future__ import annotations

import json
import logging
import posixpath
import re
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
_LOAD_IDENTIFIERS_FILENAME = "loadIdentifiers.json"
_RPM_HOME = "/data/RPM"
_AUTH_KEYS_PATH = f"{_RPM_HOME}/.ssh/authorized_keys"


class _SSHOperationError(RuntimeError):
    def __init__(self, operation: str, exit_status: int) -> None:
        super().__init__(operation)
        self.operation = operation
        self.exit_status = exit_status


class _SSHInstallError(OSError):
    def __init__(self, added: bool, cause: OSError) -> None:
        super().__init__(str(cause))
        self.added = added


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


@dataclass(slots=True)
class InfluxTokenCandidate:
    """A token candidate with only its adjacent, non-secret metadata."""

    resolution: InfluxTokenResolution
    metadata: InfluxHostMetadata | None = None

    @property
    def token(self) -> str:
        return self.resolution.token


@dataclass(slots=True)
class _AuthorizedKeyAppend:
    path: str
    original: bytes
    existed: bool
    suffix: bytes


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
    load_identifiers: tuple[dict[str, str], ...] = ()


def _read_remote_text(client, path: str, *, required: bool = False) -> str:
    _, stdout, stderr = client.exec_command(f"cat {shlex.quote(path)}")
    status = stdout.channel.recv_exit_status()
    text = stdout.read().decode("utf-8", errors="ignore").strip()
    _ = stderr.read().decode("utf-8", errors="ignore").strip()
    if status != 0:
        if required:
            raise _SSHOperationError("token_read", status)
        return ""
    return text


def _resolve_remote_influx_read_token(client) -> str:
    # Compatibility fast path for callers that only need the established
    # token; the detailed resolver performs the bounded full scan.
    for path in (_TOKEN_PATH, _ALT_TOKEN_PATH):
        token = _read_remote_text(client, path)
        if token:
            return token
    _, stdout, _stderr = client.exec_command(
        f"find / -type f -path {shlex.quote('*/InfluxDB2/.influxReadtoken')} "
        "-print 2>/dev/null | sort -u | head -n 8"
    )
    stdout.channel.recv_exit_status()
    found = stdout.read().decode("utf-8", errors="ignore").splitlines()
    for path in sorted({line.strip() for line in found if line.strip()}):
        token = _read_remote_text(client, path)
        if token:
            return token
    return ""


def _resolve_remote_influx_read_token_candidates(client) -> list[InfluxTokenResolution]:
    """Return bounded, deterministic token candidates without exposing values."""
    known: dict[str, InfluxTokenResolution] = {}
    for path in (_TOKEN_PATH, _ALT_TOKEN_PATH):
        token = _read_remote_text(client, path)
        if token:
            home = _rpm_home_from_token_path(path)
            known[path] = InfluxTokenResolution(token, path, home, home, f"{home}/.ssh/authorized_keys")
    _, stdout, stderr = client.exec_command(
        f"find / -type f -path {shlex.quote('*/InfluxDB2/.influxReadtoken')} "
        "-print 2>/dev/null | sort -u | head -n 8"
    )
    status = stdout.channel.recv_exit_status()
    found = stdout.read().decode("utf-8", errors="ignore").splitlines()
    paths = list(known)
    for path in sorted({line.strip() for line in found if line.strip()}):
        if path not in paths:
            paths.append(path)
    candidates = list(known.values())
    for path in paths[len(known):]:
        token = _read_remote_text(client, path)
        if token:
            home = _rpm_home_from_token_path(path)
            candidates.append(InfluxTokenResolution(token, path, home, home, f"{home}/.ssh/authorized_keys" if home else None))
    if status != 0:
        _LOGGER.debug("SSH find for Influx token paths returned exit status %s", status)
    _ = stderr.read().decode("utf-8", errors="ignore")
    # The same token can be exposed by more than one path. Keep provenance
    # where it differs, but never probe an exact duplicate twice.
    deduped: list[InfluxTokenResolution] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.token not in seen:
            seen.add(candidate.token)
            deduped.append(candidate)
    return deduped


def _rpm_home_from_token_path(token_path: str) -> str | None:
    rpm_home, separator, _suffix = token_path.partition("/GNUstep/")
    if separator and rpm_home.endswith("/RPM") and rpm_home.startswith("/"):
        return rpm_home
    return None


def _resolve_remote_influx_read_token_details(client) -> InfluxTokenResolution:
    candidates = _resolve_remote_influx_read_token_candidates(client)
    return candidates[0] if candidates else InfluxTokenResolution("")


def _read_influx_token_candidates(client) -> list[InfluxTokenCandidate]:
    """Read each candidate's adjacent host metadata without choosing a token."""
    result: list[InfluxTokenCandidate] = []
    for resolution in _resolve_remote_influx_read_token_candidates(client):
        setup_path, bundle_path = _metadata_paths(resolution)
        metadata = _build_influx_host_metadata(
            _read_remote_text(client, setup_path), _read_remote_text(client, bundle_path)
        )
        statusfiles_root = posixpath.dirname(posixpath.dirname(setup_path))
        load_identifiers_path = posixpath.join(statusfiles_root, _LOAD_IDENTIFIERS_FILENAME)
        load_identifiers = _parse_load_identifiers(_read_remote_text(client, load_identifiers_path))
        if load_identifiers and metadata is None:
            metadata = InfluxHostMetadata()
        if metadata:
            metadata.source_files = (setup_path, bundle_path, load_identifiers_path)
            metadata.load_identifiers = load_identifiers
        result.append(InfluxTokenCandidate(resolution=resolution, metadata=metadata))
    return result


def _parse_load_identifiers(text: str) -> tuple[dict[str, str], ...]:
    """Parse Savant's stable UUID-to-relay inventory.

    Some hosts emit an empty optional ``channels`` value for a CT-only load
    (``"channels": ,``). Repair only that known malformed value; relay records
    remain ordinary JSON and are otherwise rejected on parse failure.
    """
    if not text.strip():
        return ()
    repaired = re.sub(r'("channels"\s*:\s*),', r"\1null,", text)
    try:
        raw_records = json.loads(repaired)
    except (TypeError, ValueError):
        _LOGGER.warning("Savant loadIdentifiers.json could not be parsed")
        return ()
    if not isinstance(raw_records, list):
        return ()

    records: list[dict[str, str]] = []
    seen_uuids: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            continue
        savant_uuid = str(raw.get("uuid") or "").strip()
        if not savant_uuid or savant_uuid in seen_uuids:
            continue
        state_name = str(raw.get("stateName") or "").strip()
        channel_match = re.search(r"CurrentDimmerLevel_(\d+)_", state_name)
        records.append(
            {
                "name": str(raw.get("name") or "").strip(),
                "savant_uuid": savant_uuid,
                "relay_uid": str(raw.get("bleAddress") or "").strip(),
                "state_channel": channel_match.group(1) if channel_match else "",
            }
        )
        seen_uuids.add(savant_uuid)
    return tuple(records)


def _metadata_paths(resolution: InfluxTokenResolution) -> tuple[str, str]:
    root = (
        posixpath.dirname(resolution.token_path)
        if resolution.token_path
        else posixpath.dirname(_TOKEN_PATH)
    )
    return f"{root}/.influxsetup", f"{root}/.influxtoken"


def _remote_command_output(client, command: str, operation: str) -> str:
    _, stdout, stderr = client.exec_command(command)
    status = stdout.channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="ignore").strip()
    _ = stderr.read().decode("utf-8", errors="ignore").strip()
    if status != 0:
        _LOGGER.warning("SSH operation %s failed with exit status %s", operation, status)
        raise _SSHOperationError(operation, status)
    return output


def _resolve_authorized_keys_path(client, username: str) -> str:
    shell_home = _remote_command_output(client, "printf '%s' \"$HOME\"", "home_resolution")
    if not shell_home.startswith("/"):
        passwd_line = _remote_command_output(
            client,
            f"getent passwd {shlex.quote(username)}",
            "home_resolution",
        )
        fields = passwd_line.split(":")
        shell_home = fields[5] if len(fields) >= 6 else ""
    if not shell_home.startswith("/"):
        raise _SSHOperationError("home_resolution", 1)
    return f"{shell_home.rstrip('/')}/.ssh/authorized_keys"


def _as_bytes(value) -> bytes:
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def _install_authorized_key(client, username: str, public_key_line: str) -> tuple[str, bool]:
    auth_path = _resolve_authorized_keys_path(client, username)
    auth_dir = posixpath.dirname(auth_path)
    _remote_command_output(
        client,
        f"mkdir -p {shlex.quote(auth_dir)} && chmod 700 {shlex.quote(auth_dir)}",
        "ssh_directory",
    )
    sftp = client.open_sftp()
    added = False
    append_state: _AuthorizedKeyAppend | None = None
    try:
        try:
            with sftp.open(auth_path, "rb") as remote_file:
                content = remote_file.read()
        except OSError:
            content = b""
            existed = False
        else:
            existed = True
        original_content = _as_bytes(content)
        key_bytes = public_key_line.encode("utf-8")
        if key_bytes in original_content.splitlines():
            try:
                sftp.chmod(auth_path, 0o600)
            except OSError as exc:
                raise _SSHInstallError(added, exc) from exc
            return auth_path, False
        try:
            setattr(client, "_savant_energy_authorized_key_append", None)
        except Exception:
            pass
        # Do not replace authorized_keys with an SFTP rename.  OpenSSH/SFTP
        # servers commonly reject rename-over-existing with a generic
        # ``Failure`` (the exact error seen on SavantOS).  Append only our
        # line, preserving every existing byte.
        suffix = (b"" if not original_content or original_content.endswith(b"\n") else b"\n") + key_bytes + b"\n"
        append_state = _AuthorizedKeyAppend(auth_path, original_content, existed, suffix)
        setattr(client, "_savant_energy_authorized_key_append", append_state)
        added = True
        with sftp.open(auth_path, "ab") as remote_file:
            remote_file.write(suffix)
        try:
            sftp.chmod(auth_path, 0o600)
        except OSError as exc:
            raise _SSHInstallError(added, exc) from exc
        with sftp.open(auth_path, "rb") as remote_file:
            verified_content = _as_bytes(remote_file.read())
        if key_bytes not in verified_content.splitlines():
            raise _SSHInstallError(added, OSError("authorized key verification failed"))
        return auth_path, True
    except _SSHInstallError:
        raise
    except OSError as exc:
        raise _SSHInstallError(added, exc) from exc
    finally:
        try:
            sftp.close()
        except OSError as exc:
            raise _SSHInstallError(added, exc) from exc


def _remove_authorized_key(client, append: _AuthorizedKeyAppend) -> bool:
    """Remove only an unchanged exact append; never overwrite concurrent edits."""
    sftp = client.open_sftp()
    try:
        with sftp.open(append.path, "rb") as remote_file:
            current = _as_bytes(remote_file.read())
        if not current.endswith(append.suffix):
            _LOGGER.warning("SSH authorized_keys rollback conflict; leaving concurrent content untouched")
            return False
        if append.existed:
            # Do not rewrite the prefix: a failed write after opening `wb`
            # would erase unrelated authorized keys. The suffix check above
            # makes an in-place truncate safe and concurrency-aware.
            with sftp.open(append.path, "r+b") as remote_file:
                remote_file.truncate(len(current) - len(append.suffix))
            sftp.chmod(append.path, 0o600)
        else:
            sftp.remove(append.path)
        return True
    finally:
        sftp.close()


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


def _ssh_read_influx_bundle_candidates_with_password_worker(
    host: str, username: str, password: str
) -> tuple[list[InfluxTokenCandidate], str | None]:
    """Read all candidate token bundles without modifying the remote host."""
    try:
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception:
        return [], "ssh_unavailable"
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        candidates = _read_influx_token_candidates(client)
        return (candidates, None) if candidates else ([], "ssh_token_empty")
    except _SSHOperationError as exc:
        return [], "ssh_token_empty" if exc.operation == "token_read" else "ssh_failed"
    except Exception as exc:
        _LOGGER.warning("SSH bundle read failed: %s", _safe_ssh_error(exc, password, host, username))
        return [], "ssh_failed"
    finally:
        if client:
            client.close()


def _ssh_read_influx_bundle_with_password_worker(
    host: str, username: str, password: str
) -> tuple[str | None, InfluxHostMetadata | None, str | None]:
    """Compatibility wrapper returning the first discovered candidate only."""
    candidates, error_key = _ssh_read_influx_bundle_candidates_with_password_worker(host, username, password)
    if error_key:
        return None, None, error_key
    candidate = candidates[0]
    return candidate.token, candidate.metadata, None


def _ssh_install_and_verify_key_worker(
    host: str,
    username: str,
    password: str,
    private_key_pem: str,
    public_key_line: str,
    expected_token: str,
) -> str | None:
    """Install after validation, verify key login, and roll back on failure."""
    try:
        import io
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception:
        return "ssh_unavailable"
    password_client = None
    verify_client = None
    auth_path = None
    added = False
    verified = False
    try:
        password_client = paramiko.SSHClient()
        password_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            password_client.connect(
                hostname=host,
                username=username,
                password=password,
                timeout=10,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:
            # Keep password/connect failures separate from failures after a
            # key was installed. Paramiko's AuthenticationException is
            # intentionally detected by class name to keep test doubles and
            # optional Paramiko imports compatible.
            if exc.__class__.__name__ == "AuthenticationException":
                return "ssh_password_auth_failed"
            return "ssh_connect_failed"
        auth_path, added = _install_authorized_key(password_client, username, public_key_line)

        pkey = paramiko.Ed25519Key(file_obj=io.StringIO(private_key_pem))
        verify_client = paramiko.SSHClient()
        verify_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        verify_client.connect(
            hostname=host,
            username=username,
            pkey=pkey,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        candidates = _resolve_remote_influx_read_token_candidates(verify_client)
        if expected_token not in {candidate.token for candidate in candidates}:
            return "ssh_token_mismatch"
        verified = True
        return None
    except _SSHInstallError as exc:
        added = exc.added
        return "ssh_key_install_failed"
    except _SSHOperationError as exc:
        return "ssh_key_install_failed" if exc.operation in {"home_resolution", "ssh_directory"} else "ssh_key_verify_failed"
    except Exception as exc:
        _LOGGER.warning("SSH key verification failed: %s", _safe_ssh_error(exc, password, private_key_pem, expected_token))
        return "ssh_key_verify_failed"
    finally:
        if verify_client:
            verify_client.close()
        append = getattr(password_client, "_savant_energy_authorized_key_append", None)
        if added and not verified and password_client and append:
            try:
                _remove_authorized_key(password_client, append)
            except Exception as exc:
                _LOGGER.error("Could not roll back managed SSH key: %s", _safe_ssh_error(exc, password))
        if password_client:
            password_client.close()


def _ssh_fetch_influx_candidates_with_key_worker(
    host: str, username: str, private_key_pem: str
) -> tuple[list[InfluxTokenCandidate], None]:
    """Blocking: connect with Ed25519 key and read every token bundle."""
    try:
        import io
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception as exc:
        _LOGGER.warning("paramiko unavailable: %s", exc)
        return [], None

    client = None
    try:
        pkey = paramiko.Ed25519Key(file_obj=io.StringIO(private_key_pem))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            username=username,
            pkey=pkey,
            timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )

        return _read_influx_token_candidates(client), None

    except Exception as exc:
        _LOGGER.warning("SSH key-based token fetch from %s failed: %s", host, _safe_ssh_error(exc, private_key_pem))
        return [], None
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def _ssh_fetch_influx_bundle_with_key_worker(
    host: str, username: str, private_key_pem: str
) -> tuple[str | None, InfluxHostMetadata | None]:
    """Compatibility wrapper returning the first discovered candidate only."""
    candidates, _error = _ssh_fetch_influx_candidates_with_key_worker(host, username, private_key_pem)
    if not candidates:
        # Legacy callers/tests use this compatibility API and only expect a
        # best-effort read, not selection or persistence.
        return None, None
    return candidates[0].token, candidates[0].metadata


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


async def async_ssh_prepare_bootstrap(
    hass, host: str, username: str, password: str
) -> tuple[str | None, str | None, str | None, InfluxHostMetadata | None, str | None]:
    """Generate key material and read the token without mutating the Savant host."""
    try:
        private_pem, public_openssh = generate_ed25519_keypair()
    except Exception as exc:
        _LOGGER.error("Failed to generate Ed25519 key pair: %s", exc)
        return None, None, None, None, "keygen_failed"
    token, metadata, error_key = await hass.async_add_executor_job(
        _ssh_read_influx_bundle_with_password_worker,
        host,
        username,
        password,
    )
    if error_key:
        return None, None, None, None, error_key
    return private_pem, public_openssh, token, metadata, None


async def async_ssh_prepare_bootstrap_candidates(
    hass, host: str, username: str, password: str
) -> tuple[str | None, str | None, list[InfluxTokenCandidate], str | None]:
    """Prepare a key and enumerate, but do not select or persist, SSH tokens."""
    try:
        private_pem, public_openssh = generate_ed25519_keypair()
    except Exception:
        return None, None, [], "keygen_failed"
    candidates, error_key = await hass.async_add_executor_job(
        _ssh_read_influx_bundle_candidates_with_password_worker, host, username, password
    )
    return private_pem, public_openssh, candidates, error_key


async def async_ssh_install_and_verify_key(
    hass,
    host: str,
    username: str,
    password: str,
    private_key_pem: str,
    public_key_line: str,
    expected_token: str,
) -> str | None:
    """Install and verify a prepared key after token/org validation succeeds."""
    return await hass.async_add_executor_job(
        _ssh_install_and_verify_key_worker,
        host,
        username,
        password,
        private_key_pem,
        public_key_line,
        expected_token,
    )


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


async def async_ssh_fetch_influx_candidates_with_key(
    hass, host: str, username: str, private_key_pem: str
) -> list[InfluxTokenCandidate]:
    """Return all key-authenticated candidates for end-to-end validation."""
    candidates, _error = await hass.async_add_executor_job(
        _ssh_fetch_influx_candidates_with_key_worker, host, username, private_key_pem
    )
    return candidates
