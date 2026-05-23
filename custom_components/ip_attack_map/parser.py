"""Parse Home Assistant HTTP ban notification messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import ip_address

# Login attempt or request with invalid authentication from host (1.2.3.4).
_LOGIN_RE = re.compile(
    r"invalid authentication from\s+(.+?)\s+\(([^)]+)\)",
    re.IGNORECASE,
)

# Too many login attempts from 1.2.3.4
_BAN_RE = re.compile(
    r"Too many login attempts from\s+(\S+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ParsedAttack:
    """Parsed attack data from a notification or ban file."""

    ip: str
    hostname: str | None = None
    banned: bool = False


def parse_login_message(message: str) -> ParsedAttack | None:
    """Parse http-login persistent notification message."""
    match = _LOGIN_RE.search(message)
    if not match:
        return None
    hostname = match.group(1).strip()
    ip_str = match.group(2).strip()
    try:
        ip_address(ip_str)
    except ValueError:
        return None
    if hostname == ip_str:
        hostname = None
    return ParsedAttack(ip=ip_str, hostname=hostname, banned=False)


def parse_ban_message(message: str) -> ParsedAttack | None:
    """Parse ip-ban persistent notification message."""
    match = _BAN_RE.search(message)
    if not match:
        return None
    ip_str = match.group(1).strip()
    try:
        ip_address(ip_str)
    except ValueError:
        return None
    return ParsedAttack(ip=ip_str, hostname=None, banned=True)
