"""InfluxDB 2 client for Savant Energy.

Replaces the TCP snapshot fetcher. Queries the Savant InfluxDB instance for
live circuit data and system-level energy totals.
"""

import asyncio
import csv
import io
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)

# InfluxDB stores per-circuit energy in mWh; HASS energy dashboard uses kWh.
_MWH_TO_KWH = 1_000_000.0
_ENERGY_SCALE_CANDIDATES = (1_000.0, 1_000_000.0, 1_000_000_000.0)
_DEFAULT_ENERGY_DIVISOR = _MWH_TO_KWH
_SCALE_LEARN_MIN_POWER_W = 300.0
_SCALE_LEARN_MIN_EXPECTED_DELTA_KWH = 0.001
_CT_ENERGY_REASONABLE_MAX_KWH = 100_000.0
_CT_ENERGY_GUARD_MIN_ABSOLUTE_JUMP_KWH = 0.25
_CT_ENERGY_GUARD_DELTA_MULTIPLIER = 25.0
_CIRCUIT_KEY_SEPARATOR = "::"
_KNOWN_CT_DEVICE_TYPES = {"007A"}
_INVALID_NAME_TOKENS = {"", "false", "true", "name", "override"}

# Flux query: fetch last reading for every circuit — relay-controlled and CT-only.
# We filter on savantUUID being present rather than a specific type code so that
# CT-monitored loads (EV chargers, solar inverters, etc.) are included alongside
# relay-switched circuits regardless of their hardware type tag.
_BACKFILL_WINDOWS = ("-2m", "-15m", "-24h", "-7d")

_CIRCUIT_QUERY = """\
from(bucket: "localHub")
  |> range(start: {range_start})
  |> filter(fn: (r) => exists r.savantUUID and r.savantUUID != "")
  |> filter(fn: (r) =>
      r._field == "power" or r._field == "current" or r._field == "voltage" or
      r._field == "energy" or r._field == "percentCommanded" or r._field == "flags")
  |> last()
"""

# Flux query: fetch last power reading for all hub-aggregated channels
# (totals, groups, battery, solar). type="0000" is always the hub measurement.
_SYSTEM_QUERY = """\
from(bucket: "localHub")
  |> range(start: {range_start})
  |> filter(fn: (r) => r.type == "0000")
  |> filter(fn: (r) => r._field == "power")
  |> last()
"""


@dataclass(slots=True)
class InfluxFetchResult:
    """Structured result from an InfluxDB fetch attempt."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    auth_failure: bool = False
    org_failure: bool = False
    query_window: Optional[str] = None


@dataclass(slots=True)
class CircuitDiscoveryResult:
    """Structured result from resolving the persisted circuit map."""

    success: bool
    circuit_map: Optional[dict[str, dict[str, Any]]] = None
    error_key: Optional[str] = None
    error_message: Optional[str] = None
    query_window: Optional[str] = None


def parse_uid(uid: str) -> tuple[str, str]:
    """Split 'BASE.0' → ('BASE', '0').  Returns (uid, '') when no suffix."""
    base, sep, suffix = uid.partition(".")
    if sep and suffix in ("0", "1"):
        return base, suffix
    return uid, ""


def build_circuit_key(savant_uuid: str, channel: str) -> str:
    """Build a stable circuit key from Influx identity tags."""
    return f"{savant_uuid.strip()}{_CIRCUIT_KEY_SEPARATOR}{channel.strip()}"


def split_circuit_key(circuit_key: str) -> tuple[str, str]:
    """Split a persisted circuit key into (savantUUID, channel)."""
    savant_uuid, _sep, channel = str(circuit_key or "").partition(_CIRCUIT_KEY_SEPARATOR)
    return savant_uuid, channel


def _parse_influx_csv(text: str) -> list[dict[str, str]]:
    """Parse InfluxDB annotated CSV response.

    InfluxDB returns multiple result tables separated by blank lines. Each
    table begins with annotation rows (lines starting with '#'). We skip
    those and collect only real data rows.
    """
    rows: list[dict[str, str]] = []
    for block in re.split(r"\r?\n\r?\n+", text or ""):
        lines = [
            line
            for line in block.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not lines:
            continue
        reader = csv.DictReader(io.StringIO("\n".join(lines)))
        if not reader.fieldnames:
            continue
        for row in reader:
            if row:
                rows.append(row)
    return rows


async def _post_flux(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    org: str,
    query: str,
) -> tuple[bool, str, str, bool, bool]:
    """POST a Flux query.

    Returns (success, body_text, error_message, auth_failure, org_failure).
    """
    url = f"{base_url.rstrip('/')}/api/v2/query"
    try:
        async with session.post(
            url,
            params={"org": org},
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "application/vnd.flux",
                "Accept": "text/csv",
            },
            data=query,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            text = await resp.text()
            if resp.status == 401:
                return False, "", "Unauthorized (401) - token is invalid or expired", True, False
            if resp.status == 403:
                return False, "", "Forbidden (403) - token lacks read permission", True, False
            if resp.status != 200:
                lowered = text.lower()
                org_failure = (
                    resp.status == 400
                    and (
                        "orgid or org" in lowered
                        or "organization not found" in lowered
                        or "org not found" in lowered
                    )
                )
                return False, "", f"HTTP {resp.status}: {text[:200]}", False, org_failure
            return True, text, "", False, False
    except asyncio.TimeoutError:
        return False, "", "InfluxDB query timed out after 10 s", False, False
    except aiohttp.ClientError as exc:
        return False, "", f"Connection error: {exc}", False, False


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _safe_bool(value: Any) -> bool:
    return str(value).strip().lower() not in ("false", "0", "")


def _normalize_name(value: str) -> str:
    """Normalize names for robust relay matching."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (value or "").lower())).strip()


