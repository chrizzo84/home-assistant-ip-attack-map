"""Tests for Lovelace card URL helpers."""

import pytest

from custom_components.ip_attack_map.const import INTEGRATION_VERSION
from custom_components.ip_attack_map.frontend import (
    CARD_API_URL,
    LOCAL_CARD_URL,
    _async_maybe_await,
    _is_our_card_resource,
    _resource_is_current,
    _url_path,
    _url_version,
    card_module_url,
)


@pytest.mark.asyncio
async def test_async_maybe_await_plain_value() -> None:
    assert await _async_maybe_await([{"id": "1"}]) == [{"id": "1"}]


@pytest.mark.asyncio
async def test_async_maybe_await_coroutine() -> None:
    async def _coro() -> str:
        return "ok"

    assert await _async_maybe_await(_coro()) == "ok"


def test_card_module_url_includes_version() -> None:
    url = card_module_url()
    assert url.startswith(LOCAL_CARD_URL)
    assert f"v={INTEGRATION_VERSION}" in url


def test_url_path_strips_query() -> None:
    assert _url_path("/api/foo.js?v=1") == "/api/foo.js"


def test_url_version() -> None:
    assert _url_version("/api/ip_attack_map/card/ip-attack-map-card.js?v=0.2.1") == "0.2.1"
    assert _url_version("/local/foo.js") is None


def test_is_our_card_resource() -> None:
    assert _is_our_card_resource(CARD_API_URL)
    assert _is_our_card_resource(f"{LOCAL_CARD_URL}?v=1")
    # Common manual typo (underscore instead of hyphen in filename).
    assert _is_our_card_resource("/local/ip_attack_map/ip_attack_map-card.js?v=0.2.5")
    assert _is_our_card_resource("/other/card.js") is False


def test_resource_is_current() -> None:
    assert _resource_is_current(f"{CARD_API_URL}?v={INTEGRATION_VERSION}") is True
    assert _resource_is_current(f"{LOCAL_CARD_URL}?v={INTEGRATION_VERSION}") is False


def test_card_module_url_uses_local_path() -> None:
    from custom_components.ip_attack_map.frontend import card_module_url

    assert card_module_url().startswith(LOCAL_CARD_URL)


def test_extra_module_url_matches_lovelace_resource() -> None:
    from custom_components.ip_attack_map.frontend import (
        card_extra_module_url,
        card_module_url,
    )

    assert card_extra_module_url() == card_module_url()
