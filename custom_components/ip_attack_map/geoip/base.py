"""GeoIP provider base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GeoResult:
    """Geolocation lookup result."""

    latitude: float
    longitude: float
    country: str | None = None
    city: str | None = None
    region: str | None = None
    org: str | None = None


class GeoIpProvider(ABC):
    """Abstract GeoIP lookup provider."""

    @abstractmethod
    async def async_lookup(self, ip: str) -> GeoResult | None:
        """Look up geolocation for an IP address."""

    async def async_close(self) -> None:
        """Release resources."""
