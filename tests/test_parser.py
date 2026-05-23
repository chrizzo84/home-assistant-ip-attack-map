"""Tests for notification message parsing."""

from tests.conftest import load_module

parser = load_module("parser")
parse_ban_message = parser.parse_ban_message
parse_login_message = parser.parse_login_message


def test_parse_login_message_with_hostname() -> None:
    """Parse standard http-login notification."""
    message = (
        "Login attempt or request with invalid authentication from "
        "evil.example.com (203.0.113.50). See the log for details."
    )
    result = parse_login_message(message)
    assert result is not None
    assert result.ip == "203.0.113.50"
    assert result.hostname == "evil.example.com"
    assert result.banned is False


def test_parse_login_message_ip_only_hostname() -> None:
    """Parse login when hostname equals IP."""
    message = (
        "Login attempt or request with invalid authentication from "
        "192.168.1.20 (192.168.1.20). See the log for details."
    )
    result = parse_login_message(message)
    assert result is not None
    assert result.ip == "192.168.1.20"
    assert result.hostname is None


def test_parse_login_message_ipv6() -> None:
    """Parse login with IPv6 address."""
    message = (
        "Login attempt or request with invalid authentication from "
        "host.example (2001:db8::1). See the log for details."
    )
    result = parse_login_message(message)
    assert result is not None
    assert result.ip == "2001:db8::1"


def test_parse_ban_message() -> None:
    """Parse ip-ban notification."""
    message = "Too many login attempts from 203.0.113.99"
    result = parse_ban_message(message)
    assert result is not None
    assert result.ip == "203.0.113.99"
    assert result.banned is True


def test_parse_invalid_messages() -> None:
    """Return None for unrelated text."""
    assert parse_login_message("Something else") is None
    assert parse_ban_message("No ban here") is None
