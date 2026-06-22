"""Phase 10.0.4 SC1 — the four integration adapters (stdlib + gh only).

RED until Plan 02 adds `atlas_runtime.tools.adapters.*`. Each adapter exposes
`run(args: dict, ctx) -> ToolResult` and assumes it has ALREADY been authorized —
policy lives in the tool_service chokepoint, not the adapters. The security
surface tested here: web_fetch SSRF guard + size cap, workspace boundary, and the
github honest-failure path.
"""
from __future__ import annotations

import socket

import pytest


def _resolve_to(monkeypatch, ip: str):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda host, *a, **k: [(2, 1, 6, "", (ip, 0))]
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://169.254.1.1/",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ],
)
def test_web_fetch_assert_safe_blocks_unsafe(monkeypatch, url):
    from atlas_runtime.tools.adapters import web_fetch

    # loopback resolution for the hostname case; literal IPs checked directly.
    _resolve_to(monkeypatch, "127.0.0.1")
    with pytest.raises(Exception):
        web_fetch._assert_safe(url)


def test_web_fetch_assert_safe_allows_public(monkeypatch):
    from atlas_runtime.tools.adapters import web_fetch

    _resolve_to(monkeypatch, "93.184.216.34")
    web_fetch._assert_safe("https://example.com/page")  # must not raise


def test_web_fetch_size_cap_raises():
    from atlas_runtime.tools.adapters import web_fetch

    class _Resp:
        def __init__(self) -> None:
            self._buf = b"x" * 100

        def read(self, n: int = -1) -> bytes:
            chunk = self._buf[:n] if (n and n > 0) else self._buf
            self._buf = self._buf[len(chunk):]
            return chunk

    with pytest.raises(ValueError):
        web_fetch._read_capped(_Resp(), 10)


def test_workspace_rejects_cwd_escape(tmp_path):
    from atlas_runtime.tools.adapters import workspace

    res = workspace.run(
        {"op": "read", "path": "../../etc/passwd"},
        ctx={"workspace_root": str(tmp_path)},
    )
    assert not res.ok
    assert res.error


def test_workspace_reads_within_boundary(tmp_path):
    from atlas_runtime.tools.adapters import workspace

    (tmp_path / "hello.txt").write_text("hi", encoding="utf-8")
    res = workspace.run(
        {"op": "read", "path": "hello.txt"}, ctx={"workspace_root": str(tmp_path)}
    )
    assert res.ok
    assert "hi" in res.output


def test_github_nonzero_exit_returns_not_ok(mock_gh):
    from atlas_runtime.tools.adapters import github

    mock_gh(stdout="", returncode=1, stderr="gh: could not resolve repo")
    res = github.run({"op": "repo_view", "repo": "owner/repo"}, ctx={})
    assert not res.ok
    assert res.error


def test_github_success_uses_gh_argv(mock_gh):
    from atlas_runtime.tools.adapters import github

    calls = mock_gh(stdout='{"name":"repo"}', returncode=0)
    res = github.run({"op": "repo_view", "repo": "owner/repo"}, ctx={})
    assert res.ok
    assert calls and calls[0][0] == "gh"  # argv vector, never shell=True


def test_webhook_notify_blocks_unsafe_target(monkeypatch):
    from atlas_runtime.tools.adapters import webhook_notify

    _resolve_to(monkeypatch, "127.0.0.1")
    res = webhook_notify.run(
        {"url": "http://localhost/hook", "payload": {"x": 1}}, ctx={}
    )
    assert not res.ok
