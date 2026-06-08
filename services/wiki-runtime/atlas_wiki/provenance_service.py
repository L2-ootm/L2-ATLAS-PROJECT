"""ATLAS memory provenance service (D-019)."""
from __future__ import annotations

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
    """Write a MemoryProvenance record and return the constructed model."""
    raise NotImplementedError


def get_provenance(
    conn: sqlite3.Connection,
    item_id: str,
) -> list[MemoryProvenance]:
    """Return all MemoryProvenance records for the given item_id."""
    raise NotImplementedError
