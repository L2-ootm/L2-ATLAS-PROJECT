"""webhook_notify adapter — POST a JSON payload to an outbound webhook (Phase 10.0.4).

Write-class (approval-gated by the chokepoint). Reuses web_fetch's `_assert_safe`
SSRF guard before sending (T-10.0.4-04). stdlib urllib only. Any token in the URL
or headers is redacted at the audit boundary by tool_service, never here.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

from atlas_core.schemas.tool import ToolResult

from atlas_runtime.tools.adapters.web_fetch import WebFetchError, _assert_safe

_TOOL = "webhook_notify"
_TIMEOUT = 10


def run(args: dict, ctx: Any) -> ToolResult:
    args = args or {}
    url = args.get("url", "")
    payload = args.get("payload", args.get("body", {}))
    headers = args.get("headers", {}) or {}
    try:
        _assert_safe(url)
    except (WebFetchError, ValueError) as exc:
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(str(key), str(value))
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            out = resp.read(65536).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - honest failure
        return ToolResult(tool_name=_TOOL, ok=False, error=str(exc))
    return ToolResult(
        tool_name=_TOOL, ok=True, output=json.dumps({"status": status, "body": out})
    )
