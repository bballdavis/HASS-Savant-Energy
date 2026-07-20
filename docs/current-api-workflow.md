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
3. The flow retrieves or accepts an InfluxDB read token.
4. The flow discovers the correct Influx organization by checking host metadata, buckets, and the organization list.
5. The flow discovers the circuit map, including relay matches and CT classifications.
6. The current-mode entry is created with the token, organization, circuit map, and any generated SSH key.

If multiple organizations contain plausible Savant data, the flow shows a selection form instead of guessing.

For a manually pasted token, the integration does not use SSH or retain an SSH key. If InfluxDB rejects organization enumeration, setup asks for an explicit organization ID and validates it with a direct Flux query. A later 401 from a saved pasted token is treated as a possible rotation, revocation, or host/access mismatch and prompts the user to Reconfigure with a fresh token.

### SSH token bootstrap

When the user chooses SSH token retrieval, the integration:

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

The integration also checks the host metadata files used by the Savant InfluxDB package. If the token path is empty or unavailable, users can paste a token manually or use the CLI fallback documented in the README.

### Organization discovery

The organization resolver uses the following order:

1. Organization and bucket metadata read over SSH.
2. InfluxDB bucket listing.
3. InfluxDB organization listing.

Each candidate is probed for Savant rows over short and wider windows. Candidates are scored using circuit count, expected fields, recent data, power, and the source of the candidate. A clear winner is stored automatically. Ambiguous candidates are shown to the user with a readable summary.

The resolver treats authentication failures, empty organization lists, missing data, and ambiguous candidates as different outcomes so the config flow can show the right recovery step.

## Circuit discovery and identity

Current-mode circuit data is queried from InfluxDB using the Savant UUID and channel. The resulting circuit map is persisted in the config entry so runtime polling does not have to rediscover relay identity on every update.

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
- A refreshed token causes organization discovery and snapshot retrieval to run again.
- An invalid or missing organization triggers organization rediscovery.
- A snapshot with unknown or missing circuits keeps the data visible and requests reconfiguration.
- Temporary failures retain the last usable snapshot and report the next retry interval.

The polling interval backs off after failures and returns to the configured interval after a successful update.

## Energy and CT handling

InfluxDB hardware energy counters are converted to kWh for Home Assistant. Relay circuits use the fixed relay scale. CT circuits resolve their scale from observed power and energy deltas, record confidence and the selected divisor, and guard against implausible jumps.

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

On setup, the integration removes obsolete DMX address entities and stale circuit entities left by earlier identity schemes. Active relay devices retain their stable legacy identity where possible, while CT-only devices use their Influx identity.

## Troubleshooting

- A 401 normally means the token expired or rotated. With SSH bootstrap enabled, the stored key should refresh it automatically.
- An organization selection prompt means more than one candidate matched Savant's expected data shape. Choose the candidate with current circuit data.
- A circuit inventory warning means InfluxDB found a circuit absent from the saved relay/CT map. It is reported once for that inventory change, rather than on every poll. Mapped circuits continue operating; unmatched circuits remain unavailable for control until Reconfigure rebuilds the map.
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
