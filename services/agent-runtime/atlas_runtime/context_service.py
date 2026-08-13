"""ATLAS context-assembly service — the Intelligence Layer (WP-3, tier [A]).

Before an agent run, materialize the live, audited ATLAS state the agent should
inherit — so a `claude_code` run stops starting blank. Pulls the operator's
Current Focus, the run's Project, and recent runs for the mission, renders a
**secret-redacted** markdown brief (suitable to seed `CLAUDE.md` in the project
cwd or pass as system context), and reports provenance (which sources fed it).

The static sections (Focus, Goals, Project, Operating Contract) are rendered here;
the dynamic, retrieved sections (recent runs, loop observations, wiki knowledge,
and — as Phase B lands — prior failures and relevant skills) are delegated to the
budget-aware `MemoryRouter` (`memory_router.py`), which ranks, budgets, and
redacts them.

Trust deltas honored (see .planning/prep/intelligence-layer-alignment.md):
  - Secret redaction: every dynamic value passes through SECRET_PATTERNS before
    it can enter an agent prompt (the router redacts retrieved snippets; this
    module redacts the static sections it renders directly).
  - Provenance: `AgentContext.sources` records exactly what contributed
    (focus:<id>, project:<id>, run:<id>, ...), traceable per the MemoryProvenance
    philosophy.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass, field

from atlas_runtime import config_service, focus_service, goal_service, mission_service, project_service
from atlas_runtime.memory_router import RetrievalEnvelope, RouterQuery, default_router, redact

# `redact` is re-exported from memory_router so existing callers (and tests) keep
# using `context_service.redact`; it is the single secret-redaction implementation.
__all__ = ["AgentContext", "assemble_context", "redact"]

# Keyword extraction for the wiki/skill retrievers — turns the Focus + open goals
# into FTS query terms.
_KNOWLEDGE_TOKEN = re.compile(r"[A-Za-z0-9]+")
_KNOWLEDGE_STOPWORDS = frozenset(
    {"the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "is",
     "it", "this", "that", "be", "as", "by", "at", "from", "into", "via"}
)
_KNOWLEDGE_MAX_TERMS = 12

# Goal-tree render depth. The retrieved sections below are token-budgeted by the
# MemoryRouter, but the goal tree is static context assembled before any budget
# applies and `build_goal_tree` imposes no depth limit — so a deeply nested plan
# could grow this section without bound and crowd out everything ranked as more
# relevant. Four levels covers focus → goal → sub-goal → sub-sub-goal, which is
# as deep as the goal model is meaningfully used; deeper nodes are reported as
# omitted rather than dropped silently, so the model knows its view is partial
# instead of concluding the work does not exist.
_MAX_GOAL_DEPTH = 4


@dataclass(frozen=True)
class AgentContext:
    """Assembled, secret-redacted context for an agent run."""

    markdown: str
    sources: tuple[str, ...] = field(default_factory=tuple)
    retrieval: RetrievalEnvelope | None = None


def _count_descendants(nodes: list[dict]) -> int:
    return sum(1 + _count_descendants(node.get("children") or []) for node in nodes)


def _render_goal_nodes(
    nodes: list[dict],
    depth: int,
    lines: list[str],
    sources: list[str],
    max_depth: int = _MAX_GOAL_DEPTH,
) -> None:
    """Render the goal tree (goals → sub-goals → tasks) as nested markdown, in
    place. Records goal/observation provenance into `sources`.

    Bounded at `max_depth` levels (see _MAX_GOAL_DEPTH): this section is static
    context outside the MemoryRouter's token budget, so an unbounded recursion
    over a deep plan would silently displace better-ranked evidence."""
    indent = "  " * depth
    if depth >= max_depth:
        omitted = _count_descendants(nodes)
        if omitted:
            lines.append(
                f"{indent}- _({omitted} deeper goal(s) omitted at depth {max_depth}"
                " — query the goal tree directly if they matter)_"
            )
        return
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
        _render_goal_nodes(
            node.get("children") or [], depth + 1, lines, sources, max_depth
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
    """Deduplicated keyword terms from the Focus + open goals/tasks, for retrieval."""
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


def _module_doctrine_lines(
    conn: sqlite3.Connection, *, terms: tuple[str, ...], token_budget: int
) -> tuple[list[str], list[str]]:
    """Render active-module doctrine as a delimited, redacted brief section.

    Never raises: a broken or half-installed module must not be able to stop a
    run from getting its context. Returns ([] , []) when nothing is injectable.
    """
    try:
        from atlas_runtime import module_service  # noqa: PLC0415

        blocks = module_service.active_context_blocks(
            conn, terms=terms, token_budget=token_budget
        )
    except Exception:  # noqa: BLE001 — context assembly is best-effort here
        return [], []
    if not blocks:
        return [], []

    lines = [
        "## Active Module Doctrine",
        "_Operator-activated modules. These are instructions for work in their "
        "domain — follow them; use `atlas_module` for the module's records, "
        "workflows and on-demand context._",
        "",
    ]
    sources: list[str] = []
    for block in blocks:
        module_id = block["module_id"]
        lines.append(
            f"<module-doctrine module=\"{module_id}\" id=\"{block['id']}\" trust=\"operator\">"
        )
        lines.append(redact(block["text"]))
        lines.append("</module-doctrine>")
        lines.append("")
        sources.append(f"module:{module_id}:{block['id']}")
    return lines, sources


def assemble_context(
    conn: sqlite3.Connection,
    *,
    mission_id: str | None = None,
    project_id: str | None = None,
    max_runs: int = 5,
    include_operator_context: bool | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
) -> AgentContext:
    """Build the secret-redacted operator context brief.

    Resolves the project from `project_id`, else from the mission's project_id.
    Always safe to call with no arguments (returns a minimal brief).

    `include_operator_context` gates the Focus/Goals/Operating Contract sections
    (the loop-engineering spine). None resolves ATLAS_SKIP_CONTEXT, then the
    `context.inject_operator_context` config knob — so a run can opt out without
    the agent being permanently welded to the Current Focus.

    `session_id`/`run_id` enable scratchpad read-back (WP-D-1): a run that
    resumes a session is handed the working memory it wrote before the reset.
    Omitting both simply omits that section.
    """
    ctx_cfg = config_service.load_config().context
    if include_operator_context is None:
        if os.environ.get("ATLAS_SKIP_CONTEXT", "").strip().lower() in {"1", "true", "yes"}:
            include_operator_context = False
        else:
            include_operator_context = ctx_cfg.inject_operator_context

    sources: list[str] = []
    lines: list[str] = ["# ATLAS Operator Context", "", "_Generated for this run · secret-redacted._", ""]
    tree: list[dict] = []

    focus = focus_service.get_current_focus(conn) if include_operator_context else None
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

    # Dynamic, retrieved sections (recent runs, loop observations, wiki knowledge,
    # and — as Phase B lands — prior failures, relevant skills): ranked, budgeted,
    # and redacted by the MemoryRouter. Terms come from the Focus + open goals; the
    # wiki retriever no-ops when there is no focus (empty terms).
    terms = _knowledge_terms(focus.title, tree) if focus is not None else []

    # Active-module doctrine (capability v2). Modules the operator switched on
    # get to state the rules that must hold whenever the agent works in their
    # domain — outreach compliance, for instance. Separately budgeted from the
    # retrieval budget so activating a module never starves recall, and marked
    # as instructions (unlike retrieved evidence) because activation IS the
    # operator's authorization. Deactivating a module removes this next run.
    if ctx_cfg.inject_module_context and ctx_cfg.module_token_budget:
        module_lines, module_sources = _module_doctrine_lines(
            conn, terms=tuple(terms), token_budget=ctx_cfg.module_token_budget
        )
        lines.extend(module_lines)
        sources.extend(module_sources)
    query = RouterQuery(
        terms=tuple(terms),
        has_focus=focus is not None,
        mission_id=mission_id,
        project_id=resolved_project_id,
        max_runs=max_runs,
    )
    router = default_router(
        enable_semantic=ctx_cfg.enable_semantic,
        enable_skills=ctx_cfg.enable_skills,
        enable_brain=ctx_cfg.enable_brain,
        scratchpad_session_id=session_id or "",
        scratchpad_run_id=run_id or "",
    )
    # No explicit threshold: it applies only to retrievers that report a real
    # normalised relevance (MemorySnippet.relevance). Passing a positive value
    # here once compared it against every retriever's private sort key and
    # rejected all rank-ordered evidence, so runs executed with no recent-run
    # history, no observations and no wiki knowledge.
    retrieval = router.assemble_envelope(
        conn,
        query,
        token_budget=ctx_cfg.token_budget,
    )
    if retrieval.markdown:
        lines.extend(retrieval.markdown.rstrip().splitlines())
        lines.append("")
    sources.extend(item.source_id for item in retrieval.selected)

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
            "- Apply this context only where relevant: when the operator's prompt "
            "is unrelated to the Current Focus, answer the prompt directly and do "
            "not recite the Focus or its status."
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
    return AgentContext(markdown=markdown, sources=tuple(sources), retrieval=retrieval)
