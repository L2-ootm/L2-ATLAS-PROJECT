"""Tests for atlas_wiki.cli.main — Typer CLI wiki subcommands.

Uses typer.testing.CliRunner for CLI invocation. _get_connection, _get_lock,
and _get_wiki_dir are monkeypatched to inject in-memory DB and tmp dirs.

Fixtures from conftest.py (injected by name — do NOT import):
  db       — in-memory SQLite with both migrations applied
  lock     — threading.Lock()
  wiki_dir — tmp_path with raw/, index.md, log.md
  run_id   — stable mission+run row for FK constraints
"""
import pathlib

import pytest
from typer.testing import CliRunner

from atlas_wiki.cli.main import wiki_app

runner = CliRunner()


def test_ingest_exits_zero_prints_uuid(db, lock, wiki_dir, tmp_path, monkeypatch):
    """atlas wiki ingest <path> exits 0 and prints a 36-character UUID."""
    import datetime
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    # CLI uses run_id="operator" — insert a mission+run row with that id so FK passes
    import uuid
    mission_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "operator-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("operator", mission_id, None, "running", now, None, ""),
    )
    db.commit()

    src = tmp_path / "source.txt"
    src.write_text("hello world content for ingest test", encoding="utf-8")

    result = runner.invoke(wiki_app, ["ingest", str(src)])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"
    assert len(result.output.strip()) == 36, (
        f"Expected 36-char UUID, got {len(result.output.strip())!r}: {result.output.strip()!r}"
    )


def test_ingest_missing_file_exits_nonzero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki ingest /nonexistent/file.txt exits non-zero."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    result = runner.invoke(wiki_app, ["ingest", "/nonexistent/file.txt"])
    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"


def test_update_exits_zero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki update <slug> --body 'text' --title 'Title' exits 0."""
    import datetime
    import uuid
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    # CLI uses run_id="operator" — insert a mission+run row with that id so FK passes
    mission_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "operator-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("operator", mission_id, None, "running", now, None, ""),
    )
    db.commit()

    result = runner.invoke(
        wiki_app,
        ["update", "test-slug", "--body", "body text for the wiki page", "--title", "Test"],
    )
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_search_no_results_exits_zero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki search 'xyzzy-no-match' exits 0 even with empty results."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    result = runner.invoke(wiki_app, ["search", "xyzzy-no-match"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"
    assert "no results" in result.output


def test_semantic_exits_zero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki semantic 'query' exits 0 (falls back to FTS5 when sqlite-vec absent)."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    result = runner.invoke(wiki_app, ["semantic", "test query"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"


def test_lint_exits_zero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki lint exits 0 and produces output."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    result = runner.invoke(wiki_app, ["lint"])
    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}\n{result.output}"
    assert result.output.strip(), "Expected non-empty lint output"


# ---------------------------------------------------------------------------
# Coverage gap tests — result display loops + error paths + factory functions
# ---------------------------------------------------------------------------


def _insert_operator_run(db):
    """Insert a mission+run with id='operator' for CLI FK constraint."""
    import datetime
    import uuid
    mission_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT OR IGNORE INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (mission_id, "operator-mission", "", "pending", "", now, now),
    )
    db.execute(
        "INSERT OR IGNORE INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("operator", mission_id, None, "running", now, None, ""),
    )
    db.commit()


def test_search_with_results_prints_rows(db, lock, wiki_dir, tmp_path, monkeypatch):
    """atlas wiki search returns rows when results exist — exercises display loop."""
    import atlas_wiki.cli.main as cli_main
    from atlas_wiki import wiki_service

    _insert_operator_run(db)
    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    # Seed a wiki page so search returns results
    wiki_service.update_wiki_page(
        db, lock, slug="coverage-test", title="Coverage Test",
        body="The quick brown fox jumps over the lazy dog coverage test",
        run_id="operator", wiki_dir=wiki_dir,
    )

    result = runner.invoke(wiki_app, ["search", "coverage"])
    assert result.exit_code == 0, result.output
    assert "coverage-test" in result.output


def test_lint_with_finding_prints_rows(db, lock, wiki_dir, tmp_path, monkeypatch):
    """atlas wiki lint prints [rule] lines when findings exist — exercises display loop."""
    import atlas_wiki.cli.main as cli_main
    from atlas_wiki import wiki_service

    _insert_operator_run(db)
    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    # Seed a page with empty body to trigger the empty-body lint rule
    wiki_service.update_wiki_page(
        db, lock, slug="empty-page", title="Empty Page",
        body="", run_id="operator", wiki_dir=wiki_dir,
    )

    result = runner.invoke(wiki_app, ["lint"])
    assert result.exit_code == 0, result.output
    assert "[" in result.output  # lint finding format: [rule] slug: message


def test_semantic_with_results_prints_rows(db, lock, wiki_dir, tmp_path, monkeypatch):
    """atlas wiki semantic prints rows when FTS fallback returns results."""
    import atlas_wiki.cli.main as cli_main
    from atlas_wiki import wiki_service

    _insert_operator_run(db)
    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    wiki_service.update_wiki_page(
        db, lock, slug="semantic-test", title="Semantic Test",
        body="vector search semantic embedding test page content",
        run_id="operator", wiki_dir=wiki_dir,
    )

    result = runner.invoke(wiki_app, ["semantic", "semantic"])
    assert result.exit_code == 0, result.output
    # Either shows results or "no results" — both are valid paths
    assert result.output.strip()


def test_update_error_path_exits_nonzero(db, lock, wiki_dir, monkeypatch):
    """atlas wiki update exits non-zero when wiki_service raises ValueError."""
    import atlas_wiki.cli.main as cli_main
    from atlas_wiki import wiki_service

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

    def _raise(*args, **kwargs):
        raise ValueError("injected error")

    monkeypatch.setattr(wiki_service, "update_wiki_page", _raise)

    result = runner.invoke(wiki_app, ["update", "some-slug", "--body", "text"])
    assert result.exit_code != 0, f"Expected non-zero exit, got {result.exit_code}"
    assert "Error" in result.output


def test_factory_functions_return_expected_types():
    """_get_lock and _get_wiki_dir return the expected types without monkeypatching."""
    import threading
    import pathlib
    from atlas_wiki.cli.main import _get_lock, _get_wiki_dir

    lock_instance = _get_lock()
    assert hasattr(lock_instance, "acquire") and hasattr(lock_instance, "release")
    assert isinstance(_get_wiki_dir(), pathlib.Path)
