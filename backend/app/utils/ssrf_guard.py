import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private / reserved IP ranges to block
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local / metadata
    ipaddress.ip_network("100.64.0.0/10"),   # Shared address space
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "169.254.169.254",  # AWS / GCP metadata
    "192.168.0.1",
}

_METADATA_PATHS = [
    "/latest/meta-data",
    "/computeMetadata",
    "/openstack/2012-08-10",
]


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                return True
        return False
    except ValueError:
        return True  # malformed → block


def is_safe_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Returns (True, None) if URL is safe to crawl.
    Returns (False, reason) if URL should be blocked.
    """
    if not url:
        return False, "Empty URL"

    parsed = urlparse(url)

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        return False, f"Disallowed scheme: {parsed.scheme!r}"

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Blocked hostnames
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return False, f"Blocked hostname: {hostname}"

    # Metadata path check
    path = parsed.path.lower()
    for meta_path in _METADATA_PATHS:
        if path.startswith(meta_path):
            return False, f"Metadata endpoint blocked: {path}"

    # DNS resolution + IP check
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            ip_str = info[4][0]
            if _is_private_ip(ip_str):
                return False, f"Resolved to private IP: {ip_str}"
    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e}"
    except Exception as e:
        return False, f"SSRF check error: {e}"

    return True, None


def assert_safe_url(url: str) -> None:
    """Raise ValueError if URL is not safe."""
    safe, reason = is_safe_url(url)
    if not safe:
        raise ValueError(f"SSRF guard blocked URL '{url}': {reason}")
