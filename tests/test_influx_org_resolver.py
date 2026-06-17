import importlib.util
import sys
from pathlib import Path
import unittest
from unittest import mock


def _load_resolver_module():
    module_path = Path(__file__).resolve().parents[1] / "custom_components" / "savant_energy" / "influx_org_resolver.py"
    spec = importlib.util.spec_from_file_location("savant_energy_influx_org_resolver", module_path)
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

    async def test_discovery_returns_candidates_when_multiple_orgs_are_plausible(self):
        resolver = _load_resolver_module()
        org_rows = {
            "org-1": _build_circuit_csv("org-1", 1),
            "org-2": _build_circuit_csv("org-2", 1),
        }

        def handler(method, url, kwargs):
            if method == "GET":
                return _FakeResponse(200, payload={"orgs": [{"id": "org-1"}, {"id": "org-2"}]})
            org_id = kwargs["params"]["org"]
            return _FakeResponse(200, text=org_rows[org_id])

        with mock.patch.object(
            resolver.aiohttp,
            "ClientSession",
            side_effect=lambda: _FakeClientSession(handler),
        ):
            result = await resolver.async_discover_influx_org("http://example", "token")

        self.assertIsNone(result.selected_org_id)
        self.assertGreaterEqual(len(result.candidates), 2)

    async def test_discovery_does_not_guess_for_a_single_weak_org(self):
        resolver = _load_resolver_module()

        def handler(method, url, kwargs):
            if method == "GET":
                return _FakeResponse(200, payload={"orgs": [{"id": "org-1"}]})
            return _FakeResponse(200, text="")

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
