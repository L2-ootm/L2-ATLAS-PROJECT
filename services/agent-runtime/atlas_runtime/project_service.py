"""ATLAS project service — create_project, register_project, get_project, list_projects.

A Project maps a name to a working directory on disk (P3). Missions linked to a
project execute with the project's root_path as their working directory.

Two entry paths mirror the operator's two flows:
  - create_project:   make a NEW project directory in a chosen location (mkdir).
  - register_project: adopt an EXISTING folder on the machine as a project.

Conventions follow mission_service.py:
  - Pydantic-first write guard (construct + validate before any SQL).
  - All mutations go through the service layer; lock injection per audit_service.
  - Paths are stored as resolved absolute str (D-013 cross-platform rule).
"""
from __future__ import annotations

import pathlib
import sqlite3
import threading
from typing import Optional

from atlas_core.schemas.core import Project


class ProjectError(ValueError):
    """Raised for invalid project inputs (bad path, missing folder, collision)."""


def _resolve_dir(root_path: str) -> pathlib.Path:
    """Resolve root_path to an absolute Path, rejecting empty input."""
    if not root_path or not root_path.strip():
        raise ProjectError("root_path must not be empty")
    return pathlib.Path(root_path).expanduser().resolve()


def _insert(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    resolved: pathlib.Path,
) -> Project:
    project = Project(name=name, root_path=str(resolved))
    row = project.model_dump()
    with lock:
        with conn:
            # Reject duplicate registration of the same directory.
            existing = conn.execute(
                "SELECT id FROM projects WHERE root_path=?", (project.root_path,)
            ).fetchone()
            if existing is not None:
                raise ProjectError(
                    f"a project is already registered at {project.root_path}"
                )
            conn.execute(
                "INSERT INTO projects"
                "(id, name, root_path, created_at, updated_at) "
                "VALUES (:id, :name, :root_path, :created_at, :updated_at)",
                row,
            )
    return project


def create_project(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    root_path: str,
) -> Project:
    """Create a NEW project directory (mkdir -p) and register it.

    root_path is the desired project directory; parent dirs are created. If the
    path exists it must be a directory (not a file).
    """
    resolved = _resolve_dir(root_path)
    if resolved.exists() and not resolved.is_dir():
        raise ProjectError(f"path exists and is not a directory: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return _insert(conn, lock, name=name, resolved=resolved)


def register_project(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    name: str,
    root_path: str,
) -> Project:
    """Register an EXISTING folder on the machine as a project.

    The directory must already exist; this never creates folders.
    """
    resolved = _resolve_dir(root_path)
    if not resolved.exists():
        raise ProjectError(f"folder does not exist: {resolved}")
    if not resolved.is_dir():
        raise ProjectError(f"path is not a directory: {resolved}")
    return _insert(conn, lock, name=name, resolved=resolved)


def get_project(
    conn: sqlite3.Connection,
    project_id: str,
) -> Optional[Project]:
    """Return the Project for the given id, or None if not found."""
    cursor = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,))
    cols = [d[0] for d in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return None
    return Project(**dict(zip(cols, row)))


def list_projects(
    conn: sqlite3.Connection,
) -> list[Project]:
    """Return all Project rows ordered by created_at ASC."""
    cursor = conn.execute("SELECT * FROM projects ORDER BY created_at ASC")
    cols = [d[0] for d in cursor.description]
    return [Project(**dict(zip(cols, row))) for row in cursor]
