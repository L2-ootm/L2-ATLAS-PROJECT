"""Typed record store behind module collections — the CRM substrate.

One generic table (`module_records`, migration 0034) serves every module's
declared collections. A module is data, so per-module DDL is the wrong shape:
uninstalling a module would become a schema migration, and a plugin store could
never review it. Instead the manifest declares fields and this module validates
payloads against that declaration on every write.

Contract (docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md):

  - **Active-only.** Every entry point resolves the collection through
    `module_service.active_manifest()`. An inactive, missing or unknown module
    has no reachable records — the data stays, the capability does not.
  - **Validated writes, tolerant reads.** `create`/`update` coerce and check
    values against the field types; reads return whatever is stored (a manifest
    can gain a field after rows exist, and old rows must still load).
  - **Bounded.** 64 KB per payload, 5,000 live rows per collection: a looping
    agent must not be able to fill the operator's database.
  - **Soft delete.** `delete()` stamps `deleted_at` and returns the removed
    payload, so a run transcript carries an undo record (same philosophy as
    `atlas_graph op=forget`).

Conventions follow project_service/module_service: Pydantic-free plain dicts
here (records are schemaless by design), all mutations take the shared lock,
and repeating an idempotent call converges instead of duplicating.
"""
from __future__ import annotations

import datetime
import json
import re
import sqlite3
import threading
import uuid
from typing import Any, Optional

from atlas_runtime import module_service

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_RECORDS_PER_COLLECTION = 5_000
DEFAULT_LIMIT = 50
MAX_LIMIT = 500

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class ModuleDataError(ValueError):
    """Unknown module/collection, invalid field value, or a bound exceeded."""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def resolve_collection(
    conn: sqlite3.Connection, module_id: str, collection_id: str
) -> dict[str, Any]:
    """The collection schema of an ACTIVE module, or raise ModuleDataError."""
    manifest = module_service.active_manifest(conn, module_id)
    if manifest is None:
        raise ModuleDataError(
            f"module {module_id!r} is not active (activate it with: atlas module activate {module_id})"
        )
    collection = module_service.find_collection(manifest, collection_id)
    if collection is None:
        known = [c["id"] for c in module_service.capability(manifest, "collections")]
        raise ModuleDataError(
            f"module {module_id!r} has no collection {collection_id!r}"
            f" (known: {', '.join(known) or 'none'})"
        )
    return collection


def _coerce(field: dict[str, Any], value: Any) -> Any:
    """Coerce one value to its declared type. Raises ModuleDataError."""
    name = field["name"]
    ftype = field["type"]
    if value is None:
        return None
    if ftype in ("text", "longtext", "url", "date"):
        text = str(value).strip()
        if ftype == "url" and text and not re.match(r"^[a-z][a-z0-9+.-]*:", text):
            # Bare domains are the common agent mistake; normalize rather than
            # reject, so a research pass does not fail on a missing scheme.
            text = f"https://{text}"
        if ftype == "date" and text and not re.match(r"^\d{4}-\d{2}-\d{2}", text):
            raise ModuleDataError(f"field {name!r} must be an ISO date (YYYY-MM-DD), got {text!r}")
        return text
    if ftype == "enum":
        text = str(value).strip()
        options = field.get("options") or []
        if text and text not in options:
            raise ModuleDataError(
                f"field {name!r} must be one of {', '.join(options)} (got {text!r})"
            )
        return text
    if ftype == "number":
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ModuleDataError(f"field {name!r} must be a number (got {value!r})") from exc
        if field.get("min") is not None and number < field["min"]:
            raise ModuleDataError(f"field {name!r} must be >= {field['min']}")
        if field.get("max") is not None and number > field["max"]:
            raise ModuleDataError(f"field {name!r} must be <= {field['max']}")
        return int(number) if number.is_integer() else number
    if ftype == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if ftype == "tags":
        if isinstance(value, str):
            items = [v.strip() for v in value.split(",")]
        elif isinstance(value, (list, tuple)):
            items = [str(v).strip() for v in value]
        else:
            raise ModuleDataError(f"field {name!r} must be a list or comma-separated string")
        return [v for v in items if v]
    if ftype == "ref":
        return str(value).strip()
    raise ModuleDataError(f"field {name!r} has unsupported type {ftype!r}")


