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
from atlas_runtime import session_message_service

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


def test_default_router_toggles_semantic_and_skills():
    full = mr.default_router()
    assert any(isinstance(r, mr.HybridKnowledgeRetriever) for r in full.retrievers)
    assert any(isinstance(r, mr.SkillRetriever) for r in full.retrievers)

    minimal = mr.default_router(enable_semantic=False, enable_skills=False)
    assert not any(isinstance(r, mr.SkillRetriever) for r in minimal.retrievers)
    assert not any(isinstance(r, mr.HybridKnowledgeRetriever) for r in minimal.retrievers)
    # Pure FTS5 knowledge retriever remains.
    assert any(type(r) is mr.WikiFtsRetriever for r in minimal.retrievers)


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


def _skill_tree(tmp_path):
    """An ATLAS doctrine dir and a Hermes-shaped packaged-skill dir."""
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    (atlas / "README.md").write_text("# index, not a skill\n", encoding="utf-8")
    (atlas / "executor-runner.md").write_text(
        "# Skill: executor-runner\n\n**Use when:** running the executor subprocess loop.\n",
        encoding="utf-8",
    )
    (atlas / "lunch-orderer.md").write_text(
        "# Skill: lunch-orderer\n\nOrders tacos for the team.\n", encoding="utf-8"
    )
    hermes = tmp_path / "hermes"
    (hermes / "category" / "packaged-thing").mkdir(parents=True)
    (hermes / "category" / "packaged-thing" / "SKILL.md").write_text(
        "---\nname: packaged-thing\ndescription: Runs a vendored executor helper.\n---\n\n# body\n",
        encoding="utf-8",
    )
    return atlas, hermes


def test_skill_retriever_matches_and_ranks(tmp_path):
    atlas, hermes = _skill_tree(tmp_path)
    r = mr.SkillRetriever(path=atlas, hermes_dir=hermes)
    snippets = r.retrieve(None, mr.RouterQuery(terms=("executor", "loop"), has_focus=True))
    assert [s.source for s in snippets] == ["skill:executor-runner"]
    assert "executor-runner" in snippets[0].text
    # The path is the actionable half: a name alone is not something to read.
    assert "executor-runner.md" in snippets[0].text
    assert "tacos" not in snippets[0].text


def test_skill_retriever_reads_packaged_frontmatter_and_prefers_atlas_doctrine(tmp_path):
    atlas, hermes = _skill_tree(tmp_path)
    r = mr.SkillRetriever(path=atlas, hermes_dir=hermes)
    packaged = r.retrieve(None, mr.RouterQuery(terms=("vendored", "helper"), has_focus=True))
    assert [s.source for s in packaged] == ["skill:packaged-thing"]
    # "executor" hits both; ATLAS's own doctrine outranks the vendored skill.
    both = r.retrieve(None, mr.RouterQuery(terms=("executor",), has_focus=True))
    assert [s.source for s in both][0] == "skill:executor-runner"


def test_skill_retriever_excludes_the_readme_index(tmp_path):
    atlas, hermes = _skill_tree(tmp_path)
    r = mr.SkillRetriever(path=atlas, hermes_dir=hermes)
    snippets = r.retrieve(None, mr.RouterQuery(terms=("index", "skill"), has_focus=True))
    assert all("README" not in s.text for s in snippets)


def test_skill_retriever_drops_stopword_coincidences(tmp_path):
    """A term shared by every skill is not a match worth a slot."""
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    for name in ("alpha", "beta", "gamma", "delta"):
        (atlas / f"{name}.md").write_text(
            f"# Skill: {name}\n\n**Use when:** you need to build something.\n", encoding="utf-8"
        )
    (atlas / "sirocco.md").write_text(
        "# Skill: sirocco\n\n**Use when:** you build a sirocco.\n", encoding="utf-8"
    )
    r = mr.SkillRetriever(path=atlas, hermes_dir=tmp_path / "absent")
    snippets = r.retrieve(None, mr.RouterQuery(terms=("build", "sirocco"), has_focus=True))
    assert [s.source for s in snippets] == ["skill:sirocco"]


def test_skill_retriever_sees_the_real_atlas_doctrine(tmp_path):
    """The regression this rewrite exists for: `skills/atlas/self-extension.md`
    was invisible to every run because the section parsed an imported planning
    document instead of the skills on disk."""
    r = mr.SkillRetriever()
    snippets = r.retrieve(
        None,
        mr.RouterQuery(terms=("missing", "capability", "disposable"), has_focus=True),
    )
    assert "skill:self-extension" in [s.source for s in snippets]


