"""Listen for HTTP ban persistent notifications and import ip_bans.yaml."""

from __future__ import annotations

import logging
from pathlib import Path
from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.config import load_yaml_config_file
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from homeassistant.components.persistent_notification import (
    SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
    UpdateType,
)

from .const import (
    IP_BANS_FILE,
    NOTIFICATION_ID_BAN,
    NOTIFICATION_ID_LOGIN,
)
from .coordinator import IpAttackMapCoordinator
from .parser import parse_ban_message, parse_login_message

_LOGGER = logging.getLogger(__name__)

ATTR_MESSAGE = "message"
ATTR_NOTIFICATION_ID = "notification_id"

SCHEMA_IP_BAN_ENTRY = vol.Schema(
    {vol.Optional("banned_at"): vol.Any(None, cv.datetime)}
)


class NotificationListener:
    """Subscribe to persistent notifications from HTTP ban middleware."""

    def __init__(
        self, hass: HomeAssistant, coordinator: IpAttackMapCoordinator
    ) -> None:
        """Initialize listener."""
        self._hass = hass
        self._coordinator = coordinator
        self._unsub: Callable[[], None] | None = None
        self._seen_messages: set[str] = set()

    @callback
    def async_setup(self) -> None:
        """Register persistent notification dispatcher."""
        self._unsub = async_dispatcher_connect(
            self._hass,
            SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
            self._handle_notification_update,
        )

    @callback
    def async_unload(self) -> None:
        """Unregister listener."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_notification_update(
        self,
        update_type: UpdateType,
        notifications: dict[str, dict[str, Any]],
    ) -> None:
        """Handle persistent notification updates."""
        if update_type not in (UpdateType.ADDED, UpdateType.UPDATED, UpdateType.CURRENT):
            return

        for notification_id, data in notifications.items():
            if notification_id not in (NOTIFICATION_ID_LOGIN, NOTIFICATION_ID_BAN):
                continue
            message = data.get(ATTR_MESSAGE, "")
            dedupe_key = f"{notification_id}:{message}"
            if dedupe_key in self._seen_messages:
                continue
            self._seen_messages.add(dedupe_key)
            self._hass.async_create_task(
                self._process_notification(notification_id, message),
                f"ip_attack_map_process_{notification_id}",
            )

    async def _process_notification(
        self, notification_id: str, message: str
    ) -> None:
        """Parse and record attack from notification."""
        if notification_id == NOTIFICATION_ID_LOGIN:
            parsed = parse_login_message(message)
        else:
            parsed = parse_ban_message(message)

        if parsed is None:
            _LOGGER.debug(
                "Could not parse notification %s: %s",
                notification_id,
                message[:120],
            )
            return

        await self._coordinator.async_record_attack(parsed)


async def async_import_ip_bans(
    hass: HomeAssistant, coordinator: IpAttackMapCoordinator
) -> None:
    """Import existing bans from ip_bans.yaml."""
    path = Path(hass.config.path(IP_BANS_FILE))
    if not path.is_file():
        return

    try:
        bans = await hass.async_add_executor_job(load_yaml_config_file, str(path))
    except FileNotFoundError:
        return
    except HomeAssistantError as err:
        _LOGGER.warning("Unable to load %s: %s", path, err)
        return

    if not isinstance(bans, dict):
        return

    for ip_str, ip_info in bans.items():
        banned_at = None
        try:
            ip_info = SCHEMA_IP_BAN_ENTRY(ip_info or {})
            banned_at = ip_info.get("banned_at")
        except vol.Invalid:
            pass
        await coordinator.async_import_ban(ip_str, banned_at=banned_at)

    coordinator.sync_ban_timestamps_from_ip_bans()
    coordinator.async_set_updated_data(coordinator.attacks)
    coordinator.async_update_listeners()
