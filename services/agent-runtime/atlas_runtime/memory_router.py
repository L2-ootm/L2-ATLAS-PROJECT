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
    """The B-WP1 retriever set, in brief order: runs → observations → wiki."""
    return MemoryRouter(
        retrievers=[
            RecentRunsRetriever(),
            ObservationRetriever(),
            WikiFtsRetriever(),
        ]
    )
