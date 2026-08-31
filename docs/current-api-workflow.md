# Savant Energy Current API Workflow (>=11.2)

This document describes the implemented current-mode workflow for Savant firmware >=11.2. Current mode uses InfluxDB for telemetry and the SEM interfaces for relay identity and control. Legacy mode remains available for older firmware.

## Why current mode exists

Savant changed the Panel Bridge Controller and Smart Energy Monitor protocol in firmware 11.2. The old integration read a relay snapshot from a PBC TCP feed. Current firmware stores energy data in InfluxDB 2 and exposes relay status through the SEM companion services.

The integration now keeps those paths separate:

1. InfluxDB provides live circuit readings, hardware energy counters, and system channels.
2. The SEM companion status API and PBC inventory feed provide relay identity information.
3. The SEM TCP command socket handles relay control.

This split also gives current mode access to CT loads, solar, battery, grid, and load-group data that was not available in the old snapshot feed.

## Network endpoints

The integration uses these default endpoints:

- InfluxDB API: `http://<host_ip>:8086`
- SEM companion status API: `http://<pbc_ip>:8644/companion/status`
- SEM relay command socket: `<pbc_ip>:2000` over TCP
- PBC inventory websocket: the configured PBC host and its current-mode inventory service

The port values remain internal defaults. The config flow asks for the PBC IP and, for current mode, the host IP. It does not ask users to enter ports.

## Setup flow

### Auto mode

Auto mode starts with the PBC IP and probes the legacy activity feed.

1. If the legacy feed responds with usable data, the entry stays in legacy mode.
2. If the legacy feed is unavailable, the flow asks for the Savant host IP and current-mode credentials.
3. The flow retrieves and validates an InfluxDB read token through SSH bootstrap.
4. The flow discovers the correct Influx organization by checking host metadata, buckets, and the organization list.
5. The flow discovers the circuit map, including relay matches and CT classifications.
6. The current-mode entry is created with the validated token, organization, circuit map, and generated SSH key.

If multiple organizations contain plausible Savant data, the flow shows a selection form instead of guessing.

Existing token-only entries remain supported at runtime. Reconfigure directs them through SSH bootstrap and does not replace the old token/auth state until a candidate validates against Savant data and the generated key is installed and verified.

### SSH token bootstrap

During SSH token bootstrap, the integration:

1. Generates an Ed25519 key pair.
2. Connects to the Savant host as `RPM` with the supplied password.
3. Adds the public key to the host's authorized keys file idempotently.
4. Reads the InfluxDB token from the current Savant status file.
5. Reads available organization and bucket metadata from the host.
6. Stores the private key and token in the Home Assistant config entry.

The password is used only for bootstrap and is not persisted. The stored private key can later refresh the token after a 401 response without asking for the password again.

The primary token path is:

```text
/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
```

The integration also checks the alternate `/data/home/RPM/...` layout and bounded discovery results. It reads adjacent host metadata for every candidate, then validates candidates in deterministic order with organization/bucket discovery and a real circuit query. It only persists a candidate that completes that chain; an empty organization list can still succeed through metadata and direct bucket queries.

### Organization discovery

The organization resolver uses the following order:

1. Organization and bucket metadata read over SSH.
2. InfluxDB bucket listing.
3. InfluxDB organization listing.

Each candidate is probed for Savant rows over short and wider windows. Candidates are scored using circuit count, expected fields, recent data, power, and the source of the candidate. A clear winner is stored automatically. Ambiguous candidates are shown to the user with a readable summary.

The resolver treats authentication failures, empty organization lists, missing data, and ambiguous candidates as different outcomes so the config flow can show the right recovery step.

## Circuit discovery and identity

Current-mode circuit data is queried from InfluxDB using the Savant UUID and channel. The resulting circuit map is persisted in the config entry so runtime polling does not have to rediscover relay identity on every update.

Named type-`007A` CT rows are also accepted when Savant omits `savantUUID`. Stored Savant UUIDs always remain authoritative and are never replaced by a name or measurement id. A genuinely UUID-less CT keeps `savant_uuid` empty and uses a separate `source_uid` built from the stable Influx measurement id plus channel. Unnamed CT inputs are excluded because a channel number alone is not enough to create a safe, useful user-facing identity.

For relay mapping, the integration combines:

- InfluxDB circuit names, UUIDs, channels, classifications, and device types
- SEM companion device labels, load names, and legacy UIDs
- PBC inventory data when the companion response is incomplete

Relay matches are case-insensitive and preserve the legacy UID needed by the command path. A circuit that cannot be matched confidently is kept as a read-only CT sensor and a reconfigure warning is surfaced instead of assigning an unsafe relay target.

## Runtime polling and recovery

The current-mode coordinator polls InfluxDB and returns both circuit data and system channels. It starts with a short lookback and widens the query when Savant has not written a recent sample. The current backfill windows are:

```text
-2m, -15m, -24h, -7d
```

The coordinator records the window that produced the data and exposes snapshot status for cached data, retry timing, organization failures, and circuit-map reconfiguration requirements.

Recovery behavior is layered:

