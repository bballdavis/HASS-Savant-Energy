# Savant Energy v2.0.1-beta7

## Status

These are the beta7 prerelease notes. Installing beta7 still requires verification against a running Home Assistant instance.

## Hub-only circuit recovery

Some Savant hosts publish stored relay-circuit measurements only through type-`0000` hub channels named `Energy.Circuit.<load name>.Power` and `.Energy`, without a `savantUUID`. Earlier polling treated those stored circuits as missing even while the hub had current measurements.

Beta7 safely recovers those readings by matching raw hub labels to the persisted circuit map through deterministic, one-to-one matching. Detailed `savantUUID` rows always win. Ambiguous names, duplicate aliases, and partial multi-leg circuits remain unmatched rather than being guessed.

Hub power is used as Watts. Hub circuit energy is retained as raw Wh and converted to kWh with the explicit `hub_wh_to_kwh` divisor of 1,000. Hub-only rows contain no relay state, current, voltage, flags, commanded percentage, or relay UID, so they never create a breaker switch or relay-status control.

## SSH-only setup and reconfigure

New current-mode setup and reconfigure now go directly through SSH bootstrap. The integration validates a token candidate against Savant circuit data and installs/verifies its refresh key before it updates saved authentication data. Resumed legacy token or manual-organization flow states are redirected to SSH and discard their transient input.

Existing token-only config entries remain supported at runtime. Reconfigure preserves their stored token and authentication data until SSH bootstrap succeeds.

For diagnostics only, the Savant read token may be located at either:

```text
/data/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
/data/home/RPM/GNUstep/Library/ApplicationSupport/RacePointMedia/statusfiles/InfluxDB2/.influxReadtoken
```

Do not print or share token contents. The adjacent `.influxsetup` and `.influxtoken` files can provide organization and bucket metadata.

## Install and restart guidance

Install beta7 through the same integration distribution path used for beta6, then restart Home Assistant so the updated integration code is loaded. Confirm the current-mode entry initializes, inspect the sanitized integration log for circuit inventory warnings, and verify that hub-only circuits expose measurements without new breaker controls. A local unit-test pass is not a substitute for that installed runtime check.

## Rollback

If beta7 needs to be rolled back, reinstall `v2.0.1-beta6` from the same distribution path and restart Home Assistant. Keep the existing config entry intact: beta7 does not require deleting it, and a failed SSH reconfigure does not overwrite the previously saved token/authentication state.
