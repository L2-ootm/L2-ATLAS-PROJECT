"""Tests for workspace_service — fail-closed path containment with typed errors
(SURF-02, SURF-03, AUD-01, plan 10.3-02).

The resolver maps a (global|project) workspace request to a canonical contained root
and validates target paths against it, raising precise typed reasons and never silently
widening authority. Global root is bound to the DB home so the two never diverge.
"""
import os
import pathlib

import pytest

from atlas_runtime import db as db_module
from atlas_runtime import project_service
from atlas_runtime import workspace_service as ws
from atlas_runtime.workspace_service import WorkspaceError


# ---------------------------------------------------------------------------
# resolve_workspace — global / project
# ---------------------------------------------------------------------------


def test_global_root_derives_from_db_home(db, tmp_path, monkeypatch) -> None:
    home = tmp_path / ".atlas"
    home.mkdir()
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", home / "atlas.db")
    root = ws.resolve_workspace(db, kind="global")
    assert pathlib.Path(root) == home.resolve()


def test_resolve_project_root_through_registry(db, lock, tmp_path) -> None:
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    p = project_service.register_project(db, lock, name="p", root_path=str(proj_dir))
    root = ws.resolve_workspace(db, kind="project", project_id=p.id)
    assert pathlib.Path(root) == proj_dir.resolve()


def test_resolve_project_unregistered_raises(db) -> None:
    with pytest.raises(WorkspaceError) as ei:
        ws.resolve_workspace(db, kind="project", project_id="nope")
    assert ei.value.reason == "unregistered"


# ---------------------------------------------------------------------------
# assert_contained — typed-error matrix
# ---------------------------------------------------------------------------


def test_contained_target_returns_resolved(db, tmp_path) -> None:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    got = ws.assert_contained(str(root), str(root / "sub" / "f.txt"))
    assert pathlib.Path(got) == (root / "sub" / "f.txt").resolve()


def test_traversal_raises(db, tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(WorkspaceError) as ei:
        ws.assert_contained(str(root), str(root / ".." / "outside" / "f.txt"))
    assert ei.value.reason == "traversal"


def test_stale_root_raises(db, tmp_path) -> None:
    missing = tmp_path / "gone"
    with pytest.raises(WorkspaceError) as ei:
        ws.assert_contained(str(missing), str(missing / "f.txt"))
    assert ei.value.reason == "stale_root"


def test_mixed_drive_maps_to_typed_error(db, tmp_path) -> None:
    """Pitfall 1: os.path.commonpath raises ValueError on mixed Windows drives;
    it must never escape as a raw ValueError."""
    root = tmp_path / "root"
    root.mkdir()
    drive = pathlib.Path(str(root)).drive  # e.g. 'C:' on win32, '' on posix
    if not drive:
        pytest.skip("single-root platform — no distinct drive to cross")
    other = "Z:" if drive.upper() != "Z:" else "Y:"
    with pytest.raises(WorkspaceError):
        ws.assert_contained(str(root), other + os.sep + "elsewhere" + os.sep + "f.txt")


def test_symlink_escape_raises(db, tmp_path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "link"
    try:
        os.symlink(str(outside), str(link), target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("no symlink creation rights on this platform/run")
    with pytest.raises(WorkspaceError) as ei:
        ws.assert_contained(str(root), str(link / "f.txt"))
    assert ei.value.reason == "symlink_escape"


# ---------------------------------------------------------------------------
# assert_write_allowed — cross-project denial (SURF-03 / AUD-01)
# ---------------------------------------------------------------------------


def test_cross_project_write_denied_and_audited(db, lock, run_id, tmp_path) -> None:
    # declared workspace is the parent; a DIFFERENT project is registered nested
    # inside it, and the target lands in that other project's root.
    declared = tmp_path / "ws"
    other_proj = declared / "projB"
    other_proj.mkdir(parents=True)
    project_service.register_project(db, lock, name="B", root_path=str(other_proj))

    target = str(other_proj / "secret.txt")
    with pytest.raises(WorkspaceError) as ei:
        ws.assert_write_allowed(
            db, lock, session_id="s1", run_id=run_id, declared_root=str(declared), target=target
        )
    assert ei.value.reason == "cross_project"

    row = db.execute(
        "SELECT event_type, data FROM audit_events "
        "WHERE event_type='permission_transition' AND session_id='s1'"
    ).fetchone()
    assert row is not None
    assert "cross_project" in row[1]


def test_write_allowed_in_declared_root_returns_resolved(db, lock, run_id, tmp_path) -> None:
    declared = tmp_path / "ws"
    declared.mkdir()
    target = str(declared / "ok.txt")
    got = ws.assert_write_allowed(
        db, lock, session_id="s1", run_id=run_id, declared_root=str(declared), target=target
    )
    assert pathlib.Path(got) == pathlib.Path(target).resolve()
