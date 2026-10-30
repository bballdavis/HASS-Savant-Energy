---
title: Companion breaker-board card
---

# Put your circuits on a dashboard

The [Savant Energy Breaker Board](https://github.com/bballdavis/Savant-Card) is the companion frontend for the `savant_energy` integration. It discovers related circuit entities and presents live wattage, history graphs, relay controls, and saved-scene editing.

The screenshots below were captured from the actual card running in Home Assistant. They are not recreated interfaces or generated mockups. Readings vary with the connected equipment and capture time.

![Live breaker-board grid with current wattage, history graphs, and AVG/MAX values](../assets/breaker-board-desktop.jpg)

## Install the companion card

The breaker board is a **separate HACS Dashboard repository**. The backend integration in this repository also bundles an older scenes-only card; these are different frontend components.

1. Set up the Savant Energy integration and [verify its readings](../connect/verify.md).
2. Add `https://github.com/bballdavis/Savant-Card` to HACS as a **Dashboard** repository and install it.
3. Confirm the resource is loaded as a JavaScript module:

   ```text
   /hacsfiles/Savant-Card/Savant-Card.js
   ```

4. Refresh Home Assistant, edit your dashboard, and choose **Savant Energy Breaker Board** from the card picker.
5. Use its graphical editor to choose display and control settings. For a minimal manual card:

   ```yaml
   type: custom:savant-energy-breaker-board-card
   ```

**Expected result:** the card discovers related entities from the integration. Missing registry relationships may require the card’s manual mappings; see its [configuration reference](https://github.com/bballdavis/Savant-Card/blob/main/docs/CONFIGURATION.md).

A Home Assistant **panel view** lets the board fill the available width. Sections and masonry dashboards can also host it; the card responds to its own available width.

## Desktop and mobile layouts

On wide cards, circuits appear as tiles with current wattage, AVG/MAX values, and optional history graphs. Narrow cards switch to stacked rows. The mobile toolbar’s compact control switches between standard and ultra-compact rows.

### Standard mobile

![Actual standard mobile breaker-board layout with current power, average and maximum readings, and graphs](../assets/breaker-board-mobile.jpg)

### Ultra-compact mobile

![Actual ultra-compact mobile layout showing more circuit rows in the same space](../assets/breaker-board-compact.jpg)

These are real captures of the same installed card at a narrow viewport. Compact mode reduces each row’s displayed detail; it does not change the relay state. The selected mobile view is remembered in that browser.

## Find a load and inspect it

- **Search** filters the displayed circuits.
- **Sort** offers circuit number, name, current power, highest usage, and manual ordering. Manual ordering is a placeholder in the companion’s documented v1 surface; use the supported automatic choices.
- Tap a tile to open Home Assistant’s more-info view.
- The circular relay control uses the configured hold/confirmation behavior. Inspect a tile without holding the power control when you only want readings.

## Saved scenes

Open **Scenes** to see saved scenes, then select one to inspect its planned relay states. See [Scenes and editors](scenes.md) for captures and the distinction between editing a stored scene and executing it.

For companion-specific updates and issues, use the [Savant-Card repository](https://github.com/bballdavis/Savant-Card). Backend connection, telemetry, and identity issues belong to this integration.
