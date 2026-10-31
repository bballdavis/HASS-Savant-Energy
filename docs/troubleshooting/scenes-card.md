---
title: Scenes card does not load
---

# Fix a missing dashboard card

## Check setup first

1. Confirm the integration is set up and Home Assistant restarted after installation/update.
2. Leave **Disable Scene Builder** off in [options](../usage/options.md). It controls scene-backend and frontend setup.
3. Refresh the browser, then add **Savant Energy Card** or use:

   ```yaml
   type: custom:savant-energy-breaker-board-card
   ```

Existing `custom:savant-energy-scenes-card` YAML is an alias for this board. The older scenes-only implementation is no longer shipped.

## Check the frontend resource

The integration automatically loads these files with a version query:

```text
/local/savant_energy/Savant-Card.js
/local/savant_energy/savant-energy-scenes-card.js
```

The second file is only the old-type compatibility alias. Open these paths on your Home Assistant origin and check for successful responses. Do not add duplicate resources to fix a failed load. Capture a browser-console error and focused Home Assistant log if loading fails.

If a standalone Savant-Card resource is already installed, the integration logs that it is leaving that copy in charge. Follow [the migration steps](../usage/companion-card.md#separate-savant-card-hacs-installation) to remove the standalone resource, reload the integration, and refresh the browser. Remove custom-path copies too; only the documented standalone paths can be detected automatically.

For `already been used with this registry` or `already defined` console errors, remove duplicate/manual Dashboard resources and refresh all Home Assistant tabs. A stale browser may retain the old implementation until refreshed. The old README URL `/local/savant-energy-scenes-card.js` was incorrect; the correct path includes `/savant_energy/`.

**Expected result:** the new board loads and can read its scene list. An HTTP success alone does not prove every card feature works.

## Scene data or API errors

Confirm the scene manager and views initialized. See [REST API](../reference/rest-api.md) for authentication, required fields, and current limitations. Report exact errors with versions and sanitized logs. Do not post access tokens.
