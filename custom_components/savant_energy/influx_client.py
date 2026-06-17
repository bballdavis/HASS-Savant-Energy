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


def parse_uid(uid: str) -> tuple[str, str]:
    """Split 'BASE.0' → ('BASE', '0').  Returns (uid, '') when no suffix."""
    base, sep, suffix = uid.partition(".")
    if sep and suffix in ("0", "1"):
        return base, suffix
    return uid, ""


def _parse_influx_csv(text: str) -> list[dict[str, str]]:
    """Parse InfluxDB annotated CSV response.

    InfluxDB returns multiple result tables separated by blank lines. Each
    table begins with annotation rows (lines starting with '#'). We skip
    those and collect only real data rows.
    """
    rows: list[dict[str, str]] = []
    for block in text.split("\r\n\r\n"):
        block = block.strip()
        if not block:
            continue
        reader = csv.DictReader(io.StringIO(block))
        if not reader.fieldnames:
            continue
        for row in reader:
            # Annotation rows have keys starting with '#'
            if any(str(k).startswith("#") for k in row):
                continue
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


def _match_relay_uid(circuit_name: str, relay_uids: dict[str, str]) -> str | None:
    """Match a circuit name to a relay UID with exact-first then bounded fallback."""
    normalized_circuit = _normalize_name(circuit_name)
    if not normalized_circuit:
        return None

    normalized_map: dict[str, str] = {}
    for relay_name, relay_uid in relay_uids.items():
        norm = _normalize_name(relay_name)
        if norm and norm not in normalized_map:
            normalized_map[norm] = relay_uid

    direct = normalized_map.get(normalized_circuit)
    if direct:
        return direct

    for relay_name, relay_uid in normalized_map.items():
        shorter = min(len(relay_name), len(normalized_circuit))
        if shorter < 5:
            continue
        if relay_name in normalized_circuit or normalized_circuit in relay_name:
            return relay_uid
    return None


