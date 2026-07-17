"""Bounded, read-only queries over ATLAS's rendered knowledge graphs."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import threading
import time
from typing import Any

from atlas_runtime import graph_service

PUBLIC_SCOPES = {"global", "projects", "obsidian", "agent"}
OPERATIONS = {"search", "node", "neighbors", "path", "content", "stats"}
MAX_LIMIT = 50
MAX_DEPTH = 3
MAX_CONTENT = 12_000
_CACHE_TTL_SECONDS = 12.0
_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _backend_scope(scope: str) -> str:
    return "atlas" if scope == "agent" else scope


def _graph(root: str | None, scope: str) -> dict[str, Any]:
    base = str(Path(root or ".").resolve())
    key = (base, scope)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    built = graph_service.build_graph(root=base, scope=_backend_scope(scope))
    with _cache_lock:
        _cache[key] = (now, built)
    return built


def _bounded_limit(value: Any) -> int:
    try:
        return max(1, min(MAX_LIMIT, int(value or 12)))
    except (TypeError, ValueError):
        return 12


def _node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in graph.get("nodes", [])}


def _adjacency(graph: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for link in graph.get("links", []):
        source, target = str(link.get("source")), str(link.get("target"))
        kind = str(link.get("kind", "related"))
        out.setdefault(source, []).append((target, kind))
        out.setdefault(target, []).append((source, kind))
    return out


def _resolve_content_path(graph: dict[str, Any], scope: str, node_id: str) -> Path | None:
    if node_id == "root" or node_id.startswith(("dir:", "proj:")):
        return None
    graph_root = Path(str(graph.get("root", "."))).resolve()
    if scope == "agent":
        base, relative = graph_root / ".planning", node_id
    elif scope == "projects":
        project_slug, separator, relative = node_id.partition("/")
        if not separator:
            return None
        project = next(
            (path for path in graph_root.iterdir() if path.is_dir() and graph_service._slug(path.name) == project_slug),
            None,
        )
        if project is None:
            return None
        base = project
    else:
        base, relative = graph_root, node_id
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == ".md" else None


def query_graph(
    *,
    op: str,
    scope: str = "agent",
    root: str | None = None,
    query: str = "",
    node_id: str = "",
    target_id: str = "",
    depth: int = 1,
    limit: int = 12,
) -> dict[str, Any]:
    """Execute one safe graph operation and return a JSON-stable result."""
    op, scope = (op or "").lower(), (scope or "agent").lower()
    if op not in OPERATIONS:
        return {"ok": False, "error": f"unsupported operation: {op}"}
    if scope not in PUBLIC_SCOPES:
        return {"ok": False, "error": f"unsupported scope: {scope}"}
    limit = _bounded_limit(limit)
    depth = max(1, min(MAX_DEPTH, int(depth or 1)))
    graph = _graph(root, scope)
    nodes = _node_map(graph)
    base = {
        "ok": True,
        "operation": op,
        "scope": scope,
        "root": graph.get("root"),
        "backend": "atlas-graphify",
    }
    if graph.get("error"):
        return {**base, "ok": False, "error": graph["error"]}
    if op == "stats":
        return {**base, "counts": graph.get("counts", {}), "kinds": sorted({str(n.get("kind")) for n in nodes.values()})}
    if op == "search":
        needle = query.strip().lower()
        if not needle:
            return {**base, "ok": False, "error": "query is required for search"}
        ranked = []
        for node in nodes.values():
            haystack = f"{node.get('label', '')} {node.get('id', '')} {node.get('kind', '')} {node.get('group', '')}".lower()
            if needle not in haystack:
                continue
            label = str(node.get("label", "")).lower()
            score = 3 if label == needle else 2 if label.startswith(needle) else 1
            ranked.append((score, node))
        ranked.sort(key=lambda item: (-item[0], str(item[1].get("label", "")).lower()))
        return {**base, "results": [node for _, node in ranked[:limit]], "count": min(limit, len(ranked)), "truncated": len(ranked) > limit}
    if node_id not in nodes:
        return {**base, "ok": False, "error": f"node not found: {node_id}"}
    if op == "node":
        return {**base, "node": nodes[node_id]}
    if op == "content":
        path = _resolve_content_path(graph, scope, node_id)
        if path is None:
            return {**base, "ok": False, "error": "node has no readable Markdown content"}
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            return {**base, "ok": False, "error": str(exc)}
        clipped = content[:MAX_CONTENT]
        return {**base, "node": nodes[node_id], "content": clipped, "truncated": len(content) > len(clipped)}
    adjacency = _adjacency(graph)
    if op == "neighbors":
        visited = {node_id}
        frontier = deque([(node_id, 0)])
        results: list[dict[str, Any]] = []
        while frontier and len(results) < limit:
            current, distance = frontier.popleft()
            if distance >= depth:
                continue
            for related, kind in adjacency.get(current, []):
                if related in visited:
                    continue
                visited.add(related)
                results.append({"node": nodes[related], "distance": distance + 1, "via": kind})
                frontier.append((related, distance + 1))
                if len(results) >= limit:
                    break
        return {**base, "origin": nodes[node_id], "results": results, "depth": depth}
    if not target_id or target_id not in nodes:
        return {**base, "ok": False, "error": f"target node not found: {target_id}"}
    queue = deque([(node_id, [node_id])])
    visited = {node_id}
    while queue:
        current, path = queue.popleft()
        if len(path) - 1 >= depth:
            continue
        for related, _kind in adjacency.get(current, []):
            if related == target_id:
                ids = [*path, related]
                return {**base, "path": [nodes[item] for item in ids], "hops": len(ids) - 1}
            if related not in visited:
                visited.add(related)
                queue.append((related, [*path, related]))
    return {**base, "path": [], "hops": None, "note": f"no path within depth {depth}"}


__all__ = ["query_graph", "PUBLIC_SCOPES", "OPERATIONS"]
