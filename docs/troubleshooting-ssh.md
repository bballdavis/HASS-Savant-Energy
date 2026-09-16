# Troubleshooting Current-mode SSH setup

This guide is for Savant Energy Current mode (Savant firmware 11.2 or later),
when setup cannot authenticate to the Savant host or circuit discovery does not
complete. It is written so the useful evidence can be collected from the Home
Assistant UI without entering a development container.

## Capture a focused Home Assistant log from the UI

Home Assistant's supported integration-debug workflow is documented in the
[Home Assistant troubleshooting guide](https://www.home-assistant.io/docs/configuration/troubleshooting/).

1. Open **Settings > Devices & services**.
2. Find **Savant Energy** and open the integration.
3. Open the **three-dot menu** and choose **Enable debug logging**.
4. Reproduce the problem once: start the setup, reconfigure flow, or reload
   that is failing. Note the time, including your timezone.
5. Return to the same integration, open the **three-dot menu**, and choose
   **Disable debug logging**. Home Assistant will offer the resulting log for
   download.
6. In the downloaded log, search for `savant_energy`, `ssh`, `Authentication`,
   `setup`, and `circuit`. Share only the relevant, sanitized section.

The general log viewer is also available at **Settings > System > Logs**. The
integration-specific enable/disable workflow above is preferred because it
keeps the capture focused and gives the downloaded log to attach to an issue.
This integration does not currently provide an integration diagnostics
download, so do not expect a separate diagnostics file in the integration menu.

If the integration menu does not expose the debug toggle, add this temporary
entry to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.savant_energy: debug
```

Restart Home Assistant, reproduce the problem once, then remove the temporary
entry and restart again. Use **Settings > System > Logs** to view the result.
Do not leave debug logging enabled after collecting the evidence; it can be
verbose. Do not paste passwords, InfluxDB tokens, private keys, or complete
secret-bearing command output.

## What to include in a report

Please include:

- Home Assistant Core version and Savant Energy integration version.
- The timestamp and timezone of the single reproduction.
- Setup mode (**Auto**, **Legacy**, or **Current**) and whether this was first
  setup, reconfigure, or a reload.
- Confirmation that the PBC IP and Savant Host IP were checked separately.
  They are often different devices; Current mode SSH goes to the Savant Host.
- The exact user-facing error shown by Home Assistant.
- The smallest relevant log section, with IP addresses anonymized if desired
  and all credentials, tokens, and key material removed.

## Optional direct SSH diagnosis

If you can use a terminal on the same network, test the same host and user
directly:

```text
ssh RPM@<host-ip>
```

Enter the RPM password when prompted. Replace `<host-ip>` with the Savant Host
IP, not automatically the PBC IP. This test is optional; the Home Assistant
log capture above is sufficient for a UI-only report.

For more detailed negotiation output, use this optional parity check:

```text
ssh -vvv -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive RPM@<host-ip>
```

This mirrors the integration's password-first behavior by avoiding SSH-agent
and local-key authentication. The `-vvv` output shows the server-advertised
authentication methods and where negotiation stops. Never put the password in
the command; wait for SSH's password prompt. Before sharing the output, redact
the host IP, local usernames and paths, and any identifiers or fingerprints
that you do not want to disclose.

Interpret the result without sharing secrets:

- **Permission denied / authentication failed**: the host reached SSH but
  rejected the RPM credentials or its configured authentication policy. Verify
  the host IP and reset the RPM password through Savant System Monitor if
  needed.
- **Connection refused, timeout, or no route**: investigate the host IP,
  network reachability, firewall, or whether SSH is enabled on the Savant host.
- **Login succeeds but the integration still fails**: the later failure may
  be reading the remote token file, validating the InfluxDB token, or
  discovering circuits. Capture the focused Home Assistant log so the exact
  stage is visible.

Paramiko already attempts password authentication and the host's
keyboard-interactive fallback. Beta9 improves the error classification and
preserves the password exactly as entered; it does not add a new SSH
authentication method.

Never send the RPM password, an InfluxDB token, a private key, or the contents
of secret files. Do not run commands that print token files. Stop the test if
the host or account is not yours, or if Savant support asks you to use a
different recovery procedure.

After collecting the evidence, disable debug logging (or remove the temporary
YAML logger entry and restart) and redact the downloaded log before attaching
it to an issue.
