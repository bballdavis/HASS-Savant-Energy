---
title: Scenes and editors
---

# Manage saved relay states

There are two scene editors: the **companion breaker board’s scene view**, shown below, and the older **scenes-only card bundled with this integration**. Both work with saved relay states; their interfaces and resource URLs differ.

## Companion scene view

[Install the companion breaker board](companion-card.md), then open its **Scenes** toolbar action.

![The actual companion card’s scene list in Home Assistant](../assets/companion-scenes.jpg)

Select a saved scene to inspect its members and planned on/off states. The editor shows a total estimated load based on the available average readings; optional battery-capacity configuration adds drain estimates in supported companion versions.

![The actual companion scene editor showing a saved power-shedding scene and its relay states](../assets/companion-scene-editor.jpg)

*Real Home Assistant captures. The editor was opened for inspection; no relay was toggled, scene activated, or scene saved for these screenshots.*

Review every member before saving or activating a scene. Editing stored states does not itself prove that a physical load changed. Use the corresponding Home Assistant scene/button to execute a saved scene, then check live status.

## Bundled scenes-only card

The integration also ships `custom:savant-energy-scenes-card`. It is separate from the companion breaker board and does not show its circuit tile grid.

### Add the bundled card

1. Set up the integration and leave **Disable Scene Builder** off in [options](options.md).
2. Edit a Home Assistant dashboard and choose **Add card → Manual**.
3. Enter:

   ```yaml
   type: custom:savant-energy-scenes-card
   ```

4. Save the card.

**Expected result:** the bundled card loads its scene list. For missing custom elements, see [card troubleshooting](../troubleshooting/scenes-card.md).

### Create and edit

1. On **Scenes**, enter a name and choose **Create**. Current backend creation initializes discovered available breaker-like switches to **on**, ignoring supplied initial mappings.
2. Open **Editor**, select the new scene, and review every relay. The backend discovery heuristic includes switches with “breaker” in their entity ID or friendly name.
3. Set the intended states and choose **Save**. Read back the saved states before activation.

The REST breaker-list view defaults newly discovered unsaved members to **on**, while the service handler defaults them to **off**. Review states explicitly rather than assuming matching defaults.

## For automations and clients

Use the [service reference](../reference/generated/services.md) for Home Assistant actions and [REST API](../reference/rest-api.md) for authenticated HTTP calls. Creating a scene requires both `name` and `relay_states`; the REST guide documents the existing creation/update limitations.
