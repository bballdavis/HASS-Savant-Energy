#!/usr/bin/env python3
"""
Savant InfluxDB 2 Discovery Tool

Discovers and explores InfluxDB 2 data on the Savant host to identify
energy/power/current/voltage measurement schemas for Home Assistant integration.

Usage:
    python3 tools/savant_influx_probe.py discover \
        --influx-url http://192.168.1.14:8086 \
        --ssh-host 192.168.1.14 \
        --ssh-user RPM \
        --cache-token

    python3 tools/savant_influx_probe.py list-orgs \
        --influx-url http://192.168.1.14:8086 \
        --token "token_string_here"
"""

import argparse
import csv
import io
import json
import os
import sys
import getpass
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


# Token masking for logs
def mask_token(token: str) -> str:
    """Mask token showing only first 4 and last 4 characters."""
    if not token or len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def load_env_file(filepath: str) -> Dict[str, str]:
    """Parse .env file manually if python-dotenv is not available."""
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars

    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)

    return env_vars


def get_token_from_ssh(
    host: str,
    user: str,
    password: Optional[str],
    token_path: str
) -> Optional[str]:
    """Retrieve InfluxDB read token from remote Savant host via SSH."""
    if not HAS_PARAMIKO:
        print(
            "Error: paramiko not installed. Install with: pip install paramiko",
            file=sys.stderr
        )
        print(
            f"Alternatively, provide token via --token or SAVANT_INFLUX_TOKEN env var",
            file=sys.stderr
        )
        return None

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"Connecting to {user}@{host}...", file=sys.stderr)
        client.connect(host, username=user, password=password, timeout=10)

        print(f"Reading token from {token_path}...", file=sys.stderr)
        stdin, stdout, stderr = client.exec_command(f"cat {token_path}")
        token = stdout.read().decode().strip()

        if not token:
            error_msg = stderr.read().decode().strip()
            print(f"Error reading token file: {error_msg}", file=sys.stderr)
            client.close()
            return None

        client.close()
        print(f"Token retrieved ({mask_token(token)})", file=sys.stderr)
        return token
    except Exception as e:
        print(f"Error connecting to {host}: {e}", file=sys.stderr)
        return None


