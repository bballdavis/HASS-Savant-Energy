"""InfluxDB 2 client for Savant Energy.

Replaces the TCP snapshot fetcher. Queries the Savant InfluxDB instance for
live circuit data and system-level energy totals.
"""

import asyncio
import csv
import json
import io
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Optional

import aiohttp

try:
    from .const import DEFAULT_INFLUX_BUCKET
except ImportError:  # direct test-module loading compatibility
    DEFAULT_INFLUX_BUCKET = "localHub"

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
# Savant normally identifies circuits with savantUUID. Some 007A CT channels
# (notably Main Feed) omit that tag but retain a stable measurement id and a
# configured name. Include those named CT rows; unnamed 007A channels are spare
# inputs/noise and are intentionally excluded.
_BACKFILL_WINDOWS = ("-2m", "-15m", "-24h", "-7d")

_CIRCUIT_QUERY = """\
from(bucket: {bucket})
  |> range(start: {range_start})
  |> filter(fn: (r) =>
      (exists r.savantUUID and r.savantUUID != "") or
      (exists r.type and r.type == "007A" and exists r.name and r.name != ""))
  |> filter(fn: (r) =>
      r._field == "power" or r._field == "current" or r._field == "voltage" or
      r._field == "energy" or r._field == "percentCommanded" or r._field == "flags")
  |> last()
"""

# Flux query: fetch last power reading for all hub-aggregated channels
# (totals, groups, battery, solar). type="0000" is always the hub measurement.
_SYSTEM_QUERY = """\
from(bucket: {bucket})
  |> range(start: {range_start})
  |> filter(fn: (r) => r.type == "0000")
  |> filter(fn: (r) => r._field == "power" or r._field == "energy")
  |> last()
"""

_HUB_CIRCUIT_CHANNEL_RE = re.compile(
    r"^Energy\.Circuit\.(?P<name>.+)\.(?P<field>Power|Energy)$",
    re.IGNORECASE,
)
_HUB_FUZZY_MIN_SCORE = 0.90
_HUB_FUZZY_MIN_MARGIN = 0.08


def _flux_string(value: str) -> str:
    """Encode a bucket as a Flux string literal."""
    return json.dumps(str(value or DEFAULT_INFLUX_BUCKET).strip() or DEFAULT_INFLUX_BUCKET)


@dataclass(slots=True)
class InfluxQueryResult:
    """Structured Flux request outcome with legacy tuple iteration."""

    success: bool
    body_text: str = ""
    error_message: str = ""
    failure_class: str | None = None
    http_status: int | None = None

    @property
    def status(self) -> str:
        return "success" if self.success else (self.failure_class or "other_query")

    @property
    def classification(self) -> str | None:
        return self.failure_class

    @property
    def auth_failure(self) -> bool:
        return self.failure_class == "unauthorized_401"

    @property
    def permission_failure(self) -> bool:
        return self.failure_class == "forbidden_403"

    @property
    def org_failure(self) -> bool:
        return self.failure_class == "invalid_org"

    @property
    def bucket_failure(self) -> bool:
        return self.failure_class == "invalid_bucket"

    def __iter__(self):
        yield self.success
        yield self.body_text
        yield self.error_message
        yield self.auth_failure
        yield self.org_failure


