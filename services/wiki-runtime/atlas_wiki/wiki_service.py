"""ATLAS wiki service — ingest, update, search, lint (Phase 6)."""
from __future__ import annotations

import datetime
import hashlib
import pathlib
import re
import shutil
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import AuditEvent, Source, WikiPage
from atlas_runtime.audit_service import emit

# NOTE: DO NOT import sqlite_vec or fastembed at module level — ever.
# These are optional heavy dependencies that must be loaded lazily via
# importlib.import_module() inside functions that require semantic search.


def ingest_source(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    path: str,
    run_id: str,
    untrusted: bool = False,
    wiki_dir: pathlib.Path,
) -> Source:
    """Ingest a source file into the wiki and return the constructed Source."""
    raise NotImplementedError


def update_wiki_page(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    slug: str,
    title: str,
    body: str,
    source_id: Optional[str] = None,
    run_id: str,
    wiki_dir: pathlib.Path,
) -> WikiPage:
    """Create or update a wiki page and return the constructed WikiPage."""
    raise NotImplementedError


def search_wiki(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Full-text search the wiki and return matching page dicts."""
    raise NotImplementedError


def semantic_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Semantic vector search the wiki and return matching page dicts."""
    raise NotImplementedError


def lint(
    conn: sqlite3.Connection,
) -> list[dict]:
    """Lint wiki pages for structural issues and return a list of issue dicts."""
    raise NotImplementedError
