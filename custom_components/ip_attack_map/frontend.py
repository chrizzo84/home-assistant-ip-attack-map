"""Register the Lovelace card frontend module (zero manual setup)."""

from __future__ import annotations

import inspect
import logging
import shutil
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
LOCAL_REL_PATH = "www/ip_attack_map/ip-attack-map-card.js"
LOCAL_CARD_URL = "/local/ip_attack_map/ip-attack-map-card.js"


def card_module_url() -> str:
    """Versioned Lovelace module URL (/local is most reliable after page reload)."""
    return f"{LOCAL_CARD_URL}?v={INTEGRATION_VERSION}"


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
    return path in {CARD_API_URL, LOCAL_CARD_URL} or path.endswith(f"/{CARD_FILENAME}")


def _resource_is_current(url: str) -> bool:
    """True when the stored Lovelace resource matches the preferred local URL."""
    return (
        _url_path(url) == LOCAL_CARD_URL
        and _url_version(url) == INTEGRATION_VERSION
    )


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


def _copy_card_js(src: Path, dest: Path) -> None:
    """Copy card JavaScript into config/www (runs in executor)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


async def async_publish_card_to_www(hass: HomeAssistant) -> None:
    """Publish card JS under /config/www so /local/… works after browser reload."""
    src = Path(__file__).parent / "www" / CARD_FILENAME
    if not src.is_file():
        _LOGGER.warning("Card source missing: %s", src)
        return

    dest = Path(hass.config.path(LOCAL_REL_PATH))
    await hass.async_add_executor_job(_copy_card_js, src, dest)
    _LOGGER.info("Published IP Attack Map card for Lovelace: %s", dest)


async def async_ensure_card_assets(hass: HomeAssistant) -> str:
    """Register HTTP path, publish /local copy, and Lovelace resource (call from async_setup)."""
    await async_register_static_path(hass)
    await async_publish_card_to_www(hass)

    module_url = card_module_url()
    hass.data.setdefault(DOMAIN, {})["card_module_url"] = module_url
    await async_register_lovelace_resource(hass)
    return module_url


async def async_register_lovelace_resource(hass: HomeAssistant) -> bool:
    """Create or update the Lovelace module resource for the card."""
    if not _lovelace_storage_mode(hass):
        _LOGGER.debug("Lovelace YAML mode: skipping automatic resource registration")
        return False

    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if not lovelace_data:
        return False

    resources = (
        lovelace_data.get("resources")
        if isinstance(lovelace_data, dict)
        else getattr(lovelace_data, "resources", None)
    )
    if resources is None:
        return False

    if getattr(resources, "loaded", True) is False:
        return False

    if not callable(getattr(resources, "async_create_item", None)):
        _LOGGER.debug("Lovelace resources are not storage-managed; skipping auto-register")
        return False

    module_url = hass.data.get(DOMAIN, {}).get("card_module_url", card_module_url())

    try:
        existing = await _async_maybe_await(resources.async_items())
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources for IP Attack Map card")
        return False

    for item in existing:
        url = item.get("url", "")
        if not _is_our_card_resource(url):
            continue

        if _resource_is_current(url):
            _LOGGER.debug("IP Attack Map Lovelace resource already current: %s", url)
            return True

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
                "Updated IP Attack Map Lovelace resource to %s", module_url
            )
            return True
        except Exception:
            _LOGGER.exception("Failed to update IP Attack Map Lovelace resource")
            return False

    try:
        await _async_maybe_await(
            resources.async_create_item({"res_type": "module", "url": module_url})
        )
        _LOGGER.info("Registered IP Attack Map Lovelace resource: %s", module_url)
        return True
    except Exception:
        _LOGGER.exception("Failed to register IP Attack Map Lovelace resource")
        return False


async def _async_wait_for_lovelace_resources(hass: HomeAssistant) -> None:
    """Wait until Lovelace resources are loaded, then register or update the module."""

    @callback
    def _schedule_retry() -> None:
        async_call_later(hass, 5, _on_timer)

    @callback
    def _on_timer(_now: Any) -> None:
        hass.async_create_task(_try_register())

    async def _try_register() -> None:
        if await async_register_lovelace_resource(hass):
            return
        _schedule_retry()

    await _try_register()


@callback
def async_listen_for_card_frontend(hass: HomeAssistant) -> None:
    """Register Lovelace resource after startup (assets are ready from async_setup)."""

    async def _register_lovelace(_event: Any = None) -> None:
        await async_publish_card_to_www(hass)
        if _lovelace_storage_mode(hass):
            await _async_wait_for_lovelace_resources(hass)

    @callback
    def _on_started(_event: Any) -> None:
        hass.async_create_task(_register_lovelace())

    if hass.state == CoreState.running:
        hass.async_create_task(_register_lovelace())
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    @callback
    def _retry(_now: Any) -> None:
        hass.async_create_task(_register_lovelace())

    for delay in (15, 60, 180):
        async_call_later(hass, delay, _retry)
