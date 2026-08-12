"""ATLAS module service — registry, manifest discovery, activation, scaffolding.

A Module is an optional capability the operator turns on from the System page
(Decision 3b). Off by default so the base install stays lean. DDL in
0007_modules.sql, manifest columns in 0023_module_manifests.sql; schema in
atlas_core.schemas.core.Module.

Two module sources share one registry (docs/plans/2026-07-16-module-framework-design.md):
  - seeded built-ins (e.g. cashflow) — rows without a manifest;
  - manifest modules — directories containing `module.yaml`, discovered from
    `<repo>/modules/` (bundled) and `<ATLAS home>/modules/` (user/agent
    installed).

Capabilities are declarative in every version — a module is data, ATLAS is the
only thing that executes (docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md):

  v1  commands  — slash commands served to every surface via the gateway
      pages     — schema-driven WebUI pages rendered by ATLAS-owned components
  v2  context   — doctrine files injected into the run brief while active
      collections — typed record schemas backed by module_records (0034)
      workflows — named plays the agent fetches and executes
      mcp       — MCP servers projected onto the foundation when enabled

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
# Field/collection/workflow ids allow underscores — they are data keys, not URL
# slugs, and snake_case reads better in a record payload.
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MCP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
# Credential-shaped env keys must carry a ${VAR} reference, never a value.
_SECRET_KEY_RE = re.compile(r"(?i)(token|key|secret|password|passwd|credential)")
_ENV_REF_ONLY_RE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

# Built-in slash command names (both UI catalogs); module commands never shadow them.
RESERVED_COMMANDS = frozenset(
    {"init", "review", "dream", "distill", "goal", "mission", "deep-research"}
)

PAGE_BLOCK_KINDS = (
    # v1
    "heading", "markdown", "metrics", "actions",
    # v2 (docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md)
    "tabs", "records", "stat_row", "divider",
)

# Capability v2 vocabularies. Unknown values are rejected at sync time so a
# typo fails loudly at install instead of silently disabling a capability.
FIELD_TYPES = (
    "text", "longtext", "enum", "number", "date", "bool", "url", "tags", "ref",
)
INJECT_MODES = ("always", "matched", "on_demand")
MCP_TRANSPORTS = ("stdio", "http")

# Prompt-budget guardrails for injected module doctrine. Memory v2 spent a whole
# work package getting the prompt down; a module must not be able to undo that.
DEFAULT_CONTEXT_TOKENS = 700
MAX_CONTEXT_TOKENS = 1500
DEFAULT_MODULE_CONTEXT_BUDGET = 1800


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
        _validate_blocks(blocks, source=source, page_id=pid)
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
        "author": str(data.get("author") or "").strip(),
        "capabilities": {
            "commands": commands,
            "pages": pages,
            "context": _validate_context(caps.get("context"), source=source),
            "collections": _validate_collections(caps.get("collections"), source=source),
            "workflows": _validate_workflows(caps.get("workflows"), source=source),
            "mcp": _validate_mcp(caps.get("mcp"), source=source),
        },
    }


def _validate_blocks(blocks: list[Any], *, source: str, page_id: str) -> None:
    """Recursively check page blocks. `tabs` nests blocks, so this recurses.

    Unknown kinds are allowed through (the renderers degrade them to a labeled
    placeholder, which is how an older build survives a newer manifest); a block
    without a `kind` is not, because nothing can render it.
    """
    for block in blocks:
        if not isinstance(block, dict) or "kind" not in block:
            raise ValueError(f"{source}: page {page_id!r} has a block without kind")
        if block.get("kind") == "tabs":
            tabs = block.get("tabs") or []
            if not isinstance(tabs, list) or not tabs:
                raise ValueError(f"{source}: page {page_id!r} tabs block needs a tabs list")
            for tab in tabs:
                if not isinstance(tab, dict) or not str(tab.get("id") or "").strip():
                    raise ValueError(f"{source}: page {page_id!r} tab needs an id")
                nested = tab.get("blocks") or []
                if not isinstance(nested, list):
                    raise ValueError(f"{source}: page {page_id!r} tab blocks must be a list")
                _validate_blocks(nested, source=source, page_id=page_id)


def _validate_context(raw_list: Any, *, source: str) -> list[dict[str, Any]]:
    """Doctrine files injected into the run brief while the module is active."""
    out: list[dict[str, Any]] = []
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: context entries must be mappings")
        cid = str(raw.get("id") or "").strip()
        if not _KEY_RE.match(cid):
            raise ValueError(f"{source}: invalid context id {cid!r}")
        path = str(raw.get("path") or "").strip().replace("\\", "/")
        if not path:
            raise ValueError(f"{source}: context {cid!r} needs a path")
        if path.startswith("/") or ".." in path.split("/"):
            # The path is joined onto the module directory; escaping it would
            # let a manifest inject any file on disk into the prompt.
            raise ValueError(f"{source}: context {cid!r} path must stay inside the module")
        inject = str(raw.get("inject") or "always").strip()
        if inject not in INJECT_MODES:
            raise ValueError(f"{source}: context {cid!r} inject must be one of {INJECT_MODES}")
        terms = [str(t).strip().lower() for t in (raw.get("terms") or []) if str(t).strip()]
        if inject == "matched" and not terms:
            raise ValueError(f"{source}: context {cid!r} inject=matched needs terms")
        max_tokens = int(raw.get("max_tokens") or DEFAULT_CONTEXT_TOKENS)
        out.append(
            {
                "id": cid,
                "title": str(raw.get("title") or cid).strip(),
                "path": path,
                "inject": inject,
                "terms": terms,
                "max_tokens": max(1, min(max_tokens, MAX_CONTEXT_TOKENS)),
            }
        )
    return out


def _validate_field(raw: Any, *, source: str, collection_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: collection {collection_id!r} fields must be mappings")
    fname = str(raw.get("name") or "").strip()
    if not _KEY_RE.match(fname):
        raise ValueError(f"{source}: collection {collection_id!r} invalid field name {fname!r}")
    ftype = str(raw.get("type") or "text").strip()
    if ftype not in FIELD_TYPES:
        raise ValueError(
            f"{source}: collection {collection_id!r} field {fname!r} has unknown type {ftype!r}"
        )
    field: dict[str, Any] = {
        "name": fname,
        "type": ftype,
        "title": str(raw.get("title") or fname.replace("_", " ").title()).strip(),
        "required": bool(raw.get("required", False)),
    }
    if ftype == "enum":
        options = [str(o).strip() for o in (raw.get("options") or []) if str(o).strip()]
        if not options:
            raise ValueError(
                f"{source}: collection {collection_id!r} enum field {fname!r} needs options"
            )
        field["options"] = options
    if ftype == "ref":
        ref = str(raw.get("ref_collection") or "").strip()
        if not _KEY_RE.match(ref):
            raise ValueError(
                f"{source}: collection {collection_id!r} ref field {fname!r} needs ref_collection"
            )
        field["ref_collection"] = ref
    if ftype == "number":
        for bound in ("min", "max"):
            if raw.get(bound) is not None:
                field[bound] = float(raw[bound])
    if raw.get("default") is not None:
        field["default"] = raw["default"]
    if raw.get("description"):
        field["description"] = str(raw["description"]).strip()
    return field


def _validate_collections(raw_list: Any, *, source: str) -> list[dict[str, Any]]:
    """Typed record collections — the module's own persistent data model."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: collection entries must be mappings")
        cid = str(raw.get("id") or "").strip()
        if not _KEY_RE.match(cid):
            raise ValueError(f"{source}: invalid collection id {cid!r}")
        if cid in seen:
            raise ValueError(f"{source}: duplicate collection id {cid!r}")
        seen.add(cid)
        fields = [
            _validate_field(f, source=source, collection_id=cid) for f in (raw.get("fields") or [])
        ]
        if not fields:
            raise ValueError(f"{source}: collection {cid!r} declares no fields")
        names = {f["name"] for f in fields}
        label_field = str(raw.get("label_field") or fields[0]["name"]).strip()
        if label_field not in names:
            raise ValueError(f"{source}: collection {cid!r} label_field {label_field!r} not a field")
        out.append(
            {
                "id": cid,
                "title": str(raw.get("title") or cid.replace("_", " ").title()).strip(),
                "icon": str(raw.get("icon") or "").strip(),
                "description": str(raw.get("description") or "").strip(),
                "label_field": label_field,
                "sort": str(raw.get("sort") or "-updated_at").strip(),
                "fields": fields,
            }
        )
    return out