@dataclass(slots=True)
class InfluxFetchResult:
    """Structured result from an InfluxDB fetch attempt."""

    success: bool
    data: Optional[dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    auth_failure: bool = False
    permission_failure: bool = False
    org_failure: bool = False
    bucket_failure: bool = False
    failure_class: Optional[str] = None
    query_window: Optional[str] = None


@dataclass(slots=True)
class CircuitDiscoveryResult:
    """Structured result from resolving the persisted circuit map."""

    success: bool
    circuit_map: Optional[dict[str, dict[str, Any]]] = None
    error_key: Optional[str] = None
    error_message: Optional[str] = None
    failure_class: Optional[str] = None
    http_status: Optional[int] = None
    query_window: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    downgraded_circuits: list[dict[str, Any]] = field(default_factory=list)
    websocket_inventory_used: bool = False
    resolution_sources: dict[str, str] = field(default_factory=dict)


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
) -> InfluxQueryResult:
    """POST a Flux query.

    Returns a structured result; iteration preserves the historical tuple.
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
                return InfluxQueryResult(False, error_message="Unauthorized (401) - InfluxDB rejected the token", failure_class="unauthorized_401", http_status=401)
            if resp.status == 403:
                return InfluxQueryResult(False, error_message="Forbidden (403) - token lacks permission for this query", failure_class="forbidden_403", http_status=403)
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
                bucket_failure = "bucket" in lowered and any(word in lowered for word in ("not found", "does not exist", "invalid"))
                failure_class = "invalid_org" if org_failure else "invalid_bucket" if bucket_failure else "other_query"
                return InfluxQueryResult(False, error_message=f"HTTP {resp.status}: {text[:200]}", failure_class=failure_class, http_status=resp.status)
            return InfluxQueryResult(True, body_text=text, http_status=200)
    except asyncio.TimeoutError:
        return InfluxQueryResult(False, error_message="InfluxDB query timed out after 10 s", failure_class="unreachable")
    except aiohttp.ClientError as exc:
        return InfluxQueryResult(False, error_message=f"Connection error: {exc}", failure_class="unreachable")


def _coerce_query_result(value) -> InfluxQueryResult:
    """Accept old test/integration tuple stubs while using structured results."""
    if isinstance(value, InfluxQueryResult):
        return value
    ok, body, error, auth_failure, org_failure = value
    failure_class = "unauthorized_401" if auth_failure else "invalid_org" if org_failure else None
    return InfluxQueryResult(ok, body, error, failure_class)


def _query_error_key(result: InfluxQueryResult) -> str:
    return {
        "unauthorized_401": "influx_auth_failed",
        "forbidden_403": "influx_permission_denied",
        "invalid_org": "influx_org_invalid",
        "invalid_bucket": "influx_bucket_invalid",
        "unreachable": "influx_unreachable",
    }.get(result.failure_class or "", "influx_query_failed")


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
    """Collapse Flux CSV rows into one dict per stable source/channel circuit."""
    by_circuit_key: dict[str, dict[str, Any]] = {}
    pbc_device_id = ""

    for row in _parse_influx_csv(circuit_text):
        savant_uuid = (row.get("savantUUID") or "").strip()
        measurement = (row.get("_measurement") or "").strip()
        channel = (row.get("channel") or "").strip()
        circuit_name = (row.get("name") or "").strip()
        device_type = (row.get("type") or "").strip().upper()
        uuidless_named_ct = (
            not savant_uuid
            and bool(measurement)
            and _is_usable_name(circuit_name)
            and device_type in _KNOWN_CT_DEVICE_TYPES
        )
        if (
            (not savant_uuid and not uuidless_named_ct)
            or not channel
            or savant_uuid == "savantUUID"
            or channel == "channel"
        ):
            continue

        if not pbc_device_id:
            pbc_device_id = measurement

        stable_source_id = savant_uuid or measurement
        circuit_key = build_circuit_key(stable_source_id, channel)
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
                # Preserve the source schema: an absent Savant UUID remains
                # absent. UUID-less named CTs use a separate stable source id
                # derived from the Influx measurement.
                "savantUUID": savant_uuid,
                "source_uid": stable_source_id,
                "identity_source": "savant_uuid" if savant_uuid else "measurement",
                "channel": channel,
                "name": circuit_name,
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


def _build_hub_circuit_rows(system_text: str) -> dict[str, dict[str, Any]]:
    """Extract measurement-only circuit rows from type=0000 hub channels.

    Current Savant hosts can emit relay circuit telemetry only as
    ``Energy.Circuit.<display name>.Power`` and ``.Energy`` hub channels.  The
    rows have no ``savantUUID`` and, importantly, contain no relay state or
    control data.
    """
    hub_rows: dict[str, dict[str, Any]] = {}
    for row in _parse_influx_csv(system_text):
        channel = str(row.get("channel") or "").strip()
        match = _HUB_CIRCUIT_CHANNEL_RE.match(channel)
        if not match:
            continue
        display_name = match.group("name").strip()
        if not _is_usable_name(display_name):
            continue
        field = match.group("field").lower()
        hub_row = hub_rows.setdefault(
            display_name,
            {
                "name": display_name,
                "raw_display_name": display_name,
                "channels": {},
            },
        )
        hub_row[field] = _safe_float(row.get("_value"))
        hub_row["channels"][field] = channel
    # Savant also publishes zero-filled Energy.Circuit placeholders for relay
    # loads that have no telemetry source. Treating those rows as live created
    # convincing but false 0 W / 0 kWh sensors. A hub circuit becomes a
    # measurement source only after either counter carries actual evidence.
    return {
        name: hub_row
        for name, hub_row in hub_rows.items()
        if any(
            field in hub_row and abs(_safe_float(hub_row.get(field))) > 0.0
            for field in ("power", "energy")
        )
    }


def _canonical_hub_match_name(value: str) -> str:
    """Normalize safe Savant label variants without collapsing distinct loads."""
    text = str(value or "").lower()
    # Preserve the base name for ordinary possessives (``Kylo's`` -> ``Kylo``).
    text = re.sub(r"(?<=[a-z0-9])[\u2019']s\b", "", text)
    tokens = _normalize_name(text).split()
    canonical_tokens: list[str] = []
    index = 0
    while index < len(tokens):
        # Savant alternates between A/C and AC in relay and hub labels.
        if tokens[index:index + 2] == ["a", "c"]:
            canonical_tokens.append("ac")
            index += 2
            continue
        token = tokens[index]
        canonical_tokens.append(
            {
                "up": "upstairs",
                "down": "downstairs",
                "detectors": "detector",
            }.get(token, token)
        )
        index += 1
    return " ".join(canonical_tokens)


def _stored_match_aliases(metadata: dict[str, Any]) -> set[str]:
    """Return every safe, canonical stored name usable for hub matching."""
    aliases: set[str] = set()
    for name_field in ("display_name", "influx_name", "relay_match_name"):
        name = str(metadata.get(name_field) or "").strip()
        canonical = _canonical_hub_match_name(name)
        if _is_usable_name(canonical):
            aliases.add(canonical)
    return aliases


def _mutually_unique_pairs(edges: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Return only globally one-to-one candidate edges, in stable order."""
    reverse: dict[str, set[str]] = defaultdict(set)
    for hub_name, circuit_keys in edges.items():
        for circuit_key in circuit_keys:
            reverse[circuit_key].add(hub_name)
    return [
        (hub_name, next(iter(circuit_keys)))
        for hub_name, circuit_keys in sorted(edges.items())
        if len(circuit_keys) == 1 and len(reverse[next(iter(circuit_keys))]) == 1
    ]


