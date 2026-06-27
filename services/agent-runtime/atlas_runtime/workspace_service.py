"""Fail-closed workspace resolver and path-containment guard (SURF-02, SURF-03, AUD-01).

Maps a (global|project) workspace request to a canonical, contained root and validates
any target path against that root, raising precise typed `WorkspaceError` reasons and
NEVER silently widening authority (no string-prefix matching, no auto-reregister). This
is the access-control boundary for SURF-02/03 and the path-level expression of the
narrow-only-authority invariant.

Global-root agreement (Pitfall 4): `global_root()` derives from `db.DEFAULT_DB_PATH`'s
parent so the workspace root and the DB home can never diverge. Tests isolate it by
monkeypatching `db.DEFAULT_DB_PATH` — never the live `~/.atlas` (the CLI DB path is not
ATLAS_HOME-aware; see project memory).

Stdlib only — `os.path`/`pathlib`; no new runtime or dependency (AGNT-01).
"""
from __future__ import annotations

import os
import pathlib
from typing import Optional

from atlas_runtime import audit_service
from atlas_runtime import db as db_module
from atlas_runtime import project_service

_VALID_REASONS = frozenset(
    {"traversal", "symlink_escape", "stale_root", "unregistered", "cross_project"}
)


class WorkspaceError(ValueError):
    """A fail-closed workspace/path denial carrying a machine-distinguishable reason."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        if reason not in _VALID_REASONS:
            raise ValueError(f"unknown WorkspaceError reason: {reason}")
        self.reason = reason
        super().__init__(message or reason)


def global_root() -> pathlib.Path:
    """The ATLAS global workspace root — bound to the DB home (Pitfall 4).

    Derives from `db.DEFAULT_DB_PATH.parent` dynamically so it always agrees with the
    DB location and so tests can redirect both by monkeypatching `db.DEFAULT_DB_PATH`.
    """
    return pathlib.Path(db_module.DEFAULT_DB_PATH).parent.expanduser().resolve()


def resolve_workspace(
    conn,
    *,
    kind: Optional[str] = None,
    project_id: Optional[str] = None,
    use_global: bool = False,
) -> str:
    """Resolve a workspace request to a canonical absolute root string.

    - `global` → the DB-home-bound `global_root()`.
    - `project` → the registered project's resolved root; unknown id → `unregistered`.

    `use_global=True` is an accepted alias for `kind="global"` (added for
    `tui.session_select`'s call convention, Phase 10.6 plan 02) — callers may
    pass either `kind="global"` or `use_global=True` interchangeably.
    """
    if kind is None:
        kind = "global" if use_global else "project"
    if kind == "global":
        return str(global_root())
    if kind == "project":
        project = project_service.get_project(conn, project_id) if project_id else None
        if project is None:
            raise WorkspaceError("unregistered", f"no registered project {project_id!r}")
        return str(pathlib.Path(project.root_path).expanduser().resolve())
    raise WorkspaceError("unregistered", f"unknown workspace kind {kind!r}")


def _contains(root_p: pathlib.Path, candidate: str) -> bool:
    """True iff `candidate` is `root_p` or below it, via commonpath (not prefix match).

    Maps the mixed-drive `commonpath` ValueError (Pitfall 1) to False so the caller can
    raise a typed error rather than leak a raw traceback.
    """
    try:
        return os.path.commonpath([str(root_p), candidate]) == str(root_p)
    except ValueError:
        return False


def assert_contained(root: str, target: str) -> str:
    """Return the resolved target iff it is inside `root`, else raise a typed WorkspaceError.

    Resolution collapses symlinks BEFORE the containment check. A non-contained target is
    classified `symlink_escape` when the lexical (un-resolved) path WAS inside root but a
    symlink redirected the resolved path outside (Pitfall 5); otherwise `traversal`
    (including the mixed-drive commonpath ValueError, Pitfall 1).
    """
    root_p = pathlib.Path(root).expanduser().resolve()
    if not root_p.exists():
        # No auto-mutation / auto-reregister — fail closed (SURF-03).
        raise WorkspaceError("stale_root", f"workspace root no longer exists: {root_p}")

    raw = pathlib.Path(target).expanduser()
    target_p = raw.resolve()
    if _contains(root_p, str(target_p)):
        return str(target_p)

    # Not contained. Distinguish a symlink escape from a plain traversal: abspath
    # normalizes `..` but does NOT resolve symlinks, so a symlinked path stays lexically
    # inside root while its resolved form escapes.
    lexical = pathlib.Path(os.path.abspath(str(raw)))
    if _contains(root_p, str(lexical)) and lexical != target_p:
        raise WorkspaceError("symlink_escape", f"symlink escapes workspace root: {root_p}")
    raise WorkspaceError("traversal", f"target escapes workspace root: {root_p}")


def assert_write_allowed(
    conn,
    lock,
    *,
    session_id: str,
    run_id: str,
    declared_root: str,
    target: str,
) -> str:
    """Containment + cross-project guard for a write (SURF-03, AUD-01).

    First enforces containment within `declared_root`. Then, if the contained target
    actually lands inside a DIFFERENT registered project's root, denies it with the
    distinct `cross_project` reason (NOT mislabeled `traversal`) and audits the denial.
    A traversal target escapes the declared root; a cross_project target stays inside its
    own root but is not the declared workspace — both fail closed, with different reasons.
    """
    resolved_target = assert_contained(declared_root, target)
    declared_p = pathlib.Path(declared_root).expanduser().resolve()

    for project in project_service.list_projects(conn):
        proj_root = pathlib.Path(project.root_path).expanduser().resolve()
        if proj_root == declared_p:
            continue
        if _contains(proj_root, resolved_target):
            audit_service.emit(
                conn,
                lock,
                run_id=run_id,
                event_type="permission_transition",
                session_id=session_id,
                data={
                    "denied": "cross_project_write",
                    "reason": "cross_project",
                    "declared_root": str(declared_p),
                    "project_id": project.id,
                },
            )
            raise WorkspaceError(
                "cross_project",
                f"target writes into undeclared project {project.id}",
            )
    return resolved_target


__all__ = [
    "WorkspaceError",
    "assert_contained",
    "assert_write_allowed",
    "global_root",
    "resolve_workspace",
]
