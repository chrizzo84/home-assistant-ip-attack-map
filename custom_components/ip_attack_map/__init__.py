"""IP Attack Map – visualize HTTP login attacks on a Home Assistant map."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import IpAttackMapCoordinator
from .frontend import async_register_frontend, async_register_lovelace_resource
from .listener import NotificationListener, async_import_ip_bans

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["geo_location", "sensor"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register frontend static files for the Lovelace card."""
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IP Attack Map from a config entry."""
    await async_register_frontend(hass)

    coordinator = IpAttackMapCoordinator(hass, entry)
    await coordinator.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    listener = NotificationListener(hass, coordinator)
    listener.async_setup()
    hass.data[DOMAIN][f"{entry.entry_id}_listener"] = listener

    await async_import_ip_bans(hass, coordinator)
    await coordinator.async_refresh()

    await async_register_lovelace_resource(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload IP Attack Map."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        listener = hass.data[DOMAIN].pop(f"{entry.entry_id}_listener", None)
        if listener:
            listener.async_unload()
        coordinator: IpAttackMapCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options/data updates."""
    await hass.config_entries.async_reload(entry.entry_id)