def test_skill_retriever_delivers_the_verification_rules(tmp_path):
    """The L1 prompt states the four verdicts; `loop-discipline.md` holds the
    detail (what counts as a check, why order matters). A run asking about
    verification must be able to reach it."""
    snippets = mr.SkillRetriever().retrieve(
        None,
        mr.RouterQuery(terms=("verify", "unverified", "tests", "claiming"), has_focus=True),
    )
    assert "skill:loop-discipline" in [s.source for s in snippets]


def test_use_when_is_indexed_past_its_first_line(tmp_path):
    """Found by the delivery test above: every ATLAS doctrine file wraps its
    "Use when" sentence, and only line one was indexed — so `handoff.md` was
    searchable by everything except the word "handoff"."""
    atlas = tmp_path / "atlas"
    atlas.mkdir()
    (atlas / "wrapped.md").write_text(
        "# Skill: wrapped\n\n**Use when:** a session changed state and must\n"
        "leave a handoff the next session can trust.\n\nBody text.\n",
        encoding="utf-8",
    )
    _name, description = mr._parse_skill_file(atlas / "wrapped.md", "doctrine")
    assert "handoff" in description

    snippets = mr.SkillRetriever(path=atlas, hermes_dir=tmp_path / "absent").retrieve(
        None, mr.RouterQuery(terms=("handoff",), has_focus=True)
    )
    assert [s.source for s in snippets] == ["skill:wrapped"]


def test_yaml_block_scalar_description_is_read(tmp_path):
    """`description: |` indexed the ultra pack under the single token "|"."""
    hermes = tmp_path / "hermes" / "ultra"
    hermes.mkdir(parents=True)
    (hermes / "SKILL.md").write_text(
        "---\nname: ultra\ndescription: |\n"
        "  Methodical, proof-based, subagent-native work.\n"
        "  Routes to plan, review or design by intent.\nmodel: opus\n---\n\nBody.\n",
        encoding="utf-8",
    )
    name, description = mr._parse_skill_file(hermes / "SKILL.md", "packaged")
    assert name == "ultra"
    assert "subagent-native" in description and "|" not in description
    assert "opus" not in description  # the block ends where the indent does


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


def test_skill_retriever_missing_dir_is_empty(tmp_path):
    r = mr.SkillRetriever(path=tmp_path / "nope", hermes_dir=tmp_path / "also-nope")
    assert r.retrieve(None, mr.RouterQuery(terms=("executor",), has_focus=True)) == []


def test_skill_retriever_empty_without_focus_or_terms(tmp_path):
    atlas, hermes = _skill_tree(tmp_path)
    r = mr.SkillRetriever(path=atlas, hermes_dir=hermes)
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


def test_brain_retriever_matches_terms_and_scopes(db):
    from atlas_core.schemas.brain import BrainNode
    from atlas_runtime import brain_service

    def node(nid, label, *, project=None, confidence=0.9):
        return BrainNode(
            id=nid, entity_type="run", label=label, project_id=project,
            source_id=nid, source_version="1",
            updated_at="2026-07-10T00:00:00+00:00", confidence=confidence,
        )

    brain_service.upsert_node(db, node("run:1", "run succeeded: wired executor"))
    brain_service.upsert_node(db, node("run:2", "run failed: executor crash", confidence=0.5))
    brain_service.upsert_node(db, node("run:3", "scoped elsewhere", project="p9"))

    snippets = mr.BrainRetriever().retrieve(db, mr.RouterQuery(terms=("executor",), has_focus=True))
    assert [s.source for s in snippets] == ["brain:run:1", "brain:run:2"]
    assert all(s.source.startswith("brain:") for s in snippets)

    # No terms -> no retrieval (abstain, don't dump the graph).
    assert mr.BrainRetriever().retrieve(db, mr.RouterQuery(terms=())) == []


def test_default_router_brain_toggle():
    assert any(isinstance(r, mr.BrainRetriever) for r in mr.default_router().retrievers)
    off = mr.default_router(enable_brain=False)
    assert not any(isinstance(r, mr.BrainRetriever) for r in off.retrievers)


# ---------------------------------------------------------------------------
# Scratchpad read-back (WP-D-1)
# ---------------------------------------------------------------------------


def test_scratchpad_retriever_returns_the_sessions_open_entries(db, lock):
    from atlas_runtime import scratchpad_service

    scratchpad_service.write_entry(
        db, lock, title="Migration plan", body="1. read 0034\n2. write the retriever",
        kind="plan", scope="session", session_id="sess-a", ttl_policy="session",
    )
    scratchpad_service.write_entry(
        db, lock, title="Not mine", body="other session", kind="plan",
        scope="session", session_id="sess-b", ttl_policy="session",
    )
    snippets = mr.ScratchpadRetriever(session_id="sess-a").retrieve(db, mr.RouterQuery())
    assert [s.source for s in snippets] == ["scratch:migration-plan"]
    assert "write the retriever" in snippets[0].text