def _resolve_hub_circuit_matches(
    hub_rows: dict[str, dict[str, Any]],
    stored_metadata: dict[str, dict[str, Any]],
    detailed_circuit_keys: set[str],
) -> dict[str, tuple[str, str]]:
    """Resolve hub labels with strict, globally one-to-one matching tiers.

    Every tier considers the complete stored map, including detailed live rows,
    so a partial detailed multi-leg circuit cannot make a previously ambiguous
    hub label appear unique. ``detailed_circuit_keys`` are allowed to block a
    match but are never replaced by aggregate hub telemetry.
    """
    aliases_by_key = {
        circuit_key: _stored_match_aliases(metadata)
        for circuit_key, metadata in stored_metadata.items()
    }
    hub_names = {
        hub_key: _canonical_hub_match_name(str(hub_row.get("name") or ""))
        for hub_key, hub_row in hub_rows.items()
    }
    unresolved = {hub_key for hub_key, name in hub_names.items() if _is_usable_name(name)}
    detailed_blockers = set(detailed_circuit_keys)
    # Hub-resolved keys are lower-confidence than detailed rows and can be
    # removed from later tiers. Detailed blockers deliberately remain in every
    # candidate edge so a partial UUID snapshot continues to block a hub
    # aggregate from filling another leg.
    hub_resolved_keys: set[str] = set()
    resolved: dict[str, tuple[str, str]] = {}

    def apply_pairs(edges: dict[str, set[str]], source: str) -> None:
        for hub_key, circuit_key in _mutually_unique_pairs(edges):
            unresolved.discard(hub_key)
            if circuit_key not in detailed_blockers:
                resolved[hub_key] = (circuit_key, source)
                hub_resolved_keys.add(circuit_key)

    # Tier 1: exact canonical aliases. This covers harmless punctuation,
    # possessive, A/C, and up/downstairs variations without approximation.
    exact_edges = {
        hub_key: {
            circuit_key
            for circuit_key, aliases in aliases_by_key.items()
            if circuit_key not in hub_resolved_keys
            if hub_name in aliases
        }
        for hub_key, hub_name in hub_names.items()
        if hub_key in unresolved
    }
    apply_pairs(exact_edges, "hub_exact")

    # Tier 2a: token-set equality handles harmless word reordering while
    # keeping a shorter base label from being confused with its "Blower"
    # sibling.
    equal_token_edges: dict[str, set[str]] = {}
    for hub_key in sorted(unresolved):
        hub_tokens = set(hub_names[hub_key].split())
        if not hub_tokens:
            continue
        equal_token_edges[hub_key] = {
            circuit_key
            for circuit_key, aliases in aliases_by_key.items()
            if circuit_key not in hub_resolved_keys
            if any(hub_tokens == set(alias.split()) for alias in aliases)
        }
    apply_pairs(equal_token_edges, "hub_token_set")

    # Tier 2b: a whole token set contained in the other label. This accepts
    # label extensions such as "Patio TV Kitchen" but only under the same
    # global one-to-one rule.
    containment_edges: dict[str, set[str]] = {}
    for hub_key in sorted(unresolved):
        hub_tokens = set(hub_names[hub_key].split())
        if not hub_tokens:
            continue
        containment_edges[hub_key] = {
            circuit_key
            for circuit_key, aliases in aliases_by_key.items()
            if circuit_key not in hub_resolved_keys
            if any(
                hub_tokens < set(alias.split()) or set(alias.split()) < hub_tokens
                for alias in aliases
            )
        }
    apply_pairs(containment_edges, "hub_token_containment")

    # Tier 3: only high-confidence, mutual fuzzy best matches with a clear
    # score gap. It recovers harmless spelling/truncation variants while
    # leaving near matches unavailable instead of guessing.
    score_matrix: dict[str, dict[str, float]] = {}
    for hub_key in sorted(unresolved):
        hub_name = hub_names[hub_key]
        score_matrix[hub_key] = {
            circuit_key: max(
                (SequenceMatcher(None, hub_name, alias).ratio() for alias in aliases),
                default=0.0,
            )
            for circuit_key, aliases in aliases_by_key.items()
            if circuit_key not in hub_resolved_keys
        }

    def unique_best(scores: dict[str, float]) -> str | None:
        ranked = sorted(((score, key) for key, score in scores.items()), reverse=True)
        if not ranked or ranked[0][0] < _HUB_FUZZY_MIN_SCORE:
            return None
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < _HUB_FUZZY_MIN_MARGIN:
            return None
        return ranked[0][1]

    fuzzy_hub_best = {
        hub_key: unique_best(scores)
        for hub_key, scores in score_matrix.items()
    }
    fuzzy_circuit_keys = next(iter(score_matrix.values()), {})
    fuzzy_stored_best = {
        circuit_key: unique_best(
            {hub_key: scores[circuit_key] for hub_key, scores in score_matrix.items()}
        )
        for circuit_key in fuzzy_circuit_keys
    }
    for hub_key, circuit_key in sorted(fuzzy_hub_best.items()):
        if circuit_key is None or fuzzy_stored_best.get(circuit_key) != hub_key:
            continue
        unresolved.discard(hub_key)
        if circuit_key not in detailed_blockers:
            resolved[hub_key] = (circuit_key, "hub_fuzzy")
            hub_resolved_keys.add(circuit_key)

    return resolved


def _build_hub_present_demand(
    circuit_key: str,
    metadata: dict[str, Any],
    hub_row: dict[str, Any],
) -> dict[str, Any]:
    """Build a stored-circuit live row from measurement-only hub telemetry.

    Live Savant evidence establishes that hub circuit counters are Wh (unlike
    detailed relay rows, which use mWh), so publish kWh with an explicit
    divisor while retaining the raw value for diagnostics.
    """
    savant_uuid, stored_channel = split_circuit_key(circuit_key)
    savant_uuid = str(metadata.get("savant_uuid") or savant_uuid).strip()
    stored_channel = str(metadata.get("channel") or stored_channel).strip()
    role = str(metadata.get("role") or "ct_sensor").strip().lower()
    if role not in ("relay", "ct_sensor"):
        role = "ct_sensor"

    demand: dict[str, Any] = {
        "uid": circuit_key,
        "circuit_key": circuit_key,
        "base_uid": savant_uuid or circuit_key,
        "name": metadata.get("display_name") or metadata.get("influx_name") or hub_row["name"],
        "influx_name": metadata.get("influx_name") or hub_row["name"],
        "channel": stored_channel,
        "classification": metadata.get("classification", ""),
        "type": metadata.get("type", ""),
        "role": role,
        # Stored relay metadata must not make aggregate telemetry controllable.
        "has_relay": False,
        "relay_match_name": metadata.get("relay_match_name"),
        "relay_match_source": metadata.get("role_source"),
        "power": hub_row.get("power"),
        "energy_raw": hub_row.get("energy"),
        "energy_scale_divisor": 1_000,
        "energy_scale_confidence": 1.0,
        "energy_scale_status": "hub_wh_to_kwh",
        "energy_source": "hub_aggregate",
        "measurement_source": "hub_channel",
        "hub_match_source": hub_row.get("match_source"),
        "hub_channels": dict(hub_row.get("channels") or {}),
        "legacy_uid": metadata.get("legacy_uid", circuit_key),
        "legacy_base_uid": metadata.get("legacy_base_uid") or savant_uuid or circuit_key,
    }
    # Avoid adding a made-up zero when one of the two hub measurements is
    # absent. The field is live only when Influx actually returned it.
    if "power" not in hub_row:
        demand.pop("power")
    if "energy" in hub_row:
        demand["energy"] = _safe_float(hub_row["energy"]) / 1_000.0
    else:
        demand.pop("energy_raw")
    return demand


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


