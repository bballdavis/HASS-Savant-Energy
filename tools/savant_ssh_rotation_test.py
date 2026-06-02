#!/usr/bin/env python3
"""Interactive Savant SSH key rotation test utility.

Workflow:
1) Prompt for SSH password and connect with password auth.
2) Remove prior test keys by prefix from authorized_keys.
3) Install a new test key with deterministic marker prefix.
4) Verify key auth works before restart.
5) Pause for host restart.
6) Verify key auth still works after restart.

This utility is intentionally standalone so you can iterate outside Home Assistant.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import io
import socket
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import UTC, datetime

try:
    import paramiko
except ImportError:
    print("Error: paramiko is required. Install with: pip install paramiko", file=sys.stderr)
    sys.exit(1)


DEFAULT_SSH_USER = "RPM"
DEFAULT_AUTH_KEYS = "/data/RPM/.ssh/authorized_keys"
DEFAULT_TOKEN_PATH = (
    "/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia"
    "/statusfiles/InfluxDB2/.influxReadtoken"
)
DEFAULT_KEY_MARKER_PREFIX = "savant_energy_rotation_test"


@dataclass
class KeyMaterial:
    private_key_pem: str
    public_key_line: str
    marker: str


def _mask_secret(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def generate_rsa_keypair(marker: str) -> KeyMaterial:
    """Generate an RSA key pair and return OpenSSH public + PEM private."""
    key = paramiko.RSAKey.generate(bits=3072)
    private_buf = io.StringIO()
    key.write_private_key(private_buf)
    private_key_pem = private_buf.getvalue()
    public_b64 = key.get_base64()
    public_key_line = f"ssh-rsa {public_b64} {marker}"
    return KeyMaterial(private_key_pem=private_key_pem, public_key_line=public_key_line, marker=marker)


def _connect_password(host: str, username: str, password: str, timeout: int) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=username, password=password, timeout=timeout)
    return client


def _connect_key(host: str, username: str, private_key_pem: str, timeout: int) -> paramiko.SSHClient:
    pkey = paramiko.RSAKey.from_private_key(io.StringIO(private_key_pem))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=username, pkey=pkey, timeout=timeout)
    return client


def _exec_or_raise(client: paramiko.SSHClient, command: str) -> str:
    stdin, stdout, stderr = client.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    if exit_code != 0:
        raise RuntimeError(f"Remote command failed (exit {exit_code}): {err.strip() or out.strip()}")
    return out


def install_test_key(
    client: paramiko.SSHClient,
    auth_keys_path: str,
    marker_prefix: str,
    public_key_line: str,
) -> tuple[int, int]:
    """Install test key after pruning prior test keys matching marker_prefix.

    Returns (removed_count, total_count).
    """
    key_b64 = public_key_line.split()[1]

    py_script = textwrap.dedent(
        """
        import os

        auth_path = {auth_path!r}
        marker_prefix = {marker_prefix!r}
        key_line = {key_line!r}
        key_b64 = {key_b64!r}

        os.makedirs(os.path.dirname(auth_path), exist_ok=True)
        if not os.path.exists(auth_path):
            open(auth_path, "a", encoding="utf-8").close()

        with open(auth_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.rstrip("\\n") for line in f]

        filtered = []
        removed_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if marker_prefix in stripped:
                removed_count += 1
                continue
            if key_b64 in stripped:
                removed_count += 1
                continue
            filtered.append(stripped)

        filtered.append(key_line)

        with open(auth_path, "w", encoding="utf-8") as f:
            for line in filtered:
                f.write(line + "\\n")

        os.chmod(os.path.dirname(auth_path), 0o700)
        os.chmod(auth_path, 0o600)

        print(f"removed={{removed_count}}")
        print(f"total={{len(filtered)}}")
        """
    ).format(
        auth_path=auth_keys_path,
        marker_prefix=marker_prefix,
        key_line=public_key_line,
        key_b64=key_b64,
    )

    command = f"python3 - << 'PYEOF'\n{py_script}\nPYEOF"
    output = _exec_or_raise(client, command)

    removed_count = 0
    total_count = 0
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith("removed="):
            removed_count = int(line.split("=", 1)[1])
        elif line.startswith("total="):
            total_count = int(line.split("=", 1)[1])

    return removed_count, total_count


def fetch_token_over_key(
    host: str,
    username: str,
    private_key_pem: str,
    token_path: str,
    timeout: int,
) -> str:
    client = None
    try:
        client = _connect_key(host, username, private_key_pem, timeout)
        token = _exec_or_raise(client, f"cat {token_path}").strip()
        if not token:
            raise RuntimeError("Token file was readable but empty")
        return token
    finally:
        if client:
            client.close()


def wait_for_ssh(host: str, port: int, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            time.sleep(2)
        finally:
            sock.close()
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Interactive Savant SSH key rotation test. "
            "Bootstraps a key, pauses for host restart, and validates key auth afterward."
        )
    )
    parser.add_argument("--host", required=True, help="Savant host IP or DNS")
    parser.add_argument("--user", default=DEFAULT_SSH_USER, help=f"SSH username (default: {DEFAULT_SSH_USER})")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--token-path", default=DEFAULT_TOKEN_PATH, help="Remote Influx token file path")
    parser.add_argument("--auth-keys-path", default=DEFAULT_AUTH_KEYS, help="Remote authorized_keys path")
    parser.add_argument(
        "--marker-prefix",
        default=DEFAULT_KEY_MARKER_PREFIX,
        help=(
            "Key marker prefix used for cleanup. "
            "All existing authorized_keys lines containing this prefix are removed before install."
        ),
    )
    parser.add_argument("--timeout", type=int, default=10, help="SSH operation timeout in seconds")
    parser.add_argument(
        "--wait-after-restart",
        type=int,
        default=300,
        help="Max seconds to wait for SSH port to return after restart (default: 300)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    marker = f"{args.marker_prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    print("=== Savant SSH Rotation Test ===")
    print(f"Host: {args.host}")
    print(f"User: {args.user}")
    print(f"Token path: {args.token_path}")
    print(f"Key marker prefix: {args.marker_prefix}")
    print(f"This run marker: {marker}")
    print()

    password = getpass.getpass(f"SSH password for {args.user}@{args.host}: ")
    if not password:
        print("Aborted: password is required for bootstrap")
        return 2

    keymat = generate_rsa_keypair(marker)
    print("Generated local test key pair")

    bootstrap_client = None
    try:
        print("Connecting with password auth to install/rotate test key...")
        bootstrap_client = _connect_password(args.host, args.user, password, args.timeout)
        removed, total = install_test_key(
            bootstrap_client,
            auth_keys_path=args.auth_keys_path,
            marker_prefix=args.marker_prefix,
            public_key_line=keymat.public_key_line,
        )
        print(f"Installed key marker: {keymat.marker}")
        print(f"Removed prior matching keys: {removed}")
        print(f"authorized_keys non-empty lines now: {total}")

        token_before = _exec_or_raise(bootstrap_client, f"cat {args.token_path}").strip()
        if not token_before:
            raise RuntimeError("Token path is readable but empty during bootstrap")
        print(f"Token read over password session: {_mask_secret(token_before)}")
    except Exception as exc:
        print(f"Bootstrap failed: {exc}")
        return 1
    finally:
        if bootstrap_client:
            bootstrap_client.close()

    try:
        print("Verifying key auth works before restart...")
        pre_token = fetch_token_over_key(
            host=args.host,
            username=args.user,
            private_key_pem=keymat.private_key_pem,
            token_path=args.token_path,
            timeout=args.timeout,
        )
        print(f"Pre-restart key auth succeeded, token: {_mask_secret(pre_token)}")
    except Exception as exc:
        print(f"Pre-restart key auth failed: {exc}")
        return 1

    print()
    print("Restart your Savant host now.")
    input("Press Enter only after the host has completed reboot... ")

    print(f"Waiting for SSH port {args.port} on {args.host} to return...")
    if not wait_for_ssh(args.host, args.port, args.wait_after_restart):
        print("Host did not return SSH within the configured wait window")
        return 1

    try:
        print("Verifying key auth works after restart...")
        post_token = fetch_token_over_key(
            host=args.host,
            username=args.user,
            private_key_pem=keymat.private_key_pem,
            token_path=args.token_path,
            timeout=args.timeout,
        )
        print(f"Post-restart key auth succeeded, token: {_mask_secret(post_token)}")
        if post_token != pre_token:
            print("Token changed across restart (rotation observed)")
        else:
            print("Token unchanged across restart")
    except Exception as exc:
        print(f"Post-restart key auth failed: {exc}")
        return 1

    print()
    print("SUCCESS: Key bootstrap and post-restart key auth validation completed")
    print(
        "Note: This script removes old test keys matching the marker prefix before adding a fresh one, "
        "preventing unbounded key buildup."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
