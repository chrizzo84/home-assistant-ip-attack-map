"""Register the Lovelace card frontend module (zero manual setup)."""

from __future__ import annotations

import inspect
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
except ImportError:  # pragma: no cover - very old HA
    LOVELACE_DATA = LOVELACE_DOMAIN  # type: ignore[misc, assignment]
    MODE_STORAGE = "storage"

CARD_STATIC_PATH = "/api/ip_attack_map/card"
CARD_FILENAME = "ip-attack-map-card.js"
CARD_API_URL = f"{CARD_STATIC_PATH}/{CARD_FILENAME}"
LOCAL_REL_PATH = "www/ip_attack_map/ip-attack-map-card.js"
LOCAL_CARD_URL = "/local/ip_attack_map/ip-attack-map-card.js"
LOVELACE_RESOURCES_STORAGE_KEY = "lovelace_resources"
LOVELACE_RESOURCES_STORAGE_VERSION = 1


def card_module_url() -> str:
    """Versioned Lovelace module URL (/local — same pattern as HACS frontend cards)."""
    return f"{LOCAL_CARD_URL}?v={INTEGRATION_VERSION}"


def card_extra_module_url() -> str:
    """Same URL as the Lovelace resource (required for extra_js + dashboard resources)."""
    return card_module_url()


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
    if not url:
        return False
    path = _url_path(url).lower()
    if path in {CARD_API_URL.lower(), LOCAL_CARD_URL.lower()}:
        return True
    if path.endswith(CARD_FILENAME.lower()):
        return True
    # Legacy / typo URLs users may have added manually.
    if "ip_attack_map" in path or "ip-attack-map" in path:
        return "card" in path or path.endswith(".js")
    return False


def _resource_is_current(url: str) -> bool:
    """True when the stored Lovelace resource matches version and /local path."""
    return (
        _url_path(url) == LOCAL_CARD_URL
        and _url_version(url) == INTEGRATION_VERSION
    )


def _get_lovelace(hass: HomeAssistant) -> Any | None:
    """Return LovelaceData (HA 2024+) or legacy dict."""
    return hass.data.get(LOVELACE_DATA) or hass.data.get(LOVELACE_DOMAIN)


def _get_resources(hass: HomeAssistant) -> Any | None:
    """Return the Lovelace resources collection."""
    lovelace = _get_lovelace(hass)
    if lovelace is None:
        return None
    if hasattr(lovelace, "resources"):
        return lovelace.resources
    if isinstance(lovelace, dict):
        return lovelace.get("resources")
    return None


def _lovelace_resource_storage_mode(hass: HomeAssistant) -> bool:
    """Return True when Lovelace resources are managed in storage (default)."""
    lovelace = _get_lovelace(hass)
    if lovelace is None:
        return False
    if hasattr(lovelace, "resource_mode"):
        return lovelace.resource_mode == MODE_STORAGE
    if isinstance(lovelace, dict):
        mode = lovelace.get("resource_mode", lovelace.get("mode", MODE_STORAGE))
        return mode == MODE_STORAGE
    return True


async def _async_ensure_resources_loaded(resources: Any) -> None:
    """Load Lovelace resources from disk before list/create (avoids empty collection)."""
    if hasattr(resources, "async_get_info"):
        await resources.async_get_info()
        return
    if hasattr(resources, "_async_ensure_loaded"):
        await resources._async_ensure_loaded()
        return
    if hasattr(resources, "async_load") and not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True


async def _async_list_resources(resources: Any) -> list[dict[str, Any]]:
    """Return all Lovelace resource items."""
    await _async_ensure_resources_loaded(resources)
    items = resources.async_items()
    result = await _async_maybe_await(items)
    return list(result or [])


async def _async_patch_lovelace_resources_storage(
    hass: HomeAssistant, module_url: str
) -> bool:
    """Last resort: patch .storage/lovelace_resources when collection API fails."""
    store = Store(
        hass,
        LOVELACE_RESOURCES_STORAGE_VERSION,
        LOVELACE_RESOURCES_STORAGE_KEY,
    )
    data = await store.async_load()
    if not data or not isinstance(data.get("items"), list):
        return False

    changed = False
    found = False
    for item in data["items"]:
        url = item.get("url", "")
        if not _is_our_card_resource(url):
            continue
        found = True
        if item.get("url") != module_url or item.get("type") != "module":
            item["url"] = module_url
            item["type"] = "module"
            changed = True

    if not found:
        data["items"].append(
            {
                "id": uuid.uuid4().hex,
                "type": "module",
                "url": module_url,
            }
        )
        changed = True

    if not changed:
        return False

    await store.async_save(data)
    resources = _get_resources(hass)
    if resources is not None and hasattr(resources, "async_load"):
        await resources.async_load()
        resources.loaded = True
    _LOGGER.info(
        "Patched IP Attack Map Lovelace resource in storage to %s", module_url
    )
    return True


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


def _frontend_extra_modules_ready(hass: HomeAssistant) -> bool:
    """True when Home Assistant finished frontend setup (UrlManager exists)."""
    return DATA_EXTRA_MODULE_URL in hass.data