def _normalize_inventory_device(
    raw_device: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any] | None:
    """Normalize a relay inventory record from SEM companion or websocket payloads."""
    uid = str(
        raw_device.get("uid")
        or raw_device.get("UID")
        or raw_device.get("relay_uid")
        or raw_device.get("relayUid")
        or raw_device.get("device_uid")
        or raw_device.get("deviceUid")
        or ""
    ).strip()
    load_name = str(
        raw_device.get("load_name")
        or raw_device.get("LoadName")
        or raw_device.get("name")
        or raw_device.get("Name")
        or ""
    ).strip()
    device_label = str(
        raw_device.get("device_label")
        or raw_device.get("DeviceLabel")
        or raw_device.get("label")
        or raw_device.get("Label")
        or ""
    ).strip()

    if not uid:
        return None

    normalized: dict[str, Any] = {
        "uid": uid,
        "load_name": load_name,
        "device_label": device_label,
        "model": str(
            raw_device.get("model")
            or raw_device.get("Model")
            or raw_device.get("DeviceModelDescription")
            or ""
        ).strip(),
        "slot_number": raw_device.get("slot_number", raw_device.get("SlotNumber")),
        "start_address": raw_device.get("start_address", raw_device.get("StartAddress")),
        "source": source,
    }

    if load_name or device_label:
        return normalized

    # Some websocket payloads only expose the UID alongside opaque status fields.
    # Keep those records for diagnostics and future matching heuristics, but they
    # will not match by name until richer metadata is available.
    normalized["raw_device"] = dict(raw_device)
    return normalized


def _extract_websocket_device_candidates(payload: Any, *, source: str) -> list[dict[str, Any]]:
    """Pull device-like records out of a websocket payload."""
    candidates: list[dict[str, Any]] = []

    def _visit(node: Any) -> None:
        if isinstance(node, dict):
            normalized = _normalize_inventory_device(node, source=source)
            if normalized is not None:
                candidates.append(normalized)

            for key in ("Devices", "devices", "Inventory", "inventory", "Status", "status", "result", "Result", "data", "Data", "payload", "Payload", "contents", "Contents", "messages", "Messages"):
                child = node.get(key)
                if isinstance(child, (dict, list, str)):
                    _visit(child)

            for value in node.values():
                if isinstance(value, (dict, list)):
                    _visit(value)
                elif isinstance(value, str):
                    _visit(value)
            return

        if isinstance(node, list):
            for item in node:
                _visit(item)
            return

        if not isinstance(node, str):
            return

        text = node.strip()
        if not text:
            return

        if text.startswith("{") or text.startswith("["):
            try:
                _visit(json.loads(text))
                return
            except json.JSONDecodeError:
                pass

        if text.startswith("CON,") or "LoadName=" in text or "DeviceLabel=" in text or "UID=" in text:
            raw_device: dict[str, Any] = {"raw_message": text}
            if text.startswith("CON,"):
                parts = [part.strip() for part in text.split(",")]
                if len(parts) >= 3:
                    raw_device["pbc_device_id"] = parts[1]
                    raw_device["uid"] = parts[2]
                if len(parts) >= 4:
                    raw_device["state"] = parts[3]
                if len(parts) >= 5:
                    raw_device["signal"] = parts[4]
            else:
                for segment in re.split(r"[;| ]+", text):
                    if "=" not in segment:
                        continue
                    key, value = segment.split("=", 1)
                    raw_device[key.strip()] = value.strip().strip('"')
            normalized = _normalize_inventory_device(raw_device, source=source)
            if normalized is not None:
                candidates.append(normalized)

    _visit(payload)

    # Deduplicate by UID while preserving the first rich record we saw.
    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        uid = str(candidate.get("uid", "")).strip()
        if uid and uid not in deduped:
            deduped[uid] = candidate

    return list(deduped.values())


def _build_receive_letter_command(target_id: str, command_type: str) -> dict[str, Any]:
    """Build a best-effort SignalR ReceiveLetter command."""
    return {
        "type": 1,
        "target": "ReceiveLetter",
        "arguments": [
            target_id,
            {
                "deviceId": target_id,
                "regarding": "command",
                "contents": {
                    "address": "",
                    "command": {"commandType": command_type},
                },
                "timestamp": "1970-01-01T00:00:00.000Z",
            },
        ],
    }


