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


_RELAY_FIXTURE = [
    ("1", "B2F4BD96-9B57-BF0F-5AF0-1D6C5DB63869", "Kylos Room", "Kylos Room", "001AAE1733DC"),
    ("2", "BB56645C-604C-4606-5672-825C05AA6FCB", "Patio Kitch", "Patio Kitchen", "001AAE17353D"),
    ("3", "0CB2C37F-1721-E000-59F4-4C450F9E457C", "Patio Outle", "Patio Outlets", "001AAE17353E"),
    ("4", "F26B152F-B6CD-AF0F-71FE-219BA0ED2F90", "Master Bath", "Master Bathroom", "001AAE173D6B"),
    ("5", "FF1B9B93-3BB2-DD0D-63D2-0D2B48FA0803", "Master Bedr", "Master Bedroom", "001AAE173D6C"),
    ("6", "CFCE1479-3643-B909-547D-6F1549D407A8", "Kitchen Isl", "Kitchen Island", "001AAE173FB9"),
    ("7", "A9415FA5-331C-0E0E-4291-C4F6ED4BACAE", "Dining Room", "Dining Room", "001AAE173FBA"),
    ("8", "5AB1EB58-66B6-9E0E-442C-9EF0256160F4", "Office / Ki", "Office / King", "001AAE173FDD"),
    ("9", "F81030A4-CB69-F909-4BAD-6552E15A5940", "Dishwasher", "Dishwasher", "001AAE173FDE"),
    ("10", "58DB62D6-6CDB-3000-45E0-321E9A03BB81", "Yvettes Off", "Yvettes Office", "001AAE173FE1"),
    ("11", "D5A337C4-41DD-BB0B-4814-2E304E25772A", "Microwave", "Microwave", "001AAE173FE2"),
    ("12", "A7D80FA6-AE71-FD0D-6CE8-67139412BC95", "A/C Downsta", "A/C Downstairs", "001AAE17CB8F"),
    ("13", "CEA72060-530F-BB0B-7DA0-49A789878C3B", "A/C Upstair", "A/C Upstairs", "001AAE17CF15"),
    ("14", "8ECBD3D4-A219-0D0D-62A0-003898C7E489", "Patio Light", "Patio Lights", "001AAE17329B"),
    ("15", "9B61E784-8CE3-7E0E-4D80-54221BA7A559", "A/C Down Bl", "A/C Down Blower", "001AAE1732A9"),
    ("16", "3E0BD320-CBAC-6101-4621-C9A7D457DADA", "Queen Room", "Queen Room", "001AAE17329C"),
    ("17", "7C35F702-9381-CA0A-71CB-B13A72C18373", "Theater", "Theater", "001AAE17329D"),
    ("18", "C38F7ECB-9017-1101-6376-800845081B8B", "Kitchen Cou", "Kitchen Counter", "001AAE17329E"),
    ("19", "F455AC35-F499-4202-5AF0-45AF2141F848", "A/C Up Blow", "A/C Up Blower", "001AAE1732AA"),
    ("20", "5E2C7D79-DE76-2303-7097-9CF1F0CCE937", "Laundry Roo", "Laundry Room", "001AAE1732AF"),
    ("21", "6E63D340-09A2-6303-6D0F-09F4EFAC72B9", "Garage Ligh", "Garage Lights", "001AAE1732B0"),
    ("22", "F84A9BD6-5893-5202-783B-F451944B191B", "Garg Outlet", "Garg Outlets", "001AAE1732B3"),
    ("23", "4371DC19-0AB9-6303-659C-A135174E5ED1", "Smoke Detec", "Smoke Detector", "001AAE1733DB"),
    ("24", "FD60E66D-A46C-D707-7D1D-59A0164ABDA2", "Kitchen Lig", "Kitchen Lights", "001AAE1732B4"),
    ("25", "FE856DD2-08B2-DB0B-7EA6-9DA3407599B3", "Refrigerato", "Refrigerator", "001AAE1732DB"),
    ("26", "B1EFA22A-EE35-CF0F-5D7C-79387BB38A3F", "Garbage Dis", "Garbage Disposal", "001AAE1732DC"),
    ("27", "94B75D60-9CFB-1D0D-723A-E94DB08F1FA3", "Vent Hood", "Vent Hood", "001AAE1732FD"),
    ("28", "AD7DB1AD-001E-B707-452D-D5D65A292EA4", "Living Room", "Living Room", "001AAE1732FE"),
]

