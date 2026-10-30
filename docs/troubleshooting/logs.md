---
title: Collect useful logs
---

# Capture one focused reproduction

1. Open **Settings → Devices & services → Savant Energy**.
2. In the integration menu, choose **Enable debug logging**, if available.
3. Reproduce the problem once and note the time and timezone.
4. Choose **Disable debug logging** and save the offered log.
5. Extract the relevant `savant_energy` lines and remove secrets and private identifiers before sharing.

If the integration has not been created or the menu is unavailable, use **Settings → System → Logs**. The [SSH troubleshooting guide](../troubleshooting-ssh.md) includes an optional temporary YAML logger configuration.

This integration does not provide a separate integration-diagnostics download. For source and installed-state probes used by maintainers, see [live diagnostics](../live-diagnostics.md).

## Include in an issue

- Home Assistant Core version, integration version, and Savant firmware/mode.
- Whether the failure was installation, initial setup, Reconfigure, options, or runtime.
- Exact on-screen error and a minimal sequence to reproduce it.
- Confirmation that PBC and Host addresses were checked separately.
- Timestamp/timezone and the smallest useful sanitized log excerpt.

Never share the RPM password, Influx token, Home Assistant access token, SSH private key, or complete contents of credential files. Disable debug logging after collecting evidence.
