"""web_fetch adapter — GET-only HTTP with an SSRF guard (Phase 10.0.4).

Read-class. `_assert_safe` blocks non-http(s) schemes and any host that resolves
to a loopback / private / link-local / reserved / multicast address (SSRF,
T-10.0.4-04). Responses are size-capped and time-bounded. stdlib urllib only — no
requests/httpx (anti-bloat).

Known v0 limitation: a DNS-rebinding TOCTOU exists between `_assert_safe`'s
resolution and urllib's own resolution at connect time. Documented, not addressed
in v0 — the approval gate + read-only default bound the blast radius.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.request
from typing import Any
from urllib.parse import urlparse

from atlas_core.schemas.tool import ToolResult

_TOOL = "web_fetch"
_MAX_BYTES = 5 * 1024 * 1024
_TIMEOUT = 10
_BLOCKED_HOSTS = {"localhost", "0.0.0.0", "::1", ""}


class WebFetchError(ValueError):
    """An unsafe target or transport rejected before/while fetching."""


def _assert_safe(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebFetchError(f"unsupported scheme: {parsed.scheme!r} (http/https only)")
    host = (parsed.hostname or "").lower()
    if host in _BLOCKED_HOSTS:
        raise WebFetchError(f"blocked host: {host!r}")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise WebFetchError(f"cannot resolve {host!r}: {exc}") from exc
    for info in infos:
        ip = info[4][0]
        # Strip any IPv6 scope id (e.g. fe80::1%eth0).
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise WebFetchError(f"blocked non-public address {ip} for host {host!r}")


def _read_capped(resp: Any, cap: int) -> bytes:
    """Read at most cap bytes; raise if the body exceeds the cap."""
    data = resp.read(cap + 1)
    if data is not None and len(data) > cap:
        raise ValueError(f"response exceeds size cap of {cap} bytes")
    return data or b""


def run(args: dict, ctx: Any) -> ToolResult:
    args = args or {}
    url = args.get("url", "")
    cap = int(args.get("max_bytes", _MAX_BYTES))
    try:
        _assert_safe(url)
    except (WebFetchError, ValueError) as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = _read_capped(resp, cap)
    except ValueError as exc:  # size cap
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - any network/HTTP error is an honest failure
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    return ToolResult(tool_name=_TOOL, ok=True, output=body.decode("utf-8", errors="replace"))
