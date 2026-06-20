"""ATLAS context-assembly service — the Intelligence Layer (WP-3, tier [A]).

Before an agent run, materialize the live, audited ATLAS state the agent should
inherit — so a `claude_code` run stops starting blank. Pulls the operator's
Current Focus, the run's Project, and recent runs for the mission, renders a
**secret-redacted** markdown brief (suitable to seed `CLAUDE.md` in the project
cwd or pass as system context), and reports provenance (which sources fed it).

Trust deltas honored (see .planning/prep/intelligence-layer-alignment.md):
  - Secret redaction: every dynamic value passes through SECRET_PATTERNS before
    it can enter an agent prompt.
  - Provenance: `AgentContext.sources` records exactly what contributed
    (focus:<id>, project:<id>, run:<id>), traceable per the MemoryProvenance
    philosophy. (Writing MemoryProvenance rows is a later extension.)

Wiki pages are a documented extension point: the wiki lives in the optional
`atlas-wiki` package, so it is gated and skipped when unavailable.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from atlas_core.schemas.core import SECRET_PATTERNS

from atlas_runtime import focus_service, goal_service, mission_service, project_service

# Memory router (item #1) — FTS5 retrieval over the LLM Wiki into the brief.
# We query the shared wiki_pages/wiki_fts tables directly (same connection) rather
# than depending on the optional atlas-wiki package, and gate on table presence so
# this is safe on databases without the wiki schema.
_KNOWLEDGE_TOKEN = re.compile(r"[A-Za-z0-9]+")
_KNOWLEDGE_STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "is",
     "it", "this", "that", "be", "as", "by", "at", "from", "into", "via"}
)
_KNOWLEDGE_MAX_TERMS = 12
_KNOWLEDGE_MAX_PAGES = 5
_KNOWLEDGE_SNIPPET_CHARS = 400
_KNOWLEDGE_BUDGET_CHARS = 1400


def _redact_match(match: "object") -> str:
    # All three SECRET_PATTERNS capture the secret value in group(2); keep the
    # surrounding key/structure, replace just the value.
    full = match.group(0)  # type: ignore[attr-defined]
    secret = match.group(2)  # type: ignore[attr-defined]
    return full.replace(secret, "[REDACTED]")


def redact(text: str) -> str:
    """Replace credential values (token/api_key/secret/password/bearer) with
    [REDACTED], preserving surrounding structure."""
    if not text:
        return text
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(_redact_match, text)
    return text


@dataclass(frozen=True)
class AgentContext:
    """Assembled, secret-redacted context for an agent run."""

    markdown: str
    sources: tuple[str, ...] = field(default_factory=tuple)


def _render_goal_nodes(
    nodes: list[dict], depth: int, lines: list[str], sources: list[str]
) -> None:
    """Render the goal tree (goals → sub-goals → tasks) as nested markdown, in
    place. Records goal/observation provenance into `sources`."""
    indent = "  " * depth
    for node in nodes:
        sources.append(f"goal:{node['id']}")
        status = node.get("status", "open")
        lines.append(f"{indent}- **{redact(node['title'])}** _({status})_")
        desc = (node.get("description") or "").strip()
        if desc:
            lines.append(f"{indent}  {redact(desc)}")
        # Open tasks first (what's actionable); completed ones noted compactly.
        tasks = node.get("tasks") or []
        for task in tasks:
            mark = {"done": "x", "doing": "~"}.get(task.get("status", "todo"), " ")
            lines.append(f"{indent}  - [{mark}] {redact(task['title'])}")
        # Recent observations on this goal carry what prior runs learned.
        for obs in (node.get("observations") or [])[:3]:
            lines.append(
                f"{indent}  · _obs ({redact(obs.get('source', ''))}):_ {redact(obs['body'])}"
            )
            sources.append(f"observation:{obs['id']}")
        _render_goal_nodes(node.get("children") or [], depth + 1, lines, sources)


def _recent_runs(conn: sqlite3.Connection, mission_id: str, limit: int) -> list[tuple[str, str, str, str]]:
    """(run_id, status, started_at, summary) newest-first for a mission."""
    cursor = conn.execute(
        "SELECT id, status, started_at, summary FROM runs WHERE mission_id=? "
        "ORDER BY started_at DESC LIMIT ?",
        (mission_id, limit),
    )
    return [(r[0], r[1], r[2], r[3] or "") for r in cursor]


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _collect_open_titles(nodes: list[dict], out: list[str]) -> None:
    """Gather open goal/task titles from the goal tree to seed the wiki query."""
    for node in nodes:
        if node.get("status", "open") != "done":
            out.append(node.get("title", "") or "")
        for task in node.get("tasks") or []:
            if task.get("status") != "done":
                out.append(task.get("title", "") or "")
        _collect_open_titles(node.get("children") or [], out)


def _knowledge_terms(focus_title: str | None, tree: list[dict]) -> list[str]:
    """Deduplicated keyword terms from the Focus + open goals/tasks, for FTS5."""
    titles = [focus_title or ""]
    _collect_open_titles(tree, titles)
    seen: set[str] = set()
    terms: list[str] = []
    for title in titles:
        for tok in _KNOWLEDGE_TOKEN.findall(title.lower()):
            if len(tok) < 3 or tok in _KNOWLEDGE_STOPWORDS or tok in seen:
                continue
            seen.add(tok)
            terms.append(tok)
            if len(terms) >= _KNOWLEDGE_MAX_TERMS:
                return terms
    return terms


def _relevant_knowledge(
    conn: sqlite3.Connection, terms: list[str]
) -> tuple[list[str], list[str]]:
    """Retrieve top-k wiki pages matching the terms (FTS5/bm25), redacted and
    budget-capped. Returns (markdown lines, provenance sources). Safe on DBs
    without the wiki schema (returns empties)."""
    if not terms or not _table_exists(conn, "wiki_fts"):
        return [], []
    # Terms are bare [A-Za-z0-9]+ tokens, so quoting each is injection-safe and
    # neutralizes FTS5 operator parsing; OR-join for recall, bm25 ranks relevance.
    match = " OR ".join(f'"{t}"' for t in terms)
    try:
        rows = conn.execute(
            "SELECT wp.id, wp.slug, wp.title, substr(wp.body,1,?) "
            "FROM wiki_fts JOIN wiki_pages wp ON wiki_fts.rowid = wp.rowid "
            "WHERE wiki_fts MATCH ? ORDER BY bm25(wiki_fts) LIMIT ?",
            (_KNOWLEDGE_SNIPPET_CHARS, match, _KNOWLEDGE_MAX_PAGES),
        ).fetchall()
    except sqlite3.Error:
        return [], []
    lines: list[str] = []
    sources: list[str] = []
    used = 0
    for page_id, slug, title, snippet in rows:
        snippet = " ".join((snippet or "").split())  # collapse whitespace/newlines
        entry = f"- **{redact(title)}** (`{redact(slug)}`): {redact(snippet)}"
        if lines and used + len(entry) > _KNOWLEDGE_BUDGET_CHARS:
            break
        lines.append(entry)
        sources.append(f"wiki:{page_id}")
        used += len(entry)
    return lines, sources


def assemble_context(
    conn: sqlite3.Connection,
    *,
    mission_id: str | None = None,
    project_id: str | None = None,
    max_runs: int = 5,
) -> AgentContext:
    """Build the secret-redacted operator context brief.

    Resolves the project from `project_id`, else from the mission's project_id.
    Always safe to call with no arguments (returns a minimal brief).
    """
    sources: list[str] = []
    lines: list[str] = ["# ATLAS Operator Context", "", "_Generated for this run · secret-redacted._", ""]
    tree: list[dict] = []

    focus = focus_service.get_current_focus(conn)
    if focus is not None:
        sources.append(f"focus:{focus.id}")
        lines.append("## Current Focus")
        lines.append(f"**{redact(focus.title)}**" + (f" — framework: {redact(focus.framework)}" if focus.framework else ""))
        priorities = focus_service.decode_list(focus.priorities)
        drivers = focus_service.decode_list(focus.drivers)
        if priorities:
            lines.append("")
            lines.append("Priorities:")
            lines.extend(f"- {redact(p)}" for p in priorities)
        if drivers:
            lines.append("")
            lines.append("Drivers:")
            lines.extend(f"- {redact(d)}" for d in drivers)
        lines.append("")

        # Goal tree under the Current Focus — the WHAT the run synthesizes from
        # (Layer 4/7). Renders goals → sub-goals → tasks → recent observations.
        tree = goal_service.build_goal_tree(conn, focus_id=focus.id)
        if tree:
            lines.append("## Goals")
            _render_goal_nodes(tree, 0, lines, sources)
            lines.append("")

    # Resolve the project (explicit id wins; else the mission's project).
    resolved_project_id = project_id
    if resolved_project_id is None and mission_id is not None:
        mission = mission_service.get_mission(conn, mission_id)
        if mission is not None:
            resolved_project_id = mission.project_id
    if resolved_project_id:
        project = project_service.get_project(conn, resolved_project_id)
        if project is not None:
            sources.append(f"project:{project.id}")
            lines.append("## Project")
            lines.append(f"{redact(project.name)} — `{redact(project.root_path)}`")
            lines.append("")

    if mission_id is not None:
        runs = _recent_runs(conn, mission_id, max_runs)
        if runs:
            lines.append(f"## Recent Runs (mission {mission_id})")
            for run_id, status, started_at, summary in runs:
                sources.append(f"run:{run_id}")
                summary_txt = f": {redact(summary)}" if summary else ""
                lines.append(f"- **{status}** {started_at}{summary_txt}")
            lines.append("")

    # Recent loop observations (WP-5 compounding loop) — what prior runs learned,
    # fed forward so the next run inherits it. Newest first, bounded.
    recent_obs = goal_service.list_observations(conn, limit=max_runs)
    if recent_obs:
        lines.append("## Recent Observations")
        for obs in recent_obs:
            sources.append(f"observation:{obs.id}")
            lines.append(f"- _({redact(obs.source)})_ {redact(obs.body)}")
        lines.append("")

    # Memory router (item #1) — retrieve the operator's own knowledge (LLM Wiki,
    # FTS5) relevant to the Focus + open goals, so the run inherits what is already
    # written down instead of re-deriving it. Redacted, budget-capped, provenance.
    if focus is not None:
        k_lines, k_sources = _relevant_knowledge(conn, _knowledge_terms(focus.title, tree))
        if k_lines:
            lines.append("## Relevant Knowledge")
            lines.append("_Retrieved from the LLM Wiki (FTS5), most relevant first._")
            lines.extend(k_lines)
            lines.append("")
            sources.extend(k_sources)

    # Loop-engineering operating contract (Layer 7) — turns the context above
    # into instructions, so the run is driven by the synthesized brief rather
    # than a bare title. Only emitted when there is operator context to act on.
    if focus is not None:
        lines.append("## Operating Contract")
        lines.append(
            "- Advance the Current Focus and its goals above; treat the open tasks "
            "as the actionable surface and the observations as prior learning."
        )
        lines.append(
            "- Stay within the project workspace. If the work would expand beyond "
            "this Focus, stop and report rather than widening scope."
        )
        lines.append(
            "- Classify your claims: state what you VERIFIED (evidence), what you "
            "INFERRED, and what remains UNCERTAIN. Do not assert unverified results."
        )
        lines.append(
            "- Never echo or request credentials/secrets; redact them if encountered."
        )
        lines.append("")

    markdown = "\n".join(lines).rstrip() + "\n"
    return AgentContext(markdown=markdown, sources=tuple(sources))
