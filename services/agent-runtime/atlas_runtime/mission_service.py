"""ATLAS mission service — create_mission, get_mission, list_missions.

Implements the mission CRUD layer for the Phase 5 mission state machine.
References:
  - D-002: Audit-first runtime — every state transition emits an AuditEvent.
  - D-003: SQLite/WAL is the datastore — all mission state persisted there.

All mutations go through the service layer. No raw SQL from CLI or tests.
Lock injection pattern follows Phase 4 audit_service.py conventions.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
import uuid
from typing import Optional

from atlas_core.schemas.core import Mission
from atlas_runtime.audit_service import emit


def create_mission(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    title: str,
    intent: str = "",
    project: str = "",
) -> Mission:
    """Insert a new Mission row and return the constructed Mission.

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


def get_mission(
    conn: sqlite3.Connection,
    mission_id: str,
) -> Optional[Mission]:
    """Return the Mission for the given id, or None if not found.

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")


def list_missions(
    conn: sqlite3.Connection,
) -> list[Mission]:
    """Return all Mission rows ordered by created_at ASC.

    Raises:
        NotImplementedError: Stub — implement in Wave 1.
    """
    raise NotImplementedError("not implemented")
