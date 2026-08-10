import importlib.util
import sys
from pathlib import Path
import unittest
from unittest import mock


def _load_influx_client_module():
    module_path = Path(__file__).resolve().parents[1] / "custom_components" / "savant_energy" / "influx_client.py"
    spec = importlib.util.spec_from_file_location("savant_energy_influx_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _circuit_csv() -> str:
    return "\r\n".join(
        [
            "result,table,_measurement,savantUUID,name,channel,classification,dimmable,override,type,_field,_value",
            ",_result,pbc-1,uuid-1,Circuit 1,1,relay,false,false,0000,power,123.4",
            ",_result,pbc-1,uuid-1,Circuit 1,1,relay,false,false,0000,current,12.3",
            ",_result,pbc-1,uuid-1,Circuit 1,1,relay,false,false,0000,voltage,240",
            ",_result,pbc-1,uuid-1,Circuit 1,1,relay,false,false,0000,energy,1000",
        ]
    )


class InfluxClientBackfillTests(unittest.IsolatedAsyncioTestCase):
    def test_query_result_classifies_auth_and_is_legacy_unpackable(self):
        influx_client = _load_influx_client_module()

        result = influx_client.InfluxQueryResult(
            False, error_message="Unauthorized (401)", failure_class="unauthorized_401"
        )

        self.assertEqual(result.status, "unauthorized_401")
        self.assertTrue(result.auth_failure)
        self.assertEqual(tuple(result), (False, "", "Unauthorized (401)", True, False))

    def test_query_result_distinguishes_permission_failure(self):
        influx_client = _load_influx_client_module()

        result = influx_client.InfluxQueryResult(
            False,
            error_message="Forbidden (403)",
            failure_class="forbidden_403",
            http_status=403,
        )

        self.assertFalse(result.auth_failure)
        self.assertTrue(result.permission_failure)
        self.assertEqual(result.http_status, 403)
        self.assertEqual(influx_client._query_error_key(result), "influx_permission_denied")

    def test_query_error_keys_are_specific(self):
        influx_client = _load_influx_client_module()

        expected = {
            "unauthorized_401": "influx_auth_failed",
            "forbidden_403": "influx_permission_denied",
            "invalid_org": "influx_org_invalid",
            "invalid_bucket": "influx_bucket_invalid",
            "unreachable": "influx_unreachable",
            "other_query": "influx_query_failed",
        }
        for failure_class, error_key in expected.items():
            with self.subTest(failure_class=failure_class):
                result = influx_client.InfluxQueryResult(False, failure_class=failure_class)
                self.assertEqual(influx_client._query_error_key(result), error_key)

    def test_flux_bucket_is_encoded_as_a_string_literal(self):
        influx_client = _load_influx_client_module()

        self.assertEqual(influx_client._flux_string('hub"west'), '"hub\\\"west"')

    async def test_fetch_influx_snapshot_backfills_to_a_wider_window(self):
        influx_client = _load_influx_client_module()

        async def fake_post_flux(session, base_url, token, org, query):
            if "r.type == \"0000\"" in query:
                return True, "", "", False, False
            if "range(start: -2m)" in query:
                return True, "", "", False, False
            if "range(start: -15m)" in query:
                return True, _circuit_csv(), "", False, False
            self.fail(f"unexpected query: {query}")

        with mock.patch.object(influx_client, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            influx_client,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(return_value=(True, [{"uid": "001AAE1733DB", "load_name": "Circuit 1", "device_label": "Circuit 1"}])),
        ):
            result = await influx_client.fetch_influx_snapshot_with_backfill(
                "http://example",
                "token",
                "org-1",
                sem_host="sem",
                sem_port=8644,
                sample_seconds=5.0,
                circuit_metadata={
                    "uuid-1::1": {
                        "circuit_key": "uuid-1::1",
                        "savant_uuid": "uuid-1",
                        "channel": "1",
                        "type": "0000",
                        "role": "relay",
                        "relay_uid": "001AAE1733DB",
                        "display_name": "Circuit 1",
                        "influx_name": "Circuit 1",
                        "legacy_uid": "001AAE1733DB.0",
                        "legacy_base_uid": "001AAE1733DB",
                        "role_source": "sem_device_label",
                        "relay_match_name": "Circuit 1",
                    }
                },
            )

        self.assertTrue(result.success)
        self.assertEqual(result.query_window, "-15m")
        self.assertEqual(len(result.data["presentDemands"]), 1)

    async def test_fetch_influx_snapshot_reports_auth_failure_with_window(self):
        influx_client = _load_influx_client_module()

        async def fake_post_flux(session, base_url, token, org, query):
            if "range(start: -2m)" in query:
                return False, "", "Unauthorized (401) - token is invalid or expired", True, False
            self.fail(f"unexpected query: {query}")

        with mock.patch.object(influx_client, "_post_flux", side_effect=fake_post_flux):
            result = await influx_client.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                sem_host="sem",
                sem_port=8644,
            )

        self.assertFalse(result.success)
        self.assertTrue(result.auth_failure)
        self.assertEqual(result.query_window, "-2m")

    async def test_fetch_influx_snapshot_reports_org_failure_with_window(self):
        influx_client = _load_influx_client_module()

        async def fake_post_flux(session, base_url, token, org, query):
            if "range(start: -2m)" in query:
                return False, "", "HTTP 400: {\"code\":\"invalid\",\"message\":\"Please provide either orgID or org\"}", False, True
            self.fail(f"unexpected query: {query}")

        with mock.patch.object(influx_client, "_post_flux", side_effect=fake_post_flux):
            result = await influx_client.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                sem_host="sem",
                sem_port=8644,
            )

        self.assertFalse(result.success)
        self.assertTrue(result.org_failure)
        self.assertEqual(result.query_window, "-2m")


if __name__ == "__main__":
    unittest.main()
