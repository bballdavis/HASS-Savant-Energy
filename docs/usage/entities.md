---
title: Devices and entities
---

# What the integration creates

Entities depend on discovered equipment, connection mode, and the fields Savant actually supplies. Display names may differ from the examples; use the entity picker rather than assuming a particular entity ID.

## Circuit measurements

| Entity | Unit | Meaning |
|---|---|---|
| Power | W | Latest supported power measurement |
| Current | A | Current supplied by the source |
| Voltage | V | Voltage supplied by the source |
| Energy | kWh | Cumulative energy where a supported hardware counter is available |

Current mode includes CT-monitored loads as well as relay circuits. Multi-leg CTs can expose diagnostic leg readings and an aggregate; avoid adding both the aggregate and its legs to totals. Energy availability differs between modes and firmware. Missing source fields remain unavailable rather than being synthesized as zero.

See [the companion breaker board](companion-card.md) for real Home Assistant captures of circuit tiles and responsive layouts.

## Controls and status

Relay-capable loads may have a **Breaker** switch and **Relay Status** binary sensor. Legacy mode also provides a **DMX Address** sensor. CT monitoring alone does not imply a relay exists.

Control identity and measurement availability are separate. A saved identity shell or a historical inventory is not a guarantee that a live relay or reading is currently available.

## System channels

Current mode can expose consumption, grid feed, net power, solar production, battery power/state of charge/time remaining/mode, grid availability, and load-group totals. Availability depends on the installed equipment and firmware. Hub channels with only permanent zero-filled source values remain unavailable until activity is established.

## Buttons

Applicable installations can expose **All Loads On**, saved-scene buttons, and Legacy DMX diagnostic buttons. See [controls](controls.md) and [scenes](scenes.md) before use.

**Next:** [Energy dashboard](energy-dashboard.md) or [troubleshooting unavailable telemetry](../troubleshooting/telemetry.md).
