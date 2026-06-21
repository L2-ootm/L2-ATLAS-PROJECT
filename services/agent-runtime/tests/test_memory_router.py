"""Tests for atlas_runtime.memory_router — the budget-aware brief assembler.

Covers the router contract directly (budget enforcement, ranking order, redaction
at the boundary, provenance) with lightweight fake retrievers, plus the ported
real retrievers against the shared `db` fixture (all migrations applied).
"""
from __future__ import annotations

import datetime
import threading
import uuid

import pytest

from atlas_runtime import memory_router as mr


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


class _FakeRetriever:
    """Emits a fixed section of snippets for router-contract tests."""

    def __init__(self, title: str, snippets: list[mr.MemorySnippet]):
        self._title = title
        self._snippets = snippets

    def section_lines(self, query):
        return [self._title]

    def retrieve(self, conn, query):
        return self._snippets


def _snip(text: str, score: float, source: str) -> mr.MemorySnippet:
    return mr.MemorySnippet(text=text, score=score, source=source, approx_tokens=mr.estimate_tokens(text))


def test_estimate_tokens_chars_over_four():
    assert mr.estimate_tokens("") == 0
    assert mr.estimate_tokens("a") == 1  # always >= 1 for non-empty
    assert mr.estimate_tokens("a" * 40) == 10


def test_redact_applied_at_boundary():
    r = _FakeRetriever("## S", [_snip("api_key=sk-leakrouter999", 0.0, "x:1")])
    router = mr.MemoryRouter(retrievers=[r])
    lines, sources = router.assemble(None, mr.RouterQuery())
    body = "\n".join(lines)
    assert "sk-leakrouter999" not in body
    assert "[REDACTED]" in body
    assert sources == ["x:1"]


def test_section_skipped_when_no_snippets():
    r = _FakeRetriever("## Empty", [])
    lines, sources = mr.MemoryRouter(retrievers=[r]).assemble(None, mr.RouterQuery())
    assert lines == []
    assert sources == []


def test_budget_drops_lower_ranked_snippets():
    # Each snippet ~5 tokens (20 chars). Budget of 6 tokens keeps the first only.
    snippets = [_snip("x" * 20, 0.0, f"x:{i}") for i in range(3)]
    r = _FakeRetriever("## S", snippets)
    lines, sources = mr.MemoryRouter(retrievers=[r]).assemble(None, mr.RouterQuery(), token_budget=6)
    assert sources == ["x:0"]  # first kept, rest dropped past budget
    assert "## S" in lines  # heading still emitted because one snippet survived


def test_ranking_order_preserved():
    snippets = [_snip("first", 0.0, "x:0"), _snip("second", -1.0, "x:1")]
    r = _FakeRetriever("## S", snippets)
    lines, sources = mr.MemoryRouter(retrievers=[r]).assemble(None, mr.RouterQuery())
    assert sources == ["x:0", "x:1"]
    assert lines.index("first") < lines.index("second")


# ---------------------------------------------------------------------------
# Ported real retrievers against the live schema
# ---------------------------------------------------------------------------


def _wiki_page(conn, lock, *, slug, title, body) -> str:
    pid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO wiki_pages(id,slug,title,body,created_at,updated_at,version) "
                "VALUES (?,?,?,?,?,?,1)",
                (pid, slug, title, body, now, now),
            )
    return pid


def test_wiki_retriever_matches_terms_and_skips_unrelated(db, lock):
    pid = _wiki_page(db, lock, slug="exec", title="Executor wiring", body="how to wire the executor")
    _wiki_page(db, lock, slug="lunch", title="Lunch", body="tacos")
    snippets = mr.WikiFtsRetriever().retrieve(db, mr.RouterQuery(terms=("executor",), has_focus=True))
    assert [s.source for s in snippets] == [f"wiki:{pid}"]


def test_wiki_retriever_empty_without_terms(db):
    assert mr.WikiFtsRetriever().retrieve(db, mr.RouterQuery(terms=())) == []


def test_recent_runs_retriever_orders_newest_first(db, lock):
    from atlas_runtime import run_service

    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with db:
            db.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, "m", "", "pending", "", now, now),
            )
    run = run_service.start_run(db, lock, mission_id=mid)
    snippets = mr.RecentRunsRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    assert any(s.source == f"run:{run.id}" for s in snippets)


def test_recent_runs_retriever_empty_without_mission(db):
    assert mr.RecentRunsRetriever().retrieve(db, mr.RouterQuery(mission_id=None)) == []