def _classify_circuit_role(
    uid: str,
    matched_uid: str | None,
    sem_ok: bool,
    is_ct_tagged: bool,
    state: dict[str, Any],
) -> tuple[str, str | None, str]:
    """Classify a circuit role while preserving previously learned CT identity."""
    if matched_uid:
        state["stable_role"] = "relay"
        return "relay", matched_uid, "matched_relay"

    learned_divisor = float(state.get("divisor", _DEFAULT_ENERGY_DIVISOR))
    sticky_ct = state.get("stable_role") == "ct_sensor" or learned_divisor != _DEFAULT_ENERGY_DIVISOR

    if sem_ok:
        state["stable_role"] = "ct_sensor"
        return "ct_sensor", None, "sem_unmatched"

    if is_ct_tagged:
        state["stable_role"] = "ct_sensor"
        return "ct_sensor", None, "ct_tags"

    if sticky_ct:
        return "ct_sensor", None, "sticky_ct"

    state["stable_role"] = "relay"
    return "relay", str(uid) or None, "sem_fallback_relay"


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

    # --- Build presentDemands from circuit CSV ---
    # Group flat rows (one per field) by savantUUID so we get one dict per circuit.
    by_uuid: dict[str, dict[str, Any]] = {}
    pbc_device_id: str = ""  # _measurement tag = PBC device ID (e.g. "60640523DAC90074")
    for row in _parse_influx_csv(circuit_text):
        uuid = row.get("savantUUID", "").strip()
        if not uuid:
            continue

        # Capture PBC device ID from _measurement (same for all circuit rows)
        if not pbc_device_id:
            pbc_device_id = row.get("_measurement", "").strip()

        if uuid not in by_uuid:
            # Capture all string tag columns — dump any extras at DEBUG level on first
            # circuit so operators can see the full InfluxDB schema (helps locate
            # fields like the legacy hex UID if Savant stores it as an additional tag).
            known_keys = {
                "savantUUID", "name", "channel", "classification", "dimmable",
                "override", "type", "_field", "_value", "_measurement", "_time",
                "_start", "_stop", "result", "table",
            }
            extra_tags = {k: v for k, v in row.items() if k not in known_keys and v}
            if extra_tags and not by_uuid:  # log once, on the first circuit
                _LOGGER.debug("InfluxDB extra circuit tags (first row): %s", extra_tags)

            by_uuid[uuid] = {
                "savantUUID": uuid,
                "name": row.get("name", "").strip(),
                "channel": row.get("channel", "").strip(),
                "classification": row.get("classification", "").strip(),
                "dimmable": _safe_bool(row.get("dimmable", "False")),
                "override": _safe_bool(row.get("override", "False")),
                "type": row.get("type", "").strip(),
                # Preserve any extra tags so callers can inspect them
                "_extra_tags": extra_tags,
            }

        field = row.get("_field", "").strip()
        raw_value = row.get("_value", "")
        if field:
            by_uuid[uuid][field] = _safe_float(raw_value)

    if scale_state is None:
        scale_state = {}

    # Fetch SEM relay map early so we can classify circuits before any scaling decisions.
    sem_ok, relay_uids = await fetch_relay_uids_from_sem(sem_host=sem_host, sem_port=sem_port)

    present_demands: list[dict[str, Any]] = []
    for uuid, circuit in by_uuid.items():
        # --- A/B device handling ---
        # In legacy Savant hardware, two circuit slots on the same physical
        # relay module share a base UID (e.g. "001AAE17329B") and are
        # distinguished by a ".0" / ".1" suffix.  In current UUID-based
        # systems each circuit has a fully unique UUID with no suffix, but
        # we remain robust to the suffix form.
        #
        # uid       — used as entity unique_id (one entity per circuit)
        # base_uid  — used as HASS device identifier (A+B share one device)
        base_uid, _ab_side = parse_uid(uuid)

        power_w = _safe_float(circuit.get("power"))
        voltage_v = _safe_float(circuit.get("voltage"))
        current_a = _safe_float(circuit.get("current"))
        raw_energy = _safe_float(circuit.get("energy"))
        pct_commanded = _safe_float(circuit.get("percentCommanded"))
        flags = int(_safe_float(circuit.get("flags")))

        matched_uid = _match_relay_uid(circuit.get("name", ""), relay_uids)
        is_ct_tagged = _is_ct_from_tags(
            str(circuit.get("classification", "")),
            str(circuit.get("type", "")),
        )
        state = scale_state.setdefault(uuid, {})
        role, relay_uid, role_source = _classify_circuit_role(
            uuid,
            matched_uid,
            sem_ok,
            is_ct_tagged,
            state,
        )

        if role == "ct_sensor":
            energy_kwh, energy_diag = _resolve_energy_scale(
                uuid,
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
                "uid": uuid,          # Full savantUUID (stable entity key)
                "base_uid": base_uid, # Base UID for HASS device grouping
                "name": circuit.get("name", f"Circuit {circuit.get('channel', uuid)}"),
                "channel": circuit.get("channel", ""),
                "classification": circuit.get("classification", ""),
                "type": circuit.get("type", ""),
                "role": role,
                "relay_uid": relay_uid,
                "has_relay": role == "relay",
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
            }
        )

    if not present_demands:
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

    # --- Finalize relay mapping metadata for logging/consistency ---
    for circuit in present_demands:
        matched_uid = circuit.get("relay_uid")
        if matched_uid:
            _LOGGER.debug("Mapped circuit '%s' to relay UID %s", circuit["name"], matched_uid)

    # --- Assign legacy_uid for entity identity preservation ---
    # Group relay-controlled circuits by relay_uid, sort by channel, assign a
    # ".0"/".1" slot index. This reconstructs the MAC-based hex UIDs that were
    # used as entity unique_ids in legacy TCP mode (e.g. "001AAE17CF15.0"),
    # so existing entities are updated rather than recreated when transitioning
    # an installed system from legacy to current (InfluxDB) mode.
    relay_groups: dict[str, list] = defaultdict(list)
    for circuit in present_demands:
        if circuit.get("has_relay") and circuit.get("relay_uid"):
            relay_groups[circuit["relay_uid"]].append(circuit)

    for relay_uid_key, circuits in relay_groups.items():
        circuits.sort(
            key=lambda c: int(c["channel"]) if str(c.get("channel", "")).isdigit() else 9999
        )
        for slot, circuit in enumerate(circuits):
            circuit["legacy_uid"] = f"{relay_uid_key}.{slot}"
            circuit["legacy_base_uid"] = relay_uid_key

    # CT-monitored circuits have no legacy MAC UID — fall back to their InfluxDB UUID.
    for circuit in present_demands:
        if "legacy_uid" not in circuit:
            circuit["legacy_uid"] = circuit["uid"]
            circuit["legacy_base_uid"] = circuit.get("base_uid", circuit["uid"])

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

    return InfluxFetchResult(
        success=True,
        data={
            "presentDemands": present_demands,
            "system_data": system_data,
            "pbc_device_id": pbc_device_id,  # PBC SignalR target device ID
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


async def fetch_relay_uids_from_sem(
    sem_host: str = "192.168.1.108", sem_port: int = 8644
) -> tuple[bool, dict[str, str]]:
    """Fetch relay device UIDs from SEM companion API.

    Returns (api_ok, devices) where api_ok indicates whether the SEM was reachable.
    devices maps lowercase load names to legacy UIDs (e.g., "smoke detector" -> "001AAE1733DB").
    Only devices that appear here have physical relays; everything else is CT-monitored only.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://{sem_host}:{sem_port}/companion/status"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    devices: dict[str, str] = {}
                    for device in data.get("Devices", []):
                        uid = device.get("UID")
                        name = device.get("LoadName", "")
                        if uid and name:
                            devices[name.lower()] = uid
                    _LOGGER.debug("SEM companion API: %d relay device(s)", len(devices))
                    return True, devices
                _LOGGER.warning("SEM companion API returned HTTP %d", resp.status)
    except Exception as exc:
        _LOGGER.warning("Failed to fetch relay UIDs from SEM %s:%d: %s", sem_host, sem_port, exc)

    return False, {}
