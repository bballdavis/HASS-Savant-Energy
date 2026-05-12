#!/usr/bin/env python3
"""
Test SignalR relay control via hub /localhub WebSocket.
Uses the exact command format captured from dump9.pcapng.
"""

import asyncio
import base64
import importlib.util
import json
import os
import socket
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HUB_PORT = 8000
DEFAULT_INFLUX_URL = "http://192.168.1.14:8086"
DEFAULT_INFLUX_ORG = "912133f25b21b958"
TARGET_NAME_FRAGMENT = "smoke"
import json as _json
JWT = _json.load(open(
    __file__.replace("test_signalr_relay.py", "jwt.token")
))["token"]

SIGNALR_SEP = b'\x1e'


def decode_jwt_payload(token: str) -> dict:
    """Decode the JWT payload without verifying the signature."""
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload + padding))


CLIENT_DEVICE_ID = decode_jwt_payload(JWT).get("uuid", "")


def load_env_file(file_path: str) -> dict[str, str]:
    """Load simple KEY=VALUE pairs from a local env file."""
    env_vars: dict[str, str] = {}
    path = Path(file_path)
    if not path.exists():
        return env_vars
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env_vars[key.strip()] = value.strip()
    return env_vars


def import_influx_client():
    """Import the integration's Influx client without importing HA."""
    module_path = Path(__file__).with_name("custom_components") / "savant_energy" / "influx_client.py"
    spec = importlib.util.spec_from_file_location("savant_influx_integration_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


async def resolve_live_targets(name_fragment: str) -> dict[str, str]:
    """Resolve hub host, PBC target, and circuit UID from the live Influx snapshot."""
    env_vars = load_env_file(Path(__file__).with_name(".savant-local.env"))
    influx_url = env_vars.get("SAVANT_INFLUX_URL", DEFAULT_INFLUX_URL)
    influx_org = env_vars.get("SAVANT_INFLUX_ORG") or DEFAULT_INFLUX_ORG
    token_path = Path(__file__).with_name(".savant-influx-read.token")
    influx_token = token_path.read_text().strip()
    if not influx_token:
        raise RuntimeError(f"Influx read token file is empty: {token_path}")

    influx_client = import_influx_client()
    result = await influx_client.fetch_influx_snapshot(influx_url, influx_token, influx_org)
    if not result.success or not result.data:
        raise RuntimeError(f"Influx snapshot failed: {result.error_type} {result.error_message}")

    snapshot = result.data
    circuits = snapshot.get("presentDemands") or []
    matches = [
        circuit for circuit in circuits
        if name_fragment.lower() in str(circuit.get("name", "")).lower()
    ]
    if not matches:
        raise RuntimeError(f"No live Influx circuit matched name fragment: {name_fragment!r}")
    if len(matches) > 1:
        raise RuntimeError(
            "Multiple live Influx circuits matched "
            f"{name_fragment!r}: {[circuit.get('name') for circuit in matches]}"
        )

    parsed = urlparse(influx_url)
    return {
        "hub_host": parsed.hostname or "192.168.1.14",
        "pbc_device_id": snapshot.get("pbc_device_id", ""),
        "uid": matches[0].get("uid", ""),
        "name": matches[0].get("name", ""),
        "channel": str(matches[0].get("channel", "")),
    }


def ws_frame(data: bytes) -> bytes:
    """Create a masked WebSocket text frame."""
    frame = bytearray()
    frame.append(0x81)  # FIN + text opcode
    length = len(data)
    mask_key = os.urandom(4)
    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack(">Q", length))
    frame.extend(mask_key)
    frame.extend(b ^ mask_key[i % 4] for i, b in enumerate(data))
    return bytes(frame)


