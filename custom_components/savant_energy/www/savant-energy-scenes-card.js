/* Compatibility alias only. Savant Energy or an existing HACS resource loads the board. */
(function () {
  const legacy = "savant-energy-scenes-card";
  if (customElements.get(legacy)) return;
  customElements.whenDefined("savant-energy-breaker-board-card").then(() => {
    if (customElements.get(legacy)) return;
    const Board = customElements.get("savant-energy-breaker-board-card");
    class LegacyScenesCard extends Board {
      setConfig(config) {
        super.setConfig({
          ...config,
          type: "custom:savant-energy-breaker-board-card",
          display: {...config.display, show_title: config.show_header !== false && config.display?.show_title !== false},
        });
      }
    }
    customElements.define(legacy, LegacyScenesCard);
  });
})();
