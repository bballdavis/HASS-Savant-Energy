import importlib.util
import sys
import types
from pathlib import Path
import unittest
from datetime import datetime, timezone
from unittest import mock


def _load_resolver_module():
    repo_root = Path(__file__).resolve().parents[1]
    package_root = repo_root / "custom_components"
    savant_root = package_root / "savant_energy"

    if "custom_components" not in sys.modules:
        package = types.ModuleType("custom_components")
        package.__path__ = [str(package_root)]
        sys.modules["custom_components"] = package

    if "custom_components.savant_energy" not in sys.modules:
        package = types.ModuleType("custom_components.savant_energy")
        package.__path__ = [str(savant_root)]
        sys.modules["custom_components.savant_energy"] = package

    module_path = savant_root / "influx_org_resolver.py"
    spec = importlib.util.spec_from_file_location(
        "custom_components.savant_energy.influx_org_resolver",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_circuit_csv(org_prefix: str, circuit_count: int) -> str:
    header = (
        "result,table,_time,_measurement,savantUUID,name,channel,classification,"
        "dimmable,override,type,_field,_value"
    )
    rows = []
    for circuit_index in range(circuit_count):
        uuid = f"{org_prefix}-uuid-{circuit_index}"
        channel = circuit_index + 1
        for field_name in ("power", "current", "voltage", "energy"):
            rows.append(
                ",".join(
                    [
                        "",
                        "_result",
                        "2026-06-16T12:00:00Z",
                        f"{org_prefix}-measurement",
                        uuid,
                        f"Circuit {channel}",
                        str(channel),
                        "relay",
                        "false",
                        "false",
                        "0000",
                        field_name,
                        str(100 + circuit_index),
                    ]
                )
            )
    return "\r\n".join([header, *rows])


def _build_system_csv(*, primary_power: str = "1250", other_power: str = "25", include_other: bool = True, timestamp: str | None = None) -> str:
    header = "result,table,_time,_measurement,savantUUID,name,channel,type,_field,_value"
    timestamp = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = [
        ",".join(["", "_result", timestamp, "hub", "", "", "Energy.Total.Consumption.Power", "0000", "power", primary_power]),
    ]
    if include_other:
        rows.append(
            ",".join(["", "_result", timestamp, "hub", "", "", "Energy.Total.Feed.Power", "0000", "power", other_power])
        )
    return "\r\n".join([header, *rows])


class _FakeResponse:
    def __init__(self, status: int, payload=None, text: str = "") -> None:
        self.status = status
        self._payload = payload
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text

    async def json(self):
        return self._payload


class _FakeClientSession:
    def __init__(self, handler) -> None:
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, **kwargs):
        return self._handler("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._handler("POST", url, kwargs)


class InfluxOrgResolverTests(unittest.IsolatedAsyncioTestCase):
    def test_channel_fallback_requires_recent_nonzero_primary_and_known_peer(self):
        resolver = _load_resolver_module()
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        candidate = resolver._build_channel_candidate(
            "org-1", "Org 1", resolver._parse_influx_csv(_build_system_csv(timestamp=now)),
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.schema_mode, "channel_read_only")
        self.assertEqual(candidate.circuit_count, 0)
        self.assertGreaterEqual(candidate.system_channel_count, 2)
        self.assertIsNone(resolver._build_channel_candidate(
            "org-1", "Org 1", resolver._parse_influx_csv(_build_system_csv(primary_power="0", timestamp=now)),
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        ))
        self.assertIsNone(resolver._build_channel_candidate(
            "org-1", "Org 1", resolver._parse_influx_csv(_build_system_csv(include_other=False, timestamp=now)),
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        ))
        self.assertIsNone(resolver._build_channel_candidate(
            "org-1", "Org 1", resolver._parse_influx_csv(_build_system_csv(other_power="not-a-number", timestamp=now)),
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        ))

    def test_channel_fallback_rejects_stale_rows_and_arbitrary_channels(self):
        resolver = _load_resolver_module()
        self.assertIsNone(resolver._build_channel_candidate(
            "org-1", "Org 1", resolver._parse_influx_csv(_build_system_csv(timestamp="2020-01-01T00:00:00Z")),
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        ))
        rows = resolver._parse_influx_csv(_build_system_csv())
        rows[1]["channel"] = "Energy.UserDefined.Power"
        self.assertIsNone(resolver._build_channel_candidate(
            "org-1", "Org 1", rows,
            source="org_list", query_window="-15m", bucket_names=("localHub",),
        ))

    def test_naive_timestamps_are_treated_as_utc(self):
        resolver = _load_resolver_module()
        parsed = resolver._parse_time("2026-09-24T12:00:00")
        self.assertIsNotNone(parsed)
        self.assertIsNotNone(parsed.tzinfo)

    def test_pick_clear_winner_prefers_the_stronger_candidate(self):
        resolver = _load_resolver_module()
        winner = resolver._pick_clear_winner(
            [
                resolver.InfluxOrgCandidate(
                    org_id="org-1",
                    org_name="Org 1",
                    circuit_count=20,
                    field_names=("power", "current", "voltage", "energy"),
                    total_power_w=5_000.0,
                    last_seen="2026-06-16T12:00:00+00:00",
                    score=300,
                    summary="Org 1 - 20 circuits",
                ),
                resolver.InfluxOrgCandidate(
                    org_id="org-2",
                    org_name="Org 2",
                    circuit_count=1,
                    field_names=("power", "energy"),
                    total_power_w=100.0,
                    last_seen="2026-06-16T12:00:00+00:00",
                    score=150,
                    summary="Org 2 - 1 circuit",
                ),
            ]
        )

        self.assertEqual(winner, "org-1")

    def test_pick_clear_winner_compares_best_bucket_per_org(self):
        resolver = _load_resolver_module()
        shared = dict(
            org_name="Org 1",
            circuit_count=20,
            field_names=("power", "energy"),
            total_power_w=5_000.0,
            last_seen="2026-06-16T12:00:00+00:00",
        )

        winner = resolver._pick_clear_winner(
            [
                resolver.InfluxOrgCandidate(org_id="org-1", score=300, summary="a", selected_bucket="a", **shared),
                resolver.InfluxOrgCandidate(org_id="org-1", score=290, summary="b", selected_bucket="b", **shared),
                resolver.InfluxOrgCandidate(
                    org_id="org-2",
                    org_name="Org 2",
                    circuit_count=1,
                    field_names=("power",),
                    total_power_w=100.0,
                    last_seen="2026-06-16T12:00:00+00:00",
                    score=150,
                    summary="c",
                    selected_bucket="c",
                ),
            ]
        )

        self.assertEqual(winner, "org-1")

    async def test_bucket_scan_keeps_multiple_buckets_for_same_org(self):
        resolver = _load_resolver_module()

        async def fake_probe(_session, _url, _token, org_id, org_name, _range, **kwargs):
            bucket = kwargs["bucket_names"][0]
            return resolver.InfluxOrgCandidate(
                org_id=org_id,
                org_name=org_name,
                circuit_count=1,
                field_names=("power",),
                total_power_w=100.0,
                last_seen="2026-06-16T12:00:00+00:00",
                score=200 if bucket == "localHub" else 190,
                summary=bucket,
                selected_bucket=bucket,
            )

        with mock.patch.object(resolver, "_probe_org", side_effect=fake_probe):
            candidates = await resolver._probe_orgs_for_candidates(
                object(), "http://example", "token", [("org-1", "Org 1", ("localHub", "archive"))], source="bucket_scan"
            )

        self.assertEqual({candidate.selected_bucket for candidate in candidates}, {"localHub", "archive"})

    async def test_discovery_uses_bucket_scan_when_org_list_is_empty(self):
        resolver = _load_resolver_module()
        org_rows = _build_circuit_csv("org-1", 1)

        def handler(method, url, kwargs):
            if method == "GET" and url.endswith("/buckets"):
                return _FakeResponse(200, payload={"buckets": [{"orgID": "org-1", "name": "localHub"}]})
            if method == "GET" and url.endswith("/orgs"):
                return _FakeResponse(200, payload={"orgs": []})
            if method == "POST":
                return _FakeResponse(200, text=org_rows)
            self.fail(f"unexpected call: {method} {url}")

        with mock.patch.object(
            resolver.aiohttp,
            "ClientSession",
            side_effect=lambda: _FakeClientSession(handler),
        ):
            result = await resolver.async_discover_influx_org("http://example", "token")

        self.assertEqual(result.selected_org_id, "org-1")
        self.assertEqual(result.source, "bucket_scan")
        self.assertGreaterEqual(len(result.candidates), 1)

    async def test_discovery_identifies_token_that_cannot_enumerate_buckets(self):
        resolver = _load_resolver_module()

        def handler(method, url, kwargs):
            if method == "GET" and url.endswith("/buckets"):
                return _FakeResponse(401, text="unauthorized")
            self.fail(f"unexpected call: {method} {url}")

        with mock.patch.object(
            resolver.aiohttp,
            "ClientSession",
            side_effect=lambda: _FakeClientSession(handler),
        ):
            result = await resolver.async_discover_influx_org("http://example", "token")

        self.assertEqual(result.error_key, "org_enumeration_denied")
        self.assertTrue(result.auth_failure)
        self.assertEqual(result.source, "bucket_scan")

    async def test_discovery_prefers_host_metadata_when_it_has_real_rows(self):
        resolver = _load_resolver_module()
        metadata = resolver.InfluxHostMetadata(
            org_id="org-meta",
            org_name="Racepoint Energy",
            bucket_name="localHub",
        )

        def handler(method, url, kwargs):
            if method == "POST":
                org_id = kwargs["params"]["org"]
                if org_id == "org-meta":
                    return _FakeResponse(200, text=_build_circuit_csv("org-meta", 2))
            if method == "GET" and url.endswith("/buckets"):
                return _FakeResponse(200, payload={"buckets": []})
            if method == "GET" and url.endswith("/orgs"):
                return _FakeResponse(200, payload={"orgs": []})
            self.fail(f"unexpected call: {method} {url}")

        with mock.patch.object(
            resolver.aiohttp,
            "ClientSession",
            side_effect=lambda: _FakeClientSession(handler),
        ):
            result = await resolver.async_discover_influx_org("http://example", "token", metadata)

        self.assertEqual(result.selected_org_id, "org-meta")
        self.assertEqual(result.source, "ssh_metadata")

    async def test_discovery_does_not_guess_for_a_single_weak_org(self):
        resolver = _load_resolver_module()

        def handler(method, url, kwargs):
            if method == "GET" and url.endswith("/buckets"):
                return _FakeResponse(200, payload={"buckets": []})
            if method == "GET" and url.endswith("/orgs"):
                return _FakeResponse(200, payload={"orgs": [{"id": "org-1"}]})
            if method == "POST":
                return _FakeResponse(200, text="")
            self.fail(f"unexpected call: {method} {url}")

        with mock.patch.object(
            resolver.aiohttp,
            "ClientSession",
            side_effect=lambda: _FakeClientSession(handler),
        ):
            result = await resolver.async_discover_influx_org("http://example", "token")

        self.assertIsNone(result.selected_org_id)
        self.assertEqual(result.error_key, "org_discovery_no_data")


if __name__ == "__main__":
    unittest.main()