async def fetch_pbc_websocket_devices(
    pbc_host: str,
    pbc_port: int = 8480,
    pbc_device_id: str = "",
    timeout_seconds: float = 6.0,
) -> tuple[bool, list[dict[str, Any]]]:
    """Best-effort websocket inventory probe for relay-capable circuits.

    The websocket path is intentionally discovery-only. It attempts to coerce the
    hub into emitting its UID-bearing inventory / status payloads, then harvests
    any device-like records that include a UID plus one of the human-readable
    naming fields used for relay matching.
    """
    websocket_paths = (
        f"ws://{pbc_host}:{pbc_port}/localhub",
        f"ws://{pbc_host}:{pbc_port}/",
    )
    trigger_commands = ("GET_VERSION", "SET_SEND_ENERGY_LETTERS=1", "GET_PBC_READY")

    for websocket_url in websocket_paths:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    websocket_url,
                    protocols=("savant_protocol",),
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                    heartbeat=15,
                ) as ws:
                    _LOGGER.debug("PBC websocket connected: %s", websocket_url)

                    try:
                        await ws.send_str(json.dumps({"protocol": "json", "version": 1}) + "\x1e")
                    except Exception:
                        pass

                    if pbc_device_id:
                        for command_type in trigger_commands:
                            try:
                                await ws.send_str(
                                    json.dumps(_build_receive_letter_command(pbc_device_id, command_type))
                                    + "\x1e"
                                )
                                await asyncio.sleep(0.1)
                            except Exception:
                                break

                    raw_payloads: list[Any] = []
                    deadline = asyncio.get_running_loop().time() + timeout_seconds
                    while True:
                        remaining = deadline - asyncio.get_running_loop().time()
                        if remaining <= 0:
                            break
                        try:
                            message = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 1.0))
                        except asyncio.TimeoutError:
                            break

                        if message.type == aiohttp.WSMsgType.TEXT:
                            text = message.data.strip()
                            if not text:
                                continue
                            for frame in text.split("\x1e"):
                                frame = frame.strip()
                                if not frame:
                                    continue
                                try:
                                    raw_payloads.append(json.loads(frame))
                                except json.JSONDecodeError:
                                    raw_payloads.append(frame)
                        elif message.type == aiohttp.WSMsgType.BINARY:
                            try:
                                raw_payloads.append(message.data.decode("utf-8", errors="ignore"))
                            except Exception:
                                continue
                        elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR}:
                            break

                    devices: list[dict[str, Any]] = []
                    for payload in raw_payloads:
                        devices.extend(_extract_websocket_device_candidates(payload, source="websocket"))

                    if devices:
                        _LOGGER.debug(
                            "PBC websocket inventory returned %d device candidate(s) from %s",
                            len(devices),
                            websocket_url,
                        )
                        return True, devices
        except Exception as exc:
            _LOGGER.debug(
                "PBC websocket inventory probe failed for %s:%d via %s: %s",
                pbc_host,
                pbc_port,
                websocket_url,
                exc,
            )

    return False, []