def test_scratchpad_retriever_is_off_without_a_session_or_run(db):
    assert mr.ScratchpadRetriever().retrieve(db, mr.RouterQuery()) == []


def test_scratchpad_retriever_enforces_its_own_budget(db, lock):
    from atlas_runtime import scratchpad_service

    for index in range(5):
        scratchpad_service.write_entry(
            db, lock, title=f"entry {index}", body="x" * 800, kind="note",
            scope="session", session_id="sess-a", ttl_policy="session",
        )
    snippets = mr.ScratchpadRetriever(session_id="sess-a", token_budget=120).retrieve(
        db, mr.RouterQuery()
    )
    # At least one always survives (continuity beats an empty section), but the
    # budget stops the scratchpad from crowding out recall.
    assert 1 <= len(snippets) < 5


def test_default_router_scratchpad_is_opt_in_and_leads():
    assert not any(
        isinstance(r, mr.ScratchpadRetriever) for r in mr.default_router().retrievers
    )
    on = mr.default_router(scratchpad_session_id="sess-a")
    assert isinstance(on.retrievers[0], mr.ScratchpadRetriever)


# ---------------------------------------------------------------------------
# Structured vs. legacy runs.summary (Phase 3 Track A, F8)
#
# complete_run() now writes a structured RunSummary JSON payload (see
# test_run_service.py / test_run_summary_service.py for that path); these
# tests write runs.summary directly so each retriever's JSON-vs-legacy-text
# branch is exercised in isolation from summary generation itself.
# ---------------------------------------------------------------------------

from atlas_core.schemas.run_summary import RunSummary  # noqa: E402


def _run_with_summary(conn, lock, *, mission_id, summary: str, status: str = "succeeded") -> str:
    rid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO runs(id,mission_id,session_id,status,started_at,finished_at,summary) "
                "VALUES (?,?,?,?,?,?,?)",
                (rid, mission_id, None, status, now, now, summary),
            )
    return rid


def _failure_audit_event(conn, lock, *, run_id: str, message: str) -> None:
    import json as _json

    aid = uuid.uuid4().hex
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO audit_events(id,run_id,event_type,timestamp,data) "
                "VALUES (?,?,?,?,?)",
                (aid, run_id, "failure", now, _json.dumps({"error": message})),
            )


def test_recent_runs_renders_structured_summary_as_goal_outcome(db, lock):
    mid = _mission_row(db, lock)
    summary = RunSummary(goal="ship F8", outcome="succeeded")
    _run_with_summary(db, lock, mission_id=mid, summary=summary.to_json())

    snippets = mr.RecentRunsRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    assert len(snippets) == 1
    assert "ship F8" in snippets[0].text
    assert "succeeded" in snippets[0].text
    assert "{" not in snippets[0].text  # no raw JSON leaked into the brief


def test_recent_runs_falls_back_to_legacy_free_text(db, lock):
    mid = _mission_row(db, lock)
    _run_with_summary(db, lock, mission_id=mid, summary="agent finished the task successfully")

    snippets = mr.RecentRunsRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    assert len(snippets) == 1
    assert "agent finished the task successfully" in snippets[0].text


def test_recent_runs_empty_summary_renders_no_suffix(db, lock):
    mid = _mission_row(db, lock)
    _run_with_summary(db, lock, mission_id=mid, summary="")

    snippets = mr.RecentRunsRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    assert len(snippets) == 1
    # No summary suffix (rendered as ": <text>") appended after the
    # "- **status** timestamp" prefix. The ISO timestamp itself has colons
    # but never "colon-space", so this is a safe discriminator.
    assert ": " not in snippets[0].text


def test_failure_pattern_reads_blockers_from_structured_summary(db, lock):
    mid = _mission_row(db, lock)
    summary = RunSummary(outcome="failed", blockers=["ImportError: no module named foo"])
    run_id = _run_with_summary(db, lock, mission_id=mid, summary=summary.to_json(), status="failed")
    # A DIFFERENT failure message recorded in audit_events for the SAME run —
    # must NOT surface: a structured summary is present for this run, so the
    # retriever should not fall back to audit_events mining for it.
    _failure_audit_event(db, lock, run_id=run_id, message="this should be ignored")

    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    texts = [s.text for s in snippets]
    assert any("ImportError: no module named foo" in t for t in texts)
    assert not any("this should be ignored" in t for t in texts)


