"""Sensor platform for IP Attack Map."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IpAttackMapCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: IpAttackMapCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AttemptsTodaySensor(coordinator, entry),
            ActiveBansSensor(coordinator, entry),
            LastAttackerSensor(coordinator, entry),
            TrackedIpsSensor(coordinator, entry),
        ]
    )


class IpAttackMapSensor(CoordinatorEntity[IpAttackMapCoordinator], SensorEntity):
    """Base sensor for IP Attack Map."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self) -> DeviceInfo:
        """Link sensors to the config entry device (stable entity_id prefix)."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="IP Attack Map",
        )


class AttemptsTodaySensor(IpAttackMapSensor):
    """Count failed login attempts today."""

    _attr_name = "Attempts today"
    _attr_icon = "mdi:shield-alert"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: IpAttackMapCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_attempts_today"

    @property
    def native_value(self) -> int:
        """Return attempts today."""
        return self.coordinator.attempts_today()


class ActiveBansSensor(IpAttackMapSensor):
    """Count active banned IPs in registry."""

    _attr_name = "Active bans"
    _attr_icon = "mdi:ip-network"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: IpAttackMapCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_active_bans"

    @property
    def native_value(self) -> int:
        """Return ban count."""
        return self.coordinator.active_bans_count()


class LastAttackerSensor(IpAttackMapSensor):
    """Most recent attacker summary."""

    _attr_name = "Last attacker"
    _attr_icon = "mdi:map-marker-alert"

    def __init__(
        self, coordinator: IpAttackMapCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_attacker"

    @property
    def native_value(self) -> str | None:
        """Return last attacker label."""
        return self.coordinator.last_attacker_label()


class TrackedIpsSensor(IpAttackMapSensor):
    """Number of tracked attacking IPs."""

    _attr_name = "Tracked IPs"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: IpAttackMapCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_tracked_ips"

    @property
    def native_value(self) -> int:
        """Return tracked IP count."""
        return len(self.coordinator.attacks)
