![Savant Energy for Home Assistant — independent community integration](docs/assets/wordmark.svg)

[![Latest release](https://img.shields.io/github/v/release/bballdavis/HASS-Savant-Energy)](https://github.com/bballdavis/HASS-Savant-Energy/releases/latest)
[![HACS validation](https://github.com/bballdavis/HASS-Savant-Energy/actions/workflows/hacs.yml/badge.svg)](https://github.com/bballdavis/HASS-Savant-Energy/actions/workflows/hacs.yml)
[![Hassfest](https://github.com/bballdavis/HASS-Savant-Energy/actions/workflows/hassfest.yml/badge.svg)](https://github.com/bballdavis/HASS-Savant-Energy/actions/workflows/hassfest.yml)

Bring your Savant energy system into Home Assistant: monitor supported circuits,
track energy, control relays, and organize energy scenes from your own dashboard.

**[Install the integration](docs/get-started/installation.md)** ·
**[Read the guides](https://bballdavis.github.io/HASS-Savant-Energy/)** ·
**[Get help](docs/troubleshooting/overview.md)**

![Illustrative Home Assistant dashboard showing circuit power, grid and solar readings, and saved energy scenes.](docs/assets/overview.png)

*Demo dashboard with synthetic devices and readings. Available measurements depend on your hardware and firmware.*

## What you can do

- **Monitor circuits:** power, current, voltage, and cumulative energy where supplied by your system.
- **Track energy:** use supported hardware kWh counters in Home Assistant’s Energy dashboard.
- **See the wider picture:** CT-monitored loads and available grid, solar, battery, and load-group readings in Current mode.
- **Control supported relays:** breaker switches, relay status, cooldown settings, and All Loads On.
- **Build energy scenes:** create and run saved relay states with the included dashboard card.
- **Automate:** use Home Assistant entities and scene-management services.

## Choose your setup

| Your system | Start here | Have ready |
|---|---|---|
| New installation / unsure of firmware | [Auto or Current setup](docs/connect/current.md) | PBC address; Host address and RPM password if Current mode is needed |
| Firmware 11.2 or later | [Current setup](docs/connect/current.md) | PBC address, Savant Host address, RPM password for SSH bootstrap |
| Older firmware with the original snapshot feed | [Legacy setup](docs/legacy/README.md) | PBC address |
| Existing Legacy entry after a firmware upgrade | [Migration guide](docs/legacy/migration.md) | Existing entry, Host address, RPM password |

## Install

[![Open in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bballdavis&repository=HASS-Savant-Energy&category=integration)

1. Open this repository in HACS using the badge, or add it as a custom **Integration** repository.
2. Download **Savant Energy** and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration**, then search for **Savant Energy**.
4. Follow [setup](docs/connect/current.md), then [verify your first readings](docs/connect/verify.md).

See the [full installation guide](docs/get-started/installation.md) for prerequisites and manual installation.

## Explore the documentation

- [Requirements and hardware terminology](docs/get-started/requirements.md)
- [Devices and entities](docs/usage/entities.md) · [Energy dashboard](docs/usage/energy-dashboard.md)
- [Relay controls](docs/usage/controls.md) · [Scenes card](docs/usage/scenes.md) · [Options](docs/usage/options.md)
- [Troubleshooting](docs/troubleshooting/overview.md) · [SSH setup](docs/troubleshooting-ssh.md)
- [Service reference](docs/reference/generated/services.md) · [REST API](docs/reference/rest-api.md)
- [Contributing](docs/development/contributing.md) · [Release history](docs/development/releases.md)

## Support and independence

This is an independent community project and is not affiliated with, endorsed by, or supported by Savant.
The descriptive product names identify compatibility; the documentation uses its own typography and artwork.

For bugs and feature requests, [open a GitHub issue](https://github.com/bballdavis/HASS-Savant-Energy/issues).
Include versions, the exact error, and a [focused, sanitized log](docs/troubleshooting/logs.md).

Licensed under [GNU GPL v3](LICENSE).