def test_failure_pattern_falls_back_to_audit_events_for_legacy_runs(db, lock):
    mid = _mission_row(db, lock)
    run_id = _run_with_summary(db, lock, mission_id=mid, summary="legacy failure text", status="failed")
    _failure_audit_event(db, lock, run_id=run_id, message="mined from audit_events")

    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    texts = [s.text for s in snippets]
    assert any("legacy failure text" in t for t in texts)
    assert any("mined from audit_events" in t for t in texts)


def test_failure_pattern_no_summary_still_mines_audit_events(db, lock):
    mid = _mission_row(db, lock)
    run_id = _run_with_summary(db, lock, mission_id=mid, summary="", status="failed")
    _failure_audit_event(db, lock, run_id=run_id, message="only source of truth")

    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    texts = [s.text for s in snippets]
    assert any("only source of truth" in t for t in texts)


def test_failure_pattern_structured_summary_with_no_blockers_uses_outcome(db, lock):
    mid = _mission_row(db, lock)
    summary = RunSummary(outcome="failed: harness unavailable", blockers=[])
    _run_with_summary(db, lock, mission_id=mid, summary=summary.to_json(), status="failed")

    snippets = mr.FailurePatternRetriever().retrieve(db, mr.RouterQuery(mission_id=mid))
    texts = [s.text for s in snippets]
    assert any("harness unavailable" in t for t in texts)


# --- assemble_envelope relevance gating ------------------------------------
#
# assemble_envelope is the path context_service actually calls; the older
# assemble() tests above do not exercise the relevance threshold at all, which
# is how a threshold that rejected every rank-ordered snippet shipped green.


class _FixedRetriever:
    """Emits pre-built snippets so the gate can be tested in isolation."""

    def __init__(self, snippets):
        self._snippets = snippets

    def retrieve(self, conn, query):  # noqa: ANN001, ARG002
        return list(self._snippets)

    def section_lines(self, query):  # noqa: ANN001, ARG002
        return ["## Fixed evidence"]


def _snippet(source: str, score: float, relevance=None) -> mr.MemorySnippet:
    return mr.MemorySnippet(
        text=f"evidence from {source}",
        score=score,
        source=source,
        approx_tokens=5,
        relevance=relevance,
    )


def test_envelope_keeps_rank_ordered_snippets_regardless_of_threshold(db):
    """A negated-index sort key must never be read as a relevance value.

    Five retrievers emit score=-i purely to preserve SQL ordering, so their best
    possible score is 0.0. Comparing that to a positive relevance threshold
    rejected all of them and blanked the operator context.
    """
    router = mr.MemoryRouter(retrievers=[
        _FixedRetriever([_snippet("run:1", -0.0), _snippet("run:2", -1.0)])
    ])

    envelope = router.assemble_envelope(
        db, mr.RouterQuery(terms=("ship",)), relevance_threshold=0.25
    )

    assert [item.source_id for item in envelope.selected] == ["run:1", "run:2"]
    assert envelope.rejected_source_ids == ()
    assert "evidence from run:1" in envelope.markdown


def test_envelope_filters_only_snippets_reporting_real_relevance(db):
    router = mr.MemoryRouter(retrievers=[
        _FixedRetriever([
            _snippet("weak", 100.0, relevance=0.10),
            _snippet("strong", -5.0, relevance=0.90),
            _snippet("unscored", -1.0),
        ])
    ])

    envelope = router.assemble_envelope(
        db, mr.RouterQuery(terms=("ship",)), relevance_threshold=0.25
    )

    sources = [item.source_id for item in envelope.selected]
    assert "strong" in sources
    assert "unscored" in sources
    assert "weak" not in sources
    assert "weak" in envelope.rejected_source_ids


# --- session history includes the operator's ask ---------------------------


def _session_run(db, session_id, mission_id, summary, started_at, messages=()):
    rid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO runs(id, mission_id, session_id, status, started_at, finished_at, summary) "
        "VALUES (?, ?, ?, 'succeeded', ?, ?, ?)",
        (rid, mission_id, session_id, started_at, started_at, summary),
    )
    db.commit()
    lock = threading.Lock()
    for role, content in messages:
        session_message_service.append_message(
            db,
            lock,
            surface_session_id=session_id,
            run_id=rid,
            role=role,
            content=content,
        )
    return rid


def _mission(db, intent):
    mid = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.execute(
        "INSERT INTO missions(id, title, intent, status, project, created_at, updated_at) "
        "VALUES (?, 't', ?, 'succeeded', '', ?, ?)",
        (mid, intent, now, now),
    )
    db.commit()
    return mid