def _match_sem_device(
    circuit_name: str,
    sem_devices: list[dict[str, Any]],
    by_label: dict[str, dict[str, Any]],
    by_load_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    """Resolve a circuit name to one SEM relay device."""
    normalized_name = _normalize_name(circuit_name)
    if normalized_name in _INVALID_NAME_TOKENS:
        return None, None, []

    matched = by_label.get(normalized_name)
    if matched:
        return matched, "device_label", []

    matched = by_load_name.get(normalized_name)
    if matched:
        return matched, "load_name", []

    alias_candidates: list[tuple[dict[str, Any], str, str]] = []
    seen_uids: set[str] = set()
    for device in sem_devices:
        uid = str(device.get("uid", "")).strip()
        if not uid or uid in seen_uids:
            continue
        for field_name in ("device_label", "load_name"):
            candidate_name = str(device.get(field_name, "")).strip()
            normalized_candidate = _normalize_name(candidate_name)
            if not normalized_candidate or normalized_candidate in _INVALID_NAME_TOKENS:
                continue
            shorter = min(len(normalized_candidate), len(normalized_name))
            if shorter < 5:
                continue
            if normalized_candidate in normalized_name or normalized_name in normalized_candidate:
                alias_candidates.append((device, field_name, candidate_name))
                seen_uids.add(uid)
                break

    if len(alias_candidates) == 1:
        device, field_name, _candidate_name = alias_candidates[0]
        return device, f"{field_name}_alias", []

    return None, None, [candidate_name for _device, _field_name, candidate_name in alias_candidates]


def _describe_circuit_downgrade(
    circuit_name: str,
    channel: str,
    device_type: str,
    near_matches: list[str],
) -> str:
    """Format a human-readable warning for a downgraded relay candidate."""
    base = (
        f"{circuit_name or '<unnamed>'} (channel {channel or '?'}, type {device_type or '<unknown>'}) "
        "could not be matched confidently to a Savant relay UID, so it was saved as a CT/read-only sensor."
    )
    if near_matches:
        return f"{base} Near matches: {', '.join(near_matches[:5])}."
    return f"{base}"


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
        source_uid = str(metadata.get("source_uid", "")).strip() or savant_uuid
        channel = str(metadata.get("channel", "")).strip()
        metadata["legacy_uid"] = (
            f"{source_uid}.{channel}"
            if source_uid and channel
            else metadata["circuit_key"]
        )
        metadata["legacy_base_uid"] = source_uid or metadata["circuit_key"]


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
    influx_bucket: str = DEFAULT_INFLUX_BUCKET,
) -> InfluxFetchResult:
    """Fetch the latest circuit and system data from InfluxDB.

    Returns an InfluxFetchResult whose .data dict matches the presentDemands
    shape expected by the rest of the integration, plus a system_data dict for
    hub-level sensors (totals, groups, battery, solar).
    """
    try:
        async with aiohttp.ClientSession() as session:
            circuit_result = _coerce_query_result(await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _CIRCUIT_QUERY.format(range_start=range_start, bucket=_flux_string(influx_bucket)),
            ))
            ok = circuit_result.success
            circuit_text = circuit_result.body_text
            err = circuit_result.error_message
            auth_failure = circuit_result.auth_failure
            org_failure = circuit_result.org_failure
            if not ok:
                return InfluxFetchResult(
                    success=False,
                    error_type=_query_error_key(circuit_result),
                    error_message=err,
                    auth_failure=auth_failure,
                    permission_failure=circuit_result.permission_failure,
                    org_failure=org_failure,
                    bucket_failure=circuit_result.bucket_failure,
                    failure_class=circuit_result.failure_class,
                    query_window=range_start,
                )

            # System query failure is non-fatal — degrade gracefully.
            system_result = _coerce_query_result(await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _SYSTEM_QUERY.format(range_start=range_start, bucket=_flux_string(influx_bucket)),
            ))
            ok_sys, system_text = system_result.success, system_result.body_text
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

    # Savant emits zero-filled placeholders for unsupported system channels as
    # well as circuit channels. Publish a system channel after it has produced
    # nonzero evidence, then retain legitimate zero states for the rest of this
    # coordinator lifetime once that capability has been established.
    system_capabilities = scale_state.setdefault("__system_capabilities__", {})
    system_data: dict[str, float] = {}
    if ok_sys:
        for row in _parse_influx_csv(system_text):
            channel = row.get("channel", "").strip()
            if channel:
                value = _safe_float(row.get("_value"))
                if abs(value) > 0.0:
                    system_capabilities[channel] = True
                if system_capabilities.get(channel):
                    system_data[channel] = value
    hub_circuit_rows = _build_hub_circuit_rows(system_text) if ok_sys else {}

    stored_metadata = circuit_metadata or {}

    present_demands: list[dict[str, Any]] = []
    unknown_circuit_keys: list[str] = []
    unknown_circuits: list[dict[str, str]] = []
    seen_circuit_keys: set[str] = set()
    for circuit_key, circuit in by_circuit_key.items():
        seen_circuit_keys.add(circuit_key)
        metadata = stored_metadata.get(circuit_key)
        if metadata is None:
            unknown_circuit_keys.append(circuit_key)
            unknown_circuits.append(
                {
                    "circuit_key": circuit_key,
                    "display_name": str(circuit.get("name", "")).strip()
                    or f"Circuit {circuit.get('channel', '?')}",
                    "channel": str(circuit.get("channel", "")).strip(),
                    "type": str(circuit.get("type", "")).strip(),
                }
            )
            # A named, known CT type is safe to expose as a read-only sensor
            # before reconfigure persists it. It can never receive relay
            # control metadata. Other unknown rows remain excluded.
            if not _is_known_ct_circuit(
                circuit.get("classification", ""), circuit.get("type", "")
            ):
                continue
            source_uid = str(circuit.get("source_uid", "")).strip() or str(
                circuit.get("savantUUID", "")
            ).strip() or circuit_key
            channel = str(circuit.get("channel", "")).strip()
            metadata = {
                "circuit_key": circuit_key,
                "savant_uuid": str(circuit.get("savantUUID", "")).strip(),
                "source_uid": source_uid,
                "channel": channel,
                "type": str(circuit.get("type", "")).strip(),
                "role": "ct_sensor",
                "relay_uid": "",
                "display_name": str(circuit.get("name", "")).strip()
                or f"CT Channel {channel or '?'}",
                "influx_name": str(circuit.get("name", "")).strip(),
                "legacy_uid": f"{source_uid}.{channel}" if channel else circuit_key,
                "legacy_base_uid": source_uid,
                "role_source": "known_ct_runtime",
                "resolution_source": "known_ct_runtime",
            }

        savant_uuid = str(circuit.get("savantUUID", "")).strip()
        source_uid = str(circuit.get("source_uid", "")).strip() or savant_uuid
        base_uid, _ab_side = parse_uid(source_uid)
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
                "uid": circuit_key,   # Stable entity key = (source identity, channel)
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

    # Detailed savantUUID rows are authoritative. The resolver is globally
    # one-to-one across each matching tier, so aggregate labels never fill a
    # missing leg or an ambiguous relay identity.
    hub_matches = _resolve_hub_circuit_matches(
        hub_circuit_rows,
        stored_metadata,
        seen_circuit_keys,
    )
    for hub_key, (circuit_key, match_source) in sorted(hub_matches.items()):
        metadata = stored_metadata[circuit_key]
        hub_row = dict(hub_circuit_rows[hub_key])
        hub_row["match_source"] = match_source
        present_demands.append(_build_hub_present_demand(circuit_key, metadata, hub_row))
        seen_circuit_keys.add(circuit_key)

    if not by_circuit_key and not hub_circuit_rows:
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

    _LOGGER.debug(
        "InfluxDB fetch: %d circuits (%d hub synthesized), %d system channels",
        len(present_demands),
        sum(1 for demand in present_demands if demand.get("measurement_source") == "hub_channel"),
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
                "inventory_status": "partial" if missing_circuit_keys else "complete",
                "identity_inventory_status": "partial" if missing_circuit_keys else "complete",
                "inventory_authority": "live_snapshot",
                "inventory_authoritative": not bool(missing_circuit_keys),
                "unknown_circuit_keys": sorted(unknown_circuit_keys),
                "unknown_circuits": sorted(
                    unknown_circuits,
                    key=lambda circuit: circuit["circuit_key"],
                ),
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
    influx_bucket: str = DEFAULT_INFLUX_BUCKET,
) -> InfluxFetchResult:
    """Fetch a snapshot, widening the lookback window before failing."""
    last_empty_result: InfluxFetchResult | None = None
    first_live_result: InfluxFetchResult | None = None
    inventory_union: dict[str, dict[str, Any]] = {}

    def identity_only(demands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only circuit identity when a historical window fills inventory."""
        identity_keys = {
            "uid", "circuit_key", "base_uid", "name", "influx_name", "channel",
            "classification", "type", "role", "relay_uid", "has_relay",
            "relay_match_name", "relay_match_source", "capacity", "legacy_uid",
            "legacy_base_uid",
        }
        return [{key: value for key, value in item.items() if key in identity_keys}
                for item in demands if isinstance(item, dict)]
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
            influx_bucket=influx_bucket,
        )
        if result.success and result.data is not None:
            status = result.data.get("circuit_map_status", {})
            if first_live_result is None:
                # The first successful query is the only authority for live
                # measurements. Wider windows may fill identity inventory,
                # but must never replace presentDemands values.
                first_live_result = result
            for item in result.data.get("presentDemands") or []:
                if isinstance(item, dict):
                    key = str(item.get("circuit_key") or item.get("uid") or "")
                    if key:
                        inventory_union[key] = identity_only([item])[0]
            if not status.get("missing_circuit_keys"):
                _LOGGER.debug(
                    "InfluxDB snapshot attempt succeeded for org %s using %s",
                    influx_org or "<unset>",
                    range_start,
                )
                if first_live_result is result:
                    result.data.setdefault("circuit_map_status", {})["inventory_status"] = "complete"
                    result.data["circuit_map_status"]["identity_inventory_status"] = "complete"
                    result.data["circuit_map_status"]["inventory_authority"] = "live_snapshot"
                    return result
                first_live_result.data["inventoryDemands"] = list(inventory_union.values())
                # `inventory_status` describes the live measurement window.
                # A historical completion is identity-only and must not make a
                # partial live snapshot appear authoritative to consumers.
                first_live_result.data["circuit_map_status"]["identity_inventory_status"] = "complete"
                first_live_result.data["circuit_map_status"]["inventory_authoritative"] = False
                first_live_result.data["circuit_map_status"]["inventory_authority"] = "historical_identity_only"
                return first_live_result
            # Keep searching for a complete identity inventory. The live
            # result remains the narrow-window result captured above.
            inventory = result.data.get("presentDemands") or []
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
    if first_live_result is not None:
        status = first_live_result.data.setdefault("circuit_map_status", {})
        status["inventory_status"] = "partial"
        status["identity_inventory_status"] = "partial"
        status["inventory_authoritative"] = False
        status["inventory_authority"] = "live_snapshot_only"
        first_live_result.data["inventoryDemands"] = list(inventory_union.values())
        return first_live_result
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


def build_measurement_bootstrap_inventory(
    snapshot_data: dict[str, Any] | None,
    circuit_map: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return stable identity shells for measurement entities only.

    Stored circuit-map identities restore entities removed during a transient
    partial inventory. Historical `inventoryDemands` may supplement them, but
    no historical value fields are ever copied into live measurements.
    """
    identities: dict[str, dict[str, Any]] = {}
    for circuit_key, metadata in sorted((circuit_map or {}).items()):
        if not isinstance(metadata, dict):
            continue
        uid = str(metadata.get("circuit_key") or circuit_key).strip()
        if not uid:
            continue
        identities[uid] = {
            "uid": uid,
            "circuit_key": uid,
            "base_uid": str(
                metadata.get("source_uid") or metadata.get("savant_uuid") or uid
            ),
            "name": metadata.get("display_name") or metadata.get("influx_name") or f"Circuit {metadata.get('channel', '?')}",
            "influx_name": metadata.get("influx_name", ""),
            "channel": metadata.get("channel", ""),
            "classification": metadata.get("classification", ""),
            "type": metadata.get("type", ""),
            "role": metadata.get("role", "ct_sensor"),
            "relay_uid": metadata.get("relay_uid", ""),
            "has_relay": False,  # historical identities never authorize control
            "capacity": metadata.get("capacity", 0),
            "legacy_uid": metadata.get("legacy_uid", uid),
            "legacy_base_uid": metadata.get("legacy_base_uid")
            or metadata.get("source_uid")
            or metadata.get("savant_uuid")
            or uid,
        }
    for item in (snapshot_data or {}).get("inventoryDemands") or []:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("uid") or item.get("circuit_key") or "").strip()
        if not uid:
            continue
        shell = {key: value for key, value in item.items() if key not in {
            "power", "current", "voltage", "energy", "energy_raw", "percentCommanded", "flags",
            "energy_scale_divisor", "energy_scale_confidence", "energy_scale_status",
        }}
        shell["uid"] = uid
        shell["has_relay"] = False
        identities.setdefault(uid, shell)
    return list(identities.values())


