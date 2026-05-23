"""Tests for Lovelace card URL helpers."""

import pytest

from custom_components.ip_attack_map.frontend import (
    CARD_API_URL,
    _async_maybe_await,
    _is_our_card_resource,
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
    assert url.startswith(CARD_API_URL)
    assert "v=0.2.2" in url


def test_url_path_strips_query() -> None:
    assert _url_path("/api/foo.js?v=1") == "/api/foo.js"


def test_url_version() -> None:
    assert _url_version("/api/ip_attack_map/card/ip-attack-map-card.js?v=0.2.1") == "0.2.1"
    assert _url_version("/local/foo.js") is None


def test_is_our_card_resource() -> None:
    assert _is_our_card_resource(CARD_API_URL)
    assert _is_our_card_resource(f"{CARD_API_URL}?v=1")
    assert _is_our_card_resource("/local/ip_attack_map/ip-attack-map-card.js") is False