def get_token(args: argparse.Namespace, env_vars: Dict[str, str]) -> Optional[str]:
    """Resolve token from multiple sources in priority order."""

    # 1. CLI argument
    if hasattr(args, 'token') and args.token:
        print(f"Using token from --token argument ({mask_token(args.token)})", file=sys.stderr)
        return args.token

    # 2. Environment variable
    if "SAVANT_INFLUX_TOKEN" in env_vars and env_vars["SAVANT_INFLUX_TOKEN"]:
        token = env_vars["SAVANT_INFLUX_TOKEN"]
        print(f"Using token from SAVANT_INFLUX_TOKEN ({mask_token(token)})", file=sys.stderr)
        return token

    # 3. Local token cache file
    token_cache = ".savant-influx-read.token"
    if os.path.exists(token_cache):
        try:
            with open(token_cache, "r") as f:
                token = f.read().strip()
            if token:
                print(f"Using cached token ({mask_token(token)})", file=sys.stderr)
                return token
        except Exception as e:
            print(f"Warning: Could not read token cache: {e}", file=sys.stderr)

    # 4. SSH retrieval
    if hasattr(args, 'ssh_host') and args.ssh_host:
        ssh_user = getattr(args, 'ssh_user', None) or env_vars.get('SAVANT_SSH_USER', 'RPM')
        ssh_password = getattr(args, 'ssh_password', None)

        if not ssh_password:
            ssh_password = env_vars.get('SAVANT_SSH_PASSWORD')

        if not ssh_password:
            ssh_password = getpass.getpass(f"SSH password for {ssh_user}@{args.ssh_host}: ")

        token_path = (
            getattr(args, 'ssh_token_path', None) or
            env_vars.get(
                'SAVANT_INFLUX_TOKEN_PATH',
                '/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken'
            )
        )

        token = get_token_from_ssh(args.ssh_host, ssh_user, ssh_password, token_path)

        if token and getattr(args, 'cache_token', False):
            try:
                with open(token_cache, "w") as f:
                    f.write(token)
                print(f"Token cached to {token_cache} (gitignored)", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not cache token: {e}", file=sys.stderr)

        return token

    return None


def parse_influx_response(response_text: str) -> List[Dict[str, Any]]:
    """Parse InfluxDB annotated CSV response format."""
    rows = []
    reader = csv.DictReader(io.StringIO(response_text))

    if not reader or not reader.fieldnames:
        return rows

    try:
        for row in reader:
            if not row:
                continue
            # Skip annotation rows (start with #)
            if any(k.startswith("#") for k in row.keys()):
                continue
            rows.append(row)
    except Exception as e:
        print(f"Warning: CSV parsing error: {e}", file=sys.stderr)

    return rows


def influx_query(
    base_url: str,
    token: str,
    org_id: str,
    flux_query: str,
    timeout: int = 30
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """Execute Flux query against InfluxDB 2."""
    url = urljoin(base_url, "/api/v2/query")

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/vnd.flux",
        "Accept": "text/csv",
    }

    params = {"org": org_id}

    try:
        response = requests.post(
            url,
            data=flux_query,
            headers=headers,
            params=params,
            timeout=timeout
        )

        if response.status_code == 401:
            return False, [], "Unauthorized (401) - invalid or expired token"
        elif response.status_code == 403:
            return False, [], "Forbidden (403) - insufficient permissions"
        elif response.status_code != 200:
            return False, [], f"HTTP {response.status_code}: {response.text[:200]}"

        rows = parse_influx_response(response.text)
        return True, rows, ""

    except requests.Timeout:
        return False, [], "Request timeout"
    except Exception as e:
        return False, [], str(e)


def list_orgs(base_url: str, token: str, timeout: int = 30) -> Tuple[bool, List[Dict[str, Any]], str]:
    """List InfluxDB organizations."""
    url = urljoin(base_url, "/api/v2/orgs")
    headers = {"Authorization": f"Token {token}"}

    try:
        response = requests.get(url, headers=headers, timeout=timeout)

        if response.status_code == 401:
            return False, [], "Unauthorized (401) - invalid or expired token"
        elif response.status_code == 403:
            return False, [], "Forbidden (403) - insufficient permissions"
        elif response.status_code != 200:
            return False, [], f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        orgs = data.get("orgs", [])
        return True, orgs, ""

    except Exception as e:
        return False, [], str(e)


def list_buckets(
    base_url: str,
    token: str,
    org_id: str,
    timeout: int = 30
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """List buckets for an organization."""
    url = urljoin(base_url, "/api/v2/buckets")
    headers = {"Authorization": f"Token {token}"}
    params = {"org": org_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)

        if response.status_code == 401:
            return False, [], "Unauthorized (401) - invalid or expired token"
        elif response.status_code == 403:
            return False, [], "Forbidden (403) - insufficient permissions"
        elif response.status_code != 200:
            return False, [], f"HTTP {response.status_code}: {response.text[:200]}"

        data = response.json()
        buckets = data.get("buckets", [])
        return True, buckets, ""

    except Exception as e:
        return False, [], str(e)


def score_candidate(name: str, score_keywords: List[str]) -> int:
    """Score a string against candidate keywords (case-insensitive)."""
    name_lower = name.lower()
    score = 0
    for kw in score_keywords:
        if kw.lower() in name_lower:
            score += 10
    return score


def find_candidates(
    measurements: List[str],
    fields: List[str],
    energy_keywords: List[str] = None,
    tag_keywords: List[str] = None
) -> Dict[str, Any]:
    """Score and rank candidate measurements/fields for energy data."""
    if not energy_keywords:
        energy_keywords = ["energy", "power", "watt", "watts", "current", "voltage", "demand", "load", "circuit", "breaker", "panel", "sem"]

    if not tag_keywords:
        tag_keywords = ["uid", "name", "channel", "classification"]

    candidates = {
        "measurements": [],
        "fields": []
    }

    for m in measurements:
        score = score_candidate(m, energy_keywords)
        if score > 0:
            candidates["measurements"].append({"name": m, "score": score})

    for f in fields:
        score = score_candidate(f, energy_keywords)
        if score > 0:
            candidates["fields"].append({"name": f, "score": score})

    candidates["measurements"].sort(key=lambda x: x["score"], reverse=True)
    candidates["fields"].sort(key=lambda x: x["score"], reverse=True)

    return candidates


def discover_all(base_url: str, token: str) -> Optional[Dict[str, Any]]:
    """Run full discovery across all orgs and buckets."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "influx_url": base_url,
        "orgs": [],
        "buckets_by_org": {},
        "measurements_by_bucket": {},
        "fields_by_bucket": {},
        "tags_by_bucket": {},
        "tag_values_by_bucket": {},
        "recent_samples_by_bucket": {},
        "candidates": {}
    }

    # Get orgs
    print("\n[1/6] Fetching organizations...", file=sys.stderr)
    success, orgs, error = list_orgs(base_url, token)
    if not success:
        print(f"Error: {error}", file=sys.stderr)
        return None

    if not orgs:
        print("No organizations found.", file=sys.stderr)
        return None

    result["orgs"] = orgs
    print(f"Found {len(orgs)} organization(s)", file=sys.stderr)

    all_measurements = set()
    all_fields = set()

    # For each org, get buckets
    for org in orgs:
        org_id = org.get("id")
        org_name = org.get("name", "unknown")

        print(f"\n[2/6] Fetching buckets for org '{org_name}'...", file=sys.stderr)
        success, buckets, error = list_buckets(base_url, token, org_id)
        if not success:
            print(f"  Error: {error}", file=sys.stderr)
            continue

        result["buckets_by_org"][org_name] = buckets
        print(f"  Found {len(buckets)} bucket(s)", file=sys.stderr)

        # For each bucket, get schema and sample data
        for bucket in buckets:
            bucket_id = bucket.get("id")
            bucket_name = bucket.get("name", "unknown")

            print(f"\n[3/6] Fetching measurements for '{bucket_name}'...", file=sys.stderr)
            query = f'import "influxdata/influxdb/schema"\nschema.measurements(bucket: "{bucket_name}")'
            success, rows, error = influx_query(base_url, token, org_id, query)
            if success:
                measurements = [r.get("_value", "") for r in rows if r.get("_value")]
                result["measurements_by_bucket"][bucket_name] = measurements
                all_measurements.update(measurements)
                print(f"  Found {len(measurements)} measurement(s)", file=sys.stderr)
            else:
                print(f"  Warning: {error}", file=sys.stderr)

            print(f"[4/6] Fetching field keys for '{bucket_name}'...", file=sys.stderr)
            query = f'import "influxdata/influxdb/schema"\nschema.fieldKeys(bucket: "{bucket_name}")'
            success, rows, error = influx_query(base_url, token, org_id, query)
            if success:
                fields = [r.get("_value", "") for r in rows if r.get("_value")]
                result["fields_by_bucket"][bucket_name] = fields
                all_fields.update(fields)
                print(f"  Found {len(fields)} field(s)", file=sys.stderr)
            else:
                print(f"  Warning: {error}", file=sys.stderr)

            print(f"[5/6] Fetching tag keys for '{bucket_name}'...", file=sys.stderr)
            query = f'import "influxdata/influxdb/schema"\nschema.tagKeys(bucket: "{bucket_name}")'
            success, rows, error = influx_query(base_url, token, org_id, query)
            if success:
                tags = [r.get("_value", "") for r in rows if r.get("_value")]
                result["tags_by_bucket"][bucket_name] = tags
                print(f"  Found {len(tags)} tag(s)", file=sys.stderr)
            else:
                print(f"  Warning: {error}", file=sys.stderr)

            # Get tag values for key tags
            for tag_key in ["name", "uid", "channel", "classification"]:
                query = f'import "influxdata/influxdb/schema"\nschema.tagValues(bucket: "{bucket_name}", tag: "{tag_key}")'
                success, rows, error = influx_query(base_url, token, org_id, query)
                if success:
                    values = [r.get("_value", "") for r in rows if r.get("_value")]
                    if values:
                        if bucket_name not in result["tag_values_by_bucket"]:
                            result["tag_values_by_bucket"][bucket_name] = {}
                        result["tag_values_by_bucket"][bucket_name][tag_key] = values

            # Sample recent data
            print(f"[6/6] Fetching recent samples from '{bucket_name}'...", file=sys.stderr)
            query = f'from(bucket: "{bucket_name}")\n  |> range(start: -15m)\n  |> limit(n: 100)'
            success, rows, error = influx_query(base_url, token, org_id, query)
            if success:
                result["recent_samples_by_bucket"][bucket_name] = rows
                print(f"  Retrieved {len(rows)} row(s)", file=sys.stderr)
            else:
                print(f"  Warning: {error}", file=sys.stderr)

    # Find candidates
    result["candidates"] = find_candidates(list(all_measurements), list(all_fields))

    return result


def save_discovery_output(discovery: Dict[str, Any]) -> str:
    """Save discovery results to structured output files."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(f"savant_influx_discovery/{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving discovery output to {output_dir}/", file=sys.stderr)

    # Save full JSON
    with open(output_dir / "discovery.json", "w") as f:
        json.dump(discovery, f, indent=2, default=str)
    print(f"  ✓ discovery.json", file=sys.stderr)

    # Save orgs
    with open(output_dir / "orgs.json", "w") as f:
        json.dump(discovery["orgs"], f, indent=2, default=str)
    print(f"  ✓ orgs.json", file=sys.stderr)

    # Save buckets by org
    with open(output_dir / "buckets.json", "w") as f:
        json.dump(discovery["buckets_by_org"], f, indent=2, default=str)
    print(f"  ✓ buckets.json", file=sys.stderr)

    # Save measurements
    all_measurements = {}
    for bucket, measurements in discovery["measurements_by_bucket"].items():
        all_measurements[bucket] = measurements
    with open(output_dir / "measurements.json", "w") as f:
        json.dump(all_measurements, f, indent=2, default=str)
    print(f"  ✓ measurements.json", file=sys.stderr)

    # Save fields
    all_fields = {}
    for bucket, fields in discovery["fields_by_bucket"].items():
        all_fields[bucket] = fields
    with open(output_dir / "fields.json", "w") as f:
        json.dump(all_fields, f, indent=2, default=str)
    print(f"  ✓ fields.json", file=sys.stderr)

    # Save tags
    all_tags = {}
    for bucket, tags in discovery["tags_by_bucket"].items():
        all_tags[bucket] = tags
    with open(output_dir / "tags.json", "w") as f:
        json.dump(all_tags, f, indent=2, default=str)
    print(f"  ✓ tags.json", file=sys.stderr)

    # Save tag values
    with open(output_dir / "tag_values.json", "w") as f:
        json.dump(discovery["tag_values_by_bucket"], f, indent=2, default=str)
    print(f"  ✓ tag_values.json", file=sys.stderr)

    # Save recent samples as JSONL and CSV
    for bucket, rows in discovery["recent_samples_by_bucket"].items():
        safe_bucket_name = re.sub(r'[^\w-]', '_', bucket)

        if rows:
            # JSONL
            with open(output_dir / f"recent_sample_{safe_bucket_name}.jsonl", "w") as f:
                for row in rows:
                    f.write(json.dumps(row, default=str) + "\n")

            # CSV
            with open(output_dir / f"recent_sample_{safe_bucket_name}.csv", "w") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            print(f"  ✓ recent_sample_{safe_bucket_name}.jsonl/.csv", file=sys.stderr)

    # Save candidates
    with open(output_dir / "candidate_energy_series.json", "w") as f:
        json.dump(discovery["candidates"], f, indent=2, default=str)
    print(f"  ✓ candidate_energy_series.json", file=sys.stderr)

    # Generate summary markdown
    summary_md = generate_summary(discovery)
    with open(output_dir / "summary.md", "w") as f:
        f.write(summary_md)
    print(f"  ✓ summary.md", file=sys.stderr)

    return str(output_dir)


def generate_summary(discovery: Dict[str, Any]) -> str:
    """Generate markdown summary of discovery results."""
    lines = [
        "# Savant InfluxDB Discovery Summary",
        "",
        f"**Timestamp:** {discovery['timestamp']}",
        f"**InfluxDB URL:** {discovery['influx_url']}",
        "",
        "## Organizations",
        "",
    ]

    for org in discovery["orgs"]:
        lines.append(f"- **{org.get('name', 'unknown')}** (ID: {org.get('id', 'N/A')})")

    lines.extend(["", "## Buckets", ""])

    for org_name, buckets in discovery["buckets_by_org"].items():
        lines.append(f"### {org_name}")
        for bucket in buckets:
            lines.append(f"- {bucket.get('name', 'unknown')}")
        lines.append("")

    lines.extend(["## Measurements Found", ""])

    for bucket_name, measurements in discovery["measurements_by_bucket"].items():
        if measurements:
            lines.append(f"### {bucket_name}")
            for m in measurements[:10]:
                lines.append(f"- {m}")
            if len(measurements) > 10:
                lines.append(f"- ... and {len(measurements) - 10} more")
            lines.append("")

    lines.extend(["## Fields Found", ""])

    for bucket_name, fields in discovery["fields_by_bucket"].items():
        if fields:
            lines.append(f"### {bucket_name}")
            for f in fields[:15]:
                lines.append(f"- {f}")
            if len(fields) > 15:
                lines.append(f"- ... and {len(fields) - 15} more")
            lines.append("")

    lines.extend(["## Tags Found", ""])

    for bucket_name, tags in discovery["tags_by_bucket"].items():
        if tags:
            lines.append(f"### {bucket_name}")
            for t in tags:
                lines.append(f"- {t}")
            lines.append("")

    lines.extend(["## Top Candidate Energy/Power Fields", ""])

    if discovery["candidates"]["fields"]:
        for item in discovery["candidates"]["fields"][:5]:
            lines.append(f"- **{item['name']}** (score: {item['score']})")
    else:
        lines.append("*No strong candidates found*")

    lines.extend(["", "## Top Candidate Measurements", ""])

    if discovery["candidates"]["measurements"]:
        for item in discovery["candidates"]["measurements"][:5]:
            lines.append(f"- **{item['name']}** (score: {item['score']})")
    else:
        lines.append("*No strong candidates found*")

    lines.extend(["", "## Recent Sample Data", ""])

    for bucket_name, rows in discovery["recent_samples_by_bucket"].items():
        if rows:
            lines.append(f"### {bucket_name}")
            lines.append(f"Found {len(rows)} row(s). First row:")
            lines.append("```json")
            lines.append(json.dumps(rows[0], indent=2, default=str))
            lines.append("```")
            lines.append("")

    lines.extend(["", "## Next Steps", ""])
    lines.extend([
        "1. Review the detailed JSON files for schema information",
        "2. Identify the primary bucket and measurement for energy data",
        "3. Check which fields (power, energy, current, voltage) are available",
        "4. Note the tag keys (uid, name, channel, etc.) for circuit identification",
        "5. Verify sample data to understand units and scaling",
        "6. Use recommended Flux queries below for HA integration",
        "",
        "## Recommended Flux Queries for HA Integration",
        "",
        "### Get latest energy values for all circuits",
        "```flux",
        "from(bucket: \"BUCKET_NAME\")",
        '  |> range(start: -15m)',
        '  |> filter(fn: (r) => r._measurement == "MEASUREMENT_NAME")',
        '  |> filter(fn: (r) => r._field =~ /(?i)(power|energy|current|voltage)/)',
        '  |> last()',
        "```",
        "",
        "### Get specific field by circuit uid",
        "```flux",
        "from(bucket: \"BUCKET_NAME\")",
        '  |> range(start: -1h)',
        '  |> filter(fn: (r) => r._measurement == "MEASUREMENT_NAME")',
        '  |> filter(fn: (r) => r._field == \"power\")',
        '  |> filter(fn: (r) => r.uid == \"CIRCUIT_UID\")',
        "```",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Savant InfluxDB Discovery Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Global args
    parser.add_argument("--influx-url", default=None, help="InfluxDB base URL (default: http://192.168.1.14:8086)")
    parser.add_argument("--token", help="InfluxDB read token")

    # SSH args
    parser.add_argument("--ssh-host", help="SSH host IP or hostname")
    parser.add_argument("--ssh-user", default="RPM", help="SSH user (default: RPM)")
    parser.add_argument("--ssh-password", help="SSH password (prompted if not provided)")
    parser.add_argument("--ssh-token-path", help="Remote path to token file")
    parser.add_argument("--cache-token", action="store_true", help="Cache retrieved token locally")

    # discover command
    discover_parser = subparsers.add_parser("discover", help="Full discovery of all orgs/buckets/measurements")
    discover_parser.set_defaults(func=cmd_discover)

    # list-orgs command
    list_orgs_parser = subparsers.add_parser("list-orgs", help="List organizations")
    list_orgs_parser.set_defaults(func=cmd_list_orgs)

    # list-buckets command
    list_buckets_parser = subparsers.add_parser("list-buckets", help="List buckets in an org")
    list_buckets_parser.add_argument("--org", required=True, help="Organization ID or name")
    list_buckets_parser.set_defaults(func=cmd_list_buckets)

    args = parser.parse_args()

    # Load environment variables
    if HAS_DOTENV:
        load_dotenv(".savant-local.env")
    env_vars = load_env_file(".savant-local.env")

    # Set defaults from env
    if not args.influx_url:
        args.influx_url = env_vars.get("SAVANT_INFLUX_URL", "http://192.168.1.14:8086")

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(0)

    # Resolve token
    token = get_token(args, env_vars)
    if not token:
        print("Error: Could not obtain InfluxDB token", file=sys.stderr)
        sys.exit(1)

    args.func(args, env_vars, token)


def cmd_discover(args: argparse.Namespace, env_vars: Dict[str, str], token: str):
    """Run full discovery."""
    print(f"\n=== Starting Discovery ===", file=sys.stderr)
    print(f"InfluxDB URL: {args.influx_url}", file=sys.stderr)

    discovery = discover_all(args.influx_url, token)
    if not discovery:
        print("Discovery failed.", file=sys.stderr)
        sys.exit(1)

    output_dir = save_discovery_output(discovery)
    print(f"\n✓ Discovery complete! Results saved to: {output_dir}", file=sys.stderr)
    print(f"\nView summary at: {output_dir}/summary.md", file=sys.stderr)


def cmd_list_orgs(args: argparse.Namespace, env_vars: Dict[str, str], token: str):
    """List organizations."""
    success, orgs, error = list_orgs(args.influx_url, token)
    if not success:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(orgs, indent=2, default=str))


def cmd_list_buckets(args: argparse.Namespace, env_vars: Dict[str, str], token: str):
    """List buckets in an organization."""
    success, buckets, error = list_buckets(args.influx_url, token, args.org)
    if not success:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(buckets, indent=2, default=str))


if __name__ == "__main__":
    main()
