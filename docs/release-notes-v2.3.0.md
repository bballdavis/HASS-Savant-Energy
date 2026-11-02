---
title: Savant Energy 2.3.0
---

# Savant Energy 2.3.0

This release adds channel-only telemetry support for hosts affected by issue #17 and addresses all four requests from the HACS default-store review.

## Channel-only telemetry support

- Accept recent, recognized system channels when a Savant host has no usable UUID-backed circuit inventory, allowing setup and available system readings on these hosts.
- Keep this fallback read-only: preserve existing circuit mappings, avoid creating circuit identities from arbitrary channel names, and block relay, scene, and All Loads commands without current UUID-backed relay evidence.
- Require the recent UUID telemetry window for relay commands; older backfill readings cannot authorize control.
- Keep UUID-backed discovery as the preferred path and avoid circuit-map cleanup based on incomplete channel-only data.

## Fixes and cleanup

- Serve the included dashboard card under `/savant_energy/` so it no longer shadows files in Home Assistant's `/config/www/savant_energy` directory.
- Generate SSH keys in an executor, including the initial cryptography imports, to keep Home Assistant's event loop responsive during setup.
- Stop scene-button refresh timers when an integration entry unloads or reloads. Ignore storage reads that finish after unload so they cannot add buttons to an unloaded platform.
- Remove the unused shell-based curl helper and its subprocess import.

## Updating

Update through HACS, restart Home Assistant, and refresh your browser. Keep your existing integration entry. Existing dashboard card types and YAML remain compatible, including the legacy scenes-card alias.

The integration automatically loads the included card from `/savant_energy/Savant-Card.js`. If you manually added a Dashboard resource pointing to `/local/savant_energy/Savant-Card.js` or `/local/savant_energy/savant-energy-scenes-card.js`, remove that resource and refresh the browser. Files in `/config/www` are left untouched.

Separate Savant-Card installations continue to take precedence to avoid duplicate card registration. Follow the [card migration steps](https://bballdavis.github.io/HASS-Savant-Energy/docs/usage/companion-card/#separate-savant-card-hacs-installation) if you want to switch to the included copy.

**Using v2.1.1-beta1 for channel-only telemetry?** Its fallback is now included. You can update to this release while retaining your integration entry and existing circuit mappings. Channel-only telemetry remains read-only.

If you already installed the initial v2.3.0 publication, use HACS to redownload v2.3.0 after it is replaced, then restart Home Assistant. The replacement keeps the same version number.

[Documentation](https://bballdavis.github.io/HASS-Savant-Energy/) · [Full changelog](https://github.com/bballdavis/HASS-Savant-Energy/compare/v2.2.0...v2.3.0)
