"""Tests for cashflow_control — the vendored-module process primitive.

Only the deterministic pieces (no real Next.js process is started).
"""
from __future__ import annotations

from atlas_runtime import cashflow_control as cc


def test_invalid_backend_rejected() -> None:
    ok, msg = cc.start(backend="bogus")
    assert ok is False
    assert "unknown backend" in msg


def test_cashflow_dir_is_vendored_module() -> None:
    assert cc.CASHFLOW_DIR.name == "cashflow"
    assert cc.CASHFLOW_DIR.exists(), f"expected vendored cashflow at {cc.CASHFLOW_DIR}"


def test_current_backend_defaults_local(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    assert cc.current_backend() == "local"


def test_status_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    st = cc.status()
    assert set(st) == {"running", "backend", "url"}
    assert st["backend"] == "local"
    assert isinstance(st["running"], bool)


def test_state_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    cc._write_state({"backend": "supabase", "pid": 1234})
    assert cc.current_backend() == "supabase"
    assert cc._read_state()["pid"] == 1234
