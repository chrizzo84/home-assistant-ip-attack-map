"""Data coordinator for IP Attack Map."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLOUD_API_KEY,
    CONF_CLOUD_PROVIDER,
    CONF_GEO_PROVIDER,
    CONF_HIDE_PRIVATE_IPS,
    CONF_MAXMIND_DB_PATH,
    CONF_ONLY_EXTERNAL_ON_MAP,
    CONF_RETENTION_DAYS,
    CONF_WHITELIST,
    CLOUD_PROVIDER_IP_API,
    DOMAIN,
    GEO_PROVIDER_CLOUD,
    GEO_PROVIDER_MAXMIND,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .geoip import CloudGeoIpProvider, GeoIpProvider, GeoResult, MaxMindGeoIpProvider
from .parser import ParsedAttack
from .util import is_private_ip, should_show_on_map, should_track_ip

_LOGGER = logging.getLogger(__name__)


@dataclass
class AttackRecord:
    """Stored attack information for one IP."""

    ip: str
    hostname: str | None = None
    attempt_count: int = 0
    banned: bool = False
    banned_at: datetime | None = None
    last_seen: datetime = field(default_factory=dt_util.utcnow)
    latitude: float | None = None
    longitude: float | None = None
    country: str | None = None
    city: str | None = None
    region: str | None = None
    org: str | None = None
    user_agent: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage cache."""
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "attempt_count": self.attempt_count,
            "banned": self.banned,
            "banned_at": self.banned_at.isoformat() if self.banned_at else None,
            "last_seen": self.last_seen.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "country": self.country,
            "city": self.city,
            "region": self.region,
            "org": self.org,
            "user_agent": self.user_agent,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttackRecord:
        """Deserialize from storage cache."""
        banned_at = data.get("banned_at")
        last_seen = data.get("last_seen")
        return cls(
            ip=data["ip"],
            hostname=data.get("hostname"),
            attempt_count=int(data.get("attempt_count", 0)),
            banned=bool(data.get("banned")),
            banned_at=dt_util.parse_datetime(banned_at) if banned_at else None,
            last_seen=dt_util.parse_datetime(last_seen) or dt_util.utcnow(),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            country=data.get("country"),
            city=data.get("city"),
            region=data.get("region"),
            org=data.get("org"),
            user_agent=data.get("user_agent"),
        )


