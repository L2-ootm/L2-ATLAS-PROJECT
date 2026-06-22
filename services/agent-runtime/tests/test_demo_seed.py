"""Tests for demo_seed.seed_demo_data: idempotent demo mission+run+audit+wiki
seed, gated by a sentinel file (no natural unique business key on missions).
"""
from __future__ import annotations

import pathlib
import sqlite3
import threading

import pytest

from atlas_runtime import demo_seed


@pytest.fixture(autouse=True)
def _isolated_sentinel(tmp_path, monkeypatch):
    """Redirect the sentinel (ATLAS_HOME/.demo_seeded) to a throwaway path so
    tests never touch the real ~/.atlas/.demo_seeded sentinel. The sentinel
    path is resolved lazily from ATLAS_HOME (demo_seed._sentinel_file), so
    setting the env var here is sufficient — individual tests may still
    override ATLAS_HOME themselves (same effective directory)."""
    atlas_home = tmp_path / "atlas-home"
    monkeypatch.setenv("ATLAS_HOME", str(atlas_home))
    return atlas_home / ".demo_seeded"


def _counts(conn: sqlite3.Connection) -> tuple[int, int, int]:
    missions = conn.execute("SELECT COUNT(*) FROM missions").fetchone()[0]
    runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    audits = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    return missions, runs, audits


# --- Test 1: fresh seed creates exactly the expected rows -------------------


def test_seed_demo_data_creates_mission_run_audit_wiki(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas-home"))
    result = demo_seed.seed_demo_data(db, lock)
    assert result["created"] is True

    missions, runs, audits = _counts(db)
    assert missions == 1
    assert runs == 1
    assert audits >= 2

    run_status = db.execute("SELECT status FROM runs").fetchone()[0]
    assert run_status == "succeeded"

    sources = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert sources == 1


# --- Test 2: idempotency — second call is a no-op ---------------------------


def test_seed_demo_data_is_idempotent(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas-home"))
    first = demo_seed.seed_demo_data(db, lock)
    assert first["created"] is True
    before = _counts(db)

    second = demo_seed.seed_demo_data(db, lock)
    assert second["created"] is False

    after = _counts(db)
    assert before == after


def test_seed_demo_data_noop_when_sentinel_preexists(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path, monkeypatch, _isolated_sentinel
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas-home"))
    _isolated_sentinel.parent.mkdir(parents=True, exist_ok=True)
    _isolated_sentinel.write_text("seeded")

    result = demo_seed.seed_demo_data(db, lock)
    assert result["created"] is False

    missions, runs, audits = _counts(db)
    assert missions == 0
    assert runs == 0
    assert audits == 0


# --- Test 3: temp file used for wiki ingest is cleaned up --------------------


def test_seed_demo_data_cleans_up_temp_file(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas-home"))

    captured_paths: list[str] = []

    from atlas_wiki import wiki_service

    real_ingest = wiki_service.ingest_source

    def spy_ingest(conn, lock, *, path, run_id, untrusted=False, wiki_dir):
        captured_paths.append(path)
        # Assert the temp file exists AT call time (before demo_seed's cleanup).
        assert pathlib.Path(path).is_file()
        return real_ingest(conn, lock, path=path, run_id=run_id, untrusted=untrusted, wiki_dir=wiki_dir)

    monkeypatch.setattr(wiki_service, "ingest_source", spy_ingest)
    monkeypatch.setattr(demo_seed, "wiki_service", wiki_service)

    demo_seed.seed_demo_data(db, lock)

    assert captured_paths, "ingest_source was never called"
    # After seed_demo_data returns, the temp file must be cleaned up.
    assert not pathlib.Path(captured_paths[0]).exists()


# --- Wiki dir resolution: must land under ATLAS_HOME, never raw cwd ---------


def test_seed_demo_data_wiki_dir_under_atlas_home(
    db: sqlite3.Connection, lock: threading.Lock, tmp_path, monkeypatch
) -> None:
    atlas_home = tmp_path / "atlas-home"
    monkeypatch.setenv("ATLAS_HOME", str(atlas_home))

    demo_seed.seed_demo_data(db, lock)

    wiki_dir = atlas_home / "wiki"
    raw_dir = wiki_dir / "raw"
    assert raw_dir.is_dir()
    assert any(raw_dir.iterdir()), "expected an ingested raw file under ATLAS_HOME/wiki/raw"


# --- Test 4: CLI wiring (`atlas db init --demo`) -----------------------------


def test_db_init_demo_flag_calls_seed_demo_data(monkeypatch) -> None:
    import typer
    from typer.testing import CliRunner

    from atlas_runtime import model_registry as model_registry_module
    from atlas_runtime.cli import main as cli_main

    calls: list[tuple] = []

    class _FakeConn:
        pass

    monkeypatch.setattr(cli_main.db, "connect", lambda: _FakeConn())
    monkeypatch.setattr(cli_main.db, "apply_migrations", lambda conn: [])
    monkeypatch.setattr(model_registry_module, "seed_default_models", lambda conn, lock: [])

    fake_result = {"created": True, "mission_id": "abc123"}

    def fake_seed_demo_data(conn, lock):
        calls.append((conn, lock))
        return fake_result

    monkeypatch.setattr(demo_seed, "seed_demo_data", fake_seed_demo_data)

    runner = CliRunner()
    app = typer.Typer()
    app.add_typer(cli_main.db_app, name="db")

    result = runner.invoke(app, ["db", "init", "--demo"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1


def test_db_init_without_demo_flag_does_not_call_seed_demo_data(monkeypatch) -> None:
    import typer
    from typer.testing import CliRunner

    from atlas_runtime import model_registry as model_registry_module
    from atlas_runtime.cli import main as cli_main

    calls: list[tuple] = []

    class _FakeConn:
        pass

    monkeypatch.setattr(cli_main.db, "connect", lambda: _FakeConn())
    monkeypatch.setattr(cli_main.db, "apply_migrations", lambda conn: [])
    monkeypatch.setattr(model_registry_module, "seed_default_models", lambda conn, lock: [])

    def fake_seed_demo_data(conn, lock):
        calls.append((conn, lock))
        return {"created": True}

    monkeypatch.setattr(demo_seed, "seed_demo_data", fake_seed_demo_data)

    runner = CliRunner()
    app = typer.Typer()
    app.add_typer(cli_main.db_app, name="db")

    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0, result.output
    assert calls == []
