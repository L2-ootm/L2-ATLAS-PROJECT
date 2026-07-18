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


def test_set_root_repoints_custom_scope(db, lock, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    scope = gss.create_scope(db, lock, label="Notes", root_path=str(a))
    updated = gss.set_scope_root(db, lock, scope_id=scope["id"], root_path=str(b))
    assert updated["root_path"] == str(b.resolve())
    assert updated["updated_at"] >= scope["updated_at"]


def test_set_root_builtin_creates_override_hidden_from_list(db, lock, tmp_path):
    override = gss.set_scope_root(db, lock, scope_id="projects", root_path=str(tmp_path))
    assert override["id"] == "projects"
    assert override["root_path"] == str(tmp_path.resolve())
    # The override row must NOT appear as a custom tab.
    assert gss.list_scopes(db) == []
    # And it resolves as a built-in override.
    assert gss.resolve_builtin_override(db, "projects") == str(tmp_path.resolve())


def test_set_root_builtin_upserts_second_time(db, lock, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    gss.set_scope_root(db, lock, scope_id="obsidian", root_path=str(first))
    updated = gss.set_scope_root(db, lock, scope_id="obsidian", root_path=str(second))
    assert updated["root_path"] == str(second.resolve())
    assert gss.resolve_builtin_override(db, "obsidian") == str(second.resolve())


def test_set_root_rejects_repo_derived_and_missing(db, lock, tmp_path):
    with pytest.raises(gss.GraphScopeError, match="repo-derived"):
        gss.set_scope_root(db, lock, scope_id="atlas", root_path=str(tmp_path))
    with pytest.raises(gss.GraphScopeError, match="folder not found"):
        gss.set_scope_root(db, lock, scope_id="projects", root_path=str(tmp_path / "nope"))
    with pytest.raises(gss.GraphScopeError, match="not found"):
        gss.set_scope_root(db, lock, scope_id="ghost-scope", root_path=str(tmp_path))


def test_resolve_builtin_override_none_when_absent_or_gone(db, lock, tmp_path):
    assert gss.resolve_builtin_override(db, "projects") is None
    # Non-folder built-ins never have an override.
    assert gss.resolve_builtin_override(db, "atlas") is None
    # A stored override whose folder later vanishes resolves to None.
    gone = tmp_path / "gone"
    gone.mkdir()
    gss.set_scope_root(db, lock, scope_id="projects", root_path=str(gone))
    gone.rmdir()
    assert gss.resolve_builtin_override(db, "projects") is None


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
