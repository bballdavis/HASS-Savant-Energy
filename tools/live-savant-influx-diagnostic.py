"""Read-only direct-host diagnostic for Savant hub telemetry cadence.

Credentials are loaded from .savant-local.env and never printed. The Influx
token is retrieved through SSH when the local token is absent.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys

import paramiko
import requests


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _query(base_url: str, token: str, org: str, flux: str) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/v2/query",
        params={"org": org},
        headers={
            "Authorization": f"Token {token}",
            "Content-Type": "application/vnd.flux",
            "Accept": "text/csv",
        },
        data=flux,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def _system_query(base_url: str, token: str, org: str, bucket: str, window: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: {window})
  |> filter(fn: (r) => r.type == "0000")
  |> filter(fn: (r) => r._field == "power" or r._field == "energy")
  |> last()
'''
    return _query(base_url, token, org, flux)


def _all_system_fields_query(base_url: str, token: str, org: str, bucket: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: -15m)
  |> filter(fn: (r) => r.type == "0000")
  |> last()
'''
    return _query(base_url, token, org, flux)


def _circuit_query(base_url: str, token: str, org: str, bucket: str, window: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: {window})
  |> filter(fn: (r) => exists r.savantUUID and r.savantUUID != "")
  |> filter(fn: (r) => r._field == "power" or r._field == "current" or r._field == "voltage" or r._field == "energy")
  |> last()
'''
    return _query(base_url, token, org, flux)


def _hub_power_max_query(base_url: str, token: str, org: str, bucket: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: -24h)
  |> filter(fn: (r) => r.type == "0000" and r._field == "power")
  |> filter(fn: (r) => r.channel =~ /^Energy\\.Circuit\\..+\\.Power$/)
  |> group(columns: ["channel"])
  |> max()
'''
    return _query(base_url, token, org, flux)


def _all_recent_power_query(base_url: str, token: str, org: str, bucket: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: -15m)
  |> filter(fn: (r) => r._field == "power")
  |> last()
'''
    return _query(base_url, token, org, flux)


def _named_ct_query(base_url: str, token: str, org: str, bucket: str, aggregate: str = "last") -> str:
    operation = "|> last()" if aggregate == "last" else "|> max()"
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: -24h)
  |> filter(fn: (r) => r.type == "007A" and exists r.name and r.name != "")
  |> filter(fn: (r) => r._field == "power" or r._field == "current" or r._field == "voltage" or r._field == "energy")
  |> group(columns: ["_measurement", "channel", "_field", "name"])
  {operation}
'''
    return _query(base_url, token, org, flux)


def _all_ct_power_max_query(base_url: str, token: str, org: str, bucket: str) -> str:
    flux = f'''from(bucket: {json.dumps(bucket)})
  |> range(start: -24h)
  |> filter(fn: (r) => r.type == "007A" and r._field == "power")
  |> group(columns: ["_measurement", "channel", "name"])
  |> max()
'''
    return _query(base_url, token, org, flux)


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _read_host_credentials(env: dict[str, str]) -> tuple[str, list[object], str]:
    host = env["SAVANT_HOST"]
    user = env.get("SAVANT_SSH_USER", "RPM")
    password = env["SAVANT_SSH_PASSWORD"]
    token_path = env.get("SAVANT_INFLUX_TOKEN_PATH") or (
        "/data/RPM/GNUstep/Library/ApplicationSupport/"
        "RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken"
    )
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password, timeout=10, look_for_keys=False, allow_agent=False)
    metadata: list[object] = []
    load_identifiers_text = ""
    try:
        sftp = ssh.open_sftp()
        with sftp.open(token_path, "r") as stream:
            token = stream.read().decode("utf-8").strip()
        parent = str(Path(token_path).parent).replace("\\", "/")
        for name in (".influxtoken", ".influxsetup"):
            try:
                with sftp.open(f"{parent}/{name}", "r") as stream:
                    metadata.append(json.loads(stream.read().decode("utf-8")))
            except (OSError, ValueError, TypeError):
                continue
        try:
            statusfiles_root = parent.rsplit("/", 1)[0]
            with sftp.open(f"{statusfiles_root}/loadIdentifiers.json", "r") as stream:
                load_identifiers_text = stream.read().decode("utf-8")
        except OSError:
            pass
        return token, metadata, load_identifiers_text
    finally:
        ssh.close()


def _find_org(metadata: list[object]) -> str:
    candidates: list[str] = []

    def walk(value: object, parent_key: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if "org" in lowered and isinstance(child, str) and child.strip():
                    candidates.append(child.strip())
                walk(child, lowered)
        elif isinstance(value, list):
            for child in value:
                walk(child, parent_key)

    for item in metadata:
        walk(item)
    if not candidates:
        return ""
    candidate = candidates[0]
    if "/api/v2/orgs/" in candidate:
        candidate = candidate.rsplit("/", 1)[-1]
    return candidate


def main() -> int:
    client = _load_module("savant_influx_client", ROOT / "custom_components" / "savant_energy" / "influx_client.py")
    ssh_helper = _load_module("savant_ssh_helper", ROOT / "custom_components" / "savant_energy" / "ssh_helper.py")
    env = _load_env(ROOT / ".savant-local.env")
    token, metadata, load_identifiers_text = _read_host_credentials(env)
    load_identifiers = ssh_helper._parse_load_identifiers(load_identifiers_text)
    if not token:
        raise RuntimeError("Could not retrieve a usable Influx token.")

    base_url = env.get("SAVANT_INFLUX_URL") or f"http://{env['SAVANT_HOST']}:8086"
    org = env.get("SAVANT_INFLUX_ORG", "").strip()
    if not org:
        org = _find_org(metadata)
    if not org:
        raise RuntimeError("Could not discover an Influx organization from host metadata.")
    bucket = env.get("SAVANT_INFLUX_BUCKET", "").strip() or "localHub"

    report: dict[str, object] = {"windows": {}}
    all_system_rows = client._parse_influx_csv(
        _all_system_fields_query(base_url, token, org, bucket)
    )
    report["all_system_fields"] = {
        "row_count": len(all_system_rows),
        "fields": sorted({row.get("_field") for row in all_system_rows if row.get("_field")}),
        "rows": [
            {
                "channel": row.get("channel"),
                "field": row.get("_field"),
                "value": row.get("_value"),
                "time": row.get("_time"),
            }
            for row in all_system_rows
            if row.get("channel") and not str(row.get("channel")).startswith("Energy.Circuit.")
        ],
    }
    for window in ("-2m", "-15m", "-24h", "-7d"):
        raw = _system_query(base_url, token, org, bucket, window)
        parsed = client._parse_influx_csv(raw)
        circuits = client._build_hub_circuit_rows(raw)
        times = sorted({row.get("_time", "") for row in parsed if row.get("_time")})
        nonzero_power = sorted(
            (
                {"name": value.get("name"), "power": value.get("power"), "time": value.get("power_time")}
                for value in circuits.values()
                if abs(float(value.get("power") or 0)) > 0.000001
            ),
            key=lambda item: abs(float(item["power"] or 0)),
            reverse=True,
        )
        nonzero_system = sorted(
            (
                {
                    "channel": row.get("channel"),
                    "field": row.get("_field"),
                    "value": float(row.get("_value") or 0),
                    "time": row.get("_time"),
                }
                for row in parsed
                if abs(float(row.get("_value") or 0)) > 0.000001
            ),
            key=lambda item: abs(item["value"]),
            reverse=True,
        )
        report["windows"][window] = {
            "parsed_rows": len(parsed),
            "hub_circuit_rows": len(circuits),
            "nonzero_power_rows": len(nonzero_power),
            "oldest_timestamp": times[0] if times else None,
            "newest_timestamp": times[-1] if times else None,
            "top_nonzero_power": nonzero_power[:12],
            "top_nonzero_system": nonzero_system[:20],
        }

    detailed_raw = _circuit_query(base_url, token, org, bucket, "-2m")
    _device, detailed = client._build_circuit_rows(detailed_raw)
    report["detailed_circuits"] = [
        {
            "name": row.get("name"),
            "channel": row.get("channel"),
            "power": row.get("power"),
            "current": row.get("current"),
            "voltage": row.get("voltage"),
            "energy": row.get("energy"),
        }
        for _key, row in sorted(detailed.items())
    ]
    maxima = client._parse_influx_csv(_hub_power_max_query(base_url, token, org, bucket))
    report["hub_circuit_power_24h_maxima"] = sorted(
        (
            {
                "channel": row.get("channel"),
                "max_power": float(row.get("_value") or 0),
                "time": row.get("_time"),
            }
            for row in maxima
            if abs(float(row.get("_value") or 0)) > 0.000001
        ),
        key=lambda item: abs(item["max_power"]),
        reverse=True,
    )
    all_power_rows = client._parse_influx_csv(_all_recent_power_query(base_url, token, org, bucket))
    report["all_recent_power_summary"] = {
        "rows": len(all_power_rows),
        "measurements": sorted({row.get("_measurement") for row in all_power_rows if row.get("_measurement")}),
        "types": sorted({row.get("type") for row in all_power_rows if row.get("type")}),
        "rows_with_savant_uuid": sum(1 for row in all_power_rows if row.get("savantUUID")),
        "nonzero_rows": sorted(
            (
                {
                    "measurement": row.get("_measurement"),
                    "type": row.get("type"),
                    "channel": row.get("channel"),
                    "name": row.get("name"),
                    "has_savant_uuid": bool(row.get("savantUUID")),
                    "power": float(row.get("_value") or 0),
                    "time": row.get("_time"),
                }
                for row in all_power_rows
                if abs(float(row.get("_value") or 0)) > 0.000001
            ),
            key=lambda item: abs(item["power"]),
            reverse=True,
        )[:100],
    }
    report["all_ct_power_24h_max"] = sorted(
        (
            {
                "measurement": row.get("_measurement"),
                "channel": row.get("channel"),
                "name": row.get("name"),
                "max_power": float(row.get("_value") or 0),
                "time": row.get("_time"),
            }
            for row in client._parse_influx_csv(_all_ct_power_max_query(base_url, token, org, bucket))
        ),
        key=lambda item: abs(item["max_power"]),
        reverse=True,
    )
    for aggregate in ("last", "max"):
        named_ct_rows = client._parse_influx_csv(_named_ct_query(base_url, token, org, bucket, aggregate))
        report[f"named_ct_{aggregate}"] = sorted(
            (
                {
                    "measurement": row.get("_measurement"),
                    "channel": row.get("channel"),
                    "name": row.get("name"),
                    "field": row.get("_field"),
                    "value": float(row.get("_value") or 0),
                    "time": row.get("_time"),
                    "has_savant_uuid": bool(row.get("savantUUID")),
                }
                for row in named_ct_rows
            ),
            key=lambda item: (str(item["name"]), str(item["channel"]), str(item["field"])),
        )
    shaped = asyncio.run(
        client.fetch_influx_snapshot(
            base_url,
            token,
            org,
            circuit_metadata={},
            scale_state={},
            range_start="-2m",
            influx_bucket=bucket,
        )
    )
    report["integration_shaping"] = {
        "success": shaped.success,
        "error_type": shaped.error_type,
        "demands": [
            {
                "uid": item.get("uid"),
                "name": item.get("name"),
                "channel": item.get("channel"),
                "role": item.get("role"),
                "power": item.get("power"),
                "current": item.get("current"),
                "voltage": item.get("voltage"),
                "energy": item.get("energy"),
                "has_relay": item.get("has_relay"),
            }
            for item in ((shaped.data or {}).get("presentDemands") or [])
        ],
        "system_data": (shaped.data or {}).get("system_data"),
        "status": (shaped.data or {}).get("circuit_map_status"),
    }
    discovery = asyncio.run(
        client.discover_circuit_metadata(
            base_url,
            token,
            org,
            sem_host=env.get("SAVANT_SEM_HOST", "192.168.1.108"),
            range_start="-2m",
            influx_bucket=bucket,
            host_load_identifiers=load_identifiers,
        )
    )
    report["integration_discovery"] = {
        "success": discovery.success,
        "error_key": discovery.error_key,
        "query_window": discovery.query_window,
        "host_identity_records": len(load_identifiers),
        "circuits": [
            {
                "circuit_key": key,
                "savant_uuid": metadata.get("savant_uuid"),
                "source_uid": metadata.get("source_uid"),
                "name": metadata.get("display_name"),
                "channel": metadata.get("channel"),
                "role": metadata.get("role"),
                "role_source": metadata.get("role_source"),
                "has_relay_uid": bool(metadata.get("relay_uid")),
            }
            for key, metadata in sorted((discovery.circuit_map or {}).items())
        ],
        "warnings": discovery.warnings,
    }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
