"""Research Brief golden workflow (Phase 10.0.5-02) — internal-risk, auto-run.

Deterministic orchestrator: offline FTS5 wiki/codex search on a topic ->
markdown brief artifact + wiki page. Zero network surface BY CONSTRUCTION —
this module deliberately never imports `urllib`/`web_fetch`, which is the
network-independence guarantee asserted by the
`test_run_research_brief_never_calls_network` monkeypatch test. Per
10.0.5-CONTEXT.md "deterministic, offline" guidance, Research Brief prefers
the codex (`atlas_wiki.wiki_service.search_wiki`, FTS5) over `web_fetch` so
mock-mode smokes never depend on connectivity.

Research Brief does NOT call `tool_service.invoke` — the wiki/codex query is
a direct service call (`search_wiki`), not a manifest-gated tool. This is
intentional: there is no policy decision to make for a read-only FTS5 query
against the operator's own wiki, so no `tool_requested`/`tool_completed`
event pair appears in this workflow's audit trail (only the
`golden_workflow_started`/`artifact`/`wiki_update`/`golden_workflow_completed`
bookend events emitted via `golden_workflow_service`).
"""
from __future__ import annotations

import datetime
import pathlib
import re

from atlas_runtime import golden_workflow_service
from atlas_wiki import wiki_service

_WORKFLOW_ID = "research_brief"


def _slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def run_research_brief(
    conn,
    lock,
    *,
    topic: str,
    wiki_dir: pathlib.Path,
) -> dict:
    """Run one Research Brief pass for `topic`; return a result dict.

    Returns: {"artifact_path": str, "wiki_slug": str, "run_id": str}.
    Graceful degradation: an empty `search_wiki` result produces an honest
    "No wiki entries matched '<topic>'" line instead of raising (T-1005-06 —
    repeated demo runs against a fresh/empty wiki never crash).
    """
    run_id = golden_workflow_service.ensure_golden_run(conn, lock)
    golden_workflow_service.emit_workflow_event(
        conn, lock, run_id=run_id, workflow_id=_WORKFLOW_ID, phase="started"
    )

    matches = wiki_service.search_wiki(conn, topic, limit=10)

    date_str = datetime.date.today().isoformat()
    topic_slug = _slugify(topic)

    lines = [f"# Research Brief: {topic}\n", f"\nDate: {date_str}\n\n"]
    if matches:
        lines.append(f"Found {len(matches)} matching wiki entr{'y' if len(matches) == 1 else 'ies'}:\n\n")
        for m in matches:
            lines.append(f"- **{m['slug']}** — {m['title']}\n")
    else:
        lines.append(f"No wiki entries matched '{topic}'.\n")
    brief = "".join(lines)

    artifact_path = f"golden/research-brief-{topic_slug}-{date_str}.md"
    golden_workflow_service.record_artifact(
        conn,
        lock,
        run_id=run_id,
        path=artifact_path,
        artifact_type="file_write",
        content=brief.encode("utf-8"),
    )

    wiki_slug = f"research-brief-{topic_slug}"
    wiki_dir = pathlib.Path(wiki_dir)
    wiki_dir.mkdir(parents=True, exist_ok=True)
    wiki_service.update_wiki_page(
        conn,
        lock,
        slug=wiki_slug,
        title=f"Research Brief: {topic}",
        body=brief,
        run_id=run_id,
        wiki_dir=wiki_dir,
    )

    golden_workflow_service.emit_workflow_event(
        conn,
        lock,
        run_id=run_id,
        workflow_id=_WORKFLOW_ID,
        phase="completed",
        data={"artifact_path": artifact_path, "wiki_slug": wiki_slug},
    )

    return {"artifact_path": artifact_path, "wiki_slug": wiki_slug, "run_id": run_id}
