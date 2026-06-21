"""Tests for atlas_runtime.memory_router — the budget-aware brief assembler.

Covers the router contract directly (budget enforcement, ranking order, redaction
at the boundary, provenance) with lightweight fake retrievers, plus the ported
real retrievers against the shared `db` fixture (all migrations applied).
"""
from __future__ import annotations

import datetime
import importlib.util
import threading
import uuid

import pytest

from atlas_runtime import memory_router as mr

_HAS_SEMANTIC = bool(
    importlib.util.find_spec("sqlite_vec")
    and importlib.util.find_spec("fastembed")
    and importlib.util.find_spec("atlas_wiki")
)
requires_semantic = pytest.mark.skipif(
    not _HAS_SEMANTIC, reason="optional [semantic] deps / atlas_wiki not installed"
)


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


# ---------------------------------------------------------------------------
# Failure-pattern retriever (B-WP2)
# ---------------------------------------------------------------------------


def _failed_run(conn, lock, mission_id, *, summary) -> str:
    from atlas_runtime import run_service

    # Reopen to pending first so successive failed runs accumulate (the retry loop).
    with lock:
        with conn:
            conn.execute("UPDATE missions SET status='pending' WHERE id=?", (mission_id,))
    run = run_service.start_run(conn, lock, mission_id=mission_id)
    run_service.complete_run(
        conn, lock, run_id=run.id, mission_id=mission_id, status="failed", summary=summary
    )
    return run.id


def _mission_row(conn, lock) -> str:
    mid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (mid, "m", "", "pending", "", now, now),
            )
    return mid


def test_failure_retriever_surfaces_failed_run_summary(db, lock):
    mid = _mission_row(db, lock)
    _failed_run(db, lock, mid, summary="403 from provider without credentials")
    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    assert len(snippets) == 1
    assert "403 from provider" in snippets[0].text
    assert snippets[0].source.startswith("failure:")


def test_failure_retriever_dedupes_and_counts_recurring(db, lock):
    mid = _mission_row(db, lock)
    _failed_run(db, lock, mid, summary="connection refused on port 8484")
    _failed_run(db, lock, mid, summary="connection refused on port 8484")
    _failed_run(db, lock, mid, summary="unique one-off error")
    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    # Two distinct messages; the recurring one is first and carries a count.
    assert len(snippets) == 2
    assert "(×2)" in snippets[0].text
    assert "connection refused" in snippets[0].text


def test_failure_retriever_empty_without_mission(db):
    assert mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=None)) == []


def test_skill_retriever_matches_and_ranks(tmp_path):
    inv = tmp_path / "SKILL_INVENTORY.md"
    inv.write_text(
        "| skill | class | reason |\n"
        "|---|---|---|\n"
        "| executor-runner | operator | Runs the executor subprocess loop. |\n"
        "| lunch-orderer | operator | Orders tacos for the team. |\n",
        encoding="utf-8",
    )
    r = mr.SkillRetriever(path=inv)
    snippets = r.retrieve(None, mr.RouterQuery(terms=("executor", "loop"), has_focus=True))
    assert [s.source for s in snippets] == ["skill:executor-runner"]
    assert "executor-runner" in snippets[0].text


def test_hybrid_knowledge_pure_fts_without_embeddings(db, lock):
    # No wiki_vec table / no embeddings -> hybrid == pure FTS5 (no regression).
    _wiki_page(db, lock, slug="exec", title="Executor wiring", body="how to wire the executor")
    q = mr.RouterQuery(terms=("executor",), has_focus=True)
    hybrid = mr.HybridKnowledgeRetriever().retrieve(db, q)
    fts = mr.WikiFtsRetriever().retrieve(db, q)
    assert [s.source for s in hybrid] == [s.source for s in fts]


@requires_semantic
def test_hybrid_knowledge_blends_semantic(db, lock, tmp_path):
    from atlas_wiki import wiki_service

    wiki_service.update_wiki_page(
        db, lock, slug="exec", title="Executor wiring",
        body="wiring the run executor subprocess and its stop conditions",
        run_id="operator", wiki_dir=tmp_path,
    )
    assert db.execute("SELECT COUNT(*) FROM wiki_vec").fetchone()[0] >= 1
    snippets = mr.HybridKnowledgeRetriever().retrieve(
        db, mr.RouterQuery(terms=("executor", "loop"), has_focus=True)
    )
    assert any(s.source.startswith("wiki:") for s in snippets)
    assert any("Executor wiring" in s.text for s in snippets)


def test_skill_retriever_missing_file_is_empty(tmp_path):
    r = mr.SkillRetriever(path=tmp_path / "nope.md")
    assert r.retrieve(None, mr.RouterQuery(terms=("executor",), has_focus=True)) == []


def test_skill_retriever_empty_without_focus_or_terms(tmp_path):
    inv = tmp_path / "SKILL_INVENTORY.md"
    inv.write_text("| s | operator | x |\n", encoding="utf-8")
    r = mr.SkillRetriever(path=inv)
    assert r.retrieve(None, mr.RouterQuery(terms=("x",), has_focus=False)) == []
    assert r.retrieve(None, mr.RouterQuery(terms=(), has_focus=True)) == []


def test_failure_retriever_redacted_through_router(db, lock):
    mid = _mission_row(db, lock)
    _failed_run(db, lock, mid, summary="auth failed api_key=sk-failleak123")
    lines, sources = mr.MemoryRouter(retrievers=[mr.FailurePatternRetriever()]).assemble(
        db, mr.RouterQuery(mission_id=mid)
    )
    body = "\n".join(lines)
    assert "## Prior Failures (avoid repeating)" in body
    assert "sk-failleak123" not in body
    assert "[REDACTED]" in body