def _validate_workflows(raw_list: Any, *, source: str) -> list[dict[str, Any]]:
    """Named plays: ordered steps the agent fetches and executes itself."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: workflow entries must be mappings")
        wid = str(raw.get("id") or "").strip()
        if not _KEY_RE.match(wid):
            raise ValueError(f"{source}: invalid workflow id {wid!r}")
        if wid in seen:
            raise ValueError(f"{source}: duplicate workflow id {wid!r}")
        seen.add(wid)
        steps = [str(s).strip() for s in (raw.get("steps") or []) if str(s).strip()]
        if not steps:
            raise ValueError(f"{source}: workflow {wid!r} declares no steps")
        out.append(
            {
                "id": wid,
                "title": str(raw.get("title") or wid.replace("_", " ").title()).strip(),
                "description": str(raw.get("description") or "").strip(),
                "inputs": [str(i).strip() for i in (raw.get("inputs") or []) if str(i).strip()],
                "steps": steps,
                "done_when": str(raw.get("done_when") or "").strip(),
            }
        )
    return out


def _validate_mcp(raw_list: Any, *, source: str) -> list[dict[str, Any]]:
    """MCP servers the module wants available to the agent.

    Declared, never auto-enabled: an install must not silently start talking to
    a third-party process. Env values hold `${VAR}` references, not secrets —
    a literal-looking credential is rejected here rather than committed to a
    manifest that ships in a repo.
    """
    from atlas_core.schemas.core import SECRET_PATTERNS  # noqa: PLC0415

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_list or []:
        if not isinstance(raw, dict):
            raise ValueError(f"{source}: mcp entries must be mappings")
        mname = str(raw.get("name") or "").strip()
        if not _MCP_NAME_RE.match(mname):
            raise ValueError(f"{source}: invalid mcp server name {mname!r}")
        if mname in seen:
            raise ValueError(f"{source}: duplicate mcp server {mname!r}")
        seen.add(mname)
        transport = str(raw.get("transport") or "stdio").strip()
        if transport not in MCP_TRANSPORTS:
            raise ValueError(f"{source}: mcp {mname!r} transport must be one of {MCP_TRANSPORTS}")
        command = str(raw.get("command") or "").strip()
        url = str(raw.get("url") or "").strip()
        if transport == "stdio" and not command:
            raise ValueError(f"{source}: mcp {mname!r} (stdio) needs a command")
        if transport == "http" and not url:
            raise ValueError(f"{source}: mcp {mname!r} (http) needs a url")
        env_raw = raw.get("env") or {}
        if not isinstance(env_raw, dict):
            raise ValueError(f"{source}: mcp {mname!r} env must be a mapping")
        env = {str(k): str(v) for k, v in env_raw.items()}
        for key, value in env.items():
            # A credential-shaped key must carry a reference, not a value. This
            # catches the common mistake directly; SECRET_PATTERNS then catches
            # a secret smuggled under an innocuous key name.
            if _SECRET_KEY_RE.search(key) and not _ENV_REF_ONLY_RE.match(value):
                raise ValueError(
                    f"{source}: mcp {mname!r} env {key!r} looks like a literal secret — "
                    "use ${ENV_VAR} indirection"
                )
            if any(pattern.search(f"{key}={value}") for pattern in SECRET_PATTERNS):
                raise ValueError(
                    f"{source}: mcp {mname!r} env {key!r} looks like a literal secret — "
                    "use ${ENV_VAR} indirection"
                )
        out.append(
            {
                "name": mname,
                "transport": transport,
                "command": command,
                "args": [str(a) for a in (raw.get("args") or [])],
                "env": env,
                "url": url,
                "description": str(raw.get("description") or "").strip(),
                "enabled": bool(raw.get("enabled", False)),
            }
        )
    return out


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


# ---------------------------------------------------------------------------
# Capability v2 reads — every one filters on active AND present, so deactivating
# a module removes its capability from every surface without deleting anything.
# ---------------------------------------------------------------------------


def active_manifests(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Parsed manifests of active, present modules, ordered by id.

    Each manifest carries `source_path` (set at discovery) so callers can resolve
    declared files relative to the module directory.
    """
    out: list[dict[str, Any]] = []
    rows = conn.execute(
        "SELECT manifest_json FROM modules"
        " WHERE status='active' AND missing=0 AND manifest_json != ''"
        " ORDER BY id"
    ).fetchall()
    for (manifest_json,) in rows:
        try:
            manifest = json.loads(manifest_json)
        except json.JSONDecodeError:
            continue
        if isinstance(manifest, dict) and manifest.get("id"):
            out.append(manifest)
    return out


