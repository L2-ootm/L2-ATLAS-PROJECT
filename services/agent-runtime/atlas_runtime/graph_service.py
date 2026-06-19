"""Knowledge-graph builder for the ATLAS cockpit "Graphify" view.

Scans the project ``.planning/`` corpus (markdown planning docs) and produces a
bounded ``{nodes, links}`` graph: each doc is a node, folders are hub nodes, and
cross-references (relative links, wikilinks, phase + decision mentions) are
edges. This is the curated project-knowledge graph the autonomous loops reason
over — deliberately distinct from the full code-symbol graph (which is ~100k
nodes and unusable in a browser).

The output is intentionally generic ({nodes, links}) so the cockpit 3D view can
render it directly and a richer source can be swapped in later.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Section + file classification for node coloring/grouping in the UI.
KIND_BY_DIR: dict[str, str] = {
    "phases": "phase",
    "milestones": "milestone",
    "prep": "prep",
    "research": "research",
    "reports": "report",
    "intel": "intel",
}
KIND_BY_NAME: dict[str, str] = {
    "ROADMAP.md": "roadmap",
    "STATE.md": "state",
    "PROJECT.md": "project",
    "REQUIREMENTS.md": "requirements",
    "RISKS.md": "risks",
    "RETROSPECTIVE.md": "retro",
    "MILESTONES.md": "milestone",
}

DECISION_RE = re.compile(r"\bD-0*(\d+)\b")
PHASE_RE = re.compile(r"\bPhase\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
MDLINK_RE = re.compile(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")
DECISION_DEF_RE = re.compile(r"(?:^|\n)[#*\s>]*D-0*(\d+)\b")


def _kind(rel: Path) -> str:
    if rel.name in KIND_BY_NAME:
        return KIND_BY_NAME[rel.name]
    if rel.parts and rel.parts[0] in KIND_BY_DIR:
        return KIND_BY_DIR[rel.parts[0]]
    return "doc"


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def build_graph(root: str | None = None) -> dict[str, Any]:
    """Build the knowledge graph from ``<root>/.planning``.

    Returns ``{"nodes": [...], "links": [...], "root": str, "counts": {...}}``.
    Each node: ``{id, label, kind, group, size}``. Hub nodes use ``kind:"group"``.
    Each link: ``{source, target, kind}`` where kind is one of
    ``contains | link | wikilink | phase | decision``.
    """
    base = Path(root or ".").resolve()
    planning = base / ".planning"
    if not planning.is_dir():
        return {"nodes": [], "links": [], "root": str(base), "counts": {"nodes": 0, "links": 0}}

    files = sorted(p for p in planning.rglob("*.md") if p.is_file())

    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    texts: dict[str, str] = {}
    rel_by_id: dict[str, Path] = {}

    def ensure_node(node_id: str, label: str, kind: str, group: str, size: int = 0) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, "label": label, "kind": kind, "group": group, "size": size})

    # Root hub keeps the whole graph one connected component.
    ensure_node("root", ".planning", "group", "root", size=0)

    # File + folder-hub nodes (folder hubs give the graph a readable backbone).
    for path in files:
        rel = path.relative_to(planning)
        node_id = rel.as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        texts[node_id] = text
        rel_by_id[node_id] = rel
        group = rel.parts[0] if len(rel.parts) > 1 else "root"
        ensure_node(node_id, _title(text, path.stem), _kind(rel), group, size=len(text))
        # Ensure a hub node for each ancestor folder under .planning.
        for depth in range(1, len(rel.parts)):
            folder = "/".join(rel.parts[:depth])
            ensure_node(f"dir:{folder}", rel.parts[depth - 1], "group", rel.parts[0], size=0)

    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_link(source: str, target: str, kind: str) -> None:
        if source == target or source not in node_ids or target not in node_ids:
            return
        key = (source, target)
        if key in seen or (target, source) in seen:
            return
        seen.add(key)
        links.append({"source": source, "target": target, "kind": kind})

    # Containment backbone: file -> nearest folder hub -> parent hub -> root.
    for node_id, rel in rel_by_id.items():
        if len(rel.parts) > 1:
            parent_hub = f"dir:{'/'.join(rel.parts[:-1])}"
            add_link(parent_hub, node_id, "contains")
            for depth in range(len(rel.parts) - 1, 1, -1):
                child = f"dir:{'/'.join(rel.parts[:depth])}"
                grandparent = f"dir:{'/'.join(rel.parts[:depth - 1])}"
                add_link(grandparent, child, "contains")
            add_link("root", f"dir:{rel.parts[0]}", "contains")
        else:
            add_link("root", node_id, "contains")

    # Reference indexes.
    by_basename: dict[str, str] = {}
    for node_id in node_ids:
        if node_id.startswith("dir:"):
            continue
        name = Path(node_id).name.lower()
        stem = Path(node_id).stem.lower()
        by_basename.setdefault(name, node_id)
        by_basename.setdefault(stem, node_id)

    # Decision definitions: which doc defines D-0xx (first doc that mentions it
    # at a heading/list position); ROADMAP.md is the canonical fallback.
    decision_def: dict[str, str] = {}
    for node_id, text in texts.items():
        for num in DECISION_DEF_RE.findall(text):
            decision_def.setdefault(num, node_id)
    roadmap_id = "ROADMAP.md" if "ROADMAP.md" in node_ids else None

    # Phase folder lookup: phase id (e.g. "10.0.3") -> its folder hub.
    phase_hub: dict[str, str] = {}
    for node_id in node_ids:
        if node_id.startswith("dir:phases/"):
            folder_name = node_id.split("/", 2)[-1]
            match = re.match(r"(\d+(?:\.\d+)*)", folder_name)
            if match:
                phase_hub[match.group(1)] = node_id

    # Cross-reference edges from each doc's text.
    for node_id, text in texts.items():
        rel = rel_by_id[node_id]
        for raw in MDLINK_RE.findall(text):
            target = (planning / rel.parent / raw).resolve()
            try:
                target_id = target.relative_to(planning).as_posix()
            except ValueError:
                continue
            add_link(node_id, target_id, "link")
        for raw in WIKILINK_RE.findall(text):
            key = raw.strip().lower()
            target_id = by_basename.get(key) or by_basename.get(f"{key}.md")
            if target_id:
                add_link(node_id, target_id, "wikilink")
        for num in DECISION_RE.findall(text):
            target_id = decision_def.get(num) or roadmap_id
            if target_id:
                add_link(node_id, target_id, "decision")
        for phase_id in PHASE_RE.findall(text):
            target_id = phase_hub.get(phase_id)
            if target_id:
                add_link(node_id, target_id, "phase")

    return {
        "nodes": nodes,
        "links": links,
        "root": str(base),
        "counts": {"nodes": len(nodes), "links": len(links)},
    }
