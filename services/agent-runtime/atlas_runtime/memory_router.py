"""ATLAS MemoryRouter — budget-aware assembly of the agent context brief (Phase B).

The router is the single place where the agent's working knowledge is gathered,
ranked, budgeted, and secret-redacted before it enters a run prompt. Each source
of knowledge is a `Retriever` that returns scored `MemorySnippet`s for a named
section; the router emits sections in priority order, applies the per-run token
budget, and redacts every snippet at the boundary so a new retriever cannot leak
a credential.

`context_service.assemble_context` drives this: it computes the static brief
(Focus, Goals, Project, Operating Contract) and delegates the dynamic, retrieved
sections (recent runs, loop observations, wiki knowledge, prior failures, relevant
skills) to a `MemoryRouter`.

Trust posture mirrors `context_service`:
  - Secret redaction is applied once, by the router, to every snippet body.
  - Provenance: every emitted snippet contributes a source token (e.g. `wiki:<id>`,
    `run:<id>`, `observation:<id>`, `failure:<run_id>`, `skill:<name>`).

Heavy optional dependencies (semantic embeddings) are never imported here; the
semantic retriever (B-WP5) calls into the wiki runtime which already loads
sqlite-vec / fastembed lazily with an FTS5 fallback.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from atlas_core.schemas.core import SECRET_PATTERNS

from atlas_runtime import goal_service

# Wiki FTS retrieval budget (ported from context_service's original inline logic).
_KNOWLEDGE_MAX_PAGES = 5
_KNOWLEDGE_SNIPPET_CHARS = 400
_KNOWLEDGE_BUDGET_CHARS = 1400

# Default per-run token budget for the dynamic (retrieved) sections. Generous so
# the brief is rarely truncated in practice; the operator can lower it via config.
DEFAULT_TOKEN_BUDGET = 8000


def estimate_tokens(text: str) -> int:
    """Cheap token estimate without a tokenizer dependency (anti-bloat).

    ~4 characters per token is a deliberate approximation; if a real count is
    ever needed it swaps in behind this one function. Always >= 1 for non-empty.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _redact_match(match: "object") -> str:
    # SECRET_PATTERNS capture the secret value in group(2); keep the surrounding
    # key/structure, replace just the value.
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


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


@dataclass(frozen=True)
class MemorySnippet:
    """One rendered brief line with its ranking, budget cost, and provenance."""

    text: str
    score: float
    source: str
    approx_tokens: int


@dataclass(frozen=True)
class RouterQuery:
    """Everything the retrievers need, resolved once by assemble_context."""

    terms: tuple[str, ...] = ()
    has_focus: bool = False
    mission_id: str | None = None
    project_id: str | None = None
    max_runs: int = 5


@runtime_checkable
class Retriever(Protocol):
    """A source of brief knowledge. `section_lines` returns the heading block
    (rendered only when `retrieve` yields snippets); `retrieve` returns the
    already-ranked snippets for this section."""

    def section_lines(self, query: RouterQuery) -> list[str]: ...

    def retrieve(self, conn: sqlite3.Connection, query: RouterQuery) -> list[MemorySnippet]: ...


# ---------------------------------------------------------------------------
# Concrete retrievers (B-WP1 — port the existing inline retrievals)
# ---------------------------------------------------------------------------


class RecentRunsRetriever:
    """Newest-first terminal/active runs for the mission."""

    def section_lines(self, query: RouterQuery) -> list[str]:
        return [f"## Recent Runs (mission {query.mission_id})"]

    def retrieve(self, conn: sqlite3.Connection, query: RouterQuery) -> list[MemorySnippet]:
        if query.mission_id is None:
            return []
        rows = conn.execute(
            "SELECT id, status, started_at, summary FROM runs WHERE mission_id=? "
            "ORDER BY started_at DESC LIMIT ?",
            (query.mission_id, query.max_runs),
        ).fetchall()
        out: list[MemorySnippet] = []
        for i, (run_id, status, started_at, summary) in enumerate(rows):
            summary_txt = f": {summary}" if summary else ""
            text = f"- **{status}** {started_at}{summary_txt}"
            out.append(
                MemorySnippet(
                    text=text,
                    score=float(-i),  # preserve newest-first order
                    source=f"run:{run_id}",
                    approx_tokens=estimate_tokens(text),
                )
            )
        return out


class ObservationRetriever:
    """Recent loop observations (WP-5 compounding loop) — what prior runs learned."""

    def section_lines(self, query: RouterQuery) -> list[str]:
        return ["## Recent Observations"]

    def retrieve(self, conn: sqlite3.Connection, query: RouterQuery) -> list[MemorySnippet]:
        observations = goal_service.list_observations(conn, limit=query.max_runs)
        out: list[MemorySnippet] = []
        for i, obs in enumerate(observations):
            text = f"- _({obs.source})_ {obs.body}"
            out.append(
                MemorySnippet(
                    text=text,
                    score=float(-i),
                    source=f"observation:{obs.id}",
                    approx_tokens=estimate_tokens(text),
                )
            )
        return out


_FAILURE_MAX = 5
_FAILURE_MSG_CHARS = 240


