---
title: Legacy setup
slug: /legacy/
---

# Set up Legacy mode

Use this path for older Savant firmware that still provides the original activity/snapshot feed. Firmware 11.2 or later generally uses [Current setup](../connect/current.md).

## Before you start

[Install the integration](../get-started/installation.md), restart Home Assistant, and identify the **PBC address**. Home Assistant must reach the PBC’s snapshot feed on TCP 2000 and its DMX/OLA API on port 9090. Legacy setup does not ask for a Host address or SSH password.

## Connect

1. Open **Settings → Devices & services → Add integration → Savant Energy**.
2. Choose **Legacy**.
3. Enter the **PBC IP Address** and submit.
4. Open the created entry’s devices and [verify the first readings](../connect/verify.md).

Auto mode can also select Legacy when it finds a usable snapshot feed. Explicit Legacy setup creates the entry after address validation; reaching the end of the form does not prove the feed is healthy.

**Expected result:** the entry uses the original snapshot data and DMX/OLA control path. Applicable relay devices have breaker switches, relay status, and DMX address entities. Measurements depend on what the Legacy snapshot supplies; do not expect every Current-mode system or CT channel.

## Check a known relay

Confirm the physical load, request one state change, and wait for subsequent snapshot updates. Relay confirmation is inferred through polling. The default cooldown is 15 seconds. **DMX Testing Mode** should be off for normal control; it logs commands without sending them when enabled.

## If readings or control fail

- Check the PBC address and network access separately for the snapshot and OLA endpoints.
- Confirm the firmware still provides the original feed.
- Review the integration’s notifications and [focused logs](../troubleshooting/logs.md).
- If firmware was upgraded, use [Legacy-to-Current migration](migration.md).

## Technical background

Legacy reads TCP snapshots, decodes the base64 `SET_ENERGY` payload, and shapes `presentDemands` into entities. Relay commands use DMX/OLA and preserve managed channel state. Current mode instead separates InfluxDB telemetry from SEM relay control; see [architecture](../current-api-workflow.md).
