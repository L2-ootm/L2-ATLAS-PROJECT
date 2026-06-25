"""Bounded, deterministic Brain graph contract tests."""
from __future__ import annotations

import pytest

from atlas_core.schemas.brain import BrainEdge, BrainNode
from atlas_runtime import brain_service


def _node(node_id: str, *, project: str = "p1", confidence: float = 1.0) -> BrainNode:
    return BrainNode(
        id=node_id,
        entity_type="wiki",
        label=f"Node {node_id}",
        project_id=project,
        source_id=f"source:{node_id}",
        source_version="1",
        updated_at="2026-06-25T00:00:00Z",
        confidence=confidence,
        metadata_json="{}",
    )


def test_migration_creates_brain_tables(db):
    names = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'brain_%'"
        )
    }
    assert {"brain_nodes", "brain_edges"} <= names


def test_upsert_search_explain_and_replacement_are_deterministic(db):
    brain_service.upsert_node(db, _node("a"))
    brain_service.upsert_node(db, _node("a", confidence=0.7))
    found = brain_service.search(db, "Node a", project_id="p1")
    assert [node.id for node in found] == ["a"]
    assert found[0].confidence == 0.7
    assert brain_service.explain(db, "a").source_id == "source:a"


def test_neighbors_and_path_are_bounded_cycle_safe_and_scope_safe(db):
    for node in (_node("a"), _node("b"), _node("c"), _node("x", project="p2")):
        brain_service.upsert_node(db, node)
    for edge in (
        BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1"),
        BrainEdge(source_id="b", target_id="c", relation="supports", project_id="p1"),
        BrainEdge(source_id="c", target_id="a", relation="supports", project_id="p1"),
    ):
        brain_service.upsert_edge(db, edge)

    assert [item.id for item in brain_service.neighbors(db, "a", project_id="p1")] == ["b"]
    assert brain_service.find_path(db, "a", "c", project_id="p1") == ("a", "b", "c")
    assert brain_service.find_path(db, "a", "x", project_id="p1") == ()
    with pytest.raises(ValueError):
        brain_service.neighbors(db, "a", project_id="p1", depth=9)


def test_stale_and_low_confidence_nodes_rank_after_fresh_confident_nodes(db):
    fresh = _node("fresh", confidence=0.9)
    stale = _node("stale", confidence=0.2).model_copy(
        update={"updated_at": "2020-01-01T00:00:00Z"}
    )
    brain_service.upsert_node(db, stale)
    brain_service.upsert_node(db, fresh)
    assert [node.id for node in brain_service.search(db, "Node", project_id="p1")] == [
        "fresh",
        "stale",
    ]
