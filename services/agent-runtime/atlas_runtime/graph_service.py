"""Knowledge-graph builder for the ATLAS cockpit "Graphify" view.

Scans a markdown corpus and produces a bounded ``{nodes, links}`` graph: each
doc is a node, folders are hub nodes, and cross-references (relative links,
wikilinks, phase + decision mentions) are edges. This is the curated knowledge
graph the autonomous loops reason over — deliberately distinct from the full
code-symbol graph (which is ~100k nodes and unusable in a browser).

Four scopes are supported (``build_graph(scope=...)``):

* ``atlas``    — the project's ``.planning/`` corpus (default, back-compat).
* ``global``   — the whole repo's markdown knowledge (planning + wiki + docs…).
* ``projects`` — sibling L2 projects under ``ATLAS_PROJECTS_DIR``, one cluster
                 per project (each project's top docs + ``.planning``).
* ``obsidian`` — an Obsidian vault (``ATLAS_OBSIDIAN_DIR``), wikilink-centric.

The output is intentionally generic ({nodes, links}) so the cockpit 3D view can
render it directly and a richer source can be swapped in later.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable

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

# Directories never worth walking for a knowledge graph.
EXCLUDE_DIRS: set[str] = {
    ".git", ".hg", ".svn", "node_modules", "target", "dist", "build", "out",
    ".venv", "venv", "__pycache__", ".obsidian", "graphify-out", ".playwright-cli",
    ".next", ".turbo", ".vite", "vendor", "coverage", ".pytest_cache", ".mypy_cache",
    ".cargo", ".rustup", "site-packages", ".idea", ".vscode",
}

# Resolved at runtime from the real home dir (keeps no hardcoded username in
# source while still pointing at a real folder — a literal "<USER_HOME>"
# placeholder here rendered the projects/obsidian tabs blank).
DEFAULT_OBSIDIAN = str(Path.home() / "Desktop" / "Obsidian")
DEFAULT_PROJECTS = str(Path.home() / "Desktop" / "Projects")

# Per-scope node budgets — keep the browser graph readable + fast.
SCOPE_CAP: dict[str, int] = {"atlas": 400, "global": 460, "projects": 520, "obsidian": 600}

DECISION_RE = re.compile(r"\bD-0*(\d+)\b")
PHASE_RE = re.compile(r"\bPhase\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
MDLINK_RE = re.compile(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")
DECISION_DEF_RE = re.compile(r"(?:^|\n)[#*\s>]*D-0*(\d+)\b")


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()[:80]
    return fallback


def _section_kind(rel: Path) -> str:
    """Classify by ATLAS section if recognised, else by top-level folder slug.

    Returning the folder slug (rather than a generic "doc") lets the cockpit
    color each community distinctly via its palette fallback.
    """
    if rel.name in KIND_BY_NAME:
        return KIND_BY_NAME[rel.name]
    parts = rel.parts
    if parts and parts[0] in KIND_BY_DIR:
        return KIND_BY_DIR[parts[0]]
    if len(parts) > 1:
        return _slug(parts[0])
    return "doc"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "doc"


def _collect_md(base: Path, cap: int) -> list[Path]:
    """Walk ``base`` for ``*.md`` files, pruning noise dirs, bounded to ``cap``.

    Prefers shallow/top-level docs (most index-like) when over budget.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                found.append(Path(dirpath) / fn)
    found.sort(key=lambda p: (len(p.relative_to(base).parts), p.as_posix().lower()))
    return found[:cap]


def _build(
    base: Path,
    files: list[Path],
    root_label: str,
    kind_fn: Callable[[Path], str],
    group_fn: Callable[[Path], str] | None = None,
) -> dict[str, Any]:
    """Core builder: turn ``files`` (under ``base``) into a {nodes, links} graph."""
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
    ensure_node("root", root_label, "group", "root", size=0)

    for path in files:
        rel = path.relative_to(base)
        node_id = rel.as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        texts[node_id] = text
        rel_by_id[node_id] = rel
        group = (group_fn(rel) if group_fn else (rel.parts[0] if len(rel.parts) > 1 else "root"))
        ensure_node(node_id, _title(text, path.stem), kind_fn(rel), group, size=len(text))
        # Folder-hub node for each ancestor directory (readable backbone).
        for depth in range(1, len(rel.parts)):
            folder = "/".join(rel.parts[:depth])
            ensure_node(f"dir:{folder}", rel.parts[depth - 1], "group", group, size=0)

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

    decision_def: dict[str, str] = {}
    for node_id, text in texts.items():
        for num in DECISION_DEF_RE.findall(text):
            decision_def.setdefault(num, node_id)
    roadmap_id = by_basename.get("roadmap.md")

    phase_hub: dict[str, str] = {}
    for node_id in node_ids:
        if node_id.startswith("dir:") and "phases/" in node_id:
            folder_name = node_id.rsplit("/", 1)[-1]
            match = re.match(r"(\d+(?:\.\d+)*)", folder_name)
            if match:
                phase_hub[match.group(1)] = node_id

    for node_id, text in texts.items():
        rel = rel_by_id[node_id]
        for raw in MDLINK_RE.findall(text):
            target = (base / rel.parent / raw).resolve()
            try:
                target_id = target.relative_to(base).as_posix()
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

    return {"nodes": nodes, "links": links, "counts": {"nodes": len(nodes), "links": len(links)}}