@callback
def async_register_extra_module(hass: HomeAssistant) -> bool:
    """Load card JS with the main frontend (Community Cards picker), not only Lovelace resources."""
    if not _frontend_extra_modules_ready(hass):
        _LOGGER.debug(
            "Frontend extra module registry not ready yet; extra_js will retry after start"
        )
        return False

    module_url = card_extra_module_url()
    data = hass.data.setdefault(DOMAIN, {})
    previous = data.get("extra_module_url")

    try:
        if previous and previous != module_url:
            frontend.remove_extra_js_url(hass, previous)
        if previous != module_url:
            frontend.add_extra_js_url(hass, module_url)
            _LOGGER.info(
                "Registered IP Attack Map frontend module (extra_js): %s",
                module_url,
            )
        else:
            _LOGGER.debug(
                "IP Attack Map frontend module (extra_js) already registered: %s",
                module_url,
            )
        data["extra_module_url"] = module_url
        return True
    except Exception:
        _LOGGER.exception(
            "Failed to register IP Attack Map frontend module (extra_js): %s",
            module_url,
        )
        return False


def _copy_card_js(src: Path, dest: Path) -> None:
    """Copy card JavaScript into config/www (runs in executor)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


async def async_publish_card_to_www(
    hass: HomeAssistant, *, quiet: bool = False
) -> None:
    """Publish card JS under /config/www so /local/… works after browser reload."""
    src = Path(__file__).parent / "www" / CARD_FILENAME
    if not src.is_file():
        _LOGGER.warning("Card source missing: %s", src)
        return

    dest = Path(hass.config.path(LOCAL_REL_PATH))
    await hass.async_add_executor_job(_copy_card_js, src, dest)
    log = _LOGGER.debug if quiet else _LOGGER.info
    log("Published IP Attack Map card for Lovelace: %s", dest)


async def async_ensure_card_assets(
    hass: HomeAssistant, *, quiet: bool = False
) -> str:
    """Register HTTP path, publish /local copy, and Lovelace resource (call from async_setup)."""
    await async_register_static_path(hass)
    await async_publish_card_to_www(hass, quiet=quiet)

    module_url = card_module_url()
    hass.data.setdefault(DOMAIN, {})["card_module_url"] = module_url
    # extra_js and Lovelace resource must use the same /local URL (card-mod pattern).
    async_register_extra_module(hass)
    await async_register_lovelace_resource(hass, quiet=quiet)
    return module_url


async def async_register_lovelace_resource(
    hass: HomeAssistant, *, quiet: bool = False
) -> bool:
    """Create or update the Lovelace module resource for the card."""
    if not _lovelace_resource_storage_mode(hass):
        _LOGGER.info(
            "Lovelace resources use YAML mode; add this module resource manually: %s",
            card_module_url(),
        )
        return False

    resources = _get_resources(hass)
    if resources is None:
        _LOGGER.warning(
            "Lovelace not ready; IP Attack Map card resource not registered yet"
        )
        return False

    if not callable(getattr(resources, "async_create_item", None)):
        _LOGGER.debug(
            "Lovelace resources are not storage-managed; skipping auto-register"
        )
        return False

    module_url = hass.data.get(DOMAIN, {}).get("card_module_url", card_module_url())

    try:
        existing = await _async_list_resources(resources)
    except Exception:
        _LOGGER.exception("Could not read Lovelace resources for IP Attack Map card")
        return await _async_patch_lovelace_resources_storage(hass, module_url)

    our_items = [
        item for item in existing if _is_our_card_resource(item.get("url", ""))
    ]

    if our_items:
        current_items = [
            item for item in our_items if _resource_is_current(item.get("url", ""))
        ]
        if current_items:
            keeper_id = current_items[0]["id"]
            for item in our_items:
                if item["id"] != keeper_id:
                    await resources.async_delete_item(item["id"])
                    _LOGGER.info(
                        "Removed duplicate IP Attack Map resource: %s",
                        item.get("url"),
                    )
            log = _LOGGER.debug if quiet else _LOGGER.info
            log(
                "IP Attack Map Lovelace resource is current: %s (integration %s)",
                current_items[0].get("url"),
                INTEGRATION_VERSION,
            )
            return True

        try:
            old_url = our_items[0].get("url", "")
            await resources.async_update_item(
                our_items[0]["id"],
                {"res_type": "module", "url": module_url},
            )
            _LOGGER.info(
                "Aligned IP Attack Map Lovelace resource to integration %s (was %s)",
                INTEGRATION_VERSION,
                old_url,
            )
            for item in our_items[1:]:
                await resources.async_delete_item(item["id"])
                _LOGGER.info(
                    "Removed duplicate IP Attack Map resource: %s",
                    item.get("url"),
                )
            return True
        except Exception:
            _LOGGER.exception("Failed to update IP Attack Map Lovelace resource")
            return await _async_patch_lovelace_resources_storage(hass, module_url)

    try:
        await resources.async_create_item(
            {"res_type": "module", "url": module_url}
        )
        _LOGGER.info("Registered IP Attack Map Lovelace resource: %s", module_url)
        return True
    except Exception:
        _LOGGER.exception("Failed to register IP Attack Map Lovelace resource")
        return await _async_patch_lovelace_resources_storage(hass, module_url)


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
        await async_register_static_path(hass)
        if not async_register_extra_module(hass):
            _LOGGER.warning(
                "IP Attack Map extra_js not registered yet; Community Cards may be "
                "missing until the next retry"
            )
        await async_publish_card_to_www(hass, quiet=True)
        await async_register_lovelace_resource(hass, quiet=True)

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

    for delay in (5, 15, 60, 180, 600):
        async_call_later(hass, delay, _retry)

    hass.async_create_task(_async_wait_for_lovelace_resources(hass))
