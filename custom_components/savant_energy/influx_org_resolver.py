"""Discover and score InfluxDB organizations for Savant Energy."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiohttp

_LOGGER = logging.getLogger(__name__)

_EXPECTED_FIELDS = ("power", "current", "voltage", "energy")
_PLAUSIBLE_FIELDS = ("power", "energy")
_PROBE_WINDOWS = ("-15m", "-24h", "-7d")


def _probe_query(range_start: str) -> str:
    return f"""\
from(bucket: "localHub")
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

    @property
    def field_count(self) -> int:
        return len(self.field_names)


@dataclass(slots=True)
class InfluxOrgDiscoveryResult:
    """Outcome of discovering the best Influx organization."""

    selected_org_id: str | None = None
    candidates: list[InfluxOrgCandidate] = field(default_factory=list)
    error_key: str | None = None
    error_message: str | None = None
    auth_failure: bool = False


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

    summary = (
        f"{org_name} - {len(uuids)} circuits, {len(fields)} fields, "
        f"{total_power_w / 1000.0:.1f} kW, {_format_age(last_seen)}"
    )
    _LOGGER.debug(
        "Influx org candidate %s (%s): circuits=%d fields=%s power_w=%.1f last_seen=%s score=%d",
        org_name,
        org_id,
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
    )


def _is_plausible(candidate: InfluxOrgCandidate) -> bool:
    if candidate.circuit_count <= 0:
        return False
    if not any(field_name in candidate.field_names for field_name in _PLAUSIBLE_FIELDS):
        return False
    return candidate.last_seen is not None


def _pick_clear_winner(candidates: list[InfluxOrgCandidate]) -> str | None:
    plausible = [candidate for candidate in candidates if _is_plausible(candidate)]
    if len(plausible) == 1:
        return plausible[0].org_id
    if len(plausible) < 2:
        return None

    ranked = sorted(plausible, key=lambda item: item.score, reverse=True)
    top = ranked[0]
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
            data=_probe_query(range_start),
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
            return _build_candidate(org_id, org_name, rows)
    except (aiohttp.ClientError, TimeoutError) as exc:
        _LOGGER.debug(
            "Influx org probe error for %s (%s, %s): %s",
            org_name,
            org_id,
            range_start,
            exc,
        )
        return None


async def async_discover_influx_org(
    base_url: str,
    token: str,
) -> InfluxOrgDiscoveryResult:
    """Discover the best Influx organization for Savant energy data."""
    url = f"{base_url.rstrip('/')}/api/v2/orgs"
    _LOGGER.debug("Starting Influx org discovery against %s", url)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": f"Token {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                text = await response.text()
                if response.status == 401:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_auth_failed",
                        error_message="Unauthorized (401) while listing organizations",
                        auth_failure=True,
                    )
                if response.status == 403:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_failed",
                        error_message="Forbidden (403) while listing organizations",
                    )
                if response.status != 200:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_failed",
                        error_message=f"HTTP {response.status}: {text[:200]}",
                    )
                payload = await response.json()
                orgs = payload.get("orgs", [])
                if not orgs:
                    return InfluxOrgDiscoveryResult(
                        error_key="org_discovery_no_orgs",
                        error_message="Token returned no organizations",
                    )

            candidates: list[InfluxOrgCandidate] = []
            org_list = [
                (str(org.get("id", "")).strip(), str(org.get("name", org.get("id", "unknown"))))
                for org in orgs
                if str(org.get("id", "")).strip()
            ]
            _LOGGER.debug("Influx org discovery found %d org(s): %s", len(org_list), ", ".join(name for _, name in org_list))
            for range_start in _PROBE_WINDOWS:
                _LOGGER.debug(
                    "Probing %d Influx org(s) with lookback %s",
                    len(org_list),
                    range_start,
                )
                candidates = []
                for org_id, org_name in org_list:
                    candidate = await _probe_org(
                        session,
                        base_url,
                        token,
                        org_id,
                        org_name,
                        range_start,
                    )
                    if candidate is not None:
                        candidates.append(candidate)
                _LOGGER.debug(
                    "Influx org discovery at %s produced %d candidate(s)",
                    range_start,
                    len(candidates),
                )
                if candidates:
                    break
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        return InfluxOrgDiscoveryResult(
            error_key="org_discovery_failed",
            error_message=str(exc),
        )

    if not candidates:
        _LOGGER.debug(
            "Influx org discovery found no matching candidates for %d org(s)",
            len(org_list),
        )
        return InfluxOrgDiscoveryResult(
            error_key="org_discovery_no_data",
            error_message="No organizations matched the expected Savant data shape",
        )

    winner = _pick_clear_winner(candidates)
    plausible = sorted(
        [candidate for candidate in candidates if _is_plausible(candidate)],
        key=lambda item: item.score,
        reverse=True,
    )

    if winner is not None:
        _LOGGER.info(
            "Influx org discovery selected %s from %d plausible candidate(s)",
            winner,
            len(plausible) or len(candidates),
        )
        return InfluxOrgDiscoveryResult(
            selected_org_id=winner,
            candidates=plausible or sorted(candidates, key=lambda item: item.score, reverse=True),
        )

    if plausible:
        _LOGGER.info(
            "Influx org discovery found %d plausible candidate(s) but no clear winner",
            len(plausible),
        )
        return InfluxOrgDiscoveryResult(candidates=plausible[:5])

    scored = sorted(candidates, key=lambda item: item.score, reverse=True)
    if len(scored) == 1 and scored[0].circuit_count > 0:
        _LOGGER.info(
            "Influx org discovery selected only scored candidate %s with %d circuits",
            scored[0].org_id,
            scored[0].circuit_count,
        )
        return InfluxOrgDiscoveryResult(selected_org_id=scored[0].org_id, candidates=scored)

    _LOGGER.debug(
        "Influx org discovery returning no-data after scoring %d candidate(s)",
        len(scored),
    )
    return InfluxOrgDiscoveryResult(
        error_key="org_discovery_no_data",
        error_message="Organizations were found, but none had Savant circuit data",
    )
