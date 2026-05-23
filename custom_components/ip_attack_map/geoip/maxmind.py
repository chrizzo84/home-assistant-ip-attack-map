"""MaxMind GeoLite2 local database provider."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from geoip2.database import Reader
from geoip2.errors import AddressNotFoundError

from .base import GeoIpProvider, GeoResult

_LOGGER = logging.getLogger(__name__)


class MaxMindGeoIpProvider(GeoIpProvider):
    """GeoIP lookups using a local MaxMind GeoLite2 database."""

    def __init__(self, db_path: str) -> None:
        """Initialize with path to .mmdb file."""
        self._db_path = Path(db_path)
        self._reader: Reader | None = None

    def _get_reader(self) -> Reader:
        if self._reader is None:
            if not self._db_path.is_file():
                raise FileNotFoundError(
                    f"MaxMind database not found: {self._db_path}"
                )
            self._reader = Reader(str(self._db_path))
        return self._reader

    def lookup_sync(self, ip: str) -> GeoResult | None:
        """Synchronous lookup for use in executor."""
        try:
            response = self._get_reader().city(ip)
        except AddressNotFoundError:
            return None
        except FileNotFoundError:
            _LOGGER.error("MaxMind database missing at %s", self._db_path)
            return None
        except OSError as err:
            _LOGGER.warning("MaxMind lookup failed for %s: %s", ip, err)
            return None

        if response.location.latitude is None or response.location.longitude is None:
            return None

        country = response.country.name or response.country.iso_code
        region = None
        if response.subdivisions:
            region = response.subdivisions.most_specific.name

        return GeoResult(
            latitude=response.location.latitude,
            longitude=response.location.longitude,
            country=country,
            city=response.city.name,
            region=region,
            org=response.traits.organization,
        )

    async def async_lookup(self, ip: str) -> GeoResult | None:
        """Look up IP in the local MaxMind database."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.lookup_sync, ip)

    async def async_close(self) -> None:
        """Close the database reader."""
        if self._reader is not None:
            self._reader.close()
            self._reader = None