def _failure_message(data_str: str) -> str:
    """Best-effort human message from an audit event's JSON `data` blob."""
    try:
        data = json.loads(data_str)
    except (ValueError, TypeError):
        return (data_str or "").strip()
    if isinstance(data, dict):
        for key in ("error", "message", "summary", "reason", "detail"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


class FailurePatternRetriever:
    """Recurring failures from this mission's prior runs — so a retried mission
    does not repeat the same mistake (pairs with the Phase A retry loop).

    Mines two mission-scoped signals: failed runs' `summary`, and `failure`
    audit events' `data`. Dedupes by normalized message, scoring recurring
    failures highest, then most recent.
    """

    def section_lines(self, query: RouterQuery) -> list[str]:
        return ["## Prior Failures (avoid repeating)"]

    def retrieve(self, conn: sqlite3.Connection, query: RouterQuery) -> list[MemorySnippet]:
        if query.mission_id is None:
            return []
        candidates: list[tuple[str, str]] = []  # (message, run_id) newest-first
        for run_id, summary in conn.execute(
            "SELECT id, summary FROM runs WHERE mission_id=? AND status='failed' "
            "AND summary != '' ORDER BY finished_at DESC",
            (query.mission_id,),
        ).fetchall():
            candidates.append((summary, run_id))
        try:
            rows = conn.execute(
                "SELECT ae.run_id, ae.data FROM audit_events ae "
                "JOIN runs r ON ae.run_id = r.id "
                "WHERE r.mission_id=? AND ae.event_type='failure' "
                "ORDER BY ae.timestamp DESC",
                (query.mission_id,),
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for run_id, data_str in rows:
            msg = _failure_message(data_str)
            if msg:
                candidates.append((msg, run_id))

        # Dedupe by normalized message; track frequency and most-recent run.
        agg: dict[str, dict] = {}
        for index, (msg, run_id) in enumerate(candidates):
            key = " ".join(msg.split()).lower()[:200]
            if not key:
                continue
            entry = agg.get(key)
            if entry is None:
                agg[key] = {"text": msg.strip(), "run_id": run_id, "count": 1, "index": index}
            else:
                entry["count"] += 1  # earlier index already the most recent

        # Recurring first, then most recent.
        ordered = sorted(agg.values(), key=lambda e: (-e["count"], e["index"]))
        out: list[MemorySnippet] = []
        for entry in ordered[:_FAILURE_MAX]:
            msg = entry["text"][:_FAILURE_MSG_CHARS]
            prefix = f"(×{entry['count']}) " if entry["count"] > 1 else ""
            text = f"- {prefix}{msg}"
            out.append(
                MemorySnippet(
                    text=text,
                    score=float(entry["count"]),
                    source=f"failure:{entry['run_id']}",
                    approx_tokens=estimate_tokens(text),
                )
            )
        return out


class WikiFtsRetriever:
    """Top-k LLM Wiki pages matching the query terms (FTS5 / bm25). Safe on DBs
    without the wiki schema. Ported from context_service._relevant_knowledge."""

    def section_lines(self, query: RouterQuery) -> list[str]:
        return [
            "## Relevant Knowledge",
            "_Retrieved from the LLM Wiki (FTS5), most relevant first._",
        ]

    def retrieve(self, conn: sqlite3.Connection, query: RouterQuery) -> list[MemorySnippet]:
        terms = list(query.terms)
        if not terms or not _table_exists(conn, "wiki_fts"):
            return []
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
            return []
        out: list[MemorySnippet] = []
        used = 0
        for i, (page_id, slug, title, snippet) in enumerate(rows):
            snippet = " ".join((snippet or "").split())  # collapse whitespace/newlines
            entry = f"- **{title}** (`{slug}`): {snippet}"
            # Per-section char budget (ported): keep at least one entry, then cap.
            if out and used + len(entry) > _KNOWLEDGE_BUDGET_CHARS:
                break
            used += len(entry)
            out.append(
                MemorySnippet(
                    text=entry,
                    score=float(-i),
                    source=f"wiki:{page_id}",
                    approx_tokens=estimate_tokens(entry),
                )
            )
        return out


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@dataclass
class MemoryRouter:
    """Assembles the dynamic brief sections under a global token budget.

    Retrievers are consulted in order. Within a section, snippets are emitted in
    the order the retriever returns them (already ranked); a snippet is dropped
    once the running token total would exceed `token_budget`. Every snippet body
    is redacted at this boundary.
    """

    retrievers: list[Retriever] = field(default_factory=list)

    def assemble(
        self,
        conn: sqlite3.Connection,
        query: RouterQuery,
        *,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
    ) -> tuple[list[str], list[str]]:
        """Return (markdown lines for the dynamic sections, provenance sources)."""
        lines: list[str] = []
        sources: list[str] = []
        used_tokens = 0
        for retriever in self.retrievers:
            snippets = retriever.retrieve(conn, query)
            emitted: list[MemorySnippet] = []
            for snip in snippets:
                if emitted and used_tokens + snip.approx_tokens > token_budget:
                    # Budget exhausted for this and lower-ranked snippets.
                    break
                emitted.append(snip)
                used_tokens += snip.approx_tokens
            if not emitted:
                continue
            lines.extend(retriever.section_lines(query))
            for snip in emitted:
                lines.append(redact(snip.text))
                sources.append(snip.source)
            lines.append("")
        return lines, sources


def default_router() -> MemoryRouter:
    """The default retriever set, in brief order: runs → prior failures →
    observations → wiki knowledge."""
    return MemoryRouter(
        retrievers=[
            RecentRunsRetriever(),
            FailurePatternRetriever(),
            ObservationRetriever(),
            WikiFtsRetriever(),
        ]
    )
