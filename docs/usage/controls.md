---
title: Relay controls
---

# Use relay controls

The **Breaker** switch controls the relay associated with a supported load. The label does not mean the integration replaces electrical protective hardware. Only operate loads you intend to switch.

## Test one known load

1. Identify a relay-capable device and confirm its name and physical load.
2. Use the device’s **Breaker** switch to request its intended state.
3. Allow the next telemetry poll to confirm the reported state. Avoid rapidly repeating commands.

**Expected result:** supported relay status reflects the requested state after confirmation. A socket timeout alone is not a definitive indication of the final hardware state; check the next live status and logs.

## Cooldown and confirmation

The default breaker cooldown is **15 seconds**. The debounce setting is expressed in scan intervals, with a default multiplier of **2**. See [options](options.md) before changing these values. CT-only loads and uncertain relay mappings are read-only.

## All Loads On

The **All Loads On** button requests the on state for the available relays. Review the affected equipment before using this broad action. Saved scenes provide a more specific set of relay states.

## Automation

Use the Home Assistant entity picker to select a real switch from your installation:

```yaml
action: switch.turn_on
target:
  entity_id: switch.example_load_breaker
```

This is an illustrative entity ID. See [scenes](scenes.md) for saved groups of states, or [troubleshooting](../troubleshooting/overview.md) if control and status disagree.
