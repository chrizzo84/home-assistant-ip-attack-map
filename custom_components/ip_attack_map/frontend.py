"""Register the Lovelace card frontend module (zero manual setup)."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

CARD_STATIC_PATH = "/api/ip_attack_map/card"
CARD_FILENAME = "ip-attack-map-card.js"
CARD_API_URL = f"{CARD_STATIC_PATH}/{CARD_FILENAME}"


def card_module_url() -> str:
    """Versioned module URL served from the integration (no /local/ copy)."""
    return f"{CARD_API_URL}?v={INTEGRATION_VERSION}"


def _url_path(url: str) -> str:
    """Return URL path without query string."""
    return url.split("?", 1)[0]


def _url_version(url: str) -> str | None:
    """Extract v= query parameter from a resource URL."""
    if "?" not in url:
        return None
    query = url.split("?", 1)[1]
    for part in query.split("&"):
        if part.startswith("v="):
            return part[2:]
    return None


async def _async_maybe_await(value: Any) -> Any:
    """Await coroutines; return plain values unchanged (HA version differences)."""
    if inspect.isawaitable(value):
        return await value
    return value


def _is_our_card_resource(url: str) -> bool:
    """True if this Lovelace resource belongs to IP Attack Map."""
    path = _url_path(url)
    return path == CARD_API_URL or path.endswith(f"/{CARD_FILENAME}")


def _register_extra_js(hass: HomeAssistant, url: str) -> None:
    """Load the card module on every HA frontend load (works without Lovelace resources UI)."""
    try:
        from homeassistant.components import frontend

        add_extra = getattr(frontend, "add_extra_js_url", None)
        if not callable(add_extra):
            _LOGGER.warning(
                "Home Assistant frontend does not support add_extra_js_url; "
                "Lovelace resource registration is required"
            )
            return
        add_extra(hass, url)
        _LOGGER.info("IP Attack Map card registered as frontend module: %s", url)
    except Exception:
        _LOGGER.exception("Failed to register IP Attack Map card as frontend module")


def _lovelace_storage_mode(hass: HomeAssistant) -> bool:
    """Return True when Lovelace resources are managed in storage (default)."""
    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if lovelace_data is None:
        return False
    if isinstance(lovelace_data, dict):
        mode = lovelace_data.get("mode", "storage")
    else:
        mode = getattr(lovelace_data, "mode", "storage")
    return mode == "storage"


async def async_register_static_path(hass: HomeAssistant) -> None:
    """Expose card JavaScript under /api/ip_attack_map/card/…"""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("frontend_static_registered"):
        return

    www = Path(__file__).parent / "www"
    if not www.is_dir():
        _LOGGER.error("IP Attack Map card directory missing: %s", www)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_STATIC_PATH, str(www), cache_headers=False)]
    )
    data["frontend_static_registered"] = True
    _LOGGER.debug("IP Attack Map card static path: %s", CARD_API_URL)


async def async_setup_card_frontend(hass: HomeAssistant) -> None:
    """Register static path, global JS module, and Lovelace resource (storage mode)."""
    await async_register_static_path(hass)

    module_url = card_module_url()
    hass.data.setdefault(DOMAIN, {})["card_module_url"] = module_url
    _register_extra_js(hass, module_url)

    if _lovelace_storage_mode(hass):
        await _async_wait_for_lovelace_resources(hass)
    else:
        _LOGGER.debug(
            "Lovelace YAML mode: card is loaded via frontend module only (%s)",
            CARD_API_URL,
        )


async def _async_wait_for_lovelace_resources(hass: HomeAssistant) -> None:
    """Wait until Lovelace resources are loaded, then register or update the module."""

    @callback
    def _schedule_retry() -> None:
        async_call_later(hass, 5, _on_timer)

    @callback
    def _on_timer(_now: Any) -> None:
        hass.async_create_task(_try_register())

    async def _try_register() -> None:
        lovelace_data = hass.data.get(LOVELACE_DOMAIN)
        if not lovelace_data:
            _LOGGER.debug("Lovelace not ready yet, retrying card resource registration")
            _schedule_retry()
            return

        resources = (
            lovelace_data.get("resources")
            if isinstance(lovelace_data, dict)
            else getattr(lovelace_data, "resources", None)
        )
        if resources is None:
            _schedule_retry()
            return

        if getattr(resources, "loaded", True) is False:
            _LOGGER.debug("Lovelace resources not loaded yet, retrying in 5s")
            _schedule_retry()
            return

        await _async_register_lovelace_resource(hass, resources)

    await _try_register()


async def _async_register_lovelace_resource(hass: HomeAssistant, resources: Any) -> None:
    """Create or update the Lovelace module resource for the card."""
    if not callable(getattr(resources, "async_create_item", None)):
        _LOGGER.debug("Lovelace resources are not storage-managed; skipping auto-register")
        return

    module_url = hass.data.get(DOMAIN, {}).get("card_module_url", card_module_url())

    try:
        existing = await _async_maybe_await(resources.async_items())
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources for IP Attack Map card")
        return

    for item in existing:
        url = item.get("url", "")
        if not _is_our_card_resource(url):
            continue

        if _url_version(url) == INTEGRATION_VERSION and _url_path(url) == CARD_API_URL:
            _LOGGER.debug("IP Attack Map Lovelace resource already up to date")
            return

        if not callable(getattr(resources, "async_update_item", None)):
            break

        try:
            await _async_maybe_await(
                resources.async_update_item(
                    item["id"],
                    {"res_type": "module", "url": module_url},
                )
            )
            _LOGGER.info(
                "Updated IP Attack Map Lovelace resource to version %s",
                INTEGRATION_VERSION,
            )
            return
        except Exception:
            _LOGGER.exception("Failed to update IP Attack Map Lovelace resource")
            return

    try:
        await _async_maybe_await(
            resources.async_create_item({"res_type": "module", "url": module_url})
        )
        _LOGGER.info(
            "Registered IP Attack Map Lovelace resource (%s)", module_url
        )
    except Exception:
        _LOGGER.exception("Failed to register IP Attack Map Lovelace resource")


@callback
def async_listen_for_card_frontend(hass: HomeAssistant) -> None:
    """Register the card once Home Assistant has started (and on retries)."""

    async def _setup(_event: Any = None) -> None:
        await async_setup_card_frontend(hass)

    @callback
    def _on_started(_event: Any) -> None:
        hass.async_create_task(_setup())

    if hass.state == CoreState.running:
        hass.async_create_task(_setup())
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    @callback
    def _retry(_now: Any) -> None:
        hass.async_create_task(async_setup_card_frontend(hass))

    for delay in (30, 120):
        async_call_later(hass, delay, _retry)