def _build_projects(projects_dir: Path, cap: int) -> dict[str, Any]:
    """One cluster per sibling project: scan each project's top docs + ``.planning``."""
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    texts: dict[str, str] = {}
    rel_by_id: dict[str, str] = {}  # node_id -> project slug

    def ensure_node(node_id: str, label: str, kind: str, group: str, size: int = 0) -> None:
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, "label": label, "kind": kind, "group": group, "size": size})

    def add_link(source: str, target: str, kind: str) -> None:
        if source == target or source not in node_ids or target not in node_ids:
            return
        key = (source, target)
        if key in seen or (target, source) in seen:
            return
        seen.add(key)
        links.append({"source": source, "target": target, "kind": kind})

    ensure_node("root", "Projects", "group", "root", size=0)
    projects = sorted(p for p in projects_dir.iterdir() if p.is_dir() and not p.name.startswith("."))
    per_project = max(8, cap // max(1, len(projects)))

    by_basename: dict[str, str] = {}
    for proj in projects:
        slug = _slug(proj.name)
        hub = f"proj:{slug}"
        ensure_node(hub, proj.name, "group", slug, size=0)
        add_link("root", hub, "contains")
        # Bounded per-project corpus: top-level docs + one level of .planning.
        candidates: list[Path] = sorted(proj.glob("*.md"))
        planning = proj / ".planning"
        if planning.is_dir():
            candidates += sorted(planning.glob("*.md")) + sorted(planning.glob("*/*.md"))
        for path in candidates[:per_project]:
            rel = path.relative_to(proj).as_posix()
            node_id = f"{slug}/{rel}"
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            ensure_node(node_id, _title(text, path.stem), slug, slug, size=len(text))
            add_link(hub, node_id, "contains")
            texts[node_id] = text
            rel_by_id[node_id] = slug
            by_basename.setdefault(Path(node_id).name.lower(), node_id)
            by_basename.setdefault(Path(node_id).stem.lower(), node_id)

    # Wikilink cross-refs (often the same doc family references siblings).
    for node_id, text in texts.items():
        for raw in WIKILINK_RE.findall(text):
            key = raw.strip().lower()
            target_id = by_basename.get(key) or by_basename.get(f"{key}.md")
            if target_id:
                add_link(node_id, target_id, "wikilink")

    return {"nodes": nodes, "links": links, "counts": {"nodes": len(nodes), "links": len(links)}}


def build_graph(
    root: str | None = None,
    scope: str = "atlas",
    override_root: str | None = None,
) -> dict[str, Any]:
    """Build the knowledge graph for ``scope``.

    Returns ``{"nodes": [...], "links": [...], "root": str, "scope": str,
    "counts": {...}}``. Each node: ``{id, label, kind, group, size}``; hub nodes
    use ``kind:"group"``. Each link: ``{source, target, kind}`` where kind is one
    of ``contains | link | wikilink | phase | decision``.

    ``override_root`` repoints the folder-backed built-ins (projects/obsidian)
    to an operator-chosen path, taking precedence over the env var and default.
    """
    scope = (scope or "atlas").lower()
    base = Path(root or ".").resolve()
    cap = SCOPE_CAP.get(scope, 500)
    empty = {"nodes": [], "links": [], "root": str(base), "scope": scope, "counts": {"nodes": 0, "links": 0}}

    if scope == "atlas":
        planning = base / ".planning"
        if not planning.is_dir():
            return empty
        files = sorted(p for p in planning.rglob("*.md") if p.is_file())[:cap]
        out = _build(planning, files, ".planning", _section_kind)
        out.update(root=str(base), scope=scope)
        return out

    if scope == "global":
        files = _collect_md(base, cap)
        if not files:
            return empty
        out = _build(base, files, base.name, _section_kind)
        out.update(root=str(base), scope=scope)
        return out

    if scope == "obsidian":
        vault = Path(override_root or os.environ.get("ATLAS_OBSIDIAN_DIR", DEFAULT_OBSIDIAN))
        if not vault.is_dir():
            return {**empty, "root": str(vault), "error": "vault not found"}
        files = _collect_md(vault, cap)
        # Color obsidian by top-level theme folder.
        out = _build(vault, files, vault.name, lambda rel: _slug(rel.parts[0]) if len(rel.parts) > 1 else "note")
        out.update(root=str(vault), scope=scope)
        return out

    if scope == "projects":
        projects_dir = Path(override_root or os.environ.get("ATLAS_PROJECTS_DIR", DEFAULT_PROJECTS))
        if not projects_dir.is_dir():
            return {**empty, "root": str(projects_dir), "error": "projects dir not found"}
        out = _build_projects(projects_dir, cap)
        out.update(root=str(projects_dir), scope=scope)
        return out

    return empty


def build_custom_graph(
    scope_id: str, root_path: str, kind: str = "markdown"
) -> dict[str, Any]:
    """Build a graph for an operator-defined scope (0025 graph_scopes row).

    ``markdown`` treats the folder as one corpus (like ``global``); ``projects``
    builds one cluster per child directory (like the built-in projects view but
    over the user's chosen folder). A missing folder returns an empty graph
    with an ``error`` field — never raises into the serving path.
    """
    base = Path(root_path)
    empty = {
        "nodes": [],
        "links": [],
        "root": str(base),
        "scope": scope_id,
        "counts": {"nodes": 0, "links": 0},
    }
    if not base.is_dir():
        return {**empty, "error": "folder not found"}
    if kind == "projects":
        out = _build_projects(base, SCOPE_CAP["projects"])
    else:
        files = _collect_md(base, SCOPE_CAP["global"])
        if not files:
            return {**empty, "error": "no markdown files found"}
        out = _build(
            base,
            files,
            base.name,
            lambda rel: _slug(rel.parts[0]) if len(rel.parts) > 1 else "doc",
        )
    out.update(root=str(base), scope=scope_id)
    return out