async def discover_circuit_metadata(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    pbc_websocket_port: int = 8480,
    range_start: str = "-2m",
    influx_bucket: str = DEFAULT_INFLUX_BUCKET,
) -> CircuitDiscoveryResult:
    """Resolve relay/CT identity once during setup or reconfigure."""
    try:
        async with aiohttp.ClientSession() as session:
            circuit_result = _coerce_query_result(await _post_flux(
                session,
                influx_url,
                influx_token,
                influx_org,
                _CIRCUIT_QUERY.format(range_start=range_start, bucket=_flux_string(influx_bucket)),
            ))
            ok, circuit_text, err = circuit_result.success, circuit_result.body_text, circuit_result.error_message
            auth_failure, org_failure = circuit_result.auth_failure, circuit_result.org_failure
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
            error_key=_query_error_key(circuit_result),
            error_message=err,
            failure_class=circuit_result.failure_class,
            http_status=circuit_result.http_status,
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
    warnings: list[str] = []
    downgraded_circuits: list[dict[str, Any]] = []
    resolution_sources: dict[str, str] = {}
    unresolved_relay_candidates: list[dict[str, Any]] = []

    def _build_circuit_metadata_entry(
        *,
        circuit_key: str,
        circuit: dict[str, Any],
        role: str,
        role_source: str,
        matched_device: dict[str, Any] | None = None,
        match_source: str | None = None,
        alias_candidates: list[str] | None = None,
        downgraded_from_relay: bool = False,
    ) -> dict[str, Any]:
        savant_uuid = str(circuit.get("savantUUID", "")).strip()
        source_uid = str(circuit.get("source_uid", "")).strip() or savant_uuid
        relay_uid = matched_device.get("uid", "") if matched_device and role == "relay" else ""
        relay_match_name = None
        if matched_device and role == "relay":
            relay_match_name = (
                matched_device.get("device_label")
                if match_source == "device_label"
                else matched_device.get("load_name")
                if match_source == "load_name"
                else matched_device.get("device_label")
                or matched_device.get("load_name")
            )

        return {
            "circuit_key": circuit_key,
            "savant_uuid": savant_uuid,
            "source_uid": source_uid,
            "channel": str(circuit.get("channel", "")).strip(),
            "type": str(circuit.get("type", "")).strip(),
            "role": role,
            "relay_uid": relay_uid,
            "relay_candidate_uid": relay_uid,
            "display_name": (
                matched_device.get("load_name")
                or matched_device.get("device_label")
                or str(circuit.get("name", "")).strip()
                or f"Circuit {circuit.get('channel', '?')}"
            )
            if matched_device and role == "relay"
            else str(circuit.get("name", "")).strip() or f"Circuit {circuit.get('channel', '?')}",
            "influx_name": str(circuit.get("name", "")).strip(),
            "legacy_uid": "",
            "legacy_base_uid": "",
            "role_source": role_source,
            "resolution_source": role_source,
            "relay_match_name": relay_match_name,
            "relay_match_candidates": alias_candidates or [],
            "downgraded_from_relay": downgraded_from_relay,
        }

    def _finalize_relay_downgrade(
        *,
        circuit_key: str,
        circuit: dict[str, Any],
        alias_candidates: list[str],
    ) -> None:
        circuit_name = str(circuit.get("name", "")).strip()
        warning = _describe_circuit_downgrade(
            circuit_name,
            str(circuit.get("channel", "")).strip(),
            str(circuit.get("type", "")).strip(),
            alias_candidates,
        )
        warnings.append(warning)
        downgraded_circuits.append(
            {
                "circuit_key": circuit_key,
                "circuit_name": circuit_name or f"Circuit {circuit.get('channel', '?')}",
                "channel": str(circuit.get("channel", "")).strip(),
                "type": str(circuit.get("type", "")).strip(),
                "classification": str(circuit.get("classification", "")).strip(),
                "warning": warning,
                "near_matches": alias_candidates,
            }
        )
        circuit_map[circuit_key] = _build_circuit_metadata_entry(
            circuit_key=circuit_key,
            circuit=circuit,
            role="ct_sensor",
            role_source="relay_downgraded_ct",
            alias_candidates=alias_candidates,
            downgraded_from_relay=True,
        )
        resolution_sources[circuit_key] = "relay_downgraded_ct"

    for circuit_key, circuit in sorted(
        by_circuit_key.items(),
        key=lambda item: (_safe_int_channel(item[1].get("channel")), str(item[1].get("name", ""))),
    ):
        circuit_name = str(circuit.get("name", "")).strip()
        is_known_ct = _is_known_ct_circuit(circuit.get("classification", ""), circuit.get("type", ""))
        type_code = str(circuit.get("type", "")).strip().upper()
        if is_known_ct:
            role_source = "known_ct_type" if type_code in _KNOWN_CT_DEVICE_TYPES else "ct_tags"
            circuit_map[circuit_key] = _build_circuit_metadata_entry(
                circuit_key=circuit_key,
                circuit=circuit,
                role="ct_sensor",
                role_source=role_source,
            )
            resolution_sources[circuit_key] = role_source
            continue

        matched_device, match_source, alias_candidates = _match_sem_device(
            circuit_name,
            sem_devices,
            by_label,
            by_load_name,
        )
        if matched_device is not None:
            role_source = f"sem_{match_source}" if match_source else "relay_exact"
            circuit_map[circuit_key] = _build_circuit_metadata_entry(
                circuit_key=circuit_key,
                circuit=circuit,
                role="relay",
                role_source=role_source,
                matched_device=matched_device,
                match_source=match_source,
                alias_candidates=alias_candidates,
            )
            resolution_sources[circuit_key] = role_source
            continue

        unresolved_relay_candidates.append(
            {
                "circuit_key": circuit_key,
                "circuit": circuit,
                "alias_candidates": alias_candidates,
            }
        )

    websocket_devices: list[dict[str, Any]] = []
    if unresolved_relay_candidates:
        ws_ok, websocket_devices = await fetch_pbc_websocket_devices(
            sem_host=sem_host,
            pbc_port=pbc_websocket_port,
            pbc_device_id=_pbc_device_id,
        )
        if ws_ok and websocket_devices:
            _LOGGER.info(
                "PBC websocket inventory returned %d candidate device(s) for fallback relay matching",
                len(websocket_devices),
            )
            for unresolved in unresolved_relay_candidates:
                circuit_key = unresolved["circuit_key"]
                circuit = unresolved["circuit"]
                circuit_name = str(circuit.get("name", "")).strip()
                matched_device, match_source, alias_candidates = _match_sem_device(
                    circuit_name,
                    websocket_devices,
                    _build_sem_index(websocket_devices, "device_label"),
                    _build_sem_index(websocket_devices, "load_name"),
                )
                if matched_device is not None:
                    role_source = f"websocket_{match_source}" if match_source else "websocket_match"
                    circuit_map[circuit_key] = _build_circuit_metadata_entry(
                        circuit_key=circuit_key,
                        circuit=circuit,
                        role="relay",
                        role_source=role_source,
                        matched_device=matched_device,
                        match_source=match_source,
                        alias_candidates=alias_candidates,
                    )
                    resolution_sources[circuit_key] = role_source
                    continue

                _finalize_relay_downgrade(
                    circuit_key=circuit_key,
                    circuit=circuit,
                    alias_candidates=unresolved["alias_candidates"],
                )
        else:
            for unresolved in unresolved_relay_candidates:
                _finalize_relay_downgrade(
                    circuit_key=unresolved["circuit_key"],
                    circuit=unresolved["circuit"],
                    alias_candidates=unresolved["alias_candidates"],
                )

    _assign_legacy_identity(circuit_map)
    return CircuitDiscoveryResult(
        success=True,
        circuit_map=circuit_map,
        warnings=warnings,
        downgraded_circuits=downgraded_circuits,
        websocket_inventory_used=bool(websocket_devices),
        resolution_sources=resolution_sources,
        query_window=range_start,
    )


async def discover_circuit_metadata_with_backfill(
    influx_url: str,
    influx_token: str,
    influx_org: str,
    sem_host: str = "192.168.1.108",
    sem_port: int = 8644,
    pbc_websocket_port: int = 8480,
    backfill_windows: tuple[str, ...] = _BACKFILL_WINDOWS,
    influx_bucket: str = DEFAULT_INFLUX_BUCKET,
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
            pbc_websocket_port=pbc_websocket_port,
            range_start=range_start,
            influx_bucket=influx_bucket,
        )
        if result.success and result.circuit_map:
            return result
        last_result = result
        if result.error_key in {
            "org_auth_failed",
            "org_discovery_failed",
            "influx_auth_failed",
            "influx_permission_denied",
            "influx_org_invalid",
            "influx_bucket_invalid",
            "influx_unreachable",
            "influx_query_failed",
            "sem_companion_failed",
        }:
            return result
    return last_result or CircuitDiscoveryResult(
        success=False,
        error_key="circuit_discovery_failed",
        error_message="Circuit discovery did not return any data.",
        query_window=backfill_windows[-1] if backfill_windows else None,
    )
