"""Tests for atlas_wiki.wiki_service — WIKI-01 through WIKI-05 + AUDIT-03."""
from __future__ import annotations

import pathlib
import sqlite3
import threading

import pytest

from atlas_wiki import wiki_service


# ---------------------------------------------------------------------------
# Ingest tests (WIKI-01)
# ---------------------------------------------------------------------------


def test_ingest_source_creates_row(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """After ingest_source, sources table has exactly 1 row with the returned id."""
    src_file = tmp_path / "doc.txt"
    src_file.write_text("Hello wiki source content", encoding="utf-8")

    source = wiki_service.ingest_source(
        db, lock, path=str(src_file), run_id=run_id, wiki_dir=wiki_dir
    )

    rows = db.execute("SELECT id FROM sources WHERE id = ?", (source.id,)).fetchall()
    assert len(rows) == 1, f"Expected 1 source row, got {len(rows)}"


def test_ingest_copies_file_to_raw(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """After ingest_source, wiki_dir/raw/ contains the ingested file copy."""
    src_file = tmp_path / "doc.txt"
    src_file.write_text("File content for copy test", encoding="utf-8")

    wiki_service.ingest_source(
        db, lock, path=str(src_file), run_id=run_id, wiki_dir=wiki_dir
    )

    raw_files = list((wiki_dir / "raw").iterdir())
    assert len(raw_files) == 1, f"Expected 1 file in raw/, got {raw_files}"


def test_ingest_emits_audit_event(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """After ingest_source, audit_events table has exactly 1 row with event_type='wiki_update'."""
    src_file = tmp_path / "doc.txt"
    src_file.write_text("Audit event test content", encoding="utf-8")

    wiki_service.ingest_source(
        db, lock, path=str(src_file), run_id=run_id, wiki_dir=wiki_dir
    )

    rows = db.execute(
        "SELECT id FROM audit_events WHERE run_id=? AND event_type=?",
        (run_id, "wiki_update"),
    ).fetchall()
    assert len(rows) == 1, f"Expected 1 audit_event wiki_update, got {len(rows)}"


def test_reingest_preserves_source_id(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
    tmp_path: pathlib.Path,
) -> None:
    """Re-ingesting the same file preserves source ID — no duplicate SHA256 rows."""
    src_file = tmp_path / "doc.txt"
    src_file.write_text("Stable content for re-ingest", encoding="utf-8")

    source1 = wiki_service.ingest_source(
        db, lock, path=str(src_file), run_id=run_id, wiki_dir=wiki_dir
    )
    source2 = wiki_service.ingest_source(
        db, lock, path=str(src_file), run_id=run_id, wiki_dir=wiki_dir
    )

    all_rows = db.execute("SELECT id FROM sources").fetchall()
    assert len(all_rows) == 1, f"Expected 1 source row after re-ingest, got {len(all_rows)}"
    assert source1.id == source2.id, "source.id must be stable across re-ingests"


# ---------------------------------------------------------------------------
# Update wiki page tests (WIKI-02, WIKI-03)
# ---------------------------------------------------------------------------


def test_update_wiki_page_creates_row(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """update_wiki_page creates a wiki_pages row with the correct slug, title, body."""
    page = wiki_service.update_wiki_page(
        db,
        lock,
        slug="test-page",
        title="Test Page",
        body="This is the test page body content.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    row = db.execute(
        "SELECT slug, title, body FROM wiki_pages WHERE slug=?", (page.slug,)
    ).fetchone()
    assert row is not None, "No wiki_pages row found after update_wiki_page"
    assert row[0] == "test-page"
    assert row[1] == "Test Page"


def test_update_wiki_page_upsert_increments_version(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """Second update_wiki_page on same slug increments version to 2."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="versioned-page",
        title="Versioned Page v1",
        body="Initial body content for version test.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )
    page2 = wiki_service.update_wiki_page(
        db,
        lock,
        slug="versioned-page",
        title="Versioned Page v2",
        body="Updated body content for version test.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    row = db.execute(
        "SELECT version FROM wiki_pages WHERE slug=?", ("versioned-page",)
    ).fetchone()
    assert row is not None
    assert row[0] == 2, f"Expected version=2 after second update, got {row[0]}"
    assert page2.version == 2


def test_update_index_updated(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """wiki_dir/index.md contains the slug after update_wiki_page call."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="index-test",
        title="Index Test Page",
        body="Body for index test page.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    index_content = (wiki_dir / "index.md").read_text(encoding="utf-8")
    assert "index-test" in index_content, (
        f"Expected 'index-test' in index.md, got: {index_content!r}"
    )


def test_update_log_appended(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """wiki_dir/log.md contains the slug after update_wiki_page call."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="log-test",
        title="Log Test Page",
        body="Body for log test page.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    log_content = (wiki_dir / "log.md").read_text(encoding="utf-8")
    assert "log-test" in log_content, (
        f"Expected 'log-test' in log.md, got: {log_content!r}"
    )


# ---------------------------------------------------------------------------
# Search tests (WIKI-04)
# ---------------------------------------------------------------------------


def test_search_returns_ranked_results(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """After inserting a page, search_wiki returns dicts with slug, title, source_id, rank."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="searchable-page",
        title="Searchable Page",
        body="This page contains a uniqueterm42 for search testing.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    results = wiki_service.search_wiki(db, "uniqueterm42")

    assert len(results) >= 1, "Expected at least 1 result for unique search term"
    first = results[0]
    assert "slug" in first, "Result missing 'slug' key"
    assert "title" in first, "Result missing 'title' key"
    assert "source_id" in first, "Result missing 'source_id' key"
    assert "rank" in first, "Result missing 'rank' key"
    assert first["slug"] == "searchable-page"


# ---------------------------------------------------------------------------
# Semantic search tests (WIKI-04 fallback)
# ---------------------------------------------------------------------------


def test_semantic_fallback(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """semantic_search returns a list without raising when sqlite_vec is absent.

    This test MUST NOT use pytest.importorskip — it must run even without
    sqlite_vec installed, verifying the graceful FTS5 fallback path.
    """
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="semantic-test",
        title="Semantic Test Page",
        body="Body for semantic search fallback test.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    result = wiki_service.semantic_search(db, "semantic test")
    assert isinstance(result, list), (
        f"semantic_search must return a list; got {type(result)}"
    )
    # Does not raise — passes regardless of whether sqlite_vec is installed


# ---------------------------------------------------------------------------
# Lint tests (WIKI-05)
# ---------------------------------------------------------------------------


def test_lint_empty_body(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """Page with short/empty body returns a finding with rule='empty_body'."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="empty-body-page",
        title="Empty Body Page",
        body="Short.",  # len < 20
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    findings = wiki_service.lint(db)
    rules = [f["rule"] for f in findings]
    assert "empty_body" in rules, (
        f"Expected 'empty_body' finding; got rules: {rules}"
    )
    # Verify the relevant finding has the right slug
    empty_findings = [f for f in findings if f["rule"] == "empty_body"]
    slugs = [f["slug"] for f in empty_findings]
    assert "empty-body-page" in slugs, f"Expected empty-body-page in empty_body findings, got {slugs}"


def test_lint_detects_contradiction(
    db: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> None:
    """Two pages with contradicting 'version is X' values produce a cross_page_contradiction finding."""
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="page-version-a",
        title="Page Version A",
        body="Current version is 1.0 of the software.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )
    wiki_service.update_wiki_page(
        db,
        lock,
        slug="page-version-b",
        title="Page Version B",
        body="Current version is 2.0 of the software.",
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    findings = wiki_service.lint(db)
    rules = [f["rule"] for f in findings]
    assert "cross_page_contradiction" in rules, (
        f"Expected 'cross_page_contradiction' finding; got rules: {rules}"
    )