def validate_payload(
    collection: dict[str, Any], data: dict[str, Any], *, partial: bool = False
) -> dict[str, Any]:
    """Coerce + check a payload against the collection schema.

    Unknown keys are rejected rather than silently dropped: an agent writing
    `stage` into a collection whose field is `status` should be told, not left
    believing the write landed.
    """
    if not isinstance(data, dict):
        raise ModuleDataError("record data must be a mapping")
    fields = {f["name"]: f for f in collection.get("fields", [])}
    unknown = [k for k in data if k not in fields]
    if unknown:
        raise ModuleDataError(
            f"unknown field(s) {', '.join(sorted(unknown))} for collection "
            f"{collection['id']!r} (known: {', '.join(fields) or 'none'})"
        )
    out: dict[str, Any] = {}
    for key, value in data.items():
        out[key] = _coerce(fields[key], value)
    if not partial:
        for name, field in fields.items():
            if name in out and out[name] not in (None, "", []):
                continue
            if field.get("default") is not None:
                out[name] = _coerce(field, field["default"])
            elif field.get("required"):
                raise ModuleDataError(f"field {name!r} is required")
    encoded = json.dumps(out, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ModuleDataError(
            f"record payload exceeds {MAX_PAYLOAD_BYTES} bytes — store the long form "
            "as a file and keep a path in the record"
        )
    return out


def _slug(text: str) -> str:
    slug = _SLUG_STRIP.sub("-", str(text).strip().lower()).strip("-")
    return slug[:48]


def derive_id(collection: dict[str, Any], data: dict[str, Any]) -> str:
    """A readable, stable id from the label field; uuid tail when unusable.

    Readable ids matter here: the agent refers to records by id across turns,
    and `prospect-gabriel` survives a context compaction in a way that a raw
    uuid does not.
    """
    label = data.get(collection.get("label_field", ""), "")
    slug = _slug(str(label))
    return slug or f"rec-{uuid.uuid4().hex[:12]}"


def _row_to_record(row: tuple) -> dict[str, Any]:
    (
        module_id, collection, rec_id, data_json, status,
        created_at, updated_at, deleted_at, created_by_run, updated_by_run,
    ) = row
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError:
        data = {}
    return {
        "module_id": module_id,
        "collection": collection,
        "id": rec_id,
        "data": data if isinstance(data, dict) else {},
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "deleted_at": deleted_at,
        "created_by_run": created_by_run,
        "updated_by_run": updated_by_run,
    }


_SELECT = (
    "SELECT module_id, collection, id, data_json, status, created_at, updated_at,"
    " deleted_at, created_by_run, updated_by_run FROM module_records"
)


def get_record(
    conn: sqlite3.Connection, module_id: str, collection_id: str, record_id: str
) -> Optional[dict[str, Any]]:
    """One live record, or None (deleted rows read as absent)."""
    row = conn.execute(
        f"{_SELECT} WHERE module_id=? AND collection=? AND id=? AND deleted_at IS NULL",
        (module_id, collection_id, record_id),
    ).fetchone()
    return None if row is None else _row_to_record(row)


def query_records(
    conn: sqlite3.Connection,
    module_id: str,
    collection_id: str,
    *,
    where: Optional[dict[str, Any]] = None,
    search: str = "",
    status: str = "active",
    limit: int = DEFAULT_LIMIT,
    include_deleted: bool = False,
) -> list[dict[str, Any]]:
    """Bounded query: exact field match, free-text search, status, newest first.

    Filtering happens in Python over the JSON payload rather than in SQL. That
    is the honest trade for a schemaless store at CRM scale (thousands of rows,
    not millions); the row scan is bounded by the collection cap.

    Resolves the collection first, so a deactivated module's records are
    unreachable through every path — the read side has to enforce that too, not
    only the write side.
    """
    resolve_collection(conn, module_id, collection_id)
    limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    sql = f"{_SELECT} WHERE module_id=? AND collection=?"
    params: list[Any] = [module_id, collection_id]
    if not include_deleted:
        sql += " AND deleted_at IS NULL"
    if status and status != "any":
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY updated_at DESC"
    rows = [_row_to_record(r) for r in conn.execute(sql, params)]

    needle = (search or "").strip().lower()
    out: list[dict[str, Any]] = []
    for record in rows:
        data = record["data"]
        if where:
            if any(_stringify(data.get(k)) != _stringify(v) for k, v in where.items()):
                continue
        if needle:
            haystack = " ".join(
                [record["id"]] + [_stringify(v) for v in data.values()]
            ).lower()
            if needle not in haystack:
                continue
        out.append(record)
        if len(out) >= limit:
            break
    return out


def _stringify(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def count_records(conn: sqlite3.Connection, module_id: str, collection_id: str) -> int:
    """Live (non-deleted) rows in a collection."""
    row = conn.execute(
        "SELECT COUNT(*) FROM module_records"
        " WHERE module_id=? AND collection=? AND deleted_at IS NULL",
        (module_id, collection_id),
    ).fetchone()
    return int(row[0]) if row else 0


def create_record(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    module_id: str,
    collection_id: str,
    data: dict[str, Any],
    record_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Insert a record. A colliding id merges (upsert), so retries converge.

    Idempotency is deliberate: an agent that retries a failed turn must not end
    up with `acme` and `acme-2` describing the same account.
    """
    collection = resolve_collection(conn, module_id, collection_id)
    payload = validate_payload(collection, data)
    rec_id = (record_id or derive_id(collection, payload)).strip()
    if not _ID_RE.match(rec_id):
        raise ModuleDataError(f"invalid record id {rec_id!r}")

    existing = get_record(conn, module_id, collection_id, rec_id)
    if existing is not None:
        return update_record(
            conn, lock,
            module_id=module_id, collection_id=collection_id,
            record_id=rec_id, data=payload, run_id=run_id,
        )
    if count_records(conn, module_id, collection_id) >= MAX_RECORDS_PER_COLLECTION:
        raise ModuleDataError(
            f"collection {collection_id!r} is at its {MAX_RECORDS_PER_COLLECTION}-record cap"
        )
    now = _now()
    with lock:
        with conn:
            conn.execute(
                "INSERT INTO module_records(module_id, collection, id, data_json, status,"
                " created_at, updated_at, created_by_run, updated_by_run)"
                " VALUES (?,?,?,?,'active',?,?,?,?)",
                (
                    module_id, collection_id, rec_id,
                    json.dumps(payload, ensure_ascii=False),
                    now, now, run_id, run_id,
                ),
            )
    created = get_record(conn, module_id, collection_id, rec_id)
    assert created is not None  # just inserted it
    return created


def update_record(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    module_id: str,
    collection_id: str,
    record_id: str,
    data: dict[str, Any],
    run_id: Optional[str] = None,
    status: Optional[str] = None,
) -> dict[str, Any]:
    """Merge fields into an existing record (partial update)."""
    collection = resolve_collection(conn, module_id, collection_id)
    existing = get_record(conn, module_id, collection_id, record_id)
    if existing is None:
        raise ModuleDataError(f"no record {record_id!r} in {module_id}/{collection_id}")
    patch = validate_payload(collection, data, partial=True)
    merged = {**existing["data"], **patch}
    if status is not None and status not in ("active", "archived"):
        raise ModuleDataError("status must be 'active' or 'archived'")
    now = _now()
    sets = ["data_json=?", "updated_at=?", "updated_by_run=?"]
    params: list[Any] = [json.dumps(merged, ensure_ascii=False), now, run_id]
    if status is not None:
        sets.append("status=?")
        params.append(status)
    params.extend([module_id, collection_id, record_id])
    with lock:
        with conn:
            conn.execute(
                f"UPDATE module_records SET {', '.join(sets)}"
                " WHERE module_id=? AND collection=? AND id=?",
                params,
            )
    updated = get_record(conn, module_id, collection_id, record_id)
    assert updated is not None  # just updated it
    return updated


def delete_record(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    module_id: str,
    collection_id: str,
    record_id: str,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Soft-delete a record and return the removed payload (the undo record)."""
    resolve_collection(conn, module_id, collection_id)
    existing = get_record(conn, module_id, collection_id, record_id)
    if existing is None:
        raise ModuleDataError(f"no record {record_id!r} in {module_id}/{collection_id}")
    now = _now()
    with lock:
        with conn:
            conn.execute(
                "UPDATE module_records SET deleted_at=?, updated_at=?, updated_by_run=?"
                " WHERE module_id=? AND collection=? AND id=?",
                (now, now, run_id, module_id, collection_id, record_id),
            )
    existing["deleted_at"] = now
    return existing


def collection_stats(conn: sqlite3.Connection, module_id: str) -> list[dict[str, Any]]:
    """Per-collection live counts for an active module (the page/stat surface)."""
    manifest = module_service.active_manifest(conn, module_id)
    if manifest is None:
        raise ModuleDataError(f"module {module_id!r} is not active")
    out: list[dict[str, Any]] = []
    for collection in module_service.capability(manifest, "collections"):
        cid = collection["id"]
        out.append(
            {
                "id": cid,
                "title": collection.get("title", cid),
                "count": count_records(conn, module_id, cid),
                "fields": [f["name"] for f in collection.get("fields", [])],
            }
        )
    return out


__all__ = [
    "MAX_PAYLOAD_BYTES",
    "MAX_RECORDS_PER_COLLECTION",
    "ModuleDataError",
    "collection_stats",
    "count_records",
    "create_record",
    "delete_record",
    "get_record",
    "query_records",
    "resolve_collection",
    "update_record",
    "validate_payload",
]
