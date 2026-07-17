"""Tests for graph_scope_service (custom Graphify tabs, 0025)."""
from __future__ import annotations

import threading

import pytest

from atlas_runtime import graph_scope_service as gss


@pytest.fixture(name="lock")
def lock_fixture() -> threading.Lock:
    return threading.Lock()


def test_create_and_list_scope(db, lock, tmp_path):
    scope = gss.create_scope(db, lock, label="My Projects", root_path=str(tmp_path), kind="projects")
    assert scope["id"] == "my-projects"
    assert scope["kind"] == "projects"
    listed = gss.list_scopes(db)
    assert [s["id"] for s in listed] == ["my-projects"]


def test_create_is_idempotent_same_path(db, lock, tmp_path):
    first = gss.create_scope(db, lock, label="Notes", root_path=str(tmp_path))
    second = gss.create_scope(db, lock, label="Notes", root_path=str(tmp_path))
    assert first["id"] == second["id"]
    assert len(gss.list_scopes(db)) == 1


def test_create_conflicting_path_rejected(db, lock, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    gss.create_scope(db, lock, label="Notes", root_path=str(tmp_path))
    with pytest.raises(gss.GraphScopeError, match="already exists"):
        gss.create_scope(db, lock, label="Notes", root_path=str(other))


def test_missing_folder_rejected(db, lock, tmp_path):
    with pytest.raises(gss.GraphScopeError, match="folder not found"):
        gss.create_scope(db, lock, label="Ghost", root_path=str(tmp_path / "nope"))


def test_builtin_names_rejected(db, lock, tmp_path):
    with pytest.raises(gss.GraphScopeError, match="built-in"):
        gss.create_scope(db, lock, label="Projects", root_path=str(tmp_path))


def test_invalid_kind_rejected(db, lock, tmp_path):
    with pytest.raises(gss.GraphScopeError, match="kind"):
        gss.create_scope(db, lock, label="X Y", root_path=str(tmp_path), kind="martian")


def test_delete_scope_and_unknown(db, lock, tmp_path):
    scope = gss.create_scope(db, lock, label="Temp", root_path=str(tmp_path))
    gss.delete_scope(db, lock, scope["id"])
    assert gss.list_scopes(db) == []
    with pytest.raises(gss.GraphScopeError):
        gss.delete_scope(db, lock, scope["id"])
    with pytest.raises(gss.GraphScopeError, match="built-in"):
        gss.delete_scope(db, lock, "atlas")


def test_build_custom_graph_markdown(tmp_path):
    from atlas_runtime import graph_service

    (tmp_path / "a.md").write_text("# Alpha\n[[beta]]", encoding="utf-8")
    (tmp_path / "beta.md").write_text("# Beta", encoding="utf-8")
    out = graph_service.build_custom_graph("my-notes", str(tmp_path), "markdown")
    assert out["scope"] == "my-notes"
    assert out["counts"]["nodes"] >= 3  # root + two docs
    kinds = {link["kind"] for link in out["links"]}
    assert "wikilink" in kinds


def test_build_custom_graph_projects(tmp_path):
    from atlas_runtime import graph_service

    proj = tmp_path / "proj-a"
    proj.mkdir()
    (proj / "README.md").write_text("# Proj A", encoding="utf-8")
    out = graph_service.build_custom_graph("my-projects", str(tmp_path), "projects")
    assert out["scope"] == "my-projects"
    ids = {n["id"] for n in out["nodes"]}
    assert "proj:proj-a" in ids


def test_build_custom_graph_missing_folder(tmp_path):
    from atlas_runtime import graph_service

    out = graph_service.build_custom_graph("ghost", str(tmp_path / "nope"), "markdown")
    assert out["error"] == "folder not found"
    assert out["counts"]["nodes"] == 0
