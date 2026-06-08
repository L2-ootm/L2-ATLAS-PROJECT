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


def test_ingest_exits_zero_prints_uuid(db, lock, wiki_dir, run_id, tmp_path, monkeypatch):
    """atlas wiki ingest <path> exits 0 and prints a 36-character UUID."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

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


def test_update_exits_zero(db, lock, wiki_dir, run_id, monkeypatch):
    """atlas wiki update <slug> --body 'text' --title 'Title' exits 0."""
    import atlas_wiki.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(cli_main, "_get_wiki_dir", lambda: wiki_dir)

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
