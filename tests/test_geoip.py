"""Tests for GeoIP providers."""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
from unittest.mock import MagicMock

from tests.conftest import INTEGRATION, load_module

# Stub geoip2 before loading maxmind
_geoip2 = ModuleType("geoip2")
_geoip2_database = ModuleType("geoip2.database")
_geoip2_errors = ModuleType("geoip2.errors")


class AddressNotFoundError(Exception):
    """Stub exception."""


_geoip2_errors.AddressNotFoundError = AddressNotFoundError
_geoip2_database.Reader = MagicMock
_geoip2.database = _geoip2_database
_geoip2.errors = _geoip2_errors
sys.modules["geoip2"] = _geoip2
sys.modules["geoip2.database"] = _geoip2_database
sys.modules["geoip2.errors"] = _geoip2_errors

base = load_module("base", str(INTEGRATION / "geoip" / "base.py"))
geoip_pkg = ModuleType("ip_attack_map.geoip")
geoip_pkg.base = base
sys.modules["ip_attack_map.geoip"] = geoip_pkg

maxmind_path = INTEGRATION / "geoip" / "maxmind.py"
spec = importlib.util.spec_from_file_location(
    "ip_attack_map.geoip.maxmind",
    maxmind_path,
    submodule_search_locations=[str(INTEGRATION / "geoip")],
)
assert spec and spec.loader
maxmind = importlib.util.module_from_spec(spec)
sys.modules["ip_attack_map.geoip.maxmind"] = maxmind
geoip_pkg.maxmind = maxmind
spec.loader.exec_module(maxmind)

MaxMindGeoIpProvider = maxmind.MaxMindGeoIpProvider


def test_maxmind_missing_database() -> None:
    """Return None when database file is missing."""
    provider = MaxMindGeoIpProvider("/nonexistent/GeoLite2-City.mmdb")
    assert provider.lookup_sync("203.0.113.1") is None


def test_maxmind_lookup_sync_success() -> None:
    """Parse MaxMind response into GeoResult."""
    provider = MaxMindGeoIpProvider("/tmp/GeoLite2-City.mmdb")
    mock_response = MagicMock()
    mock_response.location.latitude = 52.52
    mock_response.location.longitude = 13.405
    mock_response.country.name = "Germany"
    mock_response.country.iso_code = "DE"
    mock_response.city.name = "Berlin"
    mock_response.subdivisions.most_specific.name = "Berlin"
    mock_response.traits.organization = "Example ISP"

    mock_reader = MagicMock()
    mock_reader.city.return_value = mock_response
    provider._reader = mock_reader

    result = provider.lookup_sync("203.0.113.1")
    assert result is not None
    assert result.latitude == 52.52
    assert result.longitude == 13.405
    assert result.country == "Germany"
    assert result.city == "Berlin"
