---
title: Savant Energy 2.2.0
---

# Savant Energy 2.2.0

I’ve brought the new companion dashboard card into the integration and moved the detailed instructions into a proper documentation site. The README is now a quick overview, with the setup and troubleshooting guides easier to find.

## New features

- **Included dashboard card:** circuit tiles, live power readings, history graphs, compact mobile views, and a scene editor. No separate card installation is needed for new setups.
- **New documentation site:** installation, setup, Legacy migration, and troubleshooting guides with real Home Assistant screenshots.
- **Cleaner settings:** clearer names and options that match your connection mode. Legacy-only and Current-only settings appear where they belong.

## Fixes and cleanup

- Saved settings are preserved when switching modes.
- Avoided duplicate card loading when a separate Savant-Card installation is already present.
- Kept existing scenes-card configurations working with the new card.
- Fixed HACS validation issues and corrected the documentation and support links.

## Updating

Update through HACS, restart Home Assistant, and refresh your browser. Keep your existing integration entry; there’s no need to remove and add it again.

If you already installed Savant-Card separately, follow the [card migration steps](https://bballdavis.github.io/HASS-Savant-Energy/docs/usage/companion-card/#separate-savant-card-hacs-installation) before switching to the included copy.

**Using v2.1.1-beta1 for missing telemetry?** Stay on that beta for now. Its experimental channel-only telemetry fallback is not included in this release.

[Documentation](https://bballdavis.github.io/HASS-Savant-Energy/) · [Full changelog](https://github.com/bballdavis/HASS-Savant-Energy/compare/v2.1.0...v2.2.0)
