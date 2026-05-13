"""InfluxDB 2 client for Savant Energy.

Replaces the TCP snapshot fetcher. Queries the Savant InfluxDB instance for
live circuit data and system-level energy totals.
"""

import asyncio
import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)

# InfluxDB stores per-circuit energy in mWh; HASS energy dashboard uses kWh.
_MWH_TO_KWH = 1_000_000.0

# Flux query: fetch last reading for every circuit — relay-controlled and CT-only.
# We filter on savantUUID being present rather than a specific type code so that
# CT-monitored loads (EV chargers, solar inverters, etc.) are included alongside
# relay-switched circuits regardless of their hardware type tag.
_CIRCUIT_QUERY = """\
from(bucket: "localHub")
  |> range(start: -2m)
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
  |> range(start: -2m)
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
) -> tuple[bool, str, str]:
    """POST a Flux query. Returns (success, body_text, error_message)."""
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
                return False, "", "Unauthorized (401) — token is invalid or expired"
            if resp.status == 403:
                return False, "", "Forbidden (403) — token lacks read permission"
            if resp.status != 200:
                return False, "", f"HTTP {resp.status}: {text[:200]}"
            return True, text, ""
    except asyncio.TimeoutError:
        return False, "", "InfluxDB query timed out after 10 s"
    except aiohttp.ClientError as exc:
        return False, "", f"Connection error: {exc}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _safe_bool(value: Any) -> bool:
    return str(value).strip().lower() not in ("false", "0", "")


async def fetch_influx_snapshot(
    influx_url: str,
    influx_token: str,
    influx_org: str,
) -> InfluxFetchResult:
    """Fetch the latest circuit and system data from InfluxDB.

    Returns an InfluxFetchResult whose .data dict matches the presentDemands
    shape expected by the rest of the integration, plus a system_data dict for
    hub-level sensors (totals, groups, battery, solar).
    """
    try:
        async with aiohttp.ClientSession() as session:
            ok, circuit_text, err = await _post_flux(
                session, influx_url, influx_token, influx_org, _CIRCUIT_QUERY
            )
            if not ok:
                return InfluxFetchResult(
                    success=False,
                    error_type="circuit_query_failed",
                    error_message=err,
                )

            # System query failure is non-fatal — degrade gracefully.
            ok_sys, system_text, _ = await _post_flux(
                session, influx_url, influx_token, influx_org, _SYSTEM_QUERY
            )
    except Exception as exc:  # pragma: no cover
        return InfluxFetchResult(
            success=False,
            error_type="unexpected_error",
            error_message=str(exc),
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
        energy_kwh = _safe_float(circuit.get("energy")) / _MWH_TO_KWH
        pct_commanded = _safe_float(circuit.get("percentCommanded"))
        flags = int(_safe_float(circuit.get("flags")))

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

    # --- Fetch relay UIDs from SEM and merge into presentDemands ---
    # has_relay is authoritative only when the SEM API is reachable.
    # If it's unreachable we fall back to True for all so the integration
    # keeps working during a transient outage.
    sem_ok, relay_uids = await fetch_relay_uids_from_sem()
    for circuit in present_demands:
        circuit_name = circuit.get("name", "").lower()
        matched_uid: str | None = None
        for relay_name, relay_uid in relay_uids.items():
            if relay_name in circuit_name or circuit_name in relay_name:
                matched_uid = relay_uid
                _LOGGER.debug("Mapped circuit '%s' to relay UID %s", circuit["name"], relay_uid)
                break

        if sem_ok:
            # API reachable: only circuits the SEM knows about have a real relay
            circuit["relay_uid"] = matched_uid
            circuit["has_relay"] = matched_uid is not None
        else:
            # API unreachable: optimistically assume relay so commands still work
            circuit["relay_uid"] = matched_uid or circuit.get("uid")
            circuit["has_relay"] = True

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
