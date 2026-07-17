"""Tests for the atlas_graph agent tool (graph_bridge)."""
from __future__ import annotations

import json
import threading

import pytest

from atlas_runtime import graph_bridge


@pytest.fixture(name="bound")
def bound_fixture(db, monkeypatch):
    """Bind the bridge's shared-state seam to the test DB."""
    lock = threading.Lock()
    monkeypatch.setattr(graph_bridge, "_shared_state", lambda: (db, lock))
    monkeypatch.setattr(
        graph_bridge, "_current_run_id", lambda *a, **k: "run-test"
    )
    return db


def call(**args):
    return json.loads(graph_bridge.atlas_graph_tool(args))


def test_add_node_is_idempotent(bound):
    first = call(op="add_node", label="Retry Safety", entity_type="concept", summary="idempotency")
    assert first["ok"] is True
    assert first["node"]["id"] == "concept:retry-safety"
    second = call(op="add_node", label="Retry Safety", entity_type="concept")
    assert second["node"]["id"] == first["node"]["id"]
    count = bound.execute(
        "SELECT COUNT(*) FROM brain_nodes WHERE id='concept:retry-safety'"
    ).fetchone()[0]
    assert count == 1


def test_search_and_explain_roundtrip(bound):
    call(op="add_node", label="Alpha System", entity_type="system")
    call(op="add_node", label="Beta Concept", entity_type="concept")
    call(op="link", source_id="system:alpha-system", target_id="concept:beta-concept", relation="depends_on")

    found = call(op="search", query="Alpha")
    assert found["ok"] is True
    assert [n["id"] for n in found["nodes"]] == ["system:alpha-system"]

    explained = call(op="explain", node_id="system:alpha-system")
    assert explained["node"]["label"] == "Alpha System"
    assert [n["id"] for n in explained["neighbors"]] == ["concept:beta-concept"]


def test_link_requires_existing_endpoints(bound):
    result = call(op="link", source_id="concept:missing", target_id="concept:also-missing")
    assert result["ok"] is False
    assert "exist" in result["error"]


def test_add_scope_and_list(bound, tmp_path):
    created = call(op="add_scope", label="Team Notes", path=str(tmp_path))
    assert created["ok"] is True
    assert created["scope"]["id"] == "team-notes"
    listed = call(op="list_scopes")
    assert "atlas" in listed["builtin"]
    assert [s["id"] for s in listed["custom"]] == ["team-notes"]


def test_bad_inputs_return_errors_not_raises(bound):
    assert call(op="search")["ok"] is False
    assert call(op="explain")["ok"] is False
    assert call(op="add_node")["ok"] is False
    assert call(op="add_scope", label="X")["ok"] is False
    assert call(op="warp")["ok"] is False


def test_unbound_state_degrades(monkeypatch):
    monkeypatch.setattr(graph_bridge, "_shared_state", lambda: (None, None))
    result = json.loads(graph_bridge.atlas_graph_tool({"op": "search", "query": "x"}))
    assert result["ok"] is False
    assert "unavailable" in result["error"]
