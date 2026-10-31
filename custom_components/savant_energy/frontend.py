"""Serve the release-pinned companion card without duplicate frontend resources."""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from homeassistant.components import frontend

from .card_version import CARD_VERSION
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_DATA_KEY = f"{DOMAIN}_frontend"
_RESOURCE_BASE = f"/local/{DOMAIN}"
_EXTERNAL_CARD_PATHS = {
    "/hacsfiles/Savant-Card/Savant-Card.js",
    "/local/community/Savant-Card/Savant-Card.js",
    "/local/Savant-Card.js",
}


async def _async_has_external_card(hass) -> bool:
    """Respect an existing user-managed Dashboard resource; never delete it."""
    lovelace = hass.data.get("lovelace")
    resources = lovelace.get("resources") if isinstance(lovelace, dict) else getattr(lovelace, "resources", None)
    if resources is None:
        return False
    # This public method loads storage resources when needed (YAML is already loaded).
    await resources.async_get_info()
    return any(
        urlsplit(item.get("url", "")).path in _EXTERNAL_CARD_PATHS
        for item in resources.async_items()
    )


async def async_register_frontend_resource(hass) -> None:
    """Register once per HA process; reloads and multiple entries share the URLs."""
    state = hass.data.setdefault(_DATA_KEY, {"lock": asyncio.Lock()})
    async with state["lock"]:
        try:
            if not state.get("static_registered"):
                path = str(Path(__file__).parent / "www")
                try:
                    from homeassistant.components.http import StaticPathConfig
                except ImportError:
                    hass.http.register_static_path(_RESOURCE_BASE, path, True)
                else:
                    await hass.http.async_register_static_paths(
                        [StaticPathConfig(_RESOURCE_BASE, path, True)]
                    )
                state["static_registered"] = True

            external = await _async_has_external_card(hass)
            if external:
                _LOGGER.warning(
                    "A standalone Savant-Card Dashboard resource is installed; it remains "
                    "the card loader to avoid duplicate custom elements. Remove that resource "
                    "and reload Savant Energy to use the bundled companion card"
                )
            else:
                frontend.add_extra_js_url(
                    hass, f"{_RESOURCE_BASE}/Savant-Card.js?v={CARD_VERSION}"
                )
            # The old URL/type is an alias only, not a second card implementation.
            frontend.add_extra_js_url(
                hass, f"{_RESOURCE_BASE}/savant-energy-scenes-card.js?v={CARD_VERSION}"
            )
        except Exception:
            _LOGGER.exception("Failed to register the Savant Energy companion card")
