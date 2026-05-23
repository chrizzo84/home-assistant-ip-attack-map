"""Register the Lovelace card frontend module."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

CARD_STATIC_PATH = "/api/ip_attack_map/card"
CARD_MODULE_URL = f"{CARD_STATIC_PATH}/ip-attack-map-card.js"
NOTIFICATION_ID_RESOURCE = "ip_attack_map_card_resource"


def card_resource_yaml_snippet() -> str:
    """YAML snippet for manual Lovelace resource registration."""
    return (
        "lovelace:\n"
        "  resources:\n"
        f"    - url: {CARD_MODULE_URL}\n"
        "      type: module\n"
    )


def _can_auto_register_resources(resources: Any) -> bool:
    """Return True if resources are managed in storage (not YAML)."""
    return callable(getattr(resources, "async_create_item", None))


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
    _LOGGER.info("IP Attack Map card available at %s", CARD_MODULE_URL)


async def async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Add the card module to Lovelace resources if possible. Returns True on success."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if not lovelace_data:
        _LOGGER.debug("Lovelace not loaded yet; card resource not registered")
        return False

    resources = lovelace_data.get("resources")
    if resources is None:
        return False

    if not _can_auto_register_resources(resources):
        _LOGGER.warning(
            "Lovelace resources are YAML-managed; add the card resource manually: %s",
            CARD_MODULE_URL,
        )
        await _async_notify_manual_resource(hass)
        return False

    try:
        existing = await resources.async_items()
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources")
        return False

    versioned_url = f"{CARD_MODULE_URL}?v={INTEGRATION_VERSION}"
    if any(
        item.get("url", "").split("?")[0] == CARD_MODULE_URL for item in existing
    ):
        _LOGGER.debug("IP Attack Map Lovelace resource already registered")
        return True

    try:
        await resources.async_create_item(
            {"res_type": "module", "url": versioned_url}
        )
        _LOGGER.info(
            "Registered Lovelace resource for IP Attack Map card (%s)",
            versioned_url,
        )
        await _async_dismiss_resource_notification(hass)
        return True
    except Exception:
        _LOGGER.exception("Failed to register Lovelace resource for IP Attack Map card")
        return False


async def _async_notify_manual_resource(hass: HomeAssistant) -> None:
    """Tell the user to add the Lovelace resource manually (YAML mode)."""
    from homeassistant.components import persistent_notification

    persistent_notification.async_create(
        hass,
        (
            "Die Karte muss einmalig als Lovelace-Ressource eingetragen werden.\n\n"
            "**UI:** Einstellungen → Dashboards → Ressourcen → Ressource hinzufügen\n"
            f"- URL: `{CARD_MODULE_URL}`\n"
            "- Typ: **JavaScript-Modul**\n\n"
            "Danach Browser-Cache leeren (Cmd+Shift+R) und Dashboard neu laden.\n\n"
            "**YAML-Modus:** siehe README im Repository."
        ),
        "IP Attack Map – Karte einrichten",
        NOTIFICATION_ID_RESOURCE,
    )


async def _async_dismiss_resource_notification(hass: HomeAssistant) -> None:
    """Remove manual-setup notification after successful registration."""
    from homeassistant.components import persistent_notification

    persistent_notification.async_dismiss(hass, NOTIFICATION_ID_RESOURCE)


@callback
def async_schedule_lovelace_resource(hass: HomeAssistant) -> None:
    """Retry Lovelace resource registration until Lovelace is ready."""

    @callback
    def _try_register(_now) -> None:
        hass.async_create_task(async_register_lovelace_resource(hass))

    # Lovelace may load after the config entry; retry a few times.
    for delay in (0, 2, 10, 30):
        async_call_later(hass, delay, _try_register)
