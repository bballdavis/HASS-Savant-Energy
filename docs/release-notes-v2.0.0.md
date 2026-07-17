# Savant Energy 2.0.0

Savant threw us for a loop with firmware 11.2. The old PBC snapshot path was no longer enough, so this release moves current-mode telemetry to InfluxDB and keeps relay control on the SEM interfaces. In the end, I think it is better. The protocol change took work, but it also gave us more data and some useful recovery features.

## What changed

- Added a real current-mode data path for Savant firmware 11.2 and later.
- Added InfluxDB 2 polling for circuit readings, hardware energy counters, solar, battery, grid, and load-group channels.
- Added automatic backfill from `-2m` through `-7d` when the Savant host has not written a recent sample.
- Added SSH token bootstrap using the `RPM` account and an Ed25519 key pair.
- Stored the generated SSH private key with the Home Assistant config entry so expired Influx tokens can be refreshed automatically.
- Added host metadata parsing for organization, bucket, and auth information.
- Added organization discovery from host metadata, bucket listings, and the InfluxDB organization API.
- Added candidate scoring and a user selection step when multiple organizations look valid.
- Added persisted circuit metadata keyed by Savant UUID and channel.
- Added relay matching from SEM companion data, with PBC inventory fallback when the companion response is incomplete.
- Added safer circuit classification. Unmatched circuits stay available as read-only sensors instead of receiving an unsafe relay mapping.
- Added multi-leg CT aggregation while keeping each live leg available for diagnostics.
- Added per-circuit energy scale detection, confidence reporting, and guards against implausible CT energy jumps.
- Added clearer setup and runtime errors for SSH, Influx authentication, organization discovery, circuit discovery, and relay mapping.
- Added persistent notifications for recovery and reconfigure actions.
- Circuit inventory mismatches now produce one aggregated reconfigure warning instead of repeating one warning per circuit on every polling cycle.
- Added config storage normalization so stale options do not override fresh connection data.
- Added cleanup for old DMX entities and orphaned circuit devices left by earlier identity schemes.
- Kept legacy mode available and added Auto mode behavior that chooses legacy or current setup based on the available Savant feed.
- Updated the README, current API workflow, translations, and developer tools for the new protocol.

## What this means for users

Legacy installations stay in legacy mode after the update. If the Savant system is on firmware 11.2 or later, use Reconfigure and choose Current or Auto. Current setup needs the PBC IP, the Savant host IP, and an InfluxDB read token. SSH retrieval is optional, but using it lets the integration recover from normal token rotation later.

The first current-mode setup may ask you to choose an Influx organization if the token can see more than one plausible data set. It may also show a reconfigure notification if a circuit cannot be matched safely to a relay. That circuit will still be available as a read-only sensor.

## Upgrade notes

- The integration version is now `2.0.0`.
- The current-mode Influx organization is no longer hard-coded. It is discovered and stored per config entry.
- The current-mode token path is `/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken` on the supported Savant host layout.
- Existing entity history is preserved where the stable relay identity can be matched. CT-only loads may appear as new entities.
- Old orphaned circuit entities and DMX address entities are cleaned up during setup.

## Validation

The release includes unit tests for organization discovery, SSH helpers, config flow behavior, config storage normalization, Influx backfill, energy scaling, circuit classification, relay mapping, and multi-leg CT aggregation.

For a local test run:

```text
python -m unittest discover -s tests -p "test_*.py"
```
