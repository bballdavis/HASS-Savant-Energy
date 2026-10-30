---
title: Scenes card does not load
---

# Fix a missing scenes card

## Check setup first

1. Confirm the integration is set up and Home Assistant restarted after installation/update.
2. Check that **Disable Scene Builder** is off in [options](../usage/options.md).
3. Confirm your manual dashboard card contains:

   ```yaml
   type: custom:savant-energy-scenes-card
   ```

## Check the frontend resource

The integration registers this resource as extra frontend JavaScript:

```text
/local/savant_energy/savant-energy-scenes-card.js
```

This includes the `savant_energy` directory. The older README path `/local/savant-energy-scenes-card.js` omitted it.

Open the current path on your Home Assistant origin and check for a successful response. If automatic loading has failed, add the current URL under **Settings → Dashboards → Resources** as a **JavaScript module** (advanced mode may be needed). Avoid adding duplicate registrations. Reload the browser or clear its cached frontend files.

**Expected result:** the custom element loads and the card can read its scene list. If the JavaScript loads but the card still fails, capture the browser-console error and a focused Home Assistant log; do not assume a resource-path fix resolves every frontend exception.

## Scene data or API errors

Confirm the backend initialized its scene manager and views. See [REST API](../reference/rest-api.md) for authentication and payload expectations. Report the exact error with versions and sanitized logs. Do not post an access token.
