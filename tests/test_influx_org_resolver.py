import importlib.util
import sys
import types
from pathlib import Path
import unittest
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
