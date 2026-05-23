"""Utility helpers for IP Attack Map."""

from __future__ import annotations

from ipaddress import ip_address, ip_network


def is_private_ip(ip_str: str) -> bool:
    """Return True if the IP is private, loopback, or link-local."""
    try:
        addr = ip_address(ip_str)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
    )


def is_whitelisted(ip_str: str, whitelist: list[str]) -> bool:
    """Return True if the IP matches any whitelist entry (host or CIDR)."""
    if not whitelist:
        return False
    try:
        addr = ip_address(ip_str)
    except ValueError:
        return False
    for entry in whitelist:
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ip_network(entry, strict=False):
                    return True
            elif addr == ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def should_track_ip(
    ip_str: str,
    *,
    whitelist: list[str],
    hide_private_ips: bool,
) -> bool:
    """Return True if this IP should be recorded."""
    if is_whitelisted(ip_str, whitelist):
        return False
    if hide_private_ips and is_private_ip(ip_str):
        return False
    return True


def should_show_on_map(
    ip_str: str,
    *,
    whitelist: list[str],
    hide_private_ips: bool,
    only_external_on_map: bool,
) -> bool:
    """Return True if a geo_location entity should exist for this IP."""
    if not should_track_ip(
        ip_str,
        whitelist=whitelist,
        hide_private_ips=hide_private_ips,
    ):
        return False
    if only_external_on_map and is_private_ip(ip_str):
        return False
    return True
