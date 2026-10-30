---
title: Find and fix a problem
---

# Troubleshooting

Start with the symptom and collect one focused reproduction. Keep the existing entry while investigating.

| Symptom | First check | Guide |
|---|---|---|
| Integration not found | Folder layout and completed restart | [Installation](../get-started/installation.md) |
| SSH setup fails | Host address and RPM credentials | [SSH setup](../troubleshooting-ssh.md) |
| Influx query or token fails | Host port 8086; exact status/error | [SSH and token recovery](../troubleshooting-ssh.md) |
| No circuits or unavailable sensors | Source data, live versus historical inventory | [Telemetry](telemetry.md) |
| Card does not load | Frontend resource and browser cache | [Scenes card](scenes-card.md) |
| Relay does not confirm | Correct load, cooldown, fresh status | [Relay controls](../usage/controls.md) |
| Legacy stopped after firmware upgrade | Firmware/feed change | [Migration](../legacy/migration.md) |

## Integration not found

Confirm `<config>/custom_components/savant_energy/manifest.json` exists and the entire integration directory was copied. Restart Home Assistant, refresh the browser, and inspect **Settings → System → Logs** for import or setup errors. HACS downloading a release is not the same as loading it.

## Check addresses separately

PBC and Host are often different machines. Current-mode SSH and InfluxDB go to the Host. Legacy feed and SEM commands use the PBC. Check the [requirements table](../get-started/requirements.md) before changing credentials.

## Before opening an issue

Include Home Assistant and integration versions, firmware/mode, the exact error, reproduction time/timezone, and a [sanitized focused log](logs.md). The [generated error reference](../reference/generated/errors.md) lists source messages. Do not attach tokens, private keys, or RPM passwords.
