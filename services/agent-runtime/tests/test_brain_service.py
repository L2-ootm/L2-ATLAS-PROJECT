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


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def test_list_nodes_filters_by_type_and_scope(db):
    brain_service.upsert_node(db, _node("a"))
    brain_service.upsert_node(db, _node("x", project="p2"))
    brain_service.upsert_node(
        db, _node("d").model_copy(update={"id": "d", "entity_type": "decision"})
    )

    assert {n.id for n in brain_service.list_nodes(db, project_id="p1")} == {"a", "d"}
    assert [
        n.id for n in brain_service.list_nodes(db, project_id="p1", entity_type="decision")
    ] == ["d"]
    assert [n.id for n in brain_service.list_nodes(db, project_id="p2")] == ["x"]
    # project_id=None is the global (NULL) scope, not "everything".
    assert brain_service.list_nodes(db) == ()


def test_stats_counts_every_scope_and_flags_orphans(db):
    brain_service.upsert_node(db, _node("a"))
    brain_service.upsert_node(db, _node("b"))
    brain_service.upsert_node(db, _node("lonely"))
    brain_service.upsert_node(db, _node("x", project="p2"))
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )

    stats = brain_service.stats(db)
    assert stats["nodes"] == 4
    assert stats["edges"] == 1
    assert stats["by_entity_type"] == {"wiki": 4}
    assert stats["by_relation"] == {"supports": 1}
    assert stats["by_project"] == {"p1": 3, "p2": 1}
    assert stats["orphan_nodes"] == 2  # "lonely" and the p2 node


def test_edges_for_reports_both_directions(db):
    for node in (_node("a"), _node("b"), _node("c")):
        brain_service.upsert_node(db, node)
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )
    brain_service.upsert_edge(
        db, BrainEdge(source_id="c", target_id="b", relation="refutes", project_id="p1")
    )

    directions = {
        (edge["source_id"], edge["direction"]) for edge in brain_service.edges_for(db, "b")
    }
    assert directions == {("a", "in"), ("c", "in")}
    assert [e["direction"] for e in brain_service.edges_for(db, "a")] == ["out"]


# ---------------------------------------------------------------------------
# Curation
# ---------------------------------------------------------------------------


def test_update_node_merges_metadata_and_keeps_untouched_fields(db):
    brain_service.upsert_node(
        db,
        _node("a").model_copy(update={"metadata_json": '{"summary": "old", "origin": "keep"}'}),
    )
    updated = brain_service.update_node(
        db, "a", confidence=0.5, metadata={"summary": "new"}, updated_at="2026-07-01T00:00:00Z"
    )
    assert updated.confidence == 0.5
    assert updated.label == "Node a"  # untouched
    # The merge preserves provenance another writer recorded.
    assert '"origin": "keep"' in updated.metadata_json
    assert '"summary": "new"' in updated.metadata_json
    assert brain_service.explain(db, "a").confidence == 0.5


def test_update_node_rekeys_and_carries_edges_across(db):
    for node in (_node("a"), _node("b"), _node("c")):
        brain_service.upsert_node(db, node)
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )
    brain_service.upsert_edge(
        db, BrainEdge(source_id="c", target_id="a", relation="refutes", project_id="p1")
    )

    brain_service.update_node(db, "a", label="Renamed", new_id="wiki:renamed")

    assert brain_service.explain(db, "a") is None
    assert brain_service.explain(db, "wiki:renamed").label == "Renamed"
    moved = {
        (edge["source_id"], edge["target_id"], edge["relation"])
        for edge in brain_service.edges_for(db, "wiki:renamed")
    }
    assert moved == {
        ("wiki:renamed", "b", "supports"),
        ("c", "wiki:renamed", "refutes"),
    }


def test_update_node_refuses_to_merge_onto_an_existing_id(db):
    brain_service.upsert_node(db, _node("a"))
    brain_service.upsert_node(db, _node("b"))
    with pytest.raises(ValueError, match="already exists"):
        brain_service.update_node(db, "a", new_id="b")
    # The failed rename left both nodes intact.
    assert brain_service.explain(db, "a") is not None
    assert brain_service.explain(db, "b") is not None


def test_update_node_rejects_unknown_node(db):
    with pytest.raises(ValueError, match="unknown node"):
        brain_service.update_node(db, "nope", confidence=0.1)


def test_delete_node_returns_an_undo_record_and_removes_edges(db):
    for node in (_node("a"), _node("b")):
        brain_service.upsert_node(db, node)
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )

    removed = brain_service.delete_node(db, "a")
    assert removed["node"]["id"] == "a"
    assert [e["target_id"] for e in removed["edges"]] == ["b"]
    assert brain_service.explain(db, "a") is None
    assert db.execute("SELECT COUNT(*) FROM brain_edges").fetchone()[0] == 0
    # Surviving neighbour is untouched, and a second delete is a clean no-op.
    assert brain_service.explain(db, "b") is not None
    assert brain_service.delete_node(db, "a") is None


def test_delete_edge_is_safe_to_retry(db):
    for node in (_node("a"), _node("b")):
        brain_service.upsert_node(db, node)
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )
    assert brain_service.delete_edge(db, "a", "b", "supports") is True
    assert brain_service.delete_edge(db, "a", "b", "supports") is False
    assert brain_service.explain(db, "a") is not None  # unlink never deletes nodes


# ---------------------------------------------------------------------------
# Portability
# ---------------------------------------------------------------------------


def test_export_import_roundtrip_is_idempotent(db):
    for node in (_node("a"), _node("b")):
        brain_service.upsert_node(db, node)
    brain_service.upsert_edge(
        db, BrainEdge(source_id="a", target_id="b", relation="supports", project_id="p1")
    )
    payload = brain_service.export_graph(db)

    db.execute("DELETE FROM brain_edges")
    db.execute("DELETE FROM brain_nodes")
    first = brain_service.import_graph(db, payload)
    assert (first["nodes"], first["edges"]) == (2, 1)

    # Re-importing converges instead of duplicating.
    second = brain_service.import_graph(db, payload)
    assert (second["nodes"], second["edges"]) == (2, 1)
    assert brain_service.stats(db)["nodes"] == 2
    assert brain_service.stats(db)["edges"] == 1


def test_import_skips_edges_with_missing_endpoints_instead_of_aborting(db):
    payload = {
        "nodes": [_node("a").model_dump()],
        "edges": [
            {
                "source_id": "a",
                "target_id": "ghost",
                "relation": "supports",
                "project_id": "p1",
                "confidence": 1.0,
                "metadata_json": "{}",
            }
        ],
    }
    result = brain_service.import_graph(db, payload)
    assert result["nodes"] == 1
    assert result["edges"] == 0
    assert len(result["skipped_edges"]) == 1
    assert brain_service.explain(db, "a") is not None
