"""SSRF guard for website ingestion while the app is exposed through a tunnel.

Every URL the crawler touches (start URL, robots.txt, each page, each redirect hop) is checked:
- http/https only, no user:password@ in the URL;
- the host is RESOLVED and every address must be globally routable: loopback, private (10/8, 172.16/12, 192.168/16),
  link-local incl. cloud metadata 169.254.169.254, CGNAT 100.64/10, unspecified 0.0.0.0, multicast, reserved,
  and IPv4-mapped / numeric forms of those (http://2130706433/, http://0x7f.1/) are refused;
- one exception: the app's OWN bundled demo sites (exact prefix <self>/demo-sites/ after path normalization).
DNS-rebinding between check and connect is not fully preventable here; ingestion is admin-only while exposed.
"""
from __future__ import annotations

import ipaddress
import posixpath
import socket
from urllib.parse import urlparse, urlunparse


class Blocked(Exception):
    pass


def canonical(url: str) -> str:
    p = urlparse(url)
    path = posixpath.normpath(p.path or "/") + ("/" if (p.path or "/").endswith("/") and p.path not in ("", "/") else "")
    if path == "//":
        path = "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", p.query, ""))


def _ip_ok(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def make_guard(allowed_private_prefixes: tuple[str, ...] = ()):
    prefixes = tuple(canonical(p) for p in allowed_private_prefixes)

    def guard(url: str) -> None:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            raise Blocked("only http(s) URLs")
        if "@" in p.netloc:
            raise Blocked("credentials in URLs are not allowed")
        host = p.hostname
        if not host:
            raise Blocked("URL has no host")
        if prefixes and canonical(url).startswith(prefixes):
            return
        try:
            infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            raise Blocked(f"cannot resolve {host}")
        for info in infos:
            addr = info[4][0].split("%")[0]
            if not _ip_ok(ipaddress.ip_address(addr)):
                raise Blocked(f"blocked: {host} resolves to a private/local address ({addr})")
    return guard
