# Savant Energy Legacy Mode (<11.2)

This document describes legacy mode behavior and setup details that are specific to older Savant systems.

## When To Use Legacy Mode

Use legacy mode when your system still provides the legacy activity/snapshot feed over the PBC endpoint.

## Setup Inputs

Legacy mode setup asks for:

- PBC IP address

Ports are fixed in code by default:

- Legacy snapshot feed: TCP 2000
- OLA/DMX API: 9090

## Legacy Runtime Path

Legacy mode keeps the historical integration path:

1. Read snapshot payload from TCP port 2000.
2. Decode base64 `SET_ENERGY` payload.
3. Build `presentDemands` entities from snapshot data.
4. Use DMX/OLA command path for breaker control.

## Legacy-Specific Notes

- Relay command confirmation is inferred via subsequent snapshot updates.
- DMX writes should preserve managed channel state to avoid clobbering unrelated channels.
- Existing upgraded users default to legacy mode unless they explicitly reconfigure to current mode.

## Upgrading To Current Mode

From integration reconfigure:

1. Change mode to Current (>=11.2).
2. Provide host IP.
3. Provide Influx token directly, or provide SSH password so token can be fetched.

See [docs/current-api-workflow.md](../current-api-workflow.md) for the current-mode architecture and data/control paths.
