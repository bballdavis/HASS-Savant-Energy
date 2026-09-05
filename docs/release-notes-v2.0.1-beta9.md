# Savant Energy v2.0.1-beta9

Beta9 contains the setup and diagnostics fixes for issue #14. It is a
prerelease: install it, reproduce the affected setup path, and confirm the
result on the target Savant host before treating it as resolved.

## Changes

- Fixed the websocket circuit-discovery fallback to pass the Savant host as
  `pbc_host`, matching `fetch_pbc_websocket_devices()` and allowing valid
  Current-mode setup to continue to circuit discovery.
- SSH authentication failures are now classified separately from connection,
  remote-file, token-validation, and circuit-discovery failures, making the
  Home Assistant error and log more actionable.
- Preserved the RPM password exactly as entered during the SSH bootstrap; it
  is not stripped or stored.
- Kept the existing Paramiko password and keyboard-interactive behavior. This
  release does not add another authentication method.

## Verification

The websocket fallback test now asserts the complete awaited call, including
`pbc_host`, port `8480`, and the discovered PBC device ID. Targeted config-flow,
SSH-helper, and circuit-discovery tests passed, followed by the complete unit
suite, Python compilation checks, and `git diff --check`.

## Install and retest

Install beta9 through the Home Assistant custom repository/update mechanism,
restart Home Assistant, and retry the same Current-mode setup or reconfigure
flow. Confirm that setup reaches circuit discovery and that the PBC websocket
probe uses the Savant host address. If authentication still fails, follow the
[SSH troubleshooting guide](troubleshooting-ssh.md) and collect one focused
debug log.

## Rollback

If beta9 causes an unrelated regression, reinstall **v2.0.1-beta8** through
the same mechanism, restart Home Assistant, and report the beta9 log captured
from the failed reproduction. Do not share passwords, tokens, or private keys.
