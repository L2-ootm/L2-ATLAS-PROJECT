"""ATLAS wiki CLI — atlas wiki ingest/update/search/semantic/lint subcommands.

Design:
  - CLI handlers are thin wrappers only. No SQL, no emit() directly.
  - All business logic goes through wiki_service.
  - _get_connection(), _get_lock(), _get_wiki_dir() are module-level factories;
    monkeypatch in tests.

T-06-12: No .execute / INSERT / SELECT / UPDATE / DELETE in this file.
T-06-13: Registered into atlas_runtime via try/except ImportError.
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import threading

import typer

from atlas_wiki import wiki_service

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

wiki_app = typer.Typer(name="wiki", help="LLM Wiki commands", invoke_without_command=True)

# Module-level lock singleton (monkeypatched in tests via _get_lock)
_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Connection + lock + wiki_dir factories (injectable for tests)
# ---------------------------------------------------------------------------


def _get_connection() -> sqlite3.Connection:
    """Return a file-backed SQLite connection with WAL + FK enabled."""
    db_path = pathlib.Path.home() / ".atlas" / "atlas.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_lock() -> threading.Lock:
    """Return the module-level threading.Lock singleton."""
    return _LOCK


def _get_wiki_dir() -> pathlib.Path:
    """Return the wiki directory (resolved at call time, not module load time).

    ATLAS_WIKI_DIR overrides the CWD-relative default — required when the CLI
    is dispatched by another process (e.g. the gateway) whose working directory
    is not the project root. The directory is created if missing so index/log
    writes never fail on a fresh checkout.
    """
    override = os.environ.get("ATLAS_WIKI_DIR")
    wiki_dir = pathlib.Path(override) if override else pathlib.Path.cwd() / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    return wiki_dir


# ---------------------------------------------------------------------------
# wiki subcommands
# ---------------------------------------------------------------------------


@wiki_app.callback(invoke_without_command=True)
def wiki_root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


@wiki_app.command("ingest")
def ingest(
    path: str = typer.Argument(..., help="Path to the source file to ingest"),
    untrusted: bool = typer.Option(False, "--untrusted", help="Mark source as untrusted"),
) -> None:
    """Ingest a source file into the wiki and print its UUID."""
    conn = _get_connection()
    lock = _get_lock()
    wiki_dir = _get_wiki_dir()
    try:
        source = wiki_service.ingest_source(
            conn,
            lock,
            path=path,
            run_id="operator",
            untrusted=untrusted,
            wiki_dir=wiki_dir,
        )
        typer.echo(source.id)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@wiki_app.command("update")
def update(
    slug: str = typer.Argument(..., help="Wiki page slug"),
    body: str = typer.Option(..., "--body", help="Page body content"),
    title: str = typer.Option("", "--title", help="Page title (defaults to slug)"),
) -> None:
    """Create or update a wiki page and print its slug."""
    conn = _get_connection()
    lock = _get_lock()
    wiki_dir = _get_wiki_dir()
    try:
        page = wiki_service.update_wiki_page(
            conn,
            lock,
            slug=slug,
            title=title or slug,
            body=body,
            run_id="operator",
            wiki_dir=wiki_dir,
        )
        typer.echo(page.slug)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


@wiki_app.command("search")
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", help="Maximum number of results"),
) -> None:
    """Full-text search the wiki and print matching pages."""
    conn = _get_connection()
    results = wiki_service.search_wiki(conn, query, limit=limit)
    if results:
        for r in results:
            typer.echo(f"{r['slug']}\t{r['title']}\t{r['rank']:.4f}")
    else:
        typer.echo("no results")


@wiki_app.command("semantic")
def semantic(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(10, "--limit", help="Maximum number of results"),
) -> None:
    """Semantic vector search the wiki (falls back to FTS5 when sqlite-vec absent)."""
    conn = _get_connection()
    results = wiki_service.semantic_search(conn, query, limit=limit)
    if results:
        for r in results:
            rank_val = r.get("rank") or r.get("distance") or 0.0
            typer.echo(f"{r['slug']}\t{r.get('title', '')}\t{rank_val:.4f}")
    else:
        typer.echo("no results")


@wiki_app.command("reindex")
def reindex_cmd() -> None:
    """(Re)compute embeddings for pages with missing/stale vectors (semantic search).

    No-op when the optional semantic deps (sqlite-vec, fastembed) are absent."""
    conn = _get_connection()
    lock = _get_lock()
    count = wiki_service.reindex(conn, lock)
    typer.echo(f"reindexed {count} page(s)")


@wiki_app.command("lint")
def lint_cmd() -> None:
    """Lint wiki pages for structural issues and print findings."""
    conn = _get_connection()
    findings = wiki_service.lint(conn)
    if findings:
        for f in findings:
            typer.echo(f"[{f['rule']}] {f['slug']}: {f['message']}")
    else:
        typer.echo("no lint findings")


if __name__ == "__main__":  # pragma: no cover
    wiki_app()
