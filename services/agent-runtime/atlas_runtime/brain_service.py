"""Bounded local query + curation service for the durable ATLAS Brain graph.

Reads (``search``/``explain``/``neighbors``/``find_path``) are bounded by
``MAX_RESULTS``/``MAX_DEPTH``. Curation (``update_node``/``delete_node``/
``delete_edge``) exists so the graph can be *corrected*, not only grown — an
append-only knowledge graph keeps every wrong fact it ever learned.

Two invariants the curation path protects:

* **id == ``node_id_for(entity_type, label)``.** ``add_node`` derives the id from
  type+label so repeat calls converge. Renaming in place would break that and the
  next ``add_node`` under the new label would silently create a duplicate, so
  ``update_node`` re-keys the row and rewrites its edges instead.
* **Deletes are reported, not silent.** ``delete_node`` returns exactly what it
  removed (node + incident edges) so the caller's transcript carries enough to
  reconstruct it. Edges are removed explicitly rather than relying on
  ``ON DELETE CASCADE`` — not every connection in the process has
  ``PRAGMA foreign_keys`` on.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from collections import deque
from dataclasses import dataclass

from atlas_core.schemas import provenance
from atlas_core.schemas.brain import BrainEdge, BrainNode
from atlas_core.schemas.provenance import ASSERTED

MAX_RESULTS = 100
MAX_DEPTH = 4

_NODE_COLUMNS = (
    "id,entity_type,label,project_id,source_id,source_version,updated_at,"
    "confidence,grade,metadata_json"
)
_NODE_PLACEHOLDERS = "?,?,?,?,?,?,?,?,?,?"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _node(row: sqlite3.Row | tuple) -> BrainNode:
    return BrainNode(
        id=row[0],
        entity_type=row[1],
        label=row[2],
        project_id=row[3],
        source_id=row[4],
        source_version=row[5],
        updated_at=row[6],
        confidence=row[7],
        grade=row[8] or ASSERTED,
        metadata_json=row[9],
    )


@dataclass(frozen=True)
class UpsertOutcome:
    """What an upsert did, when it did not simply write the node.

    `kept` is what is in the graph now — the incumbent when the write was
    refused, the incoming node otherwise. Callers render `conflict` back to the
    agent so a refused write is a fact it can act on rather than a silent no-op
    it will repeat.
    """

    node: BrainNode
    written: bool
    conflict: dict | None = None


def _summary_of(node: BrainNode) -> str:
    try:
        return str(json.loads(node.metadata_json).get("summary") or "")
    except (ValueError, AttributeError):
        return ""


def _contradicts(incoming: BrainNode, incumbent: BrainNode) -> bool:
    """Whether these two say materially different things about the same entity.

    Only the claim is compared — label and summary. A node re-asserted with the
    same content by a weaker source is not a contradiction, it is corroboration,
    and refusing it would make repeat observations look like disputes.
    """
    return (
        incoming.label.strip() != incumbent.label.strip()
        or _summary_of(incoming).strip() != _summary_of(incumbent).strip()
    )


def _record_conflict(
    conn: sqlite3.Connection,
    *,
    incumbent: BrainNode,
    incoming: BrainNode,
    needs_operator: bool,
) -> dict:
    run_id = incoming.source_id if incoming.source_id.startswith("run:") else ""
    conflict = {
        "node_id": incumbent.id,
        "incumbent_grade": incumbent.grade,
        "incumbent_label": incumbent.label,
        "incoming_grade": incoming.grade,
        "incoming_label": incoming.label,
        "incoming_body": _summary_of(incoming),
        "run_id": run_id,
        "needs_operator": needs_operator,
    }
    if not _table_exists(conn, "brain_node_conflicts"):
        # A DB that predates 0038 still gets the refusal and the returned
        # conflict; it just cannot durably record it. Degraded, not broken.
        return conflict
    conn.execute(
        "INSERT INTO brain_node_conflicts(node_id,incumbent_grade,incumbent_label,"
        "incoming_grade,incoming_label,incoming_body,run_id,needs_operator,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            incumbent.id, incumbent.grade, incumbent.label,
            incoming.grade, incoming.label, _summary_of(incoming),
            run_id, int(needs_operator), _now(),
        ),
    )
    return conflict


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def upsert_node_checked(conn: sqlite3.Connection, node: BrainNode) -> UpsertOutcome:
    """Upsert, refusing a weaker claim that contradicts a stronger one.

    Node ids derive from ``(entity_type, label)``, so re-asserting an entity
    overwrites it. Before grades existed that meant a later self-declared guess
    silently replaced an earlier checked fact and the disagreement left no trace
    — recency decided what the graph believed, which is the weakest possible
    tiebreak and the only one available when nothing records provenance.

    Now rank decides, and the losing claim is *kept* rather than discarded: two
    sources that disagree is information, and only one of them surviving quietly
    is not. Equal ranks still resolve by recency, because once provenance is
    exhausted recency is genuinely all that is left.
    """
    incumbent = explain(conn, node.id)
    if incumbent is None or not _contradicts(node, incumbent):
        return UpsertOutcome(node=upsert_node(conn, node), written=True)

    if provenance.is_conflict_for_operator(node.grade, incumbent.grade):
        # Reality disagreeing with the operator's intent is not ATLAS's call.
        # Both claims are kept and the operator is told; the graph is not
        # quietly edited in either direction.
        with conn:
            conflict = _record_conflict(
                conn, incumbent=incumbent, incoming=node, needs_operator=True
            )
        return UpsertOutcome(node=incumbent, written=False, conflict=conflict)

    if provenance.outranks(node.grade, incumbent.grade):
        with conn:
            _record_conflict(
                conn, incumbent=incumbent, incoming=node, needs_operator=False
            )
        return UpsertOutcome(node=upsert_node(conn, node), written=True)

    with conn:
        conflict = _record_conflict(
            conn, incumbent=incumbent, incoming=node, needs_operator=False
        )
    return UpsertOutcome(node=incumbent, written=False, conflict=conflict)


def promote_checked_claims(
    conn: sqlite3.Connection, *, run_id: str, passing_call_ids: tuple[str, ...]
) -> int:
    """Raise this run's `derived` nodes to `verified` when a check backs them.

    The narrow rule, and the only one that is honest: a claim is promoted when
    the evidence it *cited* includes a tool call the gate counted as a **passing**
    check. Not "the run's verdict was verified" — that would promote every claim
    a passing run happened to record, including ones about things the check never
    touched, which manufactures exactly the false confidence the ladder exists to
    prevent.

    Returns the number promoted. Bounded by nodes-written-per-run, so the
    metadata parse stays cheap; the `grade='derived'` filter means a re-run
    promotes nothing twice.
    """
    if not run_id or not passing_call_ids:
        return 0
    passing = set(passing_call_ids)
    rows = conn.execute(
        "SELECT id, metadata_json FROM brain_nodes WHERE source_id=? AND grade=?",
        (f"run:{run_id}", provenance.DERIVED),
    ).fetchall()
    promoted = 0
    with conn:
        for node_id, metadata_json in rows:
            try:
                cited = json.loads(metadata_json or "{}").get("evidence") or []
            except (TypeError, ValueError):
                continue
            if not passing.intersection(str(c) for c in cited):
                continue
            conn.execute(
                "UPDATE brain_nodes SET grade=? WHERE id=?",
                (provenance.VERIFIED, node_id),
            )
            promoted += 1
    return promoted


def upsert_node(conn: sqlite3.Connection, node: BrainNode) -> BrainNode:
    """Unconditional write. Prefer `upsert_node_checked` for agent-driven writes.

    Kept unguarded because ATLAS's own projections (run and mission mirroring
    after every terminal run) are restating rows they own, not contesting a
    claim, and routing them through conflict detection would manufacture
    disputes out of ordinary bookkeeping.
    """
    with conn:
        conn.execute(
            f"INSERT INTO brain_nodes ({_NODE_COLUMNS}) "
            f"VALUES ({_NODE_PLACEHOLDERS}) "
            "ON CONFLICT(id) DO UPDATE SET entity_type=excluded.entity_type,"
            "label=excluded.label,project_id=excluded.project_id,source_id=excluded.source_id,"
            "source_version=excluded.source_version,updated_at=excluded.updated_at,"
            "confidence=excluded.confidence,grade=excluded.grade,"
            "metadata_json=excluded.metadata_json",
            (
                node.id,
                node.entity_type,
                node.label,
                node.project_id,
                node.source_id,
                node.source_version,
                node.updated_at,
                node.confidence,
                node.grade,
                node.metadata_json,
            ),
        )
    return node


def upsert_edge(conn: sqlite3.Connection, edge: BrainEdge) -> BrainEdge:
    source = explain(conn, edge.source_id)
    target = explain(conn, edge.target_id)
    if source is None or target is None:
        raise ValueError("edge endpoints must exist")
    if source.project_id != target.project_id or edge.project_id != source.project_id:
        raise ValueError("edge cannot cross project scope")
    with conn:
        conn.execute(
            "INSERT INTO brain_edges "
            "(source_id,target_id,relation,project_id,confidence,metadata_json) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(source_id,target_id,relation) DO UPDATE SET "
            "project_id=excluded.project_id,confidence=excluded.confidence,"
            "metadata_json=excluded.metadata_json",
            (
                edge.source_id,
                edge.target_id,
                edge.relation,
                edge.project_id,
                edge.confidence,
                edge.metadata_json,
            ),
        )
    return edge


def explain(conn: sqlite3.Connection, node_id: str) -> BrainNode | None:
    row = conn.execute(
        f"SELECT {_NODE_COLUMNS} FROM brain_nodes WHERE id=?",
        (node_id,),
    ).fetchone()
    return None if row is None else _node(row)


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    project_id: str | None = None,
    limit: int = 20,
) -> tuple[BrainNode, ...]:
    limit = max(1, min(limit, MAX_RESULTS))
    scope_sql = "project_id IS NULL" if project_id is None else "project_id=?"
    params: list[object] = [] if project_id is None else [project_id]
    params.extend((f"%{query.strip()}%", f"%{query.strip()}%", limit))
    rows = conn.execute(
        f"SELECT {_NODE_COLUMNS} FROM brain_nodes WHERE {scope_sql} "
        "AND (label LIKE ? OR metadata_json LIKE ?) "
        "ORDER BY confidence DESC, updated_at DESC, id ASC LIMIT ?",
        params,
    ).fetchall()
    return tuple(_node(row) for row in rows)


def _validate_bounds(depth: int, limit: int) -> tuple[int, int]:
    if depth < 1 or depth > MAX_DEPTH:
        raise ValueError(f"depth must be between 1 and {MAX_DEPTH}")
    return depth, max(1, min(limit, MAX_RESULTS))


def neighbors(
    conn: sqlite3.Connection,
    node_id: str,
    *,
    project_id: str | None,
    depth: int = 1,
    limit: int = 20,
) -> tuple[BrainNode, ...]:
    depth, limit = _validate_bounds(depth, limit)
    seen = {node_id}
    frontier = [node_id]
    ordered: list[BrainNode] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for current in frontier:
            # `IS ?` (not `=?`) so the NULL/global project scope matches its
            # own edges — `project_id = NULL` never matches in SQL.
            rows = conn.execute(
                "SELECT target_id FROM brain_edges WHERE source_id=? AND project_id IS ? "
                "ORDER BY relation,target_id",
                (current, project_id),
            ).fetchall()
            for (target_id,) in rows:
                if target_id in seen:
                    continue
                seen.add(target_id)
                node = explain(conn, target_id)
                if node is not None and node.project_id == project_id:
                    ordered.append(node)
                    next_frontier.append(target_id)
                    if len(ordered) >= limit:
                        return tuple(ordered)
        frontier = next_frontier
        if not frontier:
            break
    return tuple(ordered)


def find_path(
    conn: sqlite3.Connection,
    from_id: str,
    to_id: str,
    *,
    project_id: str,
    max_depth: int = 4,
) -> tuple[str, ...]:
    _validate_bounds(max_depth, MAX_RESULTS)
    start = explain(conn, from_id)
    target = explain(conn, to_id)
    if start is None or target is None:
        return ()
    if start.project_id != project_id or target.project_id != project_id:
        return ()
    queue = deque([(from_id, (from_id,))])
    seen = {from_id}
    while queue:
        current, path = queue.popleft()
        if len(path) - 1 >= max_depth:
            continue
        rows = conn.execute(
            "SELECT target_id FROM brain_edges WHERE source_id=? AND project_id IS ? "
            "ORDER BY relation,target_id",
            (current, project_id),
        ).fetchall()
        for (candidate,) in rows:
            if candidate == to_id:
                return (*path, candidate)
            if candidate not in seen:
                seen.add(candidate)
                queue.append((candidate, (*path, candidate)))
    return ()


# ---------------------------------------------------------------------------
# Inventory — "what does the graph actually contain?"
# ---------------------------------------------------------------------------


def list_nodes(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[BrainNode, ...]:
    """Browse nodes in a scope, newest-first. Scoping matches ``search``:
    ``project_id=None`` means the global (NULL) scope, not "every scope"."""
    limit = max(1, min(limit, MAX_RESULTS))
    offset = max(0, offset)
    where = ["project_id IS NULL" if project_id is None else "project_id=?"]
    params: list[object] = [] if project_id is None else [project_id]
    if entity_type:
        where.append("entity_type=?")
        params.append(entity_type)
    params.extend((limit, offset))
    rows = conn.execute(
        f"SELECT {_NODE_COLUMNS} FROM brain_nodes WHERE {' AND '.join(where)} "
        "ORDER BY updated_at DESC, id ASC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return tuple(_node(row) for row in rows)


def edges_for(conn: sqlite3.Connection, node_id: str) -> tuple[dict, ...]:
    """Every edge incident to ``node_id``, each tagged ``out`` or ``in``.

    ``neighbors`` only walks outbound edges; curation needs both directions so
    the caller can see what a delete would orphan.
    """
    rows = conn.execute(
        "SELECT source_id,target_id,relation,project_id,confidence FROM brain_edges "
        "WHERE source_id=? OR target_id=? ORDER BY relation,source_id,target_id",
        (node_id, node_id),
    ).fetchall()
    return tuple(
        {
            "source_id": row[0],
            "target_id": row[1],
            "relation": row[2],
            "project_id": row[3],
            "confidence": row[4],
            "direction": "out" if row[0] == node_id else "in",
        }
        for row in rows
    )


def stats(conn: sqlite3.Connection) -> dict:
    """Whole-graph inventory across every scope.

    Deliberately unscoped: the operator question this answers is "what is in my
    graph at all", and a per-project breakdown is more useful than forcing the
    caller to guess a scope first.
    """
    nodes = conn.execute("SELECT COUNT(*) FROM brain_nodes").fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM brain_edges").fetchone()[0]
    by_type = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT entity_type, COUNT(*) FROM brain_nodes GROUP BY entity_type "
            "ORDER BY COUNT(*) DESC, entity_type ASC"
        )
    }
    by_relation = {
        row[0]: row[1]
        for row in conn.execute(
            "SELECT relation, COUNT(*) FROM brain_edges GROUP BY relation "
            "ORDER BY COUNT(*) DESC, relation ASC"
        )
    }
    by_project = {
        (row[0] or "(global)"): row[1]
        for row in conn.execute(
            "SELECT project_id, COUNT(*) FROM brain_nodes GROUP BY project_id "
            "ORDER BY COUNT(*) DESC"
        )
    }
    orphans = conn.execute(
        "SELECT COUNT(*) FROM brain_nodes n WHERE NOT EXISTS "
        "(SELECT 1 FROM brain_edges e WHERE e.source_id=n.id OR e.target_id=n.id)"
    ).fetchone()[0]
    updated = conn.execute(
        "SELECT MIN(updated_at), MAX(updated_at) FROM brain_nodes"
    ).fetchone()
    return {
        "nodes": nodes,
        "edges": edges,
        "orphan_nodes": orphans,
        "by_entity_type": by_type,
        "by_relation": by_relation,
        "by_project": by_project,
        "oldest_updated_at": updated[0],
        "newest_updated_at": updated[1],
    }


# ---------------------------------------------------------------------------
# Portability — the graph is the operator's, not the tool's
# ---------------------------------------------------------------------------


def export_graph(conn: sqlite3.Connection) -> dict:
    """Whole graph as a plain JSON-able dict: ``{"nodes": [...], "edges": [...]}``.

    Unbounded on purpose — this is a backup/migration path, not a query, and a
    truncated export is worse than a slow one.
    """
    nodes = [
        {
            "id": row[0],
            "entity_type": row[1],
            "label": row[2],
            "project_id": row[3],
            "source_id": row[4],
            "source_version": row[5],
            "updated_at": row[6],
            "confidence": row[7],
            "grade": row[8],
            "metadata_json": row[9],
        }
        for row in conn.execute(f"SELECT {_NODE_COLUMNS} FROM brain_nodes ORDER BY id")
    ]
    edges = [
        {
            "source_id": row[0],
            "target_id": row[1],
            "relation": row[2],
            "project_id": row[3],
            "confidence": row[4],
            "metadata_json": row[5],
        }
        for row in conn.execute(
            "SELECT source_id,target_id,relation,project_id,confidence,metadata_json "
            "FROM brain_edges ORDER BY source_id,target_id,relation"
        )
    ]
    return {"version": 1, "nodes": nodes, "edges": edges}


def import_graph(conn: sqlite3.Connection, payload: dict) -> dict:
    """Merge an exported graph in. Upserts, so re-importing the same file is a
    no-op rather than a duplication.

    Nodes land before edges (endpoints must exist). Edges whose endpoints are
    missing are counted as skipped rather than aborting the import — a partial
    export should still restore everything it can.
    """
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    imported_nodes = 0
    for raw in nodes:
        upsert_node(conn, BrainNode(**raw))
        imported_nodes += 1
    imported_edges = 0
    skipped: list[dict] = []
    for raw in edges:
        try:
            upsert_edge(conn, BrainEdge(**raw))
            imported_edges += 1
        except ValueError as exc:
            skipped.append({**raw, "reason": str(exc)})
    return {"nodes": imported_nodes, "edges": imported_edges, "skipped_edges": skipped}


# ---------------------------------------------------------------------------
# Curation — correcting and forgetting
# ---------------------------------------------------------------------------


def update_node(
    conn: sqlite3.Connection,
    node_id: str,
    *,
    label: str | None = None,
    entity_type: str | None = None,
    confidence: float | None = None,
    metadata: dict | None = None,
    source_id: str | None = None,
    new_id: str | None = None,
    updated_at: str | None = None,
) -> BrainNode:
    """Correct a node in place; returns the stored row.

    Only the fields passed are changed. ``metadata`` is merged into the existing
    metadata (pass an explicit ``None`` value for a key to drop it) rather than
    replacing it, so a caller fixing a summary cannot silently discard
    provenance another writer recorded.

    ``new_id`` re-keys the row and rewrites every incident edge — pass the id
    derived from the new type+label to keep the ``add_node`` convergence
    invariant. Colliding with an existing node raises rather than merging;
    merging two entities is a decision, not a rename.
    """
    current = explain(conn, node_id)
    if current is None:
        raise ValueError(f"unknown node: {node_id}")

    merged = json.loads(current.metadata_json or "{}")
    if metadata:
        for key, value in metadata.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value

    target_id = new_id or node_id
    if target_id != node_id and explain(conn, target_id) is not None:
        raise ValueError(
            f"a node already exists at {target_id!r}; remove or rename it first"
        )

    updated = BrainNode(
        id=target_id,
        entity_type=entity_type or current.entity_type,
        label=label or current.label,
        project_id=current.project_id,
        source_id=source_id or current.source_id,
        source_version=current.source_version,
        updated_at=updated_at or _now(),
        confidence=current.confidence if confidence is None else confidence,
        # Curation corrects what a node says, never how it came to be known.
        # A wrong label fixed by hand does not turn a guess into an observation.
        grade=current.grade,
        metadata_json=json.dumps(merged),
    )

    with conn:
        if target_id != node_id:
            # Insert the new row before repointing edges: the edge FKs (where
            # enforced) require the endpoint to exist first.
            conn.execute(
                f"INSERT INTO brain_nodes ({_NODE_COLUMNS}) VALUES ({_NODE_PLACEHOLDERS})",
                (
                    updated.id,
                    updated.entity_type,
                    updated.label,
                    updated.project_id,
                    updated.source_id,
                    updated.source_version,
                    updated.updated_at,
                    updated.confidence,
                    updated.grade,
                    updated.metadata_json,
                ),
            )
            # OR REPLACE: the rename can collide with an edge that already
            # exists at the new key; converging on one edge is correct there.
            conn.execute(
                "UPDATE OR REPLACE brain_edges SET source_id=? WHERE source_id=?",
                (target_id, node_id),
            )
            conn.execute(
                "UPDATE OR REPLACE brain_edges SET target_id=? WHERE target_id=?",
                (target_id, node_id),
            )
            conn.execute("DELETE FROM brain_nodes WHERE id=?", (node_id,))
        else:
            conn.execute(
                "UPDATE brain_nodes SET entity_type=?,label=?,source_id=?,"
                "updated_at=?,confidence=?,grade=?,metadata_json=? WHERE id=?",
                (
                    updated.entity_type,
                    updated.label,
                    updated.source_id,
                    updated.updated_at,
                    updated.confidence,
                    updated.grade,
                    updated.metadata_json,
                    node_id,
                ),
            )
    return updated


def delete_node(conn: sqlite3.Connection, node_id: str) -> dict | None:
    """Forget a node and its edges; returns what was removed, or None if absent.

    The return value is the undo record — ``{"node": {...}, "edges": [...]}`` is
    enough to reconstruct the deletion, and every caller surfaces it.
    """
    node = explain(conn, node_id)
    if node is None:
        return None
    removed_edges = edges_for(conn, node_id)
    with conn:
        conn.execute(
            "DELETE FROM brain_edges WHERE source_id=? OR target_id=?",
            (node_id, node_id),
        )
        conn.execute("DELETE FROM brain_nodes WHERE id=?", (node_id,))
    return {
        "node": {
            "id": node.id,
            "entity_type": node.entity_type,
            "label": node.label,
            "project_id": node.project_id,
            "source_id": node.source_id,
            "source_version": node.source_version,
            "updated_at": node.updated_at,
            "confidence": node.confidence,
            "metadata_json": node.metadata_json,
        },
        "edges": [dict(edge) for edge in removed_edges],
    }


def delete_edge(
    conn: sqlite3.Connection, source_id: str, target_id: str, relation: str
) -> bool:
    """Remove one relation. Returns False when it was not there (already-gone is
    not an error — unlink must be safe to retry)."""
    with conn:
        cursor = conn.execute(
            "DELETE FROM brain_edges WHERE source_id=? AND target_id=? AND relation=?",
            (source_id, target_id, relation),
        )
    return cursor.rowcount > 0


__all__ = [
    "delete_edge",
    "delete_node",
    "edges_for",
    "explain",
    "export_graph",
    "import_graph",
    "find_path",
    "list_nodes",
    "neighbors",
    "search",
    "stats",
    "update_node",
    "upsert_edge",
    "upsert_node",
]
