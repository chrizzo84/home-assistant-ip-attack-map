"""Tests for IP utility helpers."""

from tests.conftest import load_module

util = load_module("util")
is_private_ip = util.is_private_ip
is_whitelisted = util.is_whitelisted
should_show_on_map = util.should_show_on_map
should_track_ip = util.should_track_ip


def test_is_private_ip() -> None:
    """Detect private and public addresses."""
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("10.0.0.5") is True
    assert is_private_ip("8.8.8.8") is False


def test_is_whitelisted() -> None:
    """Match whitelist entries."""
    whitelist = ["192.168.0.0/16", "203.0.113.5"]
    assert is_whitelisted("192.168.50.10", whitelist) is True
    assert is_whitelisted("203.0.113.5", whitelist) is True
    assert is_whitelisted("203.0.113.6", whitelist) is False


def test_should_track_ip_respects_whitelist() -> None:
    """Do not track whitelisted IPs."""
    assert (
        should_track_ip(
            "192.168.1.5",
            whitelist=["192.168.0.0/16"],
            hide_private_ips=True,
        )
        is False
    )


def test_should_track_ip_private_hidden() -> None:
    """Hide private IPs when configured."""
    assert (
        should_track_ip(
            "10.0.0.1",
            whitelist=[],
            hide_private_ips=True,
        )
        is False
    )


def test_should_show_on_map_external_only() -> None:
    """External-only map hides private even if tracked."""
    assert (
        should_show_on_map(
            "192.168.1.1",
            whitelist=[],
            hide_private_ips=False,
            only_external_on_map=True,
        )
        is False
    )
    assert (
        should_show_on_map(
            "8.8.8.8",
            whitelist=[],
            hide_private_ips=True,
            only_external_on_map=True,
        )
        is True
    )