_TESLA_UUID = "F3168A0C-D93F-2404-62D3-D909BB574113"


def _live_like_circuit_csv() -> str:
    tesla_header = (
        ",result,table,_start,_stop,_time,_value,_field,_measurement,channel,classification,"
        "dimmable,group,name,regarding,savantUUID,type"
    )
    relay_header = (
        ",result,table,_start,_stop,_time,_value,_field,_measurement,channel,classification,"
        "dimmable,name,override,regarding,savantUUID,type"
    )

    tesla_rows = []
    for channel, energy_value, power_value in (("6", "4319916450000", "1.04"), ("7", "4357932868750", "2.03")):
        tesla_rows.extend(
            [
                f",_result,0,start,stop,time,0.022,current,50338B0B8E28007A,{channel},Consumption,False,Auto,Tesla,energy,{_TESLA_UUID},007A",
                f",_result,0,start,stop,time,{energy_value},energy,50338B0B8E28007A,{channel},Consumption,False,Auto,Tesla,energy,{_TESLA_UUID},007A",
                f",_result,0,start,stop,time,100,percentCommanded,50338B0B8E28007A,{channel},Consumption,False,Auto,Tesla,energy,{_TESLA_UUID},007A",
                f",_result,0,start,stop,time,{power_value},power,50338B0B8E28007A,{channel},Consumption,False,Auto,Tesla,energy,{_TESLA_UUID},007A",
                f",_result,0,start,stop,time,121.5,voltage,50338B0B8E28007A,{channel},Consumption,False,Auto,Tesla,energy,{_TESLA_UUID},007A",
            ]
        )

    relay_rows = []
    for channel, savant_uuid, device_label, _load_name, _relay_uid in _RELAY_FIXTURE:
        relay_rows.extend(
            [
                f",_result,1,start,stop,time,0.28,current,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
                f",_result,1,start,stop,time,{int(channel) * 1000},energy,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
                f",_result,1,start,stop,time,1,flags,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
                f",_result,1,start,stop,time,100,percentCommanded,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
                f",_result,1,start,stop,time,30.13,power,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
                f",_result,1,start,stop,time,122.0,voltage,60640523DAC90074,{channel},Consumption,False,{device_label},False,energy,{savant_uuid},0074",
            ]
        )

    return "\n".join([tesla_header, *tesla_rows, "", relay_header, *relay_rows])


def _sem_devices():
    return [
        {
            "uid": relay_uid,
            "device_label": device_label,
            "load_name": load_name,
        }
        for _channel, _savant_uuid, device_label, load_name, relay_uid in _RELAY_FIXTURE
    ]


def _single_circuit_csv(
    *,
    name: str,
    savant_uuid: str = "UUID-1",
    channel: str = "1",
    classification: str = "relay",
    device_type: str = "0000",
    measurement: str = "PBC-1",
) -> str:
    rows = [
        "result,table,_measurement,savantUUID,name,channel,classification,dimmable,override,type,_field,_value",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},power,123.4",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},current,12.3",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},voltage,240",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},energy,1000",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},percentCommanded,100",
        f",_result,{measurement},{savant_uuid},{name},{channel},{classification},false,false,{device_type},flags,1",
    ]
    return "\n".join(rows)


class InfluxCircuitMappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_circuit_rows_handles_mixed_headers_and_newlines(self):
        module = _load_influx_client_module()

        _measurement, rows = module._build_circuit_rows(_live_like_circuit_csv())

        self.assertEqual(len(rows), 30)
        self.assertEqual(rows["B2F4BD96-9B57-BF0F-5AF0-1D6C5DB63869::1"]["name"], "Kylos Room")
        self.assertEqual(rows[f"{_TESLA_UUID}::6"]["name"], "Tesla")

    async def test_discover_circuit_metadata_resolves_relays_and_cts(self):
        module = _load_influx_client_module()
        circuit_text = _live_like_circuit_csv()

        async def fake_post_flux(session, base_url, token, org, query):
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(return_value=(True, _sem_devices())),
        ):
            result = await module.discover_circuit_metadata_with_backfill(
                "http://example",
                "token",
                "org-1",
                sem_host="sem-host",
            )

        self.assertTrue(result.success)
        assert result.circuit_map is not None
        role_counts = {"relay": 0, "ct_sensor": 0}
        for metadata in result.circuit_map.values():
            role_counts[metadata["role"]] += 1
        self.assertEqual(role_counts["relay"], 28)
        self.assertEqual(role_counts["ct_sensor"], 2)
        self.assertEqual(result.circuit_map["58DB62D6-6CDB-3000-45E0-321E9A03BB81::10"]["display_name"], "Yvettes Office")
        self.assertEqual(result.circuit_map["58DB62D6-6CDB-3000-45E0-321E9A03BB81::10"]["influx_name"], "Yvettes Off")
        self.assertEqual(result.circuit_map[f"{_TESLA_UUID}::6"]["legacy_uid"], f"{_TESLA_UUID}.6")
        self.assertEqual(result.circuit_map[f"{_TESLA_UUID}::7"]["legacy_uid"], f"{_TESLA_UUID}.7")

    async def test_discover_circuit_metadata_uses_alias_match_for_relays(self):
        module = _load_influx_client_module()
        circuit_text = _single_circuit_csv(name="Patio Kitchen")

        async def fake_post_flux(session, base_url, token, org, query):
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(
                return_value=(
                    True,
                    [
                        {
                            "uid": "001AAE17353D",
                            "device_label": "Patio Kitch",
                            "load_name": "Patio Kitchenette",
                        }
                    ],
                ),
            ),
        ), mock.patch.object(
            module,
            "fetch_pbc_websocket_devices",
            new=mock.AsyncMock(return_value=(False, [])),
        ):
            result = await module.discover_circuit_metadata(
                "http://example",
                "token",
                "org-1",
                sem_host="sem-host",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.warnings, [])
        assert result.circuit_map is not None
        circuit = result.circuit_map["UUID-1::1"]
        self.assertEqual(circuit["role"], "relay")
        self.assertEqual(circuit["relay_uid"], "001AAE17353D")
        self.assertTrue(str(circuit["role_source"]).startswith("sem_"))

    async def test_discover_circuit_metadata_recovers_relay_via_websocket_fallback(self):
        module = _load_influx_client_module()
        circuit_text = _single_circuit_csv(name="Patio Kitchen")

        async def fake_post_flux(session, base_url, token, org, query):
            return True, circuit_text, "", False, False

        websocket_inventory = [
            {
                "uid": "001AAE17353D",
                "device_label": "Patio Kitchen",
                "load_name": "Patio Kitchen",
                "model": "Relay",
                "slot_number": 2,
                "start_address": 2,
                "source": "websocket",
            }
        ]

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(
                return_value=(
                    True,
                    [
                        {
                            "uid": "001AAE17353D",
                            "device_label": "Garage Lights",
                            "load_name": "Garage Lights",
                        }
                    ],
                ),
            ),
        ), mock.patch.object(
            module,
            "fetch_pbc_websocket_devices",
            new=mock.AsyncMock(return_value=(True, websocket_inventory)),
        ) as ws_mock:
            result = await module.discover_circuit_metadata(
                "http://example",
                "token",
                "org-1",
                sem_host="sem-host",
            )

        self.assertTrue(result.success)
        self.assertTrue(result.websocket_inventory_used)
        ws_mock.assert_awaited_once()
        assert result.circuit_map is not None
        circuit = result.circuit_map["UUID-1::1"]
        self.assertEqual(circuit["role"], "relay")
        self.assertEqual(circuit["relay_uid"], "001AAE17353D")
        self.assertTrue(str(circuit["role_source"]).startswith("websocket_"))
        self.assertEqual(circuit["resolution_source"], circuit["role_source"])

    async def test_discover_circuit_metadata_downgrades_unmatched_relay_to_ct(self):
        module = _load_influx_client_module()
        circuit_text = _single_circuit_csv(name="Mystery Load")

        async def fake_post_flux(session, base_url, token, org, query):
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(
                return_value=(
                    True,
                    [
                        {
                            "uid": "001AAE17353D",
                            "device_label": "Garage Lights",
                            "load_name": "Garage Lights",
                        }
                    ],
                ),
            ),
        ), mock.patch.object(
            module,
            "fetch_pbc_websocket_devices",
            new=mock.AsyncMock(return_value=(False, [])),
        ):
            result = await module.discover_circuit_metadata(
                "http://example",
                "token",
                "org-1",
                sem_host="sem-host",
            )

        self.assertTrue(result.success)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("Mystery Load", result.warnings[0])
        assert result.circuit_map is not None
        circuit = result.circuit_map["UUID-1::1"]
        self.assertEqual(circuit["role"], "ct_sensor")
        self.assertEqual(circuit["relay_uid"], "")
        self.assertTrue(circuit["downgraded_from_relay"])
        self.assertEqual(circuit["role_source"], "relay_downgraded_ct")

    async def test_discover_circuit_metadata_recognizes_known_ct_without_warning(self):
        module = _load_influx_client_module()
        circuit_text = _single_circuit_csv(name="Tesla", classification="Consumption", device_type="007A")

        async def fake_post_flux(session, base_url, token, org, query):
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(
                return_value=(
                    True,
                    [
                        {
                            "uid": "001AAE17353D",
                            "device_label": "Garage Lights",
                            "load_name": "Garage Lights",
                        }
                    ],
                ),
            ),
        ):
            result = await module.discover_circuit_metadata(
                "http://example",
                "token",
                "org-1",
                sem_host="sem-host",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.warnings, [])
        assert result.circuit_map is not None
        circuit = result.circuit_map["UUID-1::1"]
        self.assertEqual(circuit["role"], "ct_sensor")
        self.assertEqual(circuit["role_source"], "known_ct_type")
        self.assertFalse(circuit["downgraded_from_relay"])

    async def test_fetch_influx_snapshot_uses_stored_circuit_map_and_preserves_duplicate_ct_channels(self):
        module = _load_influx_client_module()
        circuit_text = _live_like_circuit_csv()

        async def fake_post_flux(session, base_url, token, org, query):
            if "r.type == \"0000\"" in query:
                return True, "", "", False, False
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(return_value=(True, _sem_devices())),
        ):
            discovery = await module.discover_circuit_metadata("http://example", "token", "org-1", sem_host="sem-host")
            snapshot = await module.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                circuit_metadata=discovery.circuit_map,
                scale_state={},
            )

        self.assertTrue(snapshot.success)
        assert snapshot.data is not None
        demands = snapshot.data["presentDemands"]
        self.assertEqual(len(demands), 31)
        tesla_demands = [d for d in demands if d["influx_name"] == "Tesla"]
        self.assertEqual(len(tesla_demands), 3)
        aggregate = next(d for d in tesla_demands if d["uid"] == _TESLA_UUID)
        self.assertEqual(aggregate["name"], "Tesla")
        self.assertEqual(round(float(aggregate["power"]), 3), round(1.04 + 2.03, 3))
        self.assertEqual(round(float(aggregate["current"]), 3), round((0.022 + 0.022) / 2.0, 3))
        self.assertEqual(round(float(aggregate["voltage"]), 3), round(121.5 + 121.5, 3))
        leg_names = sorted(d["name"] for d in tesla_demands if d["uid"] != _TESLA_UUID)
        self.assertEqual(leg_names, ["Tesla Leg 1", "Tesla Leg 2"])
        self.assertFalse(snapshot.data["circuit_map_status"]["reconfigure_required"])

    async def test_fetch_influx_snapshot_flags_reconfigure_when_new_circuit_appears(self):
        module = _load_influx_client_module()
        circuit_text = _live_like_circuit_csv()

        async def fake_post_flux(session, base_url, token, org, query):
            if "r.type == \"0000\"" in query:
                return True, "", "", False, False
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), mock.patch.object(
            module,
            "fetch_sem_devices_from_sem",
            new=mock.AsyncMock(return_value=(True, _sem_devices())),
        ):
            discovery = await module.discover_circuit_metadata("http://example", "token", "org-1", sem_host="sem-host")

        circuit_map = dict(discovery.circuit_map or {})
        circuit_map.pop("B2F4BD96-9B57-BF0F-5AF0-1D6C5DB63869::1")

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux), self.assertNoLogs(
            module._LOGGER.name,
            level="WARNING",
        ):
            snapshot = await module.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                circuit_metadata=circuit_map,
                scale_state={},
            )

        self.assertTrue(snapshot.success)
        assert snapshot.data is not None
        self.assertTrue(snapshot.data["circuit_map_status"]["reconfigure_required"])
        self.assertIn(
            "B2F4BD96-9B57-BF0F-5AF0-1D6C5DB63869::1",
            snapshot.data["circuit_map_status"]["unknown_circuit_keys"],
        )
        unknown = snapshot.data["circuit_map_status"]["unknown_circuits"]
        self.assertEqual(
            unknown,
            [
                {
                    "circuit_key": "B2F4BD96-9B57-BF0F-5AF0-1D6C5DB63869::1",
                    "display_name": "Kylos Room",
                    "channel": "1",
                    "type": "0074",
                }
            ],
        )

    async def test_hub_circuit_measurements_fill_stored_relay_without_inventing_control(self):
        """Hub-only relay channels stay measurement-only and never beat UUID rows."""
        module = _load_influx_client_module()
        tesla_key = f"{_TESLA_UUID}::6"
        relay_key = "RELAY-UUID::1"
        circuit_text = _single_circuit_csv(
            name="Tesla",
            savant_uuid=_TESLA_UUID,
            channel="6",
            classification="Consumption",
            device_type="007A",
        )
        hub_text = "\n".join(
            [
                "result,table,_measurement,type,channel,_field,_value",
                ",_result,hub,0000,Energy.Circuit.Tesla.Power,power,999",
                ",_result,hub,0000,Energy.Circuit.Tesla.Energy,energy,999999",
                ",_result,hub,0000,Energy.Circuit.Garage Lights.Power,power,42.5",
                ",_result,hub,0000,Energy.Circuit.Garage Lights.Energy,energy,1234567",
            ]
        )
        circuit_map = {
            tesla_key: {
                "circuit_key": tesla_key,
                "savant_uuid": _TESLA_UUID,
                "channel": "6",
                "type": "007A",
                "role": "ct_sensor",
                "display_name": "Tesla",
                "influx_name": "Tesla",
                "legacy_uid": f"{_TESLA_UUID}.6",
                "legacy_base_uid": _TESLA_UUID,
            },
            relay_key: {
                "circuit_key": relay_key,
                "savant_uuid": "RELAY-UUID",
                "channel": "1",
                "type": "0000",
                "role": "relay",
                "relay_uid": "001AAE1732B0",
                "display_name": "Garage Lights",
                "influx_name": "Garage Ligh",
                "relay_match_name": "Garage Lights",
                "legacy_uid": "001AAE1732B0.0",
                "legacy_base_uid": "001AAE1732B0",
            },
        }

        async def fake_post_flux(session, base_url, token, org, query):
            if 'r.type == "0000"' in query:
                self.assertIn('r._field == "energy"', query)
                return True, hub_text, "", False, False
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux):
            snapshot = await module.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                circuit_metadata=circuit_map,
                scale_state={},
            )

        self.assertTrue(snapshot.success)
        assert snapshot.data is not None
        demands = {item["circuit_key"]: item for item in snapshot.data["presentDemands"]}
        self.assertEqual(demands[tesla_key]["power"], 123.4)
        relay = demands[relay_key]
        self.assertEqual(relay["power"], 42.5)
        self.assertEqual(relay["energy_raw"], 1234567.0)
        self.assertEqual(relay["energy"], 1234.567)
        self.assertEqual(relay["energy_scale_divisor"], 1_000)
        self.assertEqual(relay["energy_scale_status"], "hub_wh_to_kwh")
        self.assertEqual(relay["hub_match_source"], "hub_exact")
        self.assertFalse(relay["has_relay"])
        for unavailable_field in ("current", "voltage", "flags", "percentCommanded", "relay_uid"):
            self.assertNotIn(unavailable_field, relay)
        self.assertEqual(snapshot.data["circuit_map_status"]["missing_circuit_keys"], [])
        self.assertFalse(snapshot.data["circuit_map_status"]["reconfigure_required"])

    async def test_hub_aggregate_never_fills_one_missing_leg_of_an_ambiguous_alias(self):
        module = _load_influx_client_module()
        first_leg = f"{_TESLA_UUID}::6"
        missing_leg = f"{_TESLA_UUID}::7"
        circuit_text = _single_circuit_csv(
            name="Tesla",
            savant_uuid=_TESLA_UUID,
            channel="6",
            classification="Consumption",
            device_type="007A",
        )
        hub_text = "\n".join(
            [
                "result,table,_measurement,type,channel,_field,_value",
                ",_result,hub,0000,Energy.Circuit.Tesla.Power,power,999",
                ",_result,hub,0000,Energy.Circuit.Tesla.Energy,energy,999999",
            ]
        )
        circuit_map = {
            key: {
                "circuit_key": key,
                "savant_uuid": _TESLA_UUID,
                "channel": channel,
                "type": "007A",
                "role": "ct_sensor",
                "display_name": "Tesla",
                "influx_name": "Tesla",
                "legacy_uid": f"{_TESLA_UUID}.{channel}",
                "legacy_base_uid": _TESLA_UUID,
            }
            for key, channel in ((first_leg, "6"), (missing_leg, "7"))
        }

        async def fake_post_flux(session, base_url, token, org, query):
            if 'r.type == "0000"' in query:
                return True, hub_text, "", False, False
            return True, circuit_text, "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux):
            snapshot = await module.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                circuit_metadata=circuit_map,
                scale_state={},
            )

        self.assertTrue(snapshot.success)
        assert snapshot.data is not None
        demands = {item["circuit_key"]: item for item in snapshot.data["presentDemands"]}
        self.assertEqual(set(demands), {first_leg})
        self.assertEqual(demands[first_leg]["power"], 123.4)
        self.assertNotIn(missing_leg, demands)
        self.assertEqual(snapshot.data["circuit_map_status"]["missing_circuit_keys"], [missing_leg])
        self.assertTrue(snapshot.data["circuit_map_status"]["reconfigure_required"])

    async def test_distinct_raw_hub_labels_that_canonicalize_together_stay_ambiguous(self):
        module = _load_influx_client_module()
        circuit_key = "ISLAND::1"
        hub_text = "\n".join(
            [
                "result,table,_measurement,type,channel,_field,_value",
                ",_result,hub,0000,Energy.Circuit.Kitchen / Island.Power,power,42",
                ",_result,hub,0000,Energy.Circuit.Kitchen - Island.Energy,energy,42000",
            ]
        )
        circuit_map = {
            circuit_key: {
                "circuit_key": circuit_key,
                "savant_uuid": "ISLAND",
                "channel": "1",
                "role": "relay",
                "display_name": "Kitchen Island",
                "legacy_uid": "relay.0",
                "legacy_base_uid": "relay",
            }
        }

        async def fake_post_flux(session, base_url, token, org, query):
            if 'r.type == "0000"' in query:
                return True, hub_text, "", False, False
            return True, "", "", False, False

        with mock.patch.object(module, "_post_flux", side_effect=fake_post_flux):
            snapshot = await module.fetch_influx_snapshot(
                "http://example",
                "token",
                "org-1",
                circuit_metadata=circuit_map,
                scale_state={},
            )

        self.assertTrue(snapshot.success)
        assert snapshot.data is not None
        self.assertEqual(snapshot.data["presentDemands"], [])
        self.assertEqual(snapshot.data["circuit_map_status"]["missing_circuit_keys"], [circuit_key])
        self.assertTrue(snapshot.data["circuit_map_status"]["reconfigure_required"])

    def test_hub_matcher_recovers_known_label_variants_but_rejects_ambiguous_fuzzy_match(self):
        module = _load_influx_client_module()
        known_pairs = [
            ("Queen Room", "Queen"),
            ("Smoke Detector", "Smoke Detectors"),
            ("Yvettes Office", "Yvett's Office"),
            ("A/C Down Blower", "Downstairs A/C - Blower"),
            ("A/C Downstairs", "Downstairs A/C"),
            ("Kylos Room", "Kylo's Room"),
            ("Patio Kitchen", "Patio - TV / Kitchen"),
            ("A/C Upstairs", "Upstairs A/C"),
            ("Kitchen Island", "Kitchen - Island & Left Counter"),
            ("A/C Up Blower", "Upstairs A/C - Blower"),
            ("Garg Outlets", "Garage Outlets"),
        ]
        stored = {
            f"stored::{index}": {"display_name": stored_name}
            for index, (stored_name, _hub_name) in enumerate(known_pairs, start=1)
        }
        # Both candidates are high-scoring fuzzy variants for this hub label;
        # neither has enough separation to justify a match.
        stored.update(
            {
                "ambiguous::1": {"display_name": "Patio Light"},
                "ambiguous::2": {"display_name": "Patio Lightss"},
            }
        )
        hub_rows = {
            module._normalize_name(hub_name): {"name": hub_name}
            for _stored_name, hub_name in known_pairs
        }
        hub_rows[module._normalize_name("Patio Lights")] = {"name": "Patio Lights"}

        matches = module._resolve_hub_circuit_matches(hub_rows, stored, set())

        expected = {
            module._normalize_name(hub_name): f"stored::{index}"
            for index, (_stored_name, hub_name) in enumerate(known_pairs, start=1)
        }
        self.assertEqual({hub_key: key for hub_key, (key, _source) in matches.items()}, expected)
        self.assertNotIn(module._normalize_name("Patio Lights"), matches)
        self.assertEqual(matches[module._normalize_name("Yvett's Office")][1], "hub_fuzzy")
        self.assertEqual(matches[module._normalize_name("Patio - TV / Kitchen")][1], "hub_token_containment")

    def test_higher_tier_hub_match_is_excluded_from_later_containment_candidates(self):
        module = _load_influx_client_module()
        stored = {
            "island::1": {"display_name": "Kitchen Island"},
            "counter::1": {"display_name": "Kitchen Counter"},
        }
        hub_rows = {
            module._normalize_name("Kitchen - Counter"): {"name": "Kitchen - Counter"},
            module._normalize_name("Kitchen - Island & Left Counter"): {
                "name": "Kitchen - Island & Left Counter"
            },
        }

        matches = module._resolve_hub_circuit_matches(hub_rows, stored, set())

        self.assertEqual(
            matches[module._normalize_name("Kitchen - Counter")],
            ("counter::1", "hub_exact"),
        )
        self.assertEqual(
            matches[module._normalize_name("Kitchen - Island & Left Counter")],
            ("island::1", "hub_token_containment"),
        )


if __name__ == "__main__":
    unittest.main()
