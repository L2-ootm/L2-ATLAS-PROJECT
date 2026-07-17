"""ATLAS module service — registry, manifest discovery, activation, scaffolding.

A Module is an optional capability the operator turns on from the System page
(Decision 3b). Off by default so the base install stays lean. DDL in
0007_modules.sql, manifest columns in 0023_module_manifests.sql; schema in
atlas_core.schemas.core.Module.

Two module sources share one registry (docs/plans/2026-07-16-module-framework-design.md):
  - seeded built-ins (e.g. cashflow) — rows without a manifest;
  - manifest modules — directories containing `module.yaml`, discovered from
    `<repo>/modules/` (bundled) and `<ATLAS home>/modules/` (user/agent
    installed). v1 capabilities are declarative only: slash `commands`
    (served to every surface via the gateway) and schema-driven WebUI
    `pages`. No module code executes anywhere in v1.

Conventions follow project_service.py:
  - Pydantic-first reads (rows hydrate the frozen model).
  - All mutations go through the service layer with lock injection.
  - Toggling is idempotent (activating an active module is a no-op).
"""
from __future__ import annotations

import datetime
import json
import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

import yaml

from atlas_core.schemas.core import Module
from atlas_runtime import db as atlas_db

logger = logging.getLogger(__name__)

MODULE_FILE = "module.yaml"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Built-in slash command names (both UI catalogs); module commands never shadow them.
RESERVED_COMMANDS = frozenset(
    {"init", "review", "dream", "distill", "goal", "mission", "deep-research"}
)

PAGE_BLOCK_KINDS = ("heading", "markdown", "metrics", "actions")


class ModuleError(ValueError):
    """Raised for unknown module ids or invalid status transitions."""


def list_modules(conn: sqlite3.Connection) -> list[Module]:
    """Return all modules ordered by id ASC."""
    cursor = conn.execute("SELECT * FROM modules ORDER BY id ASC")
    cols = [d[0] for d in cursor.description]
    return [Module(**dict(zip(cols, row))) for row in cursor]