def _is_usable_name(value: str) -> bool:
    """Return True when a name-like tag can be trusted for matching."""
    return _normalize_name(value) not in _INVALID_NAME_TOKENS


def _is_ct_from_tags(classification: str, device_type: str) -> bool:
    """Infer whether a circuit is CT-monitored from Influx metadata tags."""
    text = f"{classification or ''} {device_type or ''}".lower()
    ct_tokens = (
        "ct",
        "current transformer",
        "current_transformer",
        "sensor",
        "read only",
        "readonly",
        "meter",
    )
    return any(token in text for token in ct_tokens)


def _is_known_ct_circuit(classification: str, device_type: str) -> bool:
    """Return True for CT/monitor circuits that should never create switches."""
    normalized_type = str(device_type or "").strip().upper()
    return normalized_type in _KNOWN_CT_DEVICE_TYPES or _is_ct_from_tags(classification, device_type)


def _safe_int_channel(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 9999


def _combine_ct_current(legs: list[dict[str, Any]]) -> float:
    """Combine split-leg CT current into one reader-friendly value."""
    currents = [
        _safe_float(leg.get("current"))
        for leg in legs
        if leg.get("current") not in (None, "")
    ]
    if not currents:
        return 0.0
    return sum(currents) / len(currents)


def _combine_ct_voltage(legs: list[dict[str, Any]]) -> float:
    """Combine split-leg CT voltage into a whole-load value."""
    voltages = [
        _safe_float(leg.get("voltage"))
        for leg in legs
        if leg.get("voltage") not in (None, "")
    ]
    if not voltages:
        return 0.0
    if len(voltages) == 1:
        return voltages[0]
    return sum(voltages)


def _expand_multi_leg_ct_circuits(
    present_demands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add aggregate CT sensors while keeping each live leg visible."""
    ct_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    passthrough: list[dict[str, Any]] = []

    for device in present_demands:
        if device.get("role") == "ct_sensor" and device.get("legacy_base_uid"):
            ct_groups[str(device["legacy_base_uid"])].append(device)
        else:
            passthrough.append(device)

    expanded = list(passthrough)
    for base_uid, legs in ct_groups.items():
        legs.sort(key=lambda item: _safe_int_channel(item.get("channel")))
        if len(legs) <= 1:
            leg = legs[0]
            leg["ct_leg_index"] = 1
            leg["ct_leg_count"] = 1
            leg["ct_parent_uid"] = base_uid
            expanded.append(leg)
            continue

        aggregate_name = str(legs[0].get("name") or legs[0].get("influx_name") or "CT Load").strip()
        aggregate = dict(legs[0])
        aggregate["uid"] = base_uid
        aggregate["circuit_key"] = f"{base_uid}{_CIRCUIT_KEY_SEPARATOR}aggregate"
        aggregate["name"] = aggregate_name
        aggregate["channel"] = ",".join(str(leg.get("channel", "")).strip() for leg in legs if leg.get("channel"))
        aggregate["power"] = sum(_safe_float(leg.get("power")) for leg in legs)
        aggregate["energy"] = sum(_safe_float(leg.get("energy")) for leg in legs)
        aggregate["energy_raw"] = sum(_safe_float(leg.get("energy_raw")) for leg in legs)
        aggregate["current"] = _combine_ct_current(legs)
        aggregate["voltage"] = _combine_ct_voltage(legs)
        aggregate["legacy_uid"] = base_uid
        aggregate["legacy_base_uid"] = base_uid
        aggregate["energy_scale_divisor"] = None
        aggregate["energy_scale_confidence"] = None
        aggregate["energy_scale_status"] = "aggregated_ct"
        aggregate["expected_delta_last_kwh"] = None
        aggregate["measured_delta_last_kwh"] = None
        aggregate["energy_guard_applied"] = any(bool(leg.get("energy_guard_applied")) for leg in legs)
        aggregate["energy_guard_reason"] = None
        aggregate["energy_guard_blocked_samples"] = sum(
            int(leg.get("energy_guard_blocked_samples", 0) or 0) for leg in legs
        )
        aggregate["energy_role_source"] = "aggregated_ct"
        aggregate["ct_leg_index"] = None
        aggregate["ct_leg_count"] = len(legs)
        aggregate["ct_parent_uid"] = base_uid
        aggregate["ct_channels"] = [str(leg.get("channel", "")).strip() for leg in legs]
        expanded.append(aggregate)

        for idx, leg in enumerate(legs, start=1):
            leg["name"] = f"{aggregate_name} Leg {idx}"
            leg["ct_leg_index"] = idx
            leg["ct_leg_count"] = len(legs)
            leg["ct_parent_uid"] = base_uid
            expanded.append(leg)

    return expanded


def _build_circuit_rows(circuit_text: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Collapse Flux CSV rows into one dict per (savantUUID, channel) circuit."""
    by_circuit_key: dict[str, dict[str, Any]] = {}
    pbc_device_id = ""

    for row in _parse_influx_csv(circuit_text):
        savant_uuid = (row.get("savantUUID") or "").strip()
        channel = (row.get("channel") or "").strip()
        if (
            not savant_uuid
            or not channel
            or savant_uuid == "savantUUID"
            or channel == "channel"
        ):
            continue

        if not pbc_device_id:
            pbc_device_id = (row.get("_measurement") or "").strip()

        circuit_key = build_circuit_key(savant_uuid, channel)
        if circuit_key not in by_circuit_key:
            known_keys = {
                "savantUUID",
                "name",
                "channel",
                "classification",
                "dimmable",
                "group",
                "override",
                "regarding",
                "type",
                "_field",
                "_value",
                "_measurement",
                "_time",
                "_start",
                "_stop",
                "result",
                "table",
            }
            extra_tags = {k: v for k, v in row.items() if k not in known_keys and v}
            if extra_tags and not by_circuit_key:
                _LOGGER.debug("InfluxDB extra circuit tags (first row): %s", extra_tags)

            by_circuit_key[circuit_key] = {
                "circuit_key": circuit_key,
                "savantUUID": savant_uuid,
                "channel": channel,
                "name": (row.get("name") or "").strip(),
                "classification": (row.get("classification") or "").strip(),
                "dimmable": _safe_bool(row.get("dimmable", "False")),
                "group": (row.get("group") or "").strip(),
                "override": _safe_bool(row.get("override", "False")),
                "regarding": (row.get("regarding") or "").strip(),
                "type": (row.get("type") or "").strip(),
                "_extra_tags": extra_tags,
            }

        field = (row.get("_field") or "").strip()
        if field:
            by_circuit_key[circuit_key][field] = _safe_float(row.get("_value"))

    return pbc_device_id, by_circuit_key


def _build_sem_index(
    devices: list[dict[str, Any]],
    name_field: str,
) -> dict[str, dict[str, Any]]:
    """Index SEM devices by one normalized name field."""
    indexed: dict[str, dict[str, Any]] = {}
    for device in devices:
        normalized = _normalize_name(str(device.get(name_field, "")))
        if normalized and normalized not in indexed:
            indexed[normalized] = device
    return indexed


def _match_sem_device(
    circuit_name: str,
    by_label: dict[str, dict[str, Any]],
    by_load_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a circuit name to one SEM relay device."""
    normalized_name = _normalize_name(circuit_name)
    if normalized_name in _INVALID_NAME_TOKENS:
        return None, None

    matched = by_label.get(normalized_name)
    if matched:
        return matched, "device_label"

    matched = by_load_name.get(normalized_name)
    if matched:
        return matched, "load_name"

    return None, None


def _assign_legacy_identity(circuit_map: dict[str, dict[str, Any]]) -> None:
    """Assign stable legacy IDs for relay and CT circuits."""
    relay_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metadata in circuit_map.values():
        if metadata.get("role") == "relay" and metadata.get("relay_uid"):
            relay_groups[str(metadata["relay_uid"])].append(metadata)

    for relay_uid, circuits in relay_groups.items():
        circuits.sort(key=lambda item: _safe_int_channel(item.get("channel")))
        for slot, metadata in enumerate(circuits):
            metadata["legacy_uid"] = f"{relay_uid}.{slot}"
            metadata["legacy_base_uid"] = relay_uid

    for metadata in circuit_map.values():
        if metadata.get("legacy_uid"):
            continue
        savant_uuid = str(metadata.get("savant_uuid", "")).strip()
        channel = str(metadata.get("channel", "")).strip()
        metadata["legacy_uid"] = f"{savant_uuid}.{channel}" if savant_uuid and channel else metadata["circuit_key"]
        metadata["legacy_base_uid"] = savant_uuid or metadata["circuit_key"]


async def fetch_sem_devices_from_sem(
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
) -> tuple[bool, list[dict[str, Any]]]:
    """Fetch relay device metadata from the SEM companion API."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://{sem_host}:{sem_port}/companion/status"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    _LOGGER.warning("SEM companion API returned HTTP %d", resp.status)
                    return False, []

                data = await resp.json()
                devices: list[dict[str, Any]] = []
                for raw_device in data.get("Devices", []):
                    uid = str(raw_device.get("UID", "")).strip()
                    load_name = str(raw_device.get("LoadName", "")).strip()
                    device_label = str(raw_device.get("DeviceLabel", "")).strip()
                    if not uid or (not load_name and not device_label):
                        continue
                    devices.append(
                        {
                            "uid": uid,
                            "load_name": load_name,
                            "device_label": device_label,
                            "model": str(raw_device.get("DeviceModelDescription", "")).strip(),
                            "slot_number": raw_device.get("SlotNumber"),
                            "start_address": raw_device.get("StartAddress"),
                        }
                    )
                _LOGGER.debug("SEM companion API: %d relay device(s)", len(devices))
                return True, devices
    except Exception as exc:
        _LOGGER.warning(
            "Failed to fetch relay devices from SEM %s:%d: %s",
            sem_host,
            sem_port,
            exc,
        )
    return False, []


def _guard_ct_energy_reading(
    energy_kwh: float,
    expected_delta_kwh: float,
    state: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Hold the last published CT energy reading when a new sample is implausible."""
    last_published = state.get("last_published_energy_kwh")
    guard_reason = ""
    guarded = False

    if isinstance(last_published, (int, float)):
        last_published = float(last_published)
        max_allowed_jump = max(
            _CT_ENERGY_GUARD_MIN_ABSOLUTE_JUMP_KWH,
            max(expected_delta_kwh, 0.0) * _CT_ENERGY_GUARD_DELTA_MULTIPLIER,
        )
        jump_kwh = energy_kwh - last_published

        if jump_kwh < 0:
            energy_kwh = last_published
            guard_reason = "decrease"
            guarded = True
        elif jump_kwh > max_allowed_jump:
            energy_kwh = last_published
            guard_reason = "jump"
            guarded = True

    if not guarded:
        state["last_published_energy_kwh"] = energy_kwh
        state["guard_blocked_samples"] = 0
    else:
        state["guard_blocked_samples"] = int(state.get("guard_blocked_samples", 0)) + 1

    state["last_guard_reason"] = guard_reason

    return energy_kwh, {
        "energy_guard_applied": guarded,
        "energy_guard_reason": guard_reason or None,
        "energy_guard_blocked_samples": int(state.get("guard_blocked_samples", 0)),
    }


def _bootstrap_ct_divisor(raw_energy: float, current_divisor: float) -> float:
    """Pick a safer starting CT divisor when the default yields absurd lifetime kWh."""
    if current_divisor != _DEFAULT_ENERGY_DIVISOR:
        return current_divisor

    default_energy_kwh = raw_energy / _DEFAULT_ENERGY_DIVISOR
    if default_energy_kwh <= _CT_ENERGY_REASONABLE_MAX_KWH:
        return current_divisor

    for divisor in reversed(_ENERGY_SCALE_CANDIDATES):
        candidate_energy_kwh = raw_energy / divisor
        if candidate_energy_kwh <= _CT_ENERGY_REASONABLE_MAX_KWH:
            return divisor

    return current_divisor


def _resolve_energy_scale(
    uid: str,
    raw_energy: float,
    power_w: float,
    sample_seconds: float,
    scale_state: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    """Resolve per-circuit energy scaling using power-based delta plausibility."""
    state = scale_state.setdefault(uid, {})
    current_divisor = float(state.get("divisor", _DEFAULT_ENERGY_DIVISOR))
    current_divisor = _bootstrap_ct_divisor(raw_energy, current_divisor)
    votes = state.get("votes")
    if not isinstance(votes, dict):
        votes = {str(int(current_divisor)): 1}
        state["votes"] = votes
    elif str(int(current_divisor)) not in votes:
        votes[str(int(current_divisor))] = 1

    expected_delta = max(power_w, 0.0) * max(sample_seconds, 1.0) / 3_600_000.0
    last_raw = state.get("last_raw")

    measured_delta = None
    candidate_errors: dict[float, float] = {}
    if isinstance(last_raw, (int, float)) and raw_energy >= float(last_raw):
        raw_delta = raw_energy - float(last_raw)
        measured_delta = raw_delta / current_divisor
        if (
            expected_delta >= _SCALE_LEARN_MIN_EXPECTED_DELTA_KWH
            and power_w >= _SCALE_LEARN_MIN_POWER_W
        ):
            for divisor in _ENERGY_SCALE_CANDIDATES:
                candidate_delta = raw_delta / divisor
                candidate_errors[divisor] = abs(candidate_delta - expected_delta) / expected_delta

    if candidate_errors:
        best_divisor = min(candidate_errors, key=candidate_errors.get)
        votes_key = str(int(best_divisor))
        votes[votes_key] = min(int(votes.get(votes_key, 0)) + 1, 20)

        # Choose a new divisor only after repeated consistent observations.
        ordered_votes = sorted(
            ((float(key), int(value)) for key, value in votes.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        if ordered_votes:
            top_divisor, top_votes = ordered_votes[0]
            second_votes = ordered_votes[1][1] if len(ordered_votes) > 1 else 0
            if top_votes >= 2 and (top_votes - second_votes) >= 1:
                if top_divisor != current_divisor:
                    _LOGGER.warning(
                        "Energy scale selected for %s: divisor %.0f -> %.0f",
                        uid,
                        current_divisor,
                        top_divisor,
                    )
                current_divisor = top_divisor

    state["last_raw"] = raw_energy
    state["divisor"] = current_divisor

    divisor_votes = int(votes.get(str(int(current_divisor)), 0))
    confidence = min(divisor_votes / 6.0, 1.0)
    status = "locked" if confidence >= 0.7 else "learning"

    energy_kwh = raw_energy / current_divisor
    diagnostics = {
        "energy_scale_divisor": int(current_divisor),
        "energy_scale_confidence": round(confidence, 3),
        "energy_scale_status": status,
        "expected_delta_last_kwh": round(expected_delta, 6),
        "measured_delta_last_kwh": round(measured_delta, 6) if measured_delta is not None else None,
    }
    return energy_kwh, diagnostics


async def fetch_influx_snapshot(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    scale_state: dict[str, dict[str, Any]] | None = None,
    circuit_metadata: dict[str, dict[str, Any]] | None = None,
    sample_seconds: float = 5.0,
    range_start: str = "-2m",
) -> InfluxFetchResult:
    """Fetch the latest circuit and system data from InfluxDB.

    Returns an InfluxFetchResult whose .data dict matches the presentDemands
    shape expected by the rest of the integration, plus a system_data dict for
    hub-level sensors (totals, groups, battery, solar).
    """
    try:
        async with aiohttp.ClientSession() as session:
            ok, circuit_text, err, auth_failure, org_failure = await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _CIRCUIT_QUERY.format(range_start=range_start),
            )
            if not ok:
                return InfluxFetchResult(
                    success=False,
                    error_type="circuit_query_failed",
                    error_message=err,
                    auth_failure=auth_failure,
                    org_failure=org_failure,
                    query_window=range_start,
                )

            # System query failure is non-fatal — degrade gracefully.
            ok_sys, system_text, _, _, _ = await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _SYSTEM_QUERY.format(range_start=range_start),
            )
    except Exception as exc:  # pragma: no cover
        return InfluxFetchResult(
            success=False,
            error_type="unexpected_error",
            error_message=str(exc),
            query_window=range_start,
        )

    pbc_device_id, by_circuit_key = _build_circuit_rows(circuit_text)

    if scale_state is None:
        scale_state = {}
    stored_metadata = circuit_metadata or {}

    present_demands: list[dict[str, Any]] = []
    unknown_circuit_keys: list[str] = []
    seen_circuit_keys: set[str] = set()
    for circuit_key, circuit in by_circuit_key.items():
        seen_circuit_keys.add(circuit_key)
        metadata = stored_metadata.get(circuit_key)
        if metadata is None:
            unknown_circuit_keys.append(circuit_key)
            _LOGGER.warning(
                "Skipping unmapped Savant circuit %s (%s, channel=%s, type=%s). Run Reconfigure to classify new circuits.",
                circuit_key,
                circuit.get("name", "<unnamed>"),
                circuit.get("channel", "?"),
                circuit.get("type", "<unknown>"),
            )
            continue

        savant_uuid = str(circuit.get("savantUUID", "")).strip()
        base_uid, _ab_side = parse_uid(savant_uuid)
        role = str(metadata.get("role", "unknown")).strip().lower()
        if role not in ("relay", "ct_sensor"):
            _LOGGER.warning(
                "Skipping circuit %s because stored role %r is not actionable",
                circuit_key,
                metadata.get("role"),
            )
            continue

        power_w = _safe_float(circuit.get("power"))
        voltage_v = _safe_float(circuit.get("voltage"))
        current_a = _safe_float(circuit.get("current"))
        raw_energy = _safe_float(circuit.get("energy"))
        pct_commanded = _safe_float(circuit.get("percentCommanded"))
        flags = int(_safe_float(circuit.get("flags")))
        state = scale_state.setdefault(circuit_key, {})
        relay_uid = str(metadata.get("relay_uid", "")).strip() or None
        role_source = str(metadata.get("role_source", "config_entry")).strip() or "config_entry"

        if role == "ct_sensor":
            energy_kwh, energy_diag = _resolve_energy_scale(
                circuit_key,
                raw_energy,
                power_w,
                sample_seconds,
                scale_state,
            )
            energy_kwh, guard_diag = _guard_ct_energy_reading(
                energy_kwh,
                float(energy_diag["expected_delta_last_kwh"] or 0.0),
                state,
            )
            energy_diag.update(guard_diag)
        else:
            # Relay circuits keep the known-good fixed conversion path.
            fixed_divisor = _DEFAULT_ENERGY_DIVISOR
            energy_kwh = raw_energy / fixed_divisor
            energy_diag = {
                "energy_scale_divisor": int(fixed_divisor),
                "energy_scale_confidence": 1.0,
                "energy_scale_status": "fixed_relay",
                "expected_delta_last_kwh": None,
                "measured_delta_last_kwh": None,
                "energy_guard_applied": False,
                "energy_guard_reason": None,
                "energy_guard_blocked_samples": 0,
            }
            state["last_published_energy_kwh"] = energy_kwh

        energy_diag["energy_role_source"] = role_source

        # Infer relay capacity from measured voltage.
        # 240 V nominal circuits → 7.2 kW (30 A); 120 V → 2.4 kW (20 A).
        capacity = 7.2 if voltage_v > 200 else 2.4

        present_demands.append(
            {
                # Identity
                "uid": circuit_key,   # Stable entity key = (savantUUID, channel)
                "circuit_key": circuit_key,
                "base_uid": base_uid, # Base UID for HASS device grouping
                "name": metadata.get("display_name")
                or circuit.get("name")
                or f"Circuit {circuit.get('channel', savant_uuid)}",
                "influx_name": circuit.get("name", ""),
                "channel": circuit.get("channel", ""),
                "classification": circuit.get("classification", ""),
                "type": circuit.get("type", ""),
                "role": role,
                "relay_uid": relay_uid,
                "has_relay": role == "relay",
                "relay_match_name": metadata.get("relay_match_name"),
                "relay_match_source": metadata.get("role_source"),
                # State
                "dimmable": circuit.get("dimmable", False),
                "override": circuit.get("override", False),
                "percentCommanded": pct_commanded,
                "flags": flags,
                # Measurements — power already in W from InfluxDB (not kW)
                "power": power_w,
                "current": current_a,
                "voltage": voltage_v,
                "energy": energy_kwh,   # kWh (converted from mWh)
                "energy_raw": raw_energy,
                "energy_scale_divisor": energy_diag["energy_scale_divisor"],
                "energy_scale_confidence": energy_diag["energy_scale_confidence"],
                "energy_scale_status": energy_diag["energy_scale_status"],
                "expected_delta_last_kwh": energy_diag["expected_delta_last_kwh"],
                "measured_delta_last_kwh": energy_diag["measured_delta_last_kwh"],
                "energy_guard_applied": energy_diag["energy_guard_applied"],
                "energy_guard_reason": energy_diag["energy_guard_reason"],
                "energy_guard_blocked_samples": energy_diag["energy_guard_blocked_samples"],
                "energy_role_source": energy_diag["energy_role_source"],
                # Device metadata
                "capacity": capacity,
                "legacy_uid": metadata.get("legacy_uid", circuit_key),
                "legacy_base_uid": metadata.get("legacy_base_uid", base_uid or circuit_key),
            }
        )

    if not by_circuit_key:
        return InfluxFetchResult(
            success=False,
            error_type="empty_response",
            error_message=(
                "InfluxDB returned no circuit data — "
                "check that the SEM is writing to the 'localHub' bucket "
                "and that the token has read access"
            ),
            query_window=range_start,
        )

    # Sort by channel number for stable, predictable ordering.
    present_demands.sort(
        key=lambda d: int(d["channel"]) if str(d["channel"]).isdigit() else 9999
    )
    present_demands = _expand_multi_leg_ct_circuits(present_demands)

    # Log all circuit names at INFO level so operators can see what came through
    # (useful for diagnosing missing devices like EV chargers that may have
    # unexpected names or type tags in InfluxDB).
    _LOGGER.info(
        "InfluxDB circuits (%d): %s",
        len(present_demands),
        ", ".join(
            f"[{d.get('channel','?')}] {d.get('name','?')} (uid={d.get('uid','?')[:8]}...)"
            for d in present_demands
        ),
    )

    # --- Build system_data from hub CSV ---
    # Keys are the InfluxDB channel tag values, e.g. "Energy.Total.Consumption.Power"
    system_data: dict[str, float] = {}
    if ok_sys:
        for row in _parse_influx_csv(system_text):
            channel = row.get("channel", "").strip()
            if channel:
                system_data[channel] = _safe_float(row.get("_value"))

    _LOGGER.debug(
        "InfluxDB fetch: %d circuits, %d system channels",
        len(present_demands),
        len(system_data),
    )

    missing_circuit_keys = sorted(set(stored_metadata) - seen_circuit_keys)
    if missing_circuit_keys:
        _LOGGER.warning(
            "Stored Savant circuits were not present in the latest Influx snapshot: %s",
            ", ".join(missing_circuit_keys[:10]),
        )

    return InfluxFetchResult(
        success=True,
        data={
            "presentDemands": present_demands,
            "system_data": system_data,
            "pbc_device_id": pbc_device_id,  # PBC SignalR target device ID
            "circuit_map_status": {
                "reconfigure_required": bool(unknown_circuit_keys or missing_circuit_keys),
                "unknown_circuit_keys": unknown_circuit_keys,
                "missing_circuit_keys": missing_circuit_keys,
            },
        },
        query_window=range_start,
    )


async def fetch_influx_snapshot_with_backfill(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    scale_state: dict[str, dict[str, Any]] | None = None,
    circuit_metadata: dict[str, dict[str, Any]] | None = None,
    sample_seconds: float = 5.0,
    backfill_windows: tuple[str, ...] = _BACKFILL_WINDOWS,
) -> InfluxFetchResult:
    """Fetch a snapshot, widening the lookback window before failing."""
    last_empty_result: InfluxFetchResult | None = None
    for range_start in backfill_windows:
        _LOGGER.debug(
            "InfluxDB snapshot attempt for org %s using lookback %s",
            influx_org or "<unset>",
            range_start,
        )
        result = await fetch_influx_snapshot(
            influx_url,
            influx_token,
            influx_org,
            sem_host=sem_host,
            sem_port=sem_port,
            scale_state=scale_state,
            circuit_metadata=circuit_metadata,
            sample_seconds=sample_seconds,
            range_start=range_start,
        )
        if result.success and result.data is not None:
            _LOGGER.debug(
                "InfluxDB snapshot attempt succeeded for org %s using %s",
                influx_org or "<unset>",
                range_start,
            )
            return result
        if result.auth_failure or result.org_failure:
            _LOGGER.debug(
                "InfluxDB snapshot attempt stopped for org %s at %s due to %s",
                influx_org or "<unset>",
                range_start,
                result.error_type,
            )
            return result
        _LOGGER.debug(
            "InfluxDB snapshot attempt returned no data for org %s at %s",
            influx_org or "<unset>",
            range_start,
        )
        last_empty_result = result

    _LOGGER.debug(
        "InfluxDB snapshot backfill exhausted for org %s after windows %s",
        influx_org or "<unset>",
        ", ".join(backfill_windows),
    )
    return last_empty_result or InfluxFetchResult(
        success=False,
        error_type="empty_response",
        error_message=(
            "InfluxDB returned no circuit data — "
            "check that the SEM is writing to the 'localHub' bucket "
            "and that the token has read access"
        ),
        query_window=backfill_windows[-1] if backfill_windows else None,
    )


async def discover_circuit_metadata(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    range_start: str = "-2m",
) -> CircuitDiscoveryResult:
    """Resolve relay/CT identity once during setup or reconfigure."""
    try:
        async with aiohttp.ClientSession() as session:
            ok, circuit_text, err, auth_failure, org_failure = await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _CIRCUIT_QUERY.format(range_start=range_start),
            )
    except Exception as exc:  # pragma: no cover
        return CircuitDiscoveryResult(
            success=False,
            error_key="circuit_discovery_failed",
            error_message=str(exc),
            query_window=range_start,
        )

    if not ok:
        return CircuitDiscoveryResult(
            success=False,
            error_key=(
                "org_auth_failed"
                if auth_failure
                else "org_discovery_failed"
                if org_failure
                else "circuit_discovery_failed"
            ),
            error_message=err,
            query_window=range_start,
        )

    _pbc_device_id, by_circuit_key = _build_circuit_rows(circuit_text)
    if not by_circuit_key:
        return CircuitDiscoveryResult(
            success=False,
            error_key="circuit_discovery_failed",
            error_message="InfluxDB returned no circuit rows during discovery.",
            query_window=range_start,
        )

    sem_ok, sem_devices = await fetch_sem_devices_from_sem(sem_host=sem_host, sem_port=sem_port)
    if not sem_ok or not sem_devices:
        return CircuitDiscoveryResult(
            success=False,
            error_key="sem_companion_failed",
            error_message="Could not reach the SEM companion status API or no relay devices were returned.",
            query_window=range_start,
        )

    by_label = _build_sem_index(sem_devices, "device_label")
    by_load_name = _build_sem_index(sem_devices, "load_name")

    circuit_map: dict[str, dict[str, Any]] = {}
    unresolved: list[str] = []
    for circuit_key, circuit in sorted(
        by_circuit_key.items(),
        key=lambda item: (_safe_int_channel(item[1].get("channel")), str(item[1].get("name", ""))),
    ):
        circuit_name = str(circuit.get("name", "")).strip()
        matched_device, match_source = _match_sem_device(circuit_name, by_label, by_load_name)
        role = "ct_sensor" if _is_known_ct_circuit(circuit.get("classification", ""), circuit.get("type", "")) else "relay_candidate"

        if matched_device is not None:
            role = "relay"
        elif role != "ct_sensor":
            unresolved.append(
                f"{circuit_name or '<unnamed>'} (channel {circuit.get('channel', '?')}, type {circuit.get('type', '<unknown>')})"
            )
            continue

        savant_uuid = str(circuit.get("savantUUID", "")).strip()
        circuit_map[circuit_key] = {
            "circuit_key": circuit_key,
            "savant_uuid": savant_uuid,
            "channel": str(circuit.get("channel", "")).strip(),
            "type": str(circuit.get("type", "")).strip(),
            "role": role if role != "relay_candidate" else "relay",
            "relay_uid": matched_device.get("uid", "") if matched_device else "",
            "display_name": (
                matched_device.get("load_name")
                or matched_device.get("device_label")
                or circuit_name
            )
            if matched_device
            else (circuit_name or f"Circuit {circuit.get('channel', '?')}"),
            "influx_name": circuit_name,
            "legacy_uid": "",
            "legacy_base_uid": "",
            "role_source": (
                f"sem_{match_source}"
                if matched_device and match_source
                else "known_ct_type"
                if str(circuit.get("type", "")).strip().upper() in _KNOWN_CT_DEVICE_TYPES
                else "ct_tags"
            ),
            "relay_match_name": (
                matched_device.get("device_label")
                if match_source == "device_label"
                else matched_device.get("load_name")
            )
            if matched_device
            else None,
        }

    if unresolved:
        return CircuitDiscoveryResult(
            success=False,
            error_key="circuit_relay_mapping_failed",
            error_message="; ".join(unresolved[:5]),
            query_window=range_start,
        )

    _assign_legacy_identity(circuit_map)
    return CircuitDiscoveryResult(
        success=True,
        circuit_map=circuit_map,
        query_window=range_start,
    )


async def discover_circuit_metadata_with_backfill(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    backfill_windows: tuple[str, ...] = _BACKFILL_WINDOWS,
) -> CircuitDiscoveryResult:
    """Resolve the persisted circuit map, widening the lookback window before failing."""
    last_result: CircuitDiscoveryResult | None = None
    for range_start in backfill_windows:
        result = await discover_circuit_metadata(
            influx_url,
            influx_token,
            influx_org,
            sem_host=sem_host,
            sem_port=sem_port,
            range_start=range_start,
        )
        if result.success and result.circuit_map:
            return result
        last_result = result
        if result.error_key in {"org_auth_failed", "org_discovery_failed", "sem_companion_failed"}:
            return result
    return last_result or CircuitDiscoveryResult(
        success=False,
        error_key="circuit_discovery_failed",
        error_message="Circuit discovery did not return any data.",
        query_window=backfill_windows[-1] if backfill_windows else None,
    )