class IpAttackMapCoordinator(DataUpdateCoordinator[dict[str, AttackRecord]]):
    """Coordinate attack registry, GeoIP lookups, and entity updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self.attacks: dict[str, AttackRecord] = {}
        self._geo_cache: dict[str, GeoResult] = {}
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self._geo_provider: GeoIpProvider | None = None
        self._add_entity_callbacks: list[Callable[[str], None]] = []
        self.entity_platform_entities: set[str] = set()
        self._attempts_today = 0
        self._attempts_today_date = dt_util.now().date()
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=1),
        )

    @property
    def whitelist(self) -> list[str]:
        """Configured IP whitelist."""
        return self.entry.data.get(CONF_WHITELIST, [])

    @property
    def hide_private_ips(self) -> bool:
        """Whether private IPs are hidden from tracking."""
        return self.entry.data.get(CONF_HIDE_PRIVATE_IPS, True)

    @property
    def only_external_on_map(self) -> bool:
        """Whether only external IPs appear on the map."""
        return self.entry.data.get(CONF_ONLY_EXTERNAL_ON_MAP, True)

    @property
    def retention_days(self) -> int:
        """Days to retain attack records."""
        return int(self.entry.data.get(CONF_RETENTION_DAYS, 30))

    def register_add_entity_callback(self, callback_fn: Callable[[str], None]) -> None:
        """Register callback when a new IP needs a geo_location entity."""
        self._add_entity_callbacks.append(callback_fn)

    def _notify_new_entity(self, ip: str) -> None:
        for callback_fn in self._add_entity_callbacks:
            callback_fn(ip)

    def _create_geo_provider(self) -> GeoIpProvider:
        provider_type = self.entry.data.get(CONF_GEO_PROVIDER, GEO_PROVIDER_MAXMIND)
        if provider_type == GEO_PROVIDER_CLOUD:
            return CloudGeoIpProvider(
                self.hass,
                provider=self.entry.data.get(
                    CONF_CLOUD_PROVIDER, CLOUD_PROVIDER_IP_API
                ),
                api_key=self.entry.data.get(CONF_CLOUD_API_KEY),
            )
        return MaxMindGeoIpProvider(
            self.entry.data[CONF_MAXMIND_DB_PATH],
        )

    async def async_setup(self) -> None:
        """Load cache and initialize GeoIP provider."""
        cached = await self._store.async_load()
        if cached and isinstance(cached.get("attacks"), dict):
            for ip, data in cached["attacks"].items():
                try:
                    self.attacks[ip] = AttackRecord.from_dict(data)
                except (KeyError, TypeError, ValueError):
                    continue
        for ip, record in list(self.attacks.items()):
            if record.latitude is not None and record.longitude is not None:
                self._geo_cache[ip] = GeoResult(
                    latitude=record.latitude,
                    longitude=record.longitude,
                    country=record.country,
                    city=record.city,
                    region=record.region,
                    org=record.org,
                )
        self._geo_provider = self._create_geo_provider()

    async def async_shutdown(self) -> None:
        """Release GeoIP provider resources."""
        if self._geo_provider is not None:
            await self._geo_provider.async_close()

    async def _async_update_data(self) -> dict[str, AttackRecord]:
        """Periodic cleanup of stale records."""
        await self._apply_retention()
        await self._persist_cache()
        return self.attacks

    async def _persist_cache(self) -> None:
        """Save attack registry and geo cache to storage."""
        await self._store.async_save(
            {
                "attacks": {ip: rec.as_dict() for ip, rec in self.attacks.items()},
            }
        )

    async def _apply_retention(self) -> None:
        """Remove attack records older than retention period."""
        cutoff = dt_util.utcnow() - timedelta(days=self.retention_days)
        removed: list[str] = []
        for ip, record in list(self.attacks.items()):
            if record.last_seen < cutoff:
                removed.append(ip)
                del self.attacks[ip]
                self._geo_cache.pop(ip, None)
        if removed:
            self.async_update_listeners()

    async def async_lookup_geo(self, ip: str) -> GeoResult | None:
        """Look up geolocation with in-memory cache."""
        if ip in self._geo_cache:
            return self._geo_cache[ip]
        if self._geo_provider is None:
            return None
        if is_private_ip(ip):
            return None
        result = await self._geo_provider.async_lookup(ip)
        if result is not None:
            self._geo_cache[ip] = result
        return result

    def get_visible_attacks(self) -> dict[str, AttackRecord]:
        """Return attacks that should appear on the map."""
        visible: dict[str, AttackRecord] = {}
        for ip, record in self.attacks.items():
            if should_show_on_map(
                ip,
                whitelist=self.whitelist,
                hide_private_ips=self.hide_private_ips,
                only_external_on_map=self.only_external_on_map,
            ):
                visible[ip] = record
        return visible

    def attempts_today(self) -> int:
        """Count login attempts since local midnight."""
        today = dt_util.now().date()
        if today != self._attempts_today_date:
            self._attempts_today = 0
            self._attempts_today_date = today
        return self._attempts_today

    def active_bans_count(self) -> int:
        """Count currently banned IPs in registry."""
        return sum(1 for record in self.attacks.values() if record.banned)

    def last_attacker_label(self) -> str | None:
        """Human-readable label for most recent attack."""
        if not self.attacks:
            return None
        latest = max(self.attacks.values(), key=lambda r: r.last_seen)
        parts = [latest.ip]
        if latest.city:
            parts.append(latest.city)
        if latest.country:
            parts.append(latest.country)
        return " · ".join(parts)

    async def async_record_attack(
        self,
        parsed: ParsedAttack,
        *,
        user_agent: str | None = None,
    ) -> None:
        """Record or update an attack from parsed notification data."""
        ip = parsed.ip
        if not should_track_ip(
            ip,
            whitelist=self.whitelist,
            hide_private_ips=self.hide_private_ips,
        ):
            return

        now = dt_util.utcnow()
        is_new = ip not in self.attacks
        if is_new:
            record = AttackRecord(ip=ip, hostname=parsed.hostname)
            self.attacks[ip] = record
        else:
            record = self.attacks[ip]

        record.attempt_count += 1
        record.last_seen = now
        today = dt_util.now().date()
        if today != self._attempts_today_date:
            self._attempts_today = 0
            self._attempts_today_date = today
        self._attempts_today += 1
        if parsed.hostname:
            record.hostname = parsed.hostname
        if parsed.banned:
            record.banned = True
            record.banned_at = record.banned_at or now
        if user_agent:
            record.user_agent = user_agent[:256]

        show_on_map = should_show_on_map(
            ip,
            whitelist=self.whitelist,
            hide_private_ips=self.hide_private_ips,
            only_external_on_map=self.only_external_on_map,
        )
        if show_on_map and record.latitude is None:
            geo = await self.async_lookup_geo(ip)
            if geo is not None:
                record.latitude = geo.latitude
                record.longitude = geo.longitude
                record.country = geo.country
                record.city = geo.city
                record.region = geo.region
                record.org = geo.org

        if is_new and show_on_map:
            self._notify_new_entity(ip)

        self.async_set_updated_data(self.attacks)
        await self._persist_cache()

    async def async_import_ban(
        self, ip: str, banned_at: datetime | None = None,
    ) -> None:
        """Import a banned IP from ip_bans.yaml without counting as new attempt."""
        if not should_track_ip(
            ip,
            whitelist=self.whitelist,
            hide_private_ips=self.hide_private_ips,
        ):
            return

        is_new = ip not in self.attacks
        if is_new:
            self.attacks[ip] = AttackRecord(
                ip=ip,
                banned=True,
                banned_at=banned_at or dt_util.utcnow(),
                attempt_count=0,
            )
        else:
            record = self.attacks[ip]
            record.banned = True
            record.banned_at = banned_at or record.banned_at or dt_util.utcnow()

        show_on_map = should_show_on_map(
            ip,
            whitelist=self.whitelist,
            hide_private_ips=self.hide_private_ips,
            only_external_on_map=self.only_external_on_map,
        )
        record = self.attacks[ip]
        if show_on_map and record.latitude is None:
            geo = await self.async_lookup_geo(ip)
            if geo is not None:
                record.latitude = geo.latitude
                record.longitude = geo.longitude
                record.country = geo.country
                record.city = geo.city
                record.region = geo.region
                record.org = geo.org

        if is_new and show_on_map:
            self._notify_new_entity(ip)

        self.async_set_updated_data(self.attacks)
        await self._persist_cache()

    @callback
    def get_record(self, ip: str) -> AttackRecord | None:
        """Return attack record for an IP."""
        return self.attacks.get(ip)
