"""Geo location platform for IP Attack Map."""

from __future__ import annotations

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ATTEMPT_COUNT,
    ATTR_BANNED,
    ATTR_BANNED_AT,
    ATTR_CITY,
    ATTR_COUNTRY,
    ATTR_HOSTNAME,
    ATTR_IP,
    ATTR_LAST_SEEN,
    ATTR_ORG,
    ATTR_REGION,
    ATTR_USER_AGENT,
    DOMAIN,
    SOURCE,
)
from .coordinator import IpAttackMapCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up geo_location entities from config entry."""
    coordinator: IpAttackMapCoordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _add_entity_for_ip(ip: str) -> None:
        if ip in coordinator.entity_platform_entities:
            return
        entity = AttackGeoLocation(coordinator, ip)
        coordinator.entity_platform_entities.add(ip)
        async_add_entities([entity], update_before_add=True)

    coordinator.register_add_entity_callback(_add_entity_for_ip)

    entities = [
        AttackGeoLocation(coordinator, ip)
        for ip in coordinator.get_visible_attacks()
    ]
    coordinator.entity_platform_entities = {e._ip for e in entities}
    async_add_entities(entities)


class AttackGeoLocation(GeolocationEvent):
    """Geolocation entity for a banned or attacking IP."""

    _attr_source = SOURCE
    _attr_icon = "mdi:shield-alert"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: IpAttackMapCoordinator, ip: str) -> None:
        """Initialize entity."""
        self.coordinator = coordinator
        self._ip = ip
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{ip}"
        self._attr_name = self._build_name()
        super().__init__()
        self._update_from_record()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _build_name(self) -> str:
        record = self.coordinator.get_record(self._ip)
        if record and record.hostname and record.hostname != self._ip:
            return f"{record.hostname} ({self._ip})"
        return self._ip

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated attack data."""
        if self._ip not in self.coordinator.get_visible_attacks():
            return
        self._update_from_record()
        self.async_write_ha_state()

    def _update_from_record(self) -> None:
        record = self.coordinator.get_record(self._ip)
        if record is None:
            return
        self._attr_name = self._build_name()
        self._attr_latitude = record.latitude
        self._attr_longitude = record.longitude
        self._attr_extra_state_attributes = {
            ATTR_IP: record.ip,
            ATTR_HOSTNAME: record.hostname,
            ATTR_COUNTRY: record.country,
            ATTR_CITY: record.city,
            ATTR_REGION: record.region,
            ATTR_ORG: record.org,
            ATTR_ATTEMPT_COUNT: record.attempt_count,
            ATTR_BANNED: record.banned,
            ATTR_BANNED_AT: record.banned_at.isoformat() if record.banned_at else None,
            ATTR_LAST_SEEN: record.last_seen.isoformat(),
            ATTR_USER_AGENT: record.user_agent,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self._ip in self.coordinator.attacks
            and self._ip in self.coordinator.get_visible_attacks()
            and self.coordinator.get_record(self._ip) is not None
            and self.coordinator.get_record(self._ip).latitude is not None
        )
