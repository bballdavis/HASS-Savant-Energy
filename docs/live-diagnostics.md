# Live Savant and Home Assistant diagnostics

Unit tests are not evidence that an installed Home Assistant entry is healthy. Use both read-only probes below before calling a telemetry change fixed.

## Direct Savant host probe

Create `.savant-local.env` from `.savant-local.env.example` and keep it untracked. Then run:

```powershell
python .\tools\live-savant-influx-diagnostic.py
```

The probe retrieves the current Influx read token over SSH without printing it, queries the configured bucket over several windows, inventories all recent power series, and runs the integration's actual discovery and snapshot shaping code against the response.

Review these report sections:

- `integration_discovery`: named circuits the current query can identify and persist.
- `integration_shaping`: entities and values the coordinator would publish from the same live response.
- `all_recent_power_summary`: source rows that are genuinely nonzero, including rows outside the normal circuit filter.
- `hub_circuit_power_24h_maxima`: whether a type-`0000` circuit channel has ever carried a real value instead of a zero-filled placeholder.

Named type-`007A` CT rows may omit `savantUUID`. Existing Savant UUIDs remain the authoritative identity. Only a genuinely UUID-less CT uses the stable Influx measurement id plus channel in a separate `source_uid`; `savant_uuid` remains empty rather than being synthesized. Unnamed type-`007A` inputs are not published because their identity is not safe or useful. Type-`0000` `Energy.Circuit.*` rows are considered measurement-capable only after power or energy is nonzero; Savant hosts can publish permanent zero-filled placeholders for relay loads with no telemetry source. Hub totals and groups likewise remain unavailable until a nonzero sample proves the channel is active, after which later zero values remain valid.

## Installed Home Assistant probe

The configured HA MCP URL remains owned by the sibling `hass-mcp` workspace. To inspect installed state without exposing that URL, run:

```powershell
.\tools\live-ha-mcp-diagnostic.ps1 `
  -EntityId @('update.savant_energy_update', 'sensor.tesla_power') `
  -IncludeAttributes

.\tools\live-ha-mcp-diagnostic.ps1 -Logs
```

The update entity confirms the version Home Assistant actually loaded. Entity `last_reported` timestamps must continue advancing across more than one configured scan interval. The log probe searches the current Home Assistant error log for Savant-related issues.

## Acceptance boundary

A release is live-verified only when all of the following are true:

1. The installed version is the intended prerelease.
2. Home Assistant reload/restart completed without a Savant setup exception.
3. Direct-host discovery and shaping succeed against the current token and bucket.
4. Supported Home Assistant sensors match the direct-host values within rounding tolerance across at least two polls.
5. Zero-filled placeholders remain unavailable rather than appearing as valid 0 W / 0 kWh measurements.
6. Missing source fields such as current or voltage remain unavailable; they are not synthesized as zero.

Relay identity and relay telemetry are separate capabilities. Preserving a stored relay map keeps controls and entity identity safe, but it cannot create measurement data that the current Savant firmware no longer publishes.
