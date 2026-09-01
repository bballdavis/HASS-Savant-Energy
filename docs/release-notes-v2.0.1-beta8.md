# Savant Energy v2.0.1-beta8

## Status

These are prerelease notes. Beta8 has direct-host and automated-test evidence, but it is not considered live-verified until the tagged build is installed in Home Assistant and its entity values are compared with the host across multiple polls.

## What beta7 got wrong

Beta7 treated every type-`0000` `Energy.Circuit.<name>.Power` / `.Energy` pair as a live measurement source. On the affected host, Savant publishes zero-filled placeholders for stored relay loads even though those channels have never carried real power or energy. That produced convincing `0 W` / `0 kWh` entities while current and voltage remained unavailable.

The same host also publishes named type-`007A` CT rows without `savantUUID`. The earlier query discarded those rows even though the Influx measurement id plus channel provides stable read-only identity. This hid the Main Feed CT while preserving only CT rows that happened to include a UUID.

## Changes

- Preserve every stored/source Savant UUID as authoritative; names are matching aliases only and never entity identity.
- Detect a successful but stalled relay feed when every authoritative live relay power reading remains at zero for 60 seconds; create one persistent Home Assistant notification recommending a Savant host restart and dismiss it after measured recovery.
- Read Savant's `loadIdentifiers.json` during SSH discovery to recover the direct UUID-to-SEM/BLE UID mapping even when detailed Influx relay rows are absent.
- Merge reconfigure results by stable Savant UUID, preserving established entity/channel identity while accepting refreshed metadata and newly discovered CTs.
- Include named type-`007A` CT rows that genuinely omit `savantUUID`, keeping `savant_uuid` empty and using a separate stable measurement-derived `source_uid` plus channel.
- Ignore unnamed CT inputs instead of inventing user-facing identities for spare/noisy channels.
- Publish newly discovered known CT rows as read-only measurements immediately while still requesting reconfigure so the identity can be persisted.
- Require nonzero power or energy evidence before promoting a type-`0000` circuit channel to live telemetry.
- Require nonzero evidence before exposing hub totals and groups; once a channel proves active, later zero samples remain legitimate for that coordinator lifetime.
- Preserve detailed UUID rows as authoritative and keep all synthesized/current-only rows non-controllable.
- Add reusable direct-host and Home Assistant MCP diagnostic tools plus a documented installed-release acceptance boundary.

## Verification completed before tagging

- Direct SSH token retrieval and Influx queries succeeded without printing credentials.
- Direct discovery found both legs of each named CT load, including the UUID-less Main Feed rows.
- The production shaping function returned the expected aggregate and leg entities and excluded the zero-filled relay placeholders.
- Live read-only discovery reconstructed all 28 relays with both their original Savant UUID and SEM UID, with no duplicate identities or warnings.
- Historical downsample data showed 28 relay/load series stopped producing nonzero values simultaneously at 2026-08-23 05:30 UTC; current raw Influx data already contains the zero placeholders before Home Assistant reads it.
- Restarting the Savant host restored 29 current circuit readings; all 29 were nonzero and changed across two direct samples, confirming the stalled acquisition pattern was host-side.
- The complete automated suite passed: 86 tests.
- Python compilation and `git diff --check` passed.

## Installed verification required

After installing beta8 and restarting Home Assistant:

1. Confirm `update.savant_energy_update` reports `v2.0.1-beta8` as installed.
2. Confirm the named CT aggregate and leg sensors advance across at least two 15-second polls and match direct-host values within rounding tolerance.
3. Confirm unsupported relay and hub placeholder channels are unavailable rather than reported as valid zero measurements.
4. Review Savant-related Home Assistant logs. The beta7 baseline contained no setup/fetch exception; it did contain small `total_increasing` energy-decrease recorder warnings, which are separate from the missing-telemetry root cause and should remain visible during verification.