def get_module(conn: sqlite3.Connection, module_id: str) -> Module | None:
    """Return the Module for the given id, or None if not found."""
    cursor = conn.execute("SELECT * FROM modules WHERE id=?", (module_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    return None if row is None else Module(**dict(zip(cols, row)))


def set_active(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    module_id: str,
    active: bool,
) -> Module:
    """Activate or deactivate a module. Idempotent. Returns the updated Module."""
    status = "active" if active else "inactive"
    activated_at = datetime.datetime.now(datetime.timezone.utc).isoformat() if active else None
    with lock:
        with conn:
            existing = conn.execute(
                "SELECT id FROM modules WHERE id=?", (module_id,)
            ).fetchone()
            if existing is None:
                raise ModuleError(f"unknown module: {module_id!r}")
            conn.execute(
                "UPDATE modules SET status=?, activated_at=? WHERE id=?",
                (status, activated_at, module_id),
            )
    updated = get_module(conn, module_id)
    assert updated is not None  # just updated it
    return updated


# ---------------------------------------------------------------------------
# Manifest modules (module framework slice 1)
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def bundled_modules_dir() -> Path:
    """<repo>/modules — manifest modules shipped with the checkout."""
    return Path(__file__).resolve().parents[3] / "modules"


def user_modules_dir() -> Path:
    """<ATLAS home>/modules — operator/agent-installed manifest modules.

    Derived from the DB home at call time (ATLAS_DB/ATLAS_HOME aware) — the
    same pattern freellmapi's sidecar_home() uses.
    """
    return atlas_db.default_db_path().parent / "modules"


def validate_manifest(data: Any, *, source: str = "") -> dict[str, Any]:
    """Validate + normalize a parsed module.yaml. Raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError(f"{source}: manifest must be a mapping")
    module_id = str(data.get("id") or "").strip()
    if not _ID_RE.match(module_id):
        raise ValueError(f"{source}: invalid module id {module_id!r} (want [a-z0-9-])")
    name = str(data.get("name") or module_id).strip()
    version = str(data.get("version") or "0.0.0").strip()
    description = str(data.get("description") or "").strip()
    caps = data.get("capabilities") or {}
    if not isinstance(caps, dict):
        raise ValueError(f"{source}: capabilities must be a mapping")

    commands: list[dict[str, str]] = []
    for raw in caps.get("commands") or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: command entries must be mappings")
        cname = str(raw.get("name") or "").strip().lstrip("/")
        template = str(raw.get("template") or "").strip()
        if not _ID_RE.match(cname):
            raise ValueError(f"{source}: invalid command name {cname!r}")
        if not template:
            raise ValueError(f"{source}: command {cname!r} needs a template")
        commands.append(
            {
                "name": cname,
                "description": str(raw.get("description") or "").strip(),
                "template": template,
            }
        )

    pages: list[dict[str, Any]] = []
    for raw in caps.get("pages") or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: page entries must be mappings")
        pid = str(raw.get("id") or "main").strip()
        blocks = raw.get("blocks") or []
        if not isinstance(blocks, list):
            raise ValueError(f"{source}: page {pid!r} blocks must be a list")
        for block in blocks:
            if not isinstance(block, dict) or "kind" not in block:
                raise ValueError(f"{source}: page {pid!r} has a block without kind")
        pages.append(
            {
                "id": pid,
                "title": str(raw.get("title") or name).strip(),
                "icon": str(raw.get("icon") or "").strip(),
                "blocks": blocks,
            }
        )

    return {
        "id": module_id,
        "name": name,
        "version": version,
        "description": description,
        "capabilities": {"commands": commands, "pages": pages},
    }


def discover_modules(
    roots: Optional[list[Path]] = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scan module roots for `<dir>/module.yaml`. Returns (manifests, problems).

    Invalid manifests are reported, never fatal — one broken user module must
    not take discovery down. Later roots do not override earlier ids (bundled
    wins over user on collision; the collision is reported).
    """
    if roots is None:
        roots = [bundled_modules_dir(), user_modules_dir()]
    manifests: list[dict[str, Any]] = []
    problems: list[str] = []
    seen: set[str] = set()
    for root in roots:
        try:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                manifest_path = child / MODULE_FILE
                if not manifest_path.is_file():
                    continue
                try:
                    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                    manifest = validate_manifest(data, source=str(manifest_path))
                except Exception as exc:  # noqa: BLE001 — report, keep scanning
                    problems.append(f"{manifest_path}: {exc}")
                    continue
                if manifest["id"] in seen:
                    problems.append(
                        f"{manifest_path}: duplicate module id {manifest['id']!r} ignored"
                    )
                    continue
                seen.add(manifest["id"])
                manifest["source_path"] = str(child)
                manifests.append(manifest)
        except OSError as exc:
            problems.append(f"{root}: {exc}")
    return manifests, problems


def sync_modules(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    roots: Optional[list[Path]] = None,
) -> dict[str, Any]:
    """Upsert discovered manifest modules into the registry.

    Operator activation state (`status`) survives re-sync; newly discovered
    modules start inactive (base install stays lean — same 0007 philosophy).
    Manifest rows whose source directory is gone are flagged missing=1 (state
    kept); reappearing modules clear the flag. Seeded built-ins (no
    source_path) are never touched. Returns a summary dict.
    """
    manifests, problems = discover_modules(roots)
    now = _now()
    discovered_ids = {m["id"] for m in manifests}
    with lock:
        with conn:
            for manifest in manifests:
                conn.execute(
                    "INSERT INTO modules(id, name, description, status, version,"
                    " source_path, manifest_json, missing, updated_at)"
                    " VALUES (?,?,?,'inactive',?,?,?,0,?)"
                    " ON CONFLICT(id) DO UPDATE SET"
                    " name=excluded.name, description=excluded.description,"
                    " version=excluded.version, source_path=excluded.source_path,"
                    " manifest_json=excluded.manifest_json, missing=0,"
                    " updated_at=excluded.updated_at",
                    (
                        manifest["id"],
                        manifest["name"],
                        manifest["description"],
                        manifest["version"],
                        manifest["source_path"],
                        json.dumps(manifest),
                        now,
                    ),
                )
            known = conn.execute(
                "SELECT id FROM modules WHERE source_path != ''"
            ).fetchall()
            for (module_id,) in known:
                if module_id not in discovered_ids:
                    conn.execute(
                        "UPDATE modules SET missing=1, updated_at=? WHERE id=?",
                        (now, module_id),
                    )
    missing = [
        r[0] for r in conn.execute("SELECT id FROM modules WHERE missing=1").fetchall()
    ]
    return {"discovered": sorted(discovered_ids), "missing": missing, "problems": problems}


def get_manifest(conn: sqlite3.Connection, module_id: str) -> Optional[dict[str, Any]]:
    """Parsed manifest for a module, or None (unknown / built-in without one)."""
    row = conn.execute(
        "SELECT manifest_json FROM modules WHERE id=?", (module_id,)
    ).fetchone()
    if row is None or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def module_commands(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """Slash commands contributed by active, present manifest modules.

    Collisions with built-in command names or an earlier module's command are
    dropped (built-ins win; first module wins) so a module can never shadow
    core behavior.
    """
    commands: list[dict[str, str]] = []
    taken = set(RESERVED_COMMANDS)
    rows = conn.execute(
        "SELECT id, manifest_json FROM modules"
        " WHERE status='active' AND missing=0 AND manifest_json != ''"
        " ORDER BY id"
    ).fetchall()
    for module_id, manifest_json in rows:
        try:
            manifest = json.loads(manifest_json)
        except json.JSONDecodeError:
            continue
        for command in manifest.get("capabilities", {}).get("commands", []):
            name = command.get("name", "")
            if not name or name in taken:
                continue
            taken.add(name)
            commands.append(
                {
                    "name": name,
                    "description": command.get("description", ""),
                    "template": command.get("template", ""),
                    "module": module_id,
                }
            )
    return commands


SCAFFOLD_MANIFEST = """\
id: {module_id}
name: {name}
version: 0.1.0
description: Describe what this module does.
author: operator
capabilities:
  commands:
    - name: {module_id}
      description: run the {name} flow
      template: |
        You are executing the {name} module command. $ARGUMENTS
  pages:
    - id: main
      title: {name}
      icon: puzzle
      blocks:
        - kind: heading
          text: {name}
        - kind: markdown
          text: >
            This page was scaffolded by `atlas module create`. Edit
            module.yaml to change blocks, commands, and actions.
        - kind: actions
          items:
            - label: Run {name}
              command: /{module_id}
"""


def create_module_scaffold(
    module_id: str,
    *,
    name: Optional[str] = None,
    target_root: Optional[Path] = None,
) -> Path:
    """Scaffold a valid manifest module directory (the self-wiring entry point).

    The agent and the operator use the same path (`atlas module create`).
    Refuses to overwrite an existing module directory.
    """
    if not _ID_RE.match(module_id):
        raise ValueError(f"invalid module id {module_id!r} (want [a-z0-9-])")
    root = target_root or user_modules_dir()
    target = root / module_id
    if target.exists():
        raise ValueError(f"module directory already exists: {target}")
    display = name or module_id.replace("-", " ").title()
    manifest = SCAFFOLD_MANIFEST.format(module_id=module_id, name=display)
    # validate what we scaffold — a broken template must fail loudly here
    validate_manifest(yaml.safe_load(manifest), source="scaffold")
    target.mkdir(parents=True)
    (target / MODULE_FILE).write_text(manifest, encoding="utf-8")
    return target
