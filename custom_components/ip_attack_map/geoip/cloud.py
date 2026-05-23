"""Cloud GeoIP providers (ip-api.com, ipinfo.io)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CLOUD_MIN_INTERVAL_SECONDS,
    CLOUD_PROVIDER_IP_API,
    CLOUD_PROVIDER_IPINFO,
)
from .base import GeoIpProvider, GeoResult

_LOGGER = logging.getLogger(__name__)


class CloudGeoIpProvider(GeoIpProvider):
    """GeoIP lookups via cloud HTTP APIs with rate limiting."""

    def __init__(
        self,
        hass,
        *,
        provider: str,
        api_key: str | None = None,
    ) -> None:
        """Initialize cloud provider."""
        self._hass = hass
        self._provider = provider
        self._api_key = api_key
        self._lock = asyncio.Lock()
        self._last_lookup: datetime | None = None

    async def _rate_limit(self) -> None:
        """Enforce minimum interval between cloud lookups."""
        async with self._lock:
            if self._last_lookup is not None:
                elapsed = datetime.utcnow() - self._last_lookup
                wait = CLOUD_MIN_INTERVAL_SECONDS - elapsed.total_seconds()
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_lookup = datetime.utcnow()

    async def async_lookup(self, ip: str) -> GeoResult | None:
        """Look up IP via configured cloud API."""
        await self._rate_limit()
        session = async_get_clientsession(self._hass)
        if self._provider == CLOUD_PROVIDER_IPINFO:
            return await self._lookup_ipinfo(session, ip)
        return await self._lookup_ip_api(session, ip)

    async def _lookup_ip_api(
        self, session: aiohttp.ClientSession, ip: str
    ) -> GeoResult | None:
        url = f"http://ip-api.com/json/{ip}"
        params = {"fields": "status,message,country,regionName,city,lat,lon,org"}
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("ip-api lookup failed for %s: %s", ip, err)
            return None

        if data.get("status") != "success":
            _LOGGER.debug(
                "ip-api lookup unsuccessful for %s: %s",
                ip,
                data.get("message"),
            )
            return None

        lat, lon = data.get("lat"), data.get("lon")
        if lat is None or lon is None:
            return None

        return GeoResult(
            latitude=float(lat),
            longitude=float(lon),
            country=data.get("country"),
            city=data.get("city"),
            region=data.get("regionName"),
            org=data.get("org"),
        )

    async def _lookup_ipinfo(
        self, session: aiohttp.ClientSession, ip: str
    ) -> GeoResult | None:
        url = f"https://ipinfo.io/{ip}/json"
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("ipinfo lookup failed for %s: %s", ip, err)
            return None

        loc = data.get("loc")
        if not loc or "," not in loc:
            return None
        lat_str, lon_str = loc.split(",", 1)
        try:
            latitude = float(lat_str)
            longitude = float(lon_str)
        except ValueError:
            return None

        return GeoResult(
            latitude=latitude,
            longitude=longitude,
            country=data.get("country"),
            city=data.get("city"),
            region=data.get("region"),
            org=data.get("org"),
        )
