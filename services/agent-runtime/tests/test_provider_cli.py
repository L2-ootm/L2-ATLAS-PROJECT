"""Provider-mesh service + `atlas provider` / `atlas version` CLI."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from atlas_runtime import provider_service
from atlas_runtime.cli.main import app

runner = CliRunner()


# --- provider_service.active_status ----------------------------------------


def test_active_status_mock_when_no_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))  # defaults, no api_key
    info = provider_service.active_status()
    assert info["auth_mode"] == "api_key"
    assert info["mock_mode"] is True
    assert info["credentials_present"] is False
    assert info["remediation"]


def test_active_status_live_with_env_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("PROBE_KEY", "sk-real")
    (tmp_path / "config.yaml").write_text(
        "provider:\n  api_key: env:PROBE_KEY\n", encoding="utf-8"
    )
    info = provider_service.active_status()
    assert info["credentials_present"] is True
    assert info["mock_mode"] is False
    assert info["remediation"] is None


def test_active_status_freellmapi_is_live_without_key(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: freellmapi\n  base_url: https://free.example/v1\n",
        encoding="utf-8",
    )
    info = provider_service.active_status()
    assert info["auth_mode"] == "freellmapi"
    assert info["mock_mode"] is False  # keyless endpoint still calls a real provider


def test_active_status_oauth_import_live_when_owned_store_present(
    monkeypatch, tmp_path: Path
):
    """oauth_import resolves its credential at run time from the foundation's
    owned store; status must agree with what a run would actually do."""
    from atlas_runtime import codex_auth

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: oauth_import\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        codex_auth, "owned_status",
        lambda: {"present": True, "has_refresh_token": True,
                 "access_token_expired": False, "expires_in_seconds": 3600},
    )
    info = provider_service.active_status()
    assert info["auth_mode"] == "oauth_import"
    assert info["mock_mode"] is False
    assert info["credentials_present"] is True
    assert info["remediation"] is None


def test_active_status_oauth_import_mock_without_owned_store(
    monkeypatch, tmp_path: Path
):
    from atlas_runtime import codex_auth

    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: oauth_import\n", encoding="utf-8"
    )
    monkeypatch.setattr(codex_auth, "owned_status", lambda: {"present": False})
    info = provider_service.active_status()
    assert info["mock_mode"] is True
    assert info["credentials_present"] is False
    assert "import-codex" in info["remediation"]


# --- provider_service.modes_status -----------------------------------------


def test_modes_status_covers_all_four_with_active_flag(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    board = provider_service.modes_status()
    modes = {m["mode"] for m in board}
    assert modes == {"api_key", "oauth_import", "claude_code", "freellmapi"}
    active = [m["mode"] for m in board if m["active"]]
    assert active == ["api_key"]  # default
    for m in board:
        assert set(m) >= {"mode", "label", "active", "available", "detail", "remediation"}


# --- CLI -------------------------------------------------------------------


def test_provider_status_json(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    result = runner.invoke(app, ["provider", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["auth_mode"] == "api_key"
    assert payload["mock_mode"] is True


def test_provider_modes_human_readable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    result = runner.invoke(app, ["provider", "modes"])
    assert result.exit_code == 0, result.output
    assert "oauth_import" in result.output
    assert "freellmapi" in result.output


def test_provider_test_exits_nonzero_in_mock_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    result = runner.invoke(app, ["provider", "test", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["ready"] is False


# --- configured vs reachable ------------------------------------------------
#
# The defect these pin: `provider status` printed "[live]" and `provider test`
# printed "credentials resolve - runs will call the provider" while the
# configured base_url was actively refusing connections. Both are config reads.
# ATLAS's own contract separates configured / reachable / verified-live, so its
# provider surface may not spend the strong word on the weak evidence.


def _freellmapi_config(tmp_path: Path, base_url: str) -> None:
    (tmp_path / "config.yaml").write_text(
        f"provider:\n  auth_mode: freellmapi\n  base_url: {base_url}\n", encoding="utf-8"
    )


def _dead_port() -> int:
    """A port with nothing listening: bind it, read it, release it."""
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_probe_reports_an_endpoint_that_answers(monkeypatch, tmp_path: Path):
    import http.server
    import threading

    class _Quiet(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(404)  # any answer proves reachability
            self.end_headers()

        def log_message(self, *args):  # noqa: ANN002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
        _freellmapi_config(tmp_path, f"http://127.0.0.1:{server.server_port}/v1")
        info = provider_service.probe_reachable(timeout=5.0)
    finally:
        server.shutdown()
    # 404 is reachable: the question is whether anything answers, not whether
    # this particular path exists.
    assert info["probed"] is True
    assert info["reachable"] is True
    assert "404" in info["probe_detail"]


def test_probe_reports_a_refused_endpoint_as_unreachable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _freellmapi_config(tmp_path, f"http://127.0.0.1:{_dead_port()}/v1")
    info = provider_service.probe_reachable(timeout=2.0)
    assert info["mock_mode"] is False  # configured...
    assert info["reachable"] is False  # ...and still not reachable
    assert info["probe_detail"]


def test_probe_admits_it_cannot_check_a_local_session_mode(monkeypatch, tmp_path: Path):
    """claude_code has no endpoint. An honest unknown, never a silent pass."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "provider:\n  auth_mode: claude_code\n", encoding="utf-8"
    )
    info = provider_service.probe_reachable()
    assert info["probed"] is False
    assert info["reachable"] is None


def test_provider_status_says_configured_not_live(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _freellmapi_config(tmp_path, "http://127.0.0.1:9/v1")
    result = runner.invoke(app, ["provider", "status"])
    assert result.exit_code == 0, result.output
    assert "[configured]" in result.output
    assert "[live]" not in result.output


def test_dry_provider_test_does_not_promise_a_working_provider(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _freellmapi_config(tmp_path, "http://127.0.0.1:9/v1")
    result = runner.invoke(app, ["provider", "test"])
    assert result.exit_code == 0, result.output
    assert "not probed" in result.output
    assert "runs will call the provider" not in result.output


def test_probing_provider_test_fails_when_the_endpoint_is_down(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    _freellmapi_config(tmp_path, f"http://127.0.0.1:{_dead_port()}/v1")
    result = runner.invoke(app, ["provider", "test", "--probe", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["configured"] is True
    assert payload["reachable"] is False
    assert payload["ready"] is False


def test_version_json(monkeypatch):
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["name"] == "atlas"
    assert payload["version"]


def test_help_lists_provider_group(monkeypatch):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "provider" in result.output


def test_provider_output_is_ascii_safe_for_windows_consoles(monkeypatch, tmp_path: Path):
    """Default human output must encode on Windows cp1252 / non-UTF terminals
    (no Unicode glyphs) — a real bug a UTF-capturing CliRunner would otherwise hide."""
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    for argv in (["provider", "modes"], ["provider", "status"], ["version"]):
        out = runner.invoke(app, argv).output
        out.encode("ascii")  # pure ASCII — raises if any non-ASCII glyph slips in
