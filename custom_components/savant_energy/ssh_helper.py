"""SSH utilities for Savant Energy: key generation and token fetching."""

import logging

_LOGGER = logging.getLogger(__name__)

_TOKEN_PATH = (
    "/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxReadtoken"
)
_AUTH_KEYS_PATH = "/data/RPM/.ssh/authorized_keys"


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
) -> tuple[str | None, str | None]:
    """Blocking: install public key via password auth, then read the influx token.

    Returns (token, None) on success or (None, error_key) on failure.
    Installs the key idempotently — safe to call multiple times.
    """
    try:
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception as exc:
        _LOGGER.warning("paramiko unavailable: %s", exc)
        return None, "ssh_unavailable"

    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, password=password, timeout=10)

        # Ensure .ssh dir exists and has correct perms
        client.exec_command("mkdir -p /data/RPM/.ssh && chmod 700 /data/RPM/.ssh")

        # Append public key only if not already present
        check_cmd = f"grep -qF '{public_key_line}' {_AUTH_KEYS_PATH} 2>/dev/null"
        _, stdout, _ = client.exec_command(check_cmd)
        stdout.channel.recv_exit_status()  # wait

        append_cmd = (
            f"grep -qF '{public_key_line}' {_AUTH_KEYS_PATH} 2>/dev/null || "
            f"echo '{public_key_line}' >> {_AUTH_KEYS_PATH} && chmod 600 {_AUTH_KEYS_PATH}"
        )
        _, _, stderr = client.exec_command(append_cmd)
        stderr.channel.recv_exit_status()

        # Read the influx token
        _, stdout, _ = client.exec_command(f"cat {_TOKEN_PATH}")
        token = stdout.read().decode("utf-8", errors="ignore").strip()
        if not token:
            return None, "ssh_token_empty"
        return token, None

    except Exception as exc:
        _LOGGER.warning("SSH bootstrap to %s failed: %s", host, exc)
        return None, "ssh_failed"
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


def _ssh_fetch_token_with_key_worker(
    host: str, username: str, private_key_pem: str
) -> str | None:
    """Blocking: connect with Ed25519 key and read the influx read token."""
    try:
        import io
        import paramiko  # type: ignore  # noqa: PLC0415
    except Exception as exc:
        _LOGGER.warning("paramiko unavailable: %s", exc)
        return None

    client = None
    try:
        pkey = paramiko.Ed25519Key(file_obj=io.StringIO(private_key_pem))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, username=username, pkey=pkey, timeout=10)
        _, stdout, _ = client.exec_command(f"cat {_TOKEN_PATH}")
        token = stdout.read().decode("utf-8", errors="ignore").strip()
        return token or None
    except Exception as exc:
        _LOGGER.warning("SSH key-based token fetch from %s failed: %s", host, exc)
        return None
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


async def async_ssh_bootstrap(
    hass, host: str, username: str, password: str
) -> tuple[str | None, str | None, str | None]:
    """Generate a key pair, install the public key, and fetch the influx token.

    Returns (private_key_pem, token, error_key).
    On success: private_key_pem and token are set, error_key is None.
    On failure: private_key_pem and token are None, error_key is set.
    """
    try:
        private_pem, public_openssh = generate_ed25519_keypair()
    except Exception as exc:
        _LOGGER.error("Failed to generate Ed25519 key pair: %s", exc)
        return None, None, "keygen_failed"

    token, error_key = await hass.async_add_executor_job(
        _ssh_bootstrap_worker, host, username, password, public_openssh
    )
    if error_key:
        return None, None, error_key
    return private_pem, token, None


async def async_ssh_fetch_token_with_key(
    hass, host: str, username: str, private_key_pem: str
) -> str | None:
    """Async wrapper: connect with Ed25519 private key and return the influx token."""
    return await hass.async_add_executor_job(
        _ssh_fetch_token_with_key_worker, host, username, private_key_pem
    )
