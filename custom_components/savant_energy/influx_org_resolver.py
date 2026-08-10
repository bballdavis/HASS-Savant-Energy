"""Discover and score InfluxDB organizations for Savant Energy."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

from .const import DEFAULT_INFLUX_BUCKET

from .ssh_helper import InfluxHostMetadata

_LOGGER = logging.getLogger(__name__)

_EXPECTED_FIELDS = ("power", "current", "voltage", "energy")
_PLAUSIBLE_FIELDS = ("power", "energy")
_PROBE_WINDOWS = ("-15m", "-24h", "-7d")
_BUCKET_SCAN_PREFIXES = ("localHub",)


def _probe_query(range_start: str, bucket: str = DEFAULT_INFLUX_BUCKET) -> str:
    import json
    return f"""\
from(bucket: {json.dumps(bucket or DEFAULT_INFLUX_BUCKET)})
  |> range(start: {range_start})
  |> filter(fn: (r) => exists r.savantUUID and r.savantUUID != "")
  |> filter(fn: (r) =>
      r._field == "power" or r._field == "current" or r._field == "voltage" or
      r._field == "energy" or r._field == "percentCommanded" or r._field == "flags")
  |> last()
"""


@dataclass(slots=True)
class InfluxOrgCandidate:
    """Summary of one organization probe."""

    org_id: str
    org_name: str
    circuit_count: int
    field_names: tuple[str, ...]
    total_power_w: float
    last_seen: str | None
    score: int
    summary: str
    source: str = "org_list"
    query_window: str | None = None
    bucket_names: tuple[str, ...] = ()
    selected_bucket: str | None = None

    @property
    def field_count(self) -> int:
        return len(self.field_names)


@dataclass(slots=True)
class InfluxOrgDiscoveryResult:
    """Outcome of discovering the best Influx organization."""

    selected_org_id: str | None = None
    selected_bucket: str | None = None
    candidates: list[InfluxOrgCandidate] = field(default_factory=list)
    error_key: str | None = None
    error_message: str | None = None
    auth_failure: bool = False
    source: str | None = None


def _parse_influx_csv(text: str) -> list[dict[str, str]]:
    """Parse InfluxDB annotated CSV response."""
    rows: list[dict[str, str]] = []
    for block in text.split("\r\n\r\n"):
        block = block.strip()
        if not block:
            continue
        reader = csv.DictReader(io.StringIO(block))
        if not reader.fieldnames:
            continue
        for row in reader:
            if any(str(key).startswith("#") for key in row):
                continue
            if row:
                rows.append(row)
    return rows


def _safe_float(value: str | None) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_age(last_seen: str | None) -> str:
    parsed = _parse_time(last_seen)
    if parsed is None:
        return "time unknown"

    age_seconds = max((datetime.now(timezone.utc) - parsed).total_seconds(), 0.0)
    if age_seconds < 90:
        return "just now"
    if age_seconds < 3600:
        return f"{int(age_seconds // 60)}m ago"
    return f"{int(age_seconds // 3600)}h ago"


def _build_candidate(
    org_id: str,
    org_name: str,
    rows: list[dict[str, str]],
    *,
    source: str = "org_list",
    query_window: str | None = None,
    bucket_names: tuple[str, ...] = (),
    selected_bucket: str | None = None,
) -> InfluxOrgCandidate:
    uuids = {row.get("savantUUID", "").strip() for row in rows if row.get("savantUUID", "").strip()}
    fields = sorted({row.get("_field", "").strip() for row in rows if row.get("_field", "").strip()})
    power_rows = [row for row in rows if row.get("_field", "").strip() == "power"]
    total_power_w = sum(abs(_safe_float(row.get("_value"))) for row in power_rows)
    last_seen_dt = max(
        (parsed for parsed in (_parse_time(row.get("_time")) for row in rows) if parsed is not None),
        default=None,
    )
    last_seen = last_seen_dt.isoformat() if last_seen_dt is not None else None
    recent = False
    if last_seen_dt is not None:
        recent = (datetime.now(timezone.utc) - last_seen_dt).total_seconds() <= 20 * 60

    field_hits = sum(1 for field_name in _EXPECTED_FIELDS if field_name in fields)
    score = 0
    if rows:
        score += 100
    score += min(len(uuids), 25) * 4
    score += field_hits * 20
    if recent:
        score += 40
    if total_power_w >= 100:
        score += min(int(total_power_w // 500), 40)
    if source == "ssh_metadata":
        score += 60
    elif source == "bucket_scan":
        score += 30

    bucket_label = ", ".join(bucket_names[:3]) if bucket_names else "bucket unknown"
    summary = (
        f"{org_name} [{source}] - {bucket_label} - {len(uuids)} circuits, {len(fields)} fields, "
        f"{total_power_w / 1000.0:.1f} kW, {_format_age(last_seen)}"
    )
    _LOGGER.debug(
        "Influx org candidate %s (%s): source=%s window=%s buckets=%s circuits=%d fields=%s power_w=%.1f last_seen=%s score=%d",
        org_name,
        org_id,
        source,
        query_window or "-",
        ",".join(bucket_names) or "-",
        len(uuids),
        ",".join(fields) or "-",
        total_power_w,
        last_seen or "-",
        score,
    )
    return InfluxOrgCandidate(
        org_id=org_id,
        org_name=org_name,
        circuit_count=len(uuids),
        field_names=tuple(fields),
        total_power_w=round(total_power_w, 1),
        last_seen=last_seen,
        score=score,
        summary=summary,
        source=source,
        query_window=query_window,
        bucket_names=bucket_names,
        selected_bucket=selected_bucket or (bucket_names[0] if bucket_names else DEFAULT_INFLUX_BUCKET),
    )


def _is_plausible(candidate: InfluxOrgCandidate) -> bool:
    if candidate.circuit_count <= 0:
        return False
    if not any(field_name in candidate.field_names for field_name in _PLAUSIBLE_FIELDS):
        return False
    return candidate.last_seen is not None


def _pick_clear_winner(candidates: list[InfluxOrgCandidate]) -> str | None:
    best_by_org: dict[str, InfluxOrgCandidate] = {}
    for candidate in candidates:
        if not _is_plausible(candidate):
            continue
        current = best_by_org.get(candidate.org_id)
        if current is None or candidate.score > current.score:
            best_by_org[candidate.org_id] = candidate
    plausible = list(best_by_org.values())
    if not plausible:
        return None

    ranked = sorted(plausible, key=lambda item: item.score, reverse=True)
    top = ranked[0]
    if len(ranked) == 1:
        return top.org_id if top.score >= 180 else None

    runner_up = ranked[1]
    if top.score >= runner_up.score + 60 and top.circuit_count >= max(runner_up.circuit_count + 4, int(runner_up.circuit_count * 1.5)):
        return top.org_id
    return None


async def _probe_org(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    org_id: str,
    org_name: str,
    range_start: str,
    *,
    source: str = "org_list",
    bucket_names: tuple[str, ...] = (),
) -> InfluxOrgCandidate | None:
    url = f"{base_url.rstrip('/')}/api/v2/query"
    try:
        async with session.post(
            url,
            params={"org": org_id},
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "application/vnd.flux",
                "Accept": "text/csv",
            },
            data=_probe_query(range_start, bucket_names[0] if bucket_names else DEFAULT_INFLUX_BUCKET),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            text = await response.text()
            if response.status != 200:
                _LOGGER.debug(
                    "Influx org probe failed for %s (%s): HTTP %s: %s",
                    org_name,
                    org_id,
                    response.status,
                    text[:200],
                )
                return None
            rows = _parse_influx_csv(text)
            return _build_candidate(
                org_id,
                org_name,
                rows,
                source=source,
                query_window=range_start,
                bucket_names=bucket_names,
                selected_bucket=bucket_names[0] if bucket_names else DEFAULT_INFLUX_BUCKET,
            )
    except (aiohttp.ClientError, TimeoutError) as exc:
        _LOGGER.debug(
            "Influx org probe error for %s (%s, %s): %s",
            org_name,
            org_id,
            range_start,
            exc,
        )
        return None


async def _list_buckets(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
) -> tuple[list[dict[str, str]], str | None]:
    url = f"{base_url.rstrip('/')}/api/v2/buckets"
    try:
        async with session.get(
            url,
            headers={"Authorization": f"Token {token}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            text = await response.text()
            if response.status == 401:
                return [], "auth"
            if response.status == 403:
                return [], "forbidden"
            if response.status != 200:
                _LOGGER.debug("Influx bucket listing failed: HTTP %s: %s", response.status, text[:200])
                return [], "failed"
            payload = await response.json()
            buckets = payload.get("buckets", [])
            if not isinstance(buckets, list):
                return [], "failed"
            return [bucket for bucket in buckets if isinstance(bucket, dict)], None
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        _LOGGER.debug("Influx bucket listing error: %s", exc)
        return [], "failed"


def _group_bucket_orgs(
    buckets: list[dict[str, str]],
    host_metadata: InfluxHostMetadata | None,
) -> list[tuple[str, str, tuple[str, ...]]]:
    grouped: dict[str, list[str]] = {}
    for bucket in buckets:
        org_id = str(bucket.get("orgID", "")).strip()
        name = str(bucket.get("name", "")).strip()
        if not org_id or not name:
            continue
        grouped.setdefault(org_id, []).append(name)

    ordered_org_ids = sorted(
        grouped,
        key=lambda org_id: (
            0 if any(bucket_name.startswith(_BUCKET_SCAN_PREFIXES) for bucket_name in grouped[org_id]) else 1,
            org_id,
        ),
    )

    result: list[tuple[str, str, tuple[str, ...]]] = []
    for org_id in ordered_org_ids:
        bucket_names = tuple(sorted(grouped[org_id]))
        if host_metadata and host_metadata.org_id == org_id and host_metadata.org_name:
            org_name = host_metadata.org_name
        else:
            org_name = bucket_names[0] if bucket_names else org_id
        result.append((org_id, org_name, bucket_names))
    return result


async def _probe_orgs_for_candidates(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    orgs: list[tuple[str, str, tuple[str, ...]]],
    *,
    source: str,
) -> list[InfluxOrgCandidate]:
    candidates: list[InfluxOrgCandidate] = []
    for range_start in _PROBE_WINDOWS:
        _LOGGER.debug(
            "Probing %d Influx org(s) from %s with lookback %s",
            len(orgs),
            source,
            range_start,
        )
        candidates = []
        for org_id, org_name, bucket_names in orgs:
            bucket_choices = bucket_names or (DEFAULT_INFLUX_BUCKET,)
            org_candidates = []
            for bucket_name in bucket_choices:
                candidate = await _probe_org(
                    session,
                    base_url,
                    token,
                    org_id,
                    org_name,
                    range_start,
                    source=source,
                    bucket_names=(bucket_name,),
                )
                if candidate is not None:
                    org_candidates.append(candidate)
            candidates.extend(org_candidates)
        _LOGGER.debug(
            "Influx org discovery at %s from %s produced %d candidate(s)",
            range_start,
            source,
            len(candidates),
        )
        if candidates:
            break
    return candidates


async def async_discover_influx_org(
    base_url: str,
    token: str,
    host_metadata: InfluxHostMetadata | None = None,
) -> InfluxOrgDiscoveryResult:
    """Discover the best Influx organization for Savant energy data."""
    org_url = f"{base_url.rstrip('/')}/api/v2/orgs"
    _LOGGER.debug(
        "Starting Influx org discovery against %s (host_metadata=%s)",
        org_url,
        bool(host_metadata and (host_metadata.org_id or host_metadata.bucket_name)),
    )

    org_candidates: list[InfluxOrgCandidate] = []
    try:
        async with aiohttp.ClientSession() as session:
            if host_metadata and host_metadata.org_id:
                _LOGGER.debug(
                    "Trying host-provided org metadata first: org_id=%s org_name=%s bucket=%s",
                    host_metadata.org_id,
                    host_metadata.org_name or "<unset>",
                    host_metadata.bucket_name or "<unset>",
                )
                metadata_candidates = await _probe_orgs_for_candidates(
                    session,
                    base_url,
                    token,
                    [
                        (
                            host_metadata.org_id,
                            host_metadata.org_name or host_metadata.bucket_name or host_metadata.org_id,
                            (host_metadata.bucket_name,) if host_metadata.bucket_name else (),
                        )
                    ],
                    source="ssh_metadata",
                )
                if metadata_candidates:
                    metadata_candidate = metadata_candidates[0]
                    if metadata_candidate.score >= 120:
                        _LOGGER.info(
                            "Influx org discovery selected host metadata org %s (%s)",
                            metadata_candidate.org_id,
                            metadata_candidate.summary,
                        )
                        return InfluxOrgDiscoveryResult(
                            selected_org_id=metadata_candidate.org_id,
                            selected_bucket=metadata_candidate.selected_bucket,
                            candidates=metadata_candidates,
                            source="ssh_metadata",
                        )
                    _LOGGER.debug(
                        "Host metadata org %s returned no strong data shape; continuing discovery",
                        host_metadata.org_id,
                    )

            buckets, bucket_error = await _list_buckets(session, base_url, token)
            if bucket_error == "auth":
                return InfluxOrgDiscoveryResult(
                    error_key="org_enumeration_denied",
                    error_message=(
                        "Unauthorized (401) while listing buckets; the token may be "
                        "invalid, rotated, or restricted from bucket enumeration"
                    ),
                    auth_failure=True,
                    source="bucket_scan",
                )
            if bucket_error == "forbidden":
                return InfluxOrgDiscoveryResult(
                    error_key="org_discovery_failed",
                    error_message="Forbidden (403) while listing buckets",
                    source="bucket_scan",
                )

            bucket_orgs = _group_bucket_orgs(buckets, host_metadata)
            if bucket_orgs:
                _LOGGER.debug(
                    "Influx bucket scan found %d bucket org(s): %s",
                    len(bucket_orgs),
                    ", ".join(f"{org_id}:{','.join(names[:3])}" for org_id, _, names in bucket_orgs),
                )
                bucket_candidates = await _probe_orgs_for_candidates(
                    session,
                    base_url,
                    token,
                    bucket_orgs,
                    source="bucket_scan",
                )
                if bucket_candidates:
                    winner = _pick_clear_winner(bucket_candidates)
                    plausible = sorted(
                        [candidate for candidate in bucket_candidates if _is_plausible(candidate)],
                        key=lambda item: item.score,
                        reverse=True,
                    )
                    if winner is not None:
                        _LOGGER.info(
                            "Influx org discovery selected %s from bucket scan",
                            winner,
                        )
                        selected_candidate = max(
                            (candidate for candidate in bucket_candidates if candidate.org_id == winner),
                            key=lambda item: item.score,
                        )
                        return InfluxOrgDiscoveryResult(
                            selected_org_id=winner,
                            selected_bucket=selected_candidate.selected_bucket,
                            candidates=plausible or sorted(bucket_candidates, key=lambda item: item.score, reverse=True),
                            source="bucket_scan",
                        )
                    if plausible:
                        _LOGGER.info(
                            "Influx bucket scan found %d plausible candidate(s) but no clear winner",
                            len(plausible),
                        )
                        return InfluxOrgDiscoveryResult(
                            candidates=plausible[:5],
                            source="bucket_scan",
                        )

            async with session.get(
                org_url,
                headers={"Authorization": f"Token {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                text = await response.text()
                if response.status == 401:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_enumeration_denied",
                        error_message=(
                            "Unauthorized (401) while listing organizations; the token may be "
                            "invalid, rotated, or restricted from organization enumeration"
                        ),
                        auth_failure=True,
                        source="org_list",
                    )
                if response.status == 403:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_failed",
                        error_message="Forbidden (403) while listing organizations",
                        source="org_list",
                    )
                if response.status != 200:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_failed",
                        error_message=f"HTTP {response.status}: {text[:200]}",
                        source="org_list",
                    )
                payload = await response.json()
                orgs = payload.get("orgs", [])
                if not orgs:
                    _LOGGER.debug("Influx /api/v2/orgs returned no entries; falling back to bucket metadata only")
                    if bucket_orgs:
                        return InfluxOrgDiscoveryResult(
                            error_key="org_discovery_no_data",
                            error_message="Buckets were visible, but no matching Savant rows were found",
                            source="bucket_scan",
                        )
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_no_orgs",
                        error_message="Token returned no organizations from the org listing endpoint",
                        source="org_list",
                    )

            org_list = [
                (str(org.get("id", "")).strip(), str(org.get("name", org.get("id", "unknown"))))
                for org in orgs
                if str(org.get("id", "")).strip()
            ]
            _LOGGER.debug(
                "Influx org discovery found %d org(s): %s",
                len(org_list),
                ", ".join(name for _, name in org_list),
            )
            org_candidates = await _probe_orgs_for_candidates(
                session,
                base_url,
                token,
                [(org_id, org_name, ()) for org_id, org_name in org_list],
                source="org_list",
            )
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        return InfluxOrgDiscoveryResult(
            error_key="org_discovery_failed",
            error_message=str(exc),
            source="org_list",
        )

    if not org_candidates:
        _LOGGER.debug(
            "Influx org discovery found no matching candidates for the current token",
        )
        return InfluxOrgDiscoveryResult(
            error_key="org_discovery_no_data",
            error_message="No organizations matched the expected Savant data shape",
            source="org_list",
        )

    winner = _pick_clear_winner(org_candidates)
    plausible = sorted(
        [candidate for candidate in org_candidates if _is_plausible(candidate)],
        key=lambda item: item.score,
        reverse=True,
    )

    if winner is not None:
        _LOGGER.info(
            "Influx org discovery selected %s from %d plausible candidate(s)",
            winner,
            len(plausible) or len(org_candidates),
        )
        selected_candidate = max(
            (candidate for candidate in org_candidates if candidate.org_id == winner),
            key=lambda item: item.score,
        )
        return InfluxOrgDiscoveryResult(
            selected_org_id=winner,
            selected_bucket=selected_candidate.selected_bucket,
            candidates=plausible or sorted(org_candidates, key=lambda item: item.score, reverse=True),
            source="org_list",
        )

    if plausible:
        _LOGGER.info(
            "Influx org discovery found %d plausible candidate(s) but no clear winner",
            len(plausible),
        )
        return InfluxOrgDiscoveryResult(candidates=plausible[:5], source="org_list")

    scored = sorted(org_candidates, key=lambda item: item.score, reverse=True)
    _LOGGER.debug(
        "Influx org discovery returning no-data after scoring %d candidate(s)",
        len(scored),
    )
    return InfluxOrgDiscoveryResult(
        error_key="org_discovery_no_data",
        error_message="Organizations were found, but none had Savant circuit data",
        source="org_list",
    )