- A 401 triggers an SSH key-based token refresh when a stored key is available.
- A refreshed token is persisted only after organization, bucket, and circuit discovery succeed; failed candidates leave the current token, organization, and bucket untouched.
- An invalid or missing organization triggers organization rediscovery.
- A snapshot with unknown or missing circuits keeps the data visible and requests reconfiguration.
- Temporary failures retain the last usable snapshot and report the next retry interval.

The polling interval backs off after failures and returns to the configured interval after a successful update.

## Energy and CT handling

InfluxDB hardware energy counters are converted to kWh for Home Assistant. Detailed relay rows use the fixed mWh scale and CT circuits resolve their scale from observed power and energy deltas. Some hosts publish stored relay circuits only through `Energy.Circuit.<name>.Power` and `.Energy` type-`0000` hub channels. Those hub counters are Wh, so the integration records their raw value and uses the explicit `hub_wh_to_kwh` divisor of 1,000. Hub-only rows do not supply relay state or control data.

Some hosts also publish permanent zero-filled hub circuit placeholders for stored relays that have no measurement source. A hub circuit is promoted to live telemetry only when either its power or energy value provides nonzero evidence. This keeps an unused-but-real circuit available after its accumulated energy becomes nonzero while preventing placeholder `0 W` / `0 kWh` rows from masquerading as working sensors.

Hub-level totals and groups use the same evidence rule. A system channel is unavailable until it first produces a nonzero value during the coordinator lifetime; after that, a later zero is retained as a legitimate measurement. This distinguishes unsupported zero-filled channels from a supported load that has turned off.

Multi-leg CT circuits are represented in two ways:

- Each live leg remains available for diagnostics.
- An aggregate sensor combines the legs under the shared circuit identity.

Aggregate power and energy are summed. Aggregate current and voltage use the CT combination rules in the Influx client. This prevents duplicate channels from appearing as separate user loads while preserving the raw legs for troubleshooting.

## Relay control

Relay control uses the legacy UID recovered from circuit discovery. The command payload is JSON encoded, base64 encoded, and sent over TCP:

```json
{"states": {"<legacy_uid>": 100}, "requestId": "<uuid>"}
```

The command is sent as:

```text
SET_LOAD_STATE=<base64_payload>\n
```

The integration does not treat a command response timeout as definitive failure. It confirms the final state through the next telemetry poll.

## Migration and cleanup

Existing entries remain in legacy mode after upgrade unless the user reconfigures them. Reconfigure can switch an entry to current mode and persist the host, token, organization, circuit map, and SSH key.

Configuration normalization moves current-mode connection values out of stale options storage and into the config entry data. This prevents old options from overriding freshly entered host, token, URL, or organization values.

On setup, the integration removes obsolete DMX address entities and stale circuit entities left by earlier identity schemes. Stored circuit-map identity shells and historical identity inventory can recreate measurement entities after a partial snapshot, but those entities remain unavailable until a fresh `presentDemands` row returns. Relay control entities are created only from current live relay data.

## Troubleshooting

### Savant host token layouts

The token may be in either of these locations, depending on SavantOS packaging:

```text
/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
/data/home/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
```

Check both layouts and bounded `find` results by path and size only. The adjacent `.influxsetup` and `.influxtoken` files can identify the organization and bucket. Do not print token contents. `influxd` is the server daemon, not the optional `influx` CLI, so an `influxd` invocation or missing CLI does not validate a token. Candidate tokens are validated end-to-end against Savant data before setup or reconfigure persists one.

SSH refresh is staged as password connection, home/path resolution, append-and-reread of the managed `authorized_keys` suffix, public-key authentication, and token validation. On failure, rollback removes only the exact appended byte suffix when it is still at the end of the file. A concurrent change is left untouched and reported as a rollback conflict. A wider historical query supplies identity inventory only; it is never used as a live measurement source. Partial inventory must not replace the stored map or trigger entity/device cleanup.

- A 401 normally means the token expired or rotated. With SSH bootstrap enabled, the stored key should refresh it automatically.
- An organization selection prompt means more than one candidate matched Savant's expected data shape. Choose the candidate with current circuit data.
- A circuit inventory warning means InfluxDB found a circuit absent from the saved relay/CT map. It is reported once for that inventory change, rather than on every poll. Mapped hub-only circuit measurements count as live measurements, but remain unavailable for relay status or control until detailed state telemetry returns.
- Use `tools/live-savant-influx-diagnostic.py` for direct-host discovery/shaping evidence and `tools/live-ha-mcp-diagnostic.ps1` for installed-version, entity timestamp, and Home Assistant log evidence. The full procedure and release acceptance boundary are in `docs/live-diagnostics.md`.
- An empty snapshot can be a timing issue on the Savant host. The integration widens its lookback window before reporting failure.
- Legacy installations should use Reconfigure after upgrading Savant to firmware 11.2 or later.

## Validation coverage

The protocol change includes unit coverage for:

- Influx organization discovery and candidate scoring
- SSH metadata parsing and key handling
- Config storage normalization
- Current and legacy config flow paths
- Influx backfill and error classification
- Energy scaling and CT energy guards
- Relay and CT circuit classification
- Multi-leg CT aggregation
