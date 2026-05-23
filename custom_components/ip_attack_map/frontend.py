"""Register the Lovelace card frontend module."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

CARD_STATIC_PATH = "/api/ip_attack_map/card"
CARD_API_URL = f"{CARD_STATIC_PATH}/ip-attack-map-card.js"
LOCAL_CARD_PATH = "www/ip_attack_map/ip-attack-map-card.js"
LOCAL_CARD_URL = "/local/ip_attack_map/ip-attack-map-card.js"
NOTIFICATION_ID_RESOURCE = "ip_attack_map_card_resource"


def card_resource_yaml_snippet() -> str:
    """YAML snippet for manual Lovelace resource registration."""
    return (
        "lovelace:\n"
        "  resources:\n"
        f"    - url: {LOCAL_CARD_URL}\n"
        "      type: module\n"
    )


def _can_auto_register_resources(resources: Any) -> bool:
    """Return True if resources are managed in storage (not YAML)."""
    return callable(getattr(resources, "async_create_item", None))


def _copy_card_js(src: Path, dest: Path) -> None:
    """Copy card JavaScript into config/www (runs in executor)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


async def async_publish_card_to_www(hass: HomeAssistant) -> str:
    """Publish card JS under /config/www for reliable /local/ loading."""
    src = Path(__file__).parent / "www" / "ip-attack-map-card.js"
    if not src.is_file():
        _LOGGER.warning("Card source missing: %s", src)
        return LOCAL_CARD_URL

    dest = Path(hass.config.path(LOCAL_CARD_PATH))
    await hass.async_add_executor_job(_copy_card_js, src, dest)
    _LOGGER.info("Published IP Attack Map card to %s", dest)
    return LOCAL_CARD_URL


def _register_extra_js(hass: HomeAssistant, url: str) -> None:
    """Load card module globally when supported (in addition to Lovelace resource)."""
    try:
        from homeassistant.components import frontend

        add_extra = getattr(frontend, "add_extra_js_url", None)
        if callable(add_extra):
            add_extra(hass, url)
            _LOGGER.debug("Registered extra JS URL for IP Attack Map card")
    except Exception:
        _LOGGER.debug("Could not register extra JS URL for IP Attack Map card")


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card from /api/... and publish a copy under /local/..."""
    data = hass.data.setdefault(DOMAIN, {})

    www = Path(__file__).parent / "www"
    if not www.is_dir():
        _LOGGER.warning("IP Attack Map card www directory missing at %s", www)
        return

    if not data.get("frontend_registered"):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_STATIC_PATH, str(www), cache_headers=False)]
        )
        data["frontend_registered"] = True
        _LOGGER.info("IP Attack Map card API path: %s", CARD_API_URL)

    card_url = await async_publish_card_to_www(hass)
    versioned_url = f"{card_url}?v={INTEGRATION_VERSION}"
    data["card_module_url"] = versioned_url
    _register_extra_js(hass, versioned_url)


async def async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Add the card module to Lovelace resources if possible."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if not lovelace_data:
        _LOGGER.debug("Lovelace not loaded yet; card resource not registered")
        return False

    resources = lovelace_data.get("resources")
    if resources is None:
        return False

    card_url_base = LOCAL_CARD_URL
    versioned_url = hass.data.get(DOMAIN, {}).get(
        "card_module_url", f"{card_url_base}?v={INTEGRATION_VERSION}"
    )
    # Normalize to path without query for duplicate check
    url_paths = {card_url_base, CARD_API_URL}

    if not _can_auto_register_resources(resources):
        _LOGGER.warning(
            "Lovelace resources are YAML-managed; add the card resource manually: %s",
            card_url_base,
        )
        await _async_notify_manual_resource(hass, card_url_base)
        return False

    try:
        existing = await resources.async_items()
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources")
        return False

    if any(
        item.get("url", "").split("?")[0] in url_paths for item in existing
    ):
        _LOGGER.debug("IP Attack Map Lovelace resource already registered")
        # Ensure /local/ URL is present (user may only have old /api/ entry)
        if not any(
            item.get("url", "").split("?")[0] == card_url_base for item in existing
        ):
            try:
                await resources.async_create_item(
                    {"res_type": "module", "url": versioned_url}
                )
                _LOGGER.info("Added /local/ Lovelace resource for IP Attack Map card")
            except Exception:
                _LOGGER.exception("Failed to add /local/ Lovelace resource")
        await _async_dismiss_resource_notification(hass)
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


async def _async_notify_manual_resource(hass: HomeAssistant, card_url: str) -> None:
    """Tell the user to add the Lovelace resource manually."""
    from homeassistant.components import persistent_notification

    persistent_notification.async_create(
        hass,
        (
            "Die Karte muss einmalig als Lovelace-Ressource eingetragen werden.\n\n"
            "**Einstellungen → Dashboards → Ressourcen → Ressource hinzufügen**\n"
            f"- URL: `{card_url}`\n"
            "- Typ: **JavaScript-Modul**\n\n"
            "Danach **Cmd+Shift+R** (Safari) und Dashboard neu laden.\n\n"
            f"Alternativ (API): `{CARD_API_URL}`"
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

    for delay in (0, 2, 10, 30, 60):
        async_call_later(hass, delay, _try_register)
