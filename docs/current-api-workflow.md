# Savant Energy Current API Workflow (>=11.2)

This document captures the validated workflow for Savant firmware >=11.2, including relay control and initial setup behavior.

## Overview

The current integration path uses two local interfaces:

1. InfluxDB 2 API for telemetry and circuit state snapshots.
2. SEM direct TCP command channel for relay control.

A companion HTTP endpoint is used to bridge identifier formats between telemetry and relay control.

## Network Endpoints

Use fixed default ports.

- PBC/Host InfluxDB API: http://<host_ip>:8086
- SEM companion status API: http://<pbc_ip>:8644/companion/status
- SEM relay command socket: <pbc_ip>:2000 (TCP)

## Data and Control Split

### Telemetry path

1. Query InfluxDB with Flux for current circuit/system data.
2. Parse rows into presentDemands style structures.
3. Preserve circuit UUID from InfluxDB as the circuit identity in HA entities.

### Identifier bridge path

1. Query companion status from SEM.
2. Read Devices array (capitalized key: Devices).
3. Build name->legacy UID map from LoadName/UID.
4. Match circuit name to relay device name (case-insensitive) and inject relay_uid per circuit.

### Relay control path

1. Resolve target relay_uid.
2. Build payload:

```json
{"states": {"<legacy_uid>": <0_or_100>}, "requestId": "<uuid>"}
```

3. Base64 encode the JSON payload.
4. Send plain-text command over TCP:

```text
SET_LOAD_STATE=<base64_payload>\n
```

5. Optionally parse response:

```text
SET_LOAD_STATE_RESPONSE=<base64_response>\n
```

A timeout waiting for response does not always indicate failure; state confirmation should come from subsequent telemetry poll.

## State Semantics

- 0 = OFF
- 100 = ON

## Required Credentials

For current (>=11.2) operation:

- Required: InfluxDB read token
- Not required for SEM control: JWT token

The relay command path and companion status path do not require JWT authentication in the validated workflow.

## Auto Setup Intent (Target Behavior)

Auto mode should ask for PBC IP first, then:

1. Test legacy activity feed availability.
2. If legacy feed is available, configure as legacy and finish.
3. If legacy feed is not available:
   - Show a second step requesting host IP and SSH password.
   - Use SSH workflow to retrieve InfluxDB token.
   - Store current mode config and finish.

## Upgrade Behavior Intent

Existing installs should remain in legacy mode by default after upgrade.
Users can run a reconfigure/upgrade flow to switch to current mode by adding host IP and obtaining Influx token.

## Notes for Implementation

- Keep port fields out of user flow unless needed for diagnostics.
- Ask only for:
  - PBC IP (legacy and current)
  - Host IP (current only)
  - SSH password (auto/current onboarding only when token retrieval is needed)
- Keep localization-first labels and descriptions for all new flow steps.
