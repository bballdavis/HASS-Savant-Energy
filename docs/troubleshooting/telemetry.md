---
title: Missing or unavailable telemetry
---

# Understand missing readings

A discovered circuit, a live measurement, and a controllable relay are different capabilities. Historical identity inventory can preserve entities while their current readings remain unavailable.

## Check in this order

1. Confirm the intended integration release actually loaded after restart.
2. Check the selected mode and both device addresses.
3. Open a supported sensor and inspect updates over at least two polling intervals.
4. Read notifications and logs for token, organization, bucket, or circuit-map errors.
5. Compare the same time window with the source system. Maintainers can use [live diagnostics](../live-diagnostics.md) to inspect direct-host data.

**Expected result:** supported entities follow fresh source data. Synthetic documentation images are not evidence of what your firmware publishes.

## Unavailable is not zero

Missing current/voltage fields are not filled with zero. Some Savant firmware emits permanent zero-filled type-`0000` circuit or hub channels; these remain unavailable until a nonzero reading establishes that the source is active. A later zero can then be valid. A circuit whose telemetry stopped cannot be repaired just by renaming an entity.

Named CT type-`007A` inputs can be accepted without a Savant UUID using a separate stable source identity. Unnamed CT inputs are excluded. Unsupported or ambiguous identity should not be turned into a guessed relay mapping.

## Circuit-map warnings

Run **Reconfigure** when a notification identifies a changed circuit inventory. Review the result: a circuit that cannot be mapped confidently may be saved read-only. Partial snapshots must not replace the stored identity map; wider historical queries are identity evidence, not current power readings.

## Token recovery

A 401 can trigger token refresh through the saved SSH key. If the key or host access no longer works, use **Refresh SSH Key And Token** in [options](../usage/options.md) or Reconfigure. A 403 is a permission issue, not proof that the password was rejected. Capture the exact error and follow [SSH troubleshooting](../troubleshooting-ssh.md).

## Energy statistics

A power entity in W is not a cumulative kWh entity. Check source availability, sensor metadata, and Home Assistant statistics before changing dashboard configuration. See [Energy dashboard](../usage/energy-dashboard.md).