def test_history_replays_durable_turns_not_synthesized_summaries(db, surface_session):
    """Assistant-only history reads as answers to unseen questions."""
    session = surface_session
    m1 = _mission(db, "audit the installer")
    m2 = _mission(db, "ship the release")
    _session_run(
        db,
        session,
        m1,
        '{"outcome":"hallucinated summary"}',
        "2026-07-26T01:00:00Z",
        [("user", "audit the installer"), ("assistant", "found the payload bug")],
    )
    _session_run(
        db,
        session,
        m2,
        '{"outcome":"another synthesized claim"}',
        "2026-07-26T02:00:00Z",
        [("user", "ship the release"), ("assistant", "cut 0.1.2")],
    )

    snippets = mr.ConversationHistoryRetriever().retrieve(
        db, mr.RouterQuery(session_id=session, max_runs=5)
    )
    messages = mr.history_snippets_to_messages(snippets)

    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert "audit the installer" in messages[0]["content"]
    assert "found the payload bug" in messages[1]["content"]
    assert "ship the release" in messages[2]["content"]
    assert all("hallucinated summary" not in m["content"] for m in messages)


def test_history_does_not_repeat_identical_operator_turn_per_run(db, surface_session):
    """Several runs of one mission share an ask; state it once."""
    session = surface_session
    mid = _mission(db, "keep going until green")
    _session_run(
        db,
        session,
        mid,
        "first attempt",
        "2026-07-26T01:00:00Z",
        [("user", "keep going until green"), ("assistant", "first attempt")],
    )
    _session_run(
        db,
        session,
        mid,
        "second attempt",
        "2026-07-26T02:00:00Z",
        [("user", "keep going until green"), ("assistant", "second attempt")],
    )

    messages = mr.history_snippets_to_messages(
        mr.ConversationHistoryRetriever().retrieve(
            db, mr.RouterQuery(session_id=session, max_runs=5)
        )
    )

    assert [m["role"] for m in messages] == ["user", "assistant", "assistant"]
    assert sum("keep going until green" in m["content"] for m in messages) == 1


def test_history_uses_newest_runs_and_remembers_last_message(db, surface_session):
    session = surface_session
    for index in range(6):
        mid = _mission(db, f"question {index}")
        _session_run(
            db,
            session,
            mid,
            f"summary {index}",
            f"2026-07-26T0{index}:00:00Z",
            [("user", f"question {index}"), ("assistant", f"answer {index}")],
        )
    messages = mr.history_snippets_to_messages(
        mr.ConversationHistoryRetriever().retrieve(
            db, mr.RouterQuery(session_id=session, max_runs=5)
        )
    )
    text = "\n".join(message["content"] for message in messages)
    assert "question 0" not in text
    assert "answer 5" in text
    assert messages[-1]["content"] == "answer 5"


def test_history_strips_compiled_context_and_drops_summary_dump(db, surface_session):
    mid = _mission(db, "what did I just ask?")
    compiled = (
        "# ATLAS Operator Context\n\n## Goals\n- stale\n\n---\n\n"
        "what did I just ask?"
    )
    malformed = (
        '- **run 1 summary:** {"outcome":"invented"}'
        '- **run 2 summary:** {"files_touched":["fake.md"]}</arg_value>'
    )
    _session_run(
        db,
        surface_session,
        mid,
        "unused",
        "2026-07-26T01:00:00Z",
        [("user", compiled), ("assistant", malformed)],
    )
    messages = mr.history_snippets_to_messages(
        mr.ConversationHistoryRetriever().retrieve(
            db, mr.RouterQuery(session_id=surface_session, max_runs=5)
        )
    )
    assert messages == [{"role": "user", "content": "what did I just ask?"}]


def test_self_keyed_retriever_survives_the_abstain_guard(db, lock):
    """A run with no Focus and no mission still gets its scratchpad back."""
    from atlas_runtime import scratchpad_service

    scratchpad_service.write_entry(
        db, lock, title="Held plan", body="continue from step 3", kind="plan",
        scope="session", session_id="sess-a", ttl_policy="session",
    )
    envelope = mr.MemoryRouter(
        retrievers=[mr.ScratchpadRetriever(session_id="sess-a")]
    ).assemble_envelope(db, mr.RouterQuery())
    assert not envelope.abstained
    assert "continue from step 3" in envelope.markdown

    # Without a self-keyed retriever the guard still abstains as before.
    empty = mr.MemoryRouter(retrievers=[mr.RecentRunsRetriever()]).assemble_envelope(
        db, mr.RouterQuery()
    )
    assert empty.abstained and empty.markdown == ""
