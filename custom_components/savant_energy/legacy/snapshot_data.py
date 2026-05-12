"""Legacy snapshot fetcher (<11.2)."""

import base64
import json
import logging
import socket
from dataclasses import dataclass
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

SOCKET_TIMEOUT_SECONDS = 10


@dataclass(slots=True)
class SnapshotFetchResult:
    """Structured snapshot fetch result with error classification."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    raw_excerpt: Optional[str] = None


def _excerpt(value: str, limit: int = 160) -> str:
    """Return a trimmed single-line excerpt for logs."""
    compact_value = " ".join((value or "").split())
    if len(compact_value) <= limit:
        return compact_value
    return f"{compact_value[:limit]}..."


def _extract_set_energy_payload(data_str: str) -> str:
    """Extract the SET_ENERGY payload from the raw TCP response."""
    payload = data_str or ""
    if "SET_ENERGY=" in payload:
        payload = payload.split("SET_ENERGY=", 1)[1]
    if "\n" in payload:
        payload = payload.split("\n", 1)[0]
    if payload.startswith("SET_ENERGY="):
        payload = payload[len("SET_ENERGY=") :]
    return payload.strip()


def fetch_current_energy_snapshot(address: str, port: int) -> SnapshotFetchResult:
    """Fetch and validate the current Savant snapshot with classified failures."""
    _LOGGER.info("Fetching Savant snapshot from %s:%s", address, port)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_TIMEOUT_SECONDS)
            sock.connect((address, port))
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.count(b"\n") >= 2:
                    break
    except socket.timeout:
        return SnapshotFetchResult(
            success=False,
            error_type="transport_timeout",
            error_message="Timed out waiting for a snapshot response",
        )
    except socket.error as err:
        return SnapshotFetchResult(
            success=False,
            error_type="transport_error",
            error_message=f"Socket error: {err}",
        )
    except Exception as err:
        return SnapshotFetchResult(
            success=False,
            error_type="unexpected_error",
            error_message=f"Unexpected error: {err}",
        )

    if not data:
        return SnapshotFetchResult(
            success=False,
            error_type="empty_response",
            error_message=(
                "Controller closed the connection without returning any snapshot data"
            ),
        )

    try:
        data_str = data.decode("utf-8")
    except UnicodeDecodeError as err:
        return SnapshotFetchResult(
            success=False,
            error_type="response_decode_error",
            error_message=f"Snapshot response was not valid UTF-8: {err}",
            raw_excerpt=_excerpt(data.decode("utf-8", errors="replace")),
        )

    payload = _extract_set_energy_payload(data_str)
    if not payload:
        error_type = "empty_payload" if "SET_ENERGY=" in data_str else "missing_payload"
        error_message = (
            "SET_ENERGY payload was present but empty"
            if error_type == "empty_payload"
            else "SET_ENERGY payload marker was not found in the controller response"
        )
        return SnapshotFetchResult(
            success=False,
            error_type=error_type,
            error_message=error_message,
            raw_excerpt=_excerpt(data_str),
        )

    try:
        decoded_string = base64.b64decode(payload, validate=True).decode("utf-8")
    except (base64.binascii.Error, UnicodeDecodeError) as err:
        return SnapshotFetchResult(
            success=False,
            error_type="payload_decode_error",
            error_message=f"Snapshot payload could not be base64-decoded into UTF-8 JSON: {err}",
            raw_excerpt=_excerpt(payload),
        )

    if not decoded_string.strip():
        return SnapshotFetchResult(
            success=False,
            error_type="empty_decoded_payload",
            error_message="Decoded snapshot payload was empty",
        )

    try:
        json_data = json.loads(decoded_string)
    except json.JSONDecodeError as err:
        return SnapshotFetchResult(
            success=False,
            error_type="invalid_json",
            error_message=f"Decoded payload was not valid JSON: {err}",
            raw_excerpt=_excerpt(decoded_string),
        )

    if not isinstance(json_data, dict):
        return SnapshotFetchResult(
            success=False,
            error_type="invalid_shape",
            error_message=(
                f"Decoded snapshot root must be an object, got {type(json_data).__name__}"
            ),
            raw_excerpt=_excerpt(json.dumps(json_data, default=str)),
        )

    present_demands = json_data.get("presentDemands")
    if not isinstance(present_demands, list):
        return SnapshotFetchResult(
            success=False,
            error_type="invalid_shape",
            error_message="Decoded snapshot is missing a valid presentDemands list",
            raw_excerpt=_excerpt(json.dumps(json_data, default=str)),
        )

    _LOGGER.info(
        "Decoded Savant snapshot with %d presentDemands entries",
        len(present_demands),
    )

    return SnapshotFetchResult(success=True, data=json_data)
