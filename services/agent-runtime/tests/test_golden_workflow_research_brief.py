"""RED-first tests for the Research Brief golden workflow (Phase 10.0.5-02).

Research Brief is an internal-risk (auto-run) deterministic orchestrator:
offline FTS5 wiki/codex search on a topic -> brief artifact + wiki page. Zero
network surface by construction (no urllib/web_fetch import anywhere in the
module) so mock-mode smokes never depend on connectivity.
"""
from __future__ import annotations

from atlas_runtime.audit_service import get_events_for_run
from atlas_runtime.golden_workflows import research_brief
from atlas_wiki import wiki_service


def test_run_research_brief_finds_seeded_pages(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    run_id = "operator"
    wiki_service.update_wiki_page(
        db, lock, slug="topic-a", title="Topic A", body="atlas is a great platform",
        run_id=run_id, wiki_dir=wiki_dir,
    )
    wiki_service.update_wiki_page(
        db, lock, slug="topic-b", title="Topic B", body="atlas powers automation",
        run_id=run_id, wiki_dir=wiki_dir,
    )

    result = research_brief.run_research_brief(db, lock, topic="atlas", wiki_dir=wiki_dir)

    assert result["artifact_path"]
    artifact_row = db.execute(
        "SELECT path FROM artifacts WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
        (result["run_id"],),
    ).fetchone()
    assert artifact_row is not None

    wiki_row = db.execute(
        "SELECT body FROM wiki_pages WHERE slug=?",
        (result["wiki_slug"],),
    ).fetchone()
    assert wiki_row is not None
    body = wiki_row[0]
    assert "topic-a" in body
    assert "topic-b" in body


def test_run_research_brief_no_match_degrades_gracefully(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    result = research_brief.run_research_brief(
        db, lock, topic="zzz-no-such-topic-zzz", wiki_dir=wiki_dir
    )

    assert result["artifact_path"]
    wiki_row = db.execute(
        "SELECT body FROM wiki_pages WHERE slug=?",
        (result["wiki_slug"],),
    ).fetchone()
    assert wiki_row is not None
    assert "no" in wiki_row[0].lower() or "no matches" in wiki_row[0].lower()


def test_run_research_brief_emits_audit_trail_without_tool_invoke(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    result = research_brief.run_research_brief(db, lock, topic="atlas", wiki_dir=wiki_dir)

    types = [e.event_type for e in get_events_for_run(db, result["run_id"])]
    assert "golden_workflow_started" in types
    assert "artifact" in types
    assert "wiki_update" in types
    assert "golden_workflow_completed" in types
    # Research Brief is a direct service call (search_wiki), not a manifest-gated
    # tool — it never invokes tool_service, so no tool_requested event appears.
    assert "tool_requested" not in types


def test_run_research_brief_never_calls_network(db, lock, tmp_path, monkeypatch):
    import urllib.request

    def _raise(*a, **k):  # noqa: ANN001
        raise AssertionError("network call attempted — research_brief must be offline")

    monkeypatch.setattr(urllib.request, "urlopen", _raise)

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    result = research_brief.run_research_brief(db, lock, topic="atlas", wiki_dir=wiki_dir)

    assert result["artifact_path"]


def test_run_research_brief_three_times_does_not_raise(db, lock, tmp_path):
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()

    for _ in range(3):
        result = research_brief.run_research_brief(db, lock, topic="atlas", wiki_dir=wiki_dir)
        assert result["artifact_path"]
