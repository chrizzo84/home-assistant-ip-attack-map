"""Register the Lovelace card frontend module."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.core import HomeAssistant

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

CARD_STATIC_PATH = "/api/ip_attack_map/card"
CARD_MODULE_URL = f"{CARD_STATIC_PATH}/ip-attack-map-card.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card JavaScript."""
    if hass.data.get(DOMAIN, {}).get("frontend_registered"):
        return

    www = Path(__file__).parent / "www"
    if not www.is_dir():
        _LOGGER.warning("IP Attack Map card www directory missing at %s", www)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_STATIC_PATH, str(www), cache_headers=False)]
    )
    hass.data.setdefault(DOMAIN, {})["frontend_registered"] = True
    _LOGGER.debug("IP Attack Map card static files registered at %s", CARD_STATIC_PATH)


async def async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Add the card module to Lovelace resources (storage mode) if missing."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if not lovelace_data:
        _LOGGER.debug("Lovelace not loaded; skip auto-registering card resource")
        return

    resources = lovelace_data.get("resources")
    if resources is None:
        return

    try:
        existing = await resources.async_items()
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources")
        return

    versioned_url = f"{CARD_MODULE_URL}?v={INTEGRATION_VERSION}"
    if any(
        item.get("url", "").split("?")[0] == CARD_MODULE_URL for item in existing
    ):
        return

    try:
        await resources.async_create_item(
            {"res_type": "module", "url": versioned_url}
        )
        _LOGGER.info(
            "Registered Lovelace resource for IP Attack Map card (%s)",
            versioned_url,
        )
    except Exception:
        _LOGGER.exception("Failed to register Lovelace resource for IP Attack Map card")
