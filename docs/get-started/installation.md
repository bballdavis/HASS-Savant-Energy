---
title: Install the integration
---

# Install Savant Energy

## Before you start

Read [requirements](requirements.md). Have access to Home Assistant administration and permission to restart it. For Current setup, gather the PBC address, Host address, and RPM password.

## Install with HACS

1. Open [this repository in Home Assistant](https://my.home-assistant.io/redirect/hacs_repository/?owner=bballdavis&repository=HASS-Savant-Energy&category=integration).
2. If it is not already available in your HACS catalog, add `https://github.com/bballdavis/HASS-Savant-Energy` as a custom repository with type **Integration**. See [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/).
3. Open **Savant Energy** in HACS and download the desired stable release. Use prereleases only when you intentionally want to test one.
4. **Restart Home Assistant.** Downloading files does not load the new integration code.
5. Open **Settings → Devices & services → Add integration** and search for **Savant Energy**.

**Expected result:** the **Savant Energy — Choose Mode** form appears. Continue to [connect your system](../connect/current.md), or [Legacy setup](../legacy/README.md).

## Install manually

1. Download the desired release’s source archive from [GitHub releases](https://github.com/bballdavis/HASS-Savant-Energy/releases).
2. Extract the archive and copy its `custom_components/savant_energy` directory into your Home Assistant configuration directory:

   ```text
   <config>/custom_components/savant_energy/manifest.json
   <config>/custom_components/savant_energy/__init__.py
   ```

   Copy the entire directory, including its subdirectories. Do not nest an extra repository directory inside `custom_components`.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and search for **Savant Energy**.

**Expected result:** the same mode-selection form as the HACS installation. Manual installations require manual file updates and a restart when upgrading.

## Add your dashboard

The companion breaker-board card is included with the integration. After setup and restart, [add it to a dashboard](../usage/companion-card.md). Existing standalone HACS card users should follow the migration steps on that page to avoid duplicate resources.

## If it does not appear

Confirm the folder path, restart completion, and Home Assistant logs. A browser refresh may be needed after restart. See [installation troubleshooting](../troubleshooting/overview.md#integration-not-found).

## Updating an existing installation

Back up Home Assistant, download the new release through your chosen method, and restart. Read the release notes before installing. Keep the existing integration entry; use [Reconfigure](../legacy/migration.md) for a firmware/mode change rather than removing and re-adding it.

**Next:** [Auto and Current setup](../connect/current.md).
