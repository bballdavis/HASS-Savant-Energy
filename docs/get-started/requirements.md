---
title: Requirements and terminology
---

# Before you install

Have a working Home Assistant installation, supported Savant energy equipment, and network access between them. This repository is a custom integration; it is not part of Home Assistant Core.

## Know which address goes where

| Term | What it means | Used for |
|---|---|---|
| **PBC** | Savant Power Control Bridge / Panel Bridge Controller connected to the energy equipment | Legacy feed; Current SEM companion and relay interfaces |
| **Host** | Savant RPM Host running the energy software and InfluxDB | Current telemetry, SSH bootstrap, and identity metadata |
| **SEM** | Smart Energy Monitor | Hardware measurements and relay control |
| **CT** | Current transformer measuring a circuit or load | Monitoring; does not by itself provide switching |
| **RPM password** | Password for the `RPM` account on the Savant Host | One-time Current-mode SSH bootstrap and later manual refresh |

**The PBC and Host are often different devices.** Confirm their addresses in your network or with the person who maintains your Savant installation. The sample addresses in screenshots are documentation examples, not values to copy.

## Current mode: firmware 11.2 or later

Have the PBC address, Host address, and RPM account password ready. Normal setup obtains and validates the InfluxDB token automatically; you do not paste a token.

Home Assistant needs access to the applicable local endpoints:

| Destination | Default port | Purpose |
|---|---|---|
| Savant Host | TCP 22 | SSH bootstrap and token recovery |
| Savant Host | TCP 8086 | InfluxDB measurements |
| PBC | TCP 8644 | SEM companion status |
| PBC | TCP 2000 | SEM relay commands |
| Savant Host | TCP 8480 | PBC inventory websocket fallback |

These are internal defaults, not setup form fields. Network paths vary with the hardware inventory. See [architecture](../current-api-workflow.md) for details.

SSH bootstrap installs a dedicated public key on the Host after data validation. The private key and validated read token are saved in Home Assistant’s config entry; the RPM password is not persisted. Protect Home Assistant storage and backups accordingly. Do not assume config-entry storage is encrypted.

## Legacy mode

Have the PBC address ready. The original snapshot feed uses TCP 2000; DMX/OLA control uses port 9090. See [Legacy setup](../legacy/README.md).

## Installation method

[HACS](https://www.hacs.xyz/) is the recommended download/update method. Manual installation is available if you do not use HACS. This project does not declare a minimum Home Assistant version in its manifest; use a maintained Home Assistant release and report the exact version if setup fails.

**Next:** [Install the integration](installation.md).
