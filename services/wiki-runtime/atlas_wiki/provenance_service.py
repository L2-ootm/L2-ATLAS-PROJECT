"""ATLAS memory provenance service (D-019)."""
from __future__ import annotations

import datetime
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import MemoryProvenance


def write_provenance(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    layer: str,
    item_id: str,
    run_id: Optional[str] = None,
    source_id: Optional[str] = None,
    audit_event_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    sensitivity: str = "internal",
    untrusted: bool = False,
) -> MemoryProvenance:
    """Write a MemoryProvenance record and return the constructed model.

    Constructs MemoryProvenance (Pydantic-first) before any SQL write.
    Acquires lock internally — caller must NOT hold lock when calling.
    """
    record = MemoryProvenance(
        layer=layer,  # type: ignore[arg-type]
        item_id=item_id,
        run_id=run_id,
        source_id=source_id,
        audit_event_id=audit_event_id,
        operator_id=operator_id,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        untrusted=untrusted,
    )

    now = record.written_at.isoformat() if isinstance(record.written_at, datetime.datetime) else str(record.written_at)

    with lock:
        with conn:
            conn.execute(
                "INSERT INTO memory_provenance("
                "id, layer, item_id, run_id, source_id, audit_event_id, "
                "operator_id, sensitivity, untrusted, written_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.layer,
                    record.item_id,
                    record.run_id,
                    record.source_id,
                    record.audit_event_id,
                    record.operator_id,
                    record.sensitivity,
                    1 if record.untrusted else 0,
                    now,
                ),
            )

    return record


def get_provenance(
    conn: sqlite3.Connection,
    item_id: str,
) -> list[MemoryProvenance]:
    """Return all MemoryProvenance records for the given item_id."""
    cursor = conn.execute(
        "SELECT id, layer, item_id, run_id, source_id, audit_event_id, "
        "operator_id, sensitivity, untrusted, written_at "
        "FROM memory_provenance WHERE item_id=? ORDER BY written_at ASC",
        (item_id,),
    )
    cols = [d[0] for d in cursor.description]
    records = []
    for row in cursor:
        row_dict = dict(zip(cols, row))
        # Convert untrusted int back to bool for Pydantic
        row_dict["untrusted"] = bool(row_dict["untrusted"])
        records.append(MemoryProvenance(**row_dict))
    return records