def capability(manifest: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """capabilities[key] as a list — tolerant of v1 manifests missing the key."""
    caps = manifest.get("capabilities") or {}
    value = caps.get(key) or []
    return value if isinstance(value, list) else []


def find_collection(
    manifest: dict[str, Any], collection_id: str
) -> Optional[dict[str, Any]]:
    """The collection schema with this id, or None."""
    for coll in capability(manifest, "collections"):
        if coll.get("id") == collection_id:
            return coll
    return None


def active_manifest(conn: sqlite3.Connection, module_id: str) -> Optional[dict[str, Any]]:
    """Manifest of `module_id` when it is active and present; else None.

    The single gate every capability read goes through — an inactive module is
    indistinguishable from an absent one at the capability layer.
    """
    row = conn.execute(
        "SELECT manifest_json FROM modules"
        " WHERE id=? AND status='active' AND missing=0 AND manifest_json != ''",
        (module_id,),
    ).fetchone()
    if row is None or not row[0]:
        return None
    try:
        manifest = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    return manifest if isinstance(manifest, dict) else None


def read_context_file(manifest: dict[str, Any], entry: dict[str, Any]) -> str:
    """Read one declared doctrine file. Missing/unreadable -> empty string.

    The path was validated at sync time to stay inside the module directory;
    it is re-resolved here and checked again, because the manifest row in the
    DB could have been written by an older, laxer validator.
    """
    root = Path(str(manifest.get("source_path") or ""))
    if not root.is_dir():
        return ""
    target = (root / str(entry.get("path") or "")).resolve()
    try:
        if not target.is_file() or root.resolve() not in target.parents:
            return ""
        return target.read_text(encoding="utf-8")
    except OSError:
        return ""


def active_context_blocks(
    conn: sqlite3.Connection,
    *,
    terms: tuple[str, ...] = (),
    token_budget: int = DEFAULT_MODULE_CONTEXT_BUDGET,
) -> list[dict[str, Any]]:
    """Doctrine blocks to inject for the active modules, under a token budget.

    `inject: always` blocks come first (they are what the operator said must
    always be present), then `matched` blocks whose declared terms overlap the
    run's terms. `on_demand` never auto-injects — the agent fetches it with
    `atlas_module op=context`. Each block is truncated to its own `max_tokens`
    and the whole set to `token_budget`; content is redacted by the caller's
    context assembly, same as every other dynamic source.
    """
    from atlas_runtime.memory_router import estimate_tokens  # noqa: PLC0415

    lowered = {t.lower() for t in terms}
    always: list[tuple[dict[str, Any], dict[str, Any]]] = []
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for manifest in active_manifests(conn):
        for entry in capability(manifest, "context"):
            mode = entry.get("inject", "always")
            if mode == "always":
                always.append((manifest, entry))
            elif mode == "matched" and lowered & set(entry.get("terms") or []):
                matched.append((manifest, entry))

    blocks: list[dict[str, Any]] = []
    used = 0
    for manifest, entry in always + matched:
        text = read_context_file(manifest, entry).strip()
        if not text:
            continue
        limit = int(entry.get("max_tokens") or DEFAULT_CONTEXT_TOKENS)
        # 4 chars/token is the estimator's own ratio (memory_router).
        if estimate_tokens(text) > limit:
            text = text[: limit * 4].rstrip() + "\n\n_(truncated at the module context budget)_"
        tokens = estimate_tokens(text)
        if blocks and used + tokens > token_budget:
            continue
        used += tokens
        blocks.append(
            {
                "module_id": manifest.get("id", ""),
                "module_name": manifest.get("name", ""),
                "id": entry.get("id", ""),
                "title": entry.get("title", ""),
                "text": text,
                "tokens": tokens,
            }
        )
    return blocks


def module_mcp_declarations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """MCP server declarations from active modules, tagged with their module."""
    out: list[dict[str, Any]] = []
    for manifest in active_manifests(conn):
        for server in capability(manifest, "mcp"):
            entry = dict(server)
            entry["module_id"] = manifest.get("id", "")
            out.append(entry)
    return out


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
        You are executing the {name} module command. Read the module doctrine
        with atlas_module(op="context", module="{module_id}") first.
        Operator input: $ARGUMENTS
  context:
    - id: doctrine
      title: {name} doctrine
      path: context/doctrine.md
      inject: always
      max_tokens: 500
  collections:
    - id: items
      title: Items
      label_field: title
      fields:
        - name: title
          type: text
          required: true
        - name: status
          type: enum
          options: [open, doing, done]
          default: open
        - name: notes
          type: longtext
  workflows:
    - id: run
      title: Run the {name} flow
      description: Replace these steps with the real play.
      steps:
        - Read the module doctrine and the open items.
        - Do the work; record what changed as records.
        - Report what is verified and what is still assumed.
      done_when: Every open item has an outcome recorded.
  pages:
    - id: main
      title: {name}
      icon: puzzle
      blocks:
        - kind: heading
          text: {name}
        - kind: tabs
          tabs:
            - id: overview
              label: Overview
              blocks:
                - kind: markdown
                  text: >
                    Scaffolded by `atlas module create`. Edit module.yaml to
                    change doctrine, collections, workflows, commands and pages.
                - kind: actions
                  items:
                    - label: Run {name}
                      command: /{module_id}
            - id: items
              label: Items
              blocks:
                - kind: records
                  collection: items
                  columns: [title, status]
"""

SCAFFOLD_DOCTRINE = """\
# {name} doctrine

Injected into every run while this module is active, so keep it short and
operational. Replace this with the rules that must hold whenever the agent
works on {name}:

- What this module is for, in one sentence.
- The constraints that must never be violated.
- The definition of done.
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
    # The scaffold declares a doctrine file, so it must also create one:
    # a manifest pointing at a missing file injects nothing and looks broken.
    context_dir = target / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "doctrine.md").write_text(
        SCAFFOLD_DOCTRINE.format(name=display), encoding="utf-8"
    )
    return target
