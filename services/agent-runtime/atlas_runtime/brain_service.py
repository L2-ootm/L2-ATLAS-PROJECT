"""Bounded local query service for the durable ATLAS Brain evidence graph."""
from __future__ import annotations

import sqlite3
from collections import deque

from atlas_core.schemas.brain import BrainEdge, BrainNode

MAX_RESULTS = 100
MAX_DEPTH = 4


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
        metadata_json=row[8],
    )


def upsert_node(conn: sqlite3.Connection, node: BrainNode) -> BrainNode:
    with conn:
        conn.execute(
            "INSERT INTO brain_nodes "
            "(id,entity_type,label,project_id,source_id,source_version,updated_at,"
            "confidence,metadata_json) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET entity_type=excluded.entity_type,"
            "label=excluded.label,project_id=excluded.project_id,source_id=excluded.source_id,"
            "source_version=excluded.source_version,updated_at=excluded.updated_at,"
            "confidence=excluded.confidence,metadata_json=excluded.metadata_json",
            (
                node.id,
                node.entity_type,
                node.label,
                node.project_id,
                node.source_id,
                node.source_version,
                node.updated_at,
                node.confidence,
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
        "SELECT id,entity_type,label,project_id,source_id,source_version,updated_at,"
        "confidence,metadata_json FROM brain_nodes WHERE id=?",
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
        "SELECT id,entity_type,label,project_id,source_id,source_version,updated_at,"
        f"confidence,metadata_json FROM brain_nodes WHERE {scope_sql} "
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
            rows = conn.execute(
                "SELECT target_id FROM brain_edges WHERE source_id=? AND project_id=? "
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
            "SELECT target_id FROM brain_edges WHERE source_id=? AND project_id=? "
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


__all__ = [
    "explain",
    "find_path",
    "neighbors",
    "search",
    "upsert_edge",
    "upsert_node",
]