def negotiate(host, port, jwt) -> str:
    """POST /localhub/negotiate to get a connection token."""
    import urllib.request
    req = urllib.request.Request(
        f"http://{host}:{port}/localhub/negotiate?negotiateVersion=1",
        method="POST",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    token = data["connectionToken"]
    print(f"  ✓ Negotiate OK — connectionToken: {token[:20]}...")
    return token


def ws_connect(host, port, jwt, connection_token):
    """Raw WebSocket upgrade to hub /localhub with auth."""
    key = base64.b64encode(os.urandom(16)).decode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((host, port))

    path = f"/localhub?id={connection_token}"
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Authorization: Bearer {jwt}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.send(request.encode())
    resp = sock.recv(4096).decode("ascii", errors="ignore")
    if "101" not in resp:
        raise RuntimeError(f"WebSocket upgrade failed:\n{resp[:300]}")
    print("  ✓ WebSocket upgrade: 101 Switching Protocols")
    return sock


def send_signalr(sock, message: dict):
    """Send a SignalR message (JSON + 0x1e)."""
    payload = json.dumps(message).encode("utf-8") + SIGNALR_SEP
    sock.send(ws_frame(payload))
    print(f"  → {json.dumps(message)[:120]}")


def drain_messages(sock, timeout: float = 0.75) -> list[dict]:
    """Drain SignalR text frames and print parsed JSON messages."""
    messages = []
    sock.settimeout(timeout)
    while True:
        try:
            resp = sock.recv(8192)
            if not resp:
                break
            txt = resp.decode("utf-8", errors="replace")
            for part in txt.split("\x1e"):
                part = part.strip().lstrip("\x81\x82\x7e\x7f").strip()
                if not part or not part.startswith("{"):
                    continue
                try:
                    parsed = json.loads(part)
                    messages.append(parsed)
                    print(f"  ← HUB MSG: {json.dumps(parsed)[:400]}")
                except Exception:
                    print(f"  ← RAW: {part[:200]}")
        except socket.timeout:
            break
    sock.settimeout(5)
    return messages


def build_receive_letter(target_id: str, command_type: str, address: str = "") -> dict:
    """Build a generic ReceiveLetter command."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    return {
        "type": 1,
        "target": "ReceiveLetter",
        "arguments": [
            target_id,
            {
                "deviceId": target_id,
                "regarding": "command",
                "contents": {
                    "address": address,
                    "command": {"commandType": command_type},
                },
                "timestamp": ts,
            },
        ],
    }


def build_set_load_state(pbc_id: str, uid: str, state: int, inv_id=None) -> dict:
    """Build a SET_LOAD_STATE SignalR invocation message."""
    request_id = str(uuid.uuid4()).upper()
    state_payload = {"states": {uid: state}, "requestId": request_id}
    b64 = base64.b64encode(json.dumps(state_payload).encode()).decode()
    msg = build_receive_letter(pbc_id, f"SET_LOAD_STATE={b64}")
    if inv_id is not None:
        msg["invocationId"] = inv_id
    return msg


def main():
    live_target = asyncio.run(resolve_live_targets(TARGET_NAME_FRAGMENT))
    hub_host = live_target["hub_host"]
    pbc_device_id = live_target["pbc_device_id"]
    smoke_uid = live_target["uid"]

    print("=" * 70)
    print("SAVANT RELAY CONTROL — SignalR /localhub")
    print("=" * 70)
    print(f"\nHub:       {hub_host}:{HUB_PORT}/localhub")
    print(f"Client ID: {CLIENT_DEVICE_ID}")
    print(f"PBC ID:    {pbc_device_id}")
    print(f"Target:    {live_target['name']} (channel {live_target['channel']})")
    print(f"Smoke UID: {smoke_uid}")
    print()

    print("Step 1: Negotiate SignalR connection...")
    conn_token = negotiate(hub_host, HUB_PORT, JWT)

    print("\nStep 2: WebSocket upgrade to /localhub...")
    sock = ws_connect(hub_host, HUB_PORT, JWT, conn_token)

    print("\nStep 3: SignalR protocol handshake...")
    handshake = {"protocol": "json", "version": 1}
    send_signalr(sock, handshake)
    import time; time.sleep(0.5)
    hub_init_messages = drain_messages(sock, timeout=1.0)

    print("\nStep 4: Register bearer token request and answer GET_VERSION...")
    send_signalr(sock, {"type": 1, "target": "HTTPBearerTokenRequest", "arguments": []})
    if any(
        message.get("target") == "ReceiveLetter"
        and message.get("arguments", [None])[0] == CLIENT_DEVICE_ID
        and message.get("arguments", [{}, {}])[1].get("contents", {}).get("command", {}).get("commandType") == "GET_VERSION"
        for message in hub_init_messages
    ):
        send_signalr(sock, build_receive_letter(CLIENT_DEVICE_ID, "SET_VERSION=HASS-Savant-Energy@0.1"))
    import time; time.sleep(1.0)
    drain_messages(sock)

    print("\nStep 5: Send app-style init sequence to PBC...")
    for command in (
        "GET_VERSION",
        "SET_SEND_ENERGY_LETTERS=1",
        "SET_OTA_MODE=0",
        "GET_PBC_READY",
    ):
        send_signalr(sock, build_receive_letter(pbc_device_id, command))
        time.sleep(0.25)
        drain_messages(sock, timeout=0.35)

    print("\nStep 6: Sending TURN OFF command (state=0, no invocationId)...")
    msg = build_set_load_state(pbc_device_id, smoke_uid, 0, None)
    send_signalr(sock, msg)

    time.sleep(0.5)
    follow_up_messages = drain_messages(sock, timeout=1.0)
    if not follow_up_messages:
        print("  (no response — normal)")

    sock.close()
    print("\n✓ Command sent. Did the smoke detector relay turn OFF?")


if __name__ == "__main__":
    main()
