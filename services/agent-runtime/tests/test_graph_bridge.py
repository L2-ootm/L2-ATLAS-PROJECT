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
    assert call(op="neighbors")["ok"] is False
    assert call(op="path", source_id="a")["ok"] is False
    assert call(op="update")["ok"] is False
    assert call(op="forget")["ok"] is False
    assert call(op="unlink", source_id="a")["ok"] is False
    assert call(op="remove_scope")["ok"] is False
    assert call(op="set_scope_root", scope_id="x")["ok"] is False


# ---------------------------------------------------------------------------
# Provenance at the write boundary — the agent cannot grade its own claim
# ---------------------------------------------------------------------------


def _audit_row(db, run_id: str, *, event_id: str, tool_call_id: str = "") -> None:
    db.execute(
        "INSERT OR IGNORE INTO missions(id,title,intent,status,project,created_at,updated_at) "
        "VALUES ('m-test','t','','pending','','2026-08-15T00:00:00Z','2026-08-15T00:00:00Z')"
    )
    db.execute(
        "INSERT INTO runs(id, mission_id, status, started_at) "
        "SELECT ?, 'm-test', 'running', '2026-08-15T00:00:00Z' "
        "WHERE NOT EXISTS (SELECT 1 FROM runs WHERE id=?)",
        (run_id, run_id),
    )
    db.execute(
        "INSERT INTO audit_events(id, run_id, tool_call_id, event_type, timestamp) "
        "VALUES (?,?,?,?,?)",
        (event_id, run_id, tool_call_id or None, "tool_completed", "2026-08-15T00:00:00Z"),
    )
    db.commit()


def test_a_node_written_without_evidence_is_recorded_as_unbacked(bound):
    """Not refused — recorded honestly, and kept out of later runs' context.

    Refusing would push the agent back to not writing at all, which is the state
    that left the graph with zero knowledge nodes in the first place.
    """
    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  summary="probably 8080")

    assert result["ok"] is True
    assert result["node"]["grade"] == "asserted"


def test_citing_real_evidence_from_this_run_earns_a_better_grade(bound):
    _audit_row(bound, "run-test", event_id="evt-1", tool_call_id="call-1")

    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  summary="listens on 8080", evidence=["call-1"])

    assert result["ok"] is True
    assert result["node"]["grade"] == "derived"


def test_derived_is_the_ceiling_for_anything_the_agent_writes(bound):
    """Reading evidence and concluding from it is not the same as being checked.

    Promotion to `verified` comes from the verification gate's verdict, never
    from the writer's own say-so — which is the whole point of the ladder.
    """
    _audit_row(bound, "run-test", event_id="evt-1", tool_call_id="call-1")

    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  summary="listens on 8080", evidence=["call-1"], confidence=1.0)

    assert result["node"]["grade"] == "derived"


def test_an_unresolvable_citation_rejects_the_write_and_names_it(bound):
    """A fabricated citation is a signal, not a reason to quietly downgrade."""
    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  summary="listens on 8080", evidence=["call-invented"])

    assert result["ok"] is False
    assert "call-invented" in result["error"]
    assert bound.execute("SELECT COUNT(*) FROM brain_nodes").fetchone()[0] == 0


def test_evidence_from_a_different_run_does_not_count(bound):
    """A citation that cannot be wrong is not evidence."""
    _audit_row(bound, "run-other", event_id="evt-9", tool_call_id="call-9")

    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  evidence=["call-9"])

    assert result["ok"] is False
    assert "call-9" in result["error"]


@pytest.mark.parametrize("cited", ["call-1", ["call-1"], "call-1,call-2"])
def test_citations_are_accepted_in_the_shapes_models_actually_send(bound, cited):
    """Rejecting two of the three would push callers back to citing nothing."""
    _audit_row(bound, "run-test", event_id="evt-1", tool_call_id="call-1")
    _audit_row(bound, "run-test", event_id="evt-2", tool_call_id="call-2")

    result = call(op="add_node", label="Gateway Port", entity_type="concept",
                  evidence=cited)

    assert result["ok"] is True
    assert result["node"]["grade"] == "derived"


def test_a_secret_is_redacted_before_it_reaches_the_database(bound):
    """redact() ran only on the way OUT, so the row itself held the secret.

    The router scrubbed it in transit while the durable graph kept it in the
    clear — a leak that survives every read path being correct.
    """
    call(op="add_node", label="Provider", entity_type="system",
         summary="auth with api_key=sk-brainleak-999")

    stored = bound.execute(
        "SELECT metadata_json FROM brain_nodes WHERE id='system:provider'"
    ).fetchone()[0]
    assert "sk-brainleak-999" not in stored
    assert "[REDACTED]" in stored


def test_a_refused_write_tells_the_agent_why_and_keeps_its_claim(bound):
    """A silent no-op is a write the agent will simply repeat."""
    _audit_row(bound, "run-test", event_id="evt-1", tool_call_id="call-1")
    call(op="add_node", label="Gateway Port", entity_type="concept",
         summary="listens on 8080", evidence=["call-1"])

    refused = call(op="add_node", label="Gateway Port", entity_type="concept",
                   summary="listens on 9090")

    assert refused["ok"] is False
    assert refused["conflict"]["incumbent_grade"] == "derived"
    assert refused["conflict"]["incoming_grade"] == "asserted"
    assert "8080" in bound.execute(
        "SELECT metadata_json FROM brain_nodes WHERE id='concept:gateway-port'"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Inventory ops — the agent can ask what it already knows
# ---------------------------------------------------------------------------


def test_list_and_stats_report_the_graph(bound):
    call(op="add_node", label="Alpha", entity_type="system")
    call(op="add_node", label="Beta", entity_type="concept")
    call(op="link", source_id="system:alpha", target_id="concept:beta", relation="depends_on")

    listed = call(op="list", entity_type="system")
    assert [n["id"] for n in listed["nodes"]] == ["system:alpha"]

    stats = call(op="stats")["stats"]
    assert stats["nodes"] == 2
    assert stats["edges"] == 1
    assert stats["by_entity_type"] == {"concept": 1, "system": 1}
    assert stats["by_relation"] == {"depends_on": 1}


def test_neighbors_and_path_traverse(bound):
    call(op="add_node", label="A", entity_type="concept")
    call(op="add_node", label="B", entity_type="concept")
    call(op="add_node", label="C", entity_type="concept")
    call(op="link", source_id="concept:a", target_id="concept:b")
    call(op="link", source_id="concept:b", target_id="concept:c")

    shallow = call(op="neighbors", node_id="concept:a")
    assert [n["id"] for n in shallow["neighbors"]] == ["concept:b"]
    assert [e["direction"] for e in shallow["edges"]] == ["out"]

    deep = call(op="neighbors", node_id="concept:a", depth=2)
    assert [n["id"] for n in deep["neighbors"]] == ["concept:b", "concept:c"]

    found = call(op="path", source_id="concept:a", target_id="concept:c")
    assert found["found"] is True
    assert found["path"] == ["concept:a", "concept:b", "concept:c"]

    missing = call(op="path", source_id="concept:c", target_id="concept:a")
    assert missing["found"] is False


# ---------------------------------------------------------------------------
# Curation ops — the graph is correctable, not only growable
# ---------------------------------------------------------------------------


def test_update_confidence_and_summary_in_place(bound):
    call(op="add_node", label="Retry Safety", entity_type="concept", summary="first")
    updated = call(op="update", node_id="concept:retry-safety", summary="corrected", confidence=0.3)

    assert updated["ok"] is True
    assert updated["renamed_from"] is None
    assert updated["node"]["metadata"]["summary"] == "corrected"
    assert updated["node"]["confidence"] == 0.3


def test_update_label_rekeys_so_add_node_still_converges(bound):
    call(op="add_node", label="Retry Safety", entity_type="concept")
    call(op="add_node", label="Queues", entity_type="concept")
    call(op="link", source_id="concept:queues", target_id="concept:retry-safety")

    renamed = call(op="update", node_id="concept:retry-safety", label="Idempotency")
    assert renamed["node"]["id"] == "concept:idempotency"
    assert renamed["renamed_from"] == "concept:retry-safety"

    # The edge followed the rename, and the old id is gone.
    assert call(op="explain", node_id="concept:retry-safety")["ok"] is False
    assert [n["id"] for n in call(op="explain", node_id="concept:queues")["neighbors"]] == [
        "concept:idempotency"
    ]

    # Re-adding under the new label converges on the renamed node, not a duplicate.
    call(op="add_node", label="Idempotency", entity_type="concept")
    assert call(op="stats")["stats"]["nodes"] == 2


def test_forget_returns_the_undo_record(bound):
    call(op="add_node", label="Wrong Fact", entity_type="concept")
    call(op="add_node", label="Anchor", entity_type="concept")
    call(op="link", source_id="concept:anchor", target_id="concept:wrong-fact")

    removed = call(op="forget", node_id="concept:wrong-fact")
    assert removed["ok"] is True
    assert removed["removed"]["node"]["label"] == "Wrong Fact"
    assert removed["removed"]["edges"][0]["source_id"] == "concept:anchor"

    assert call(op="explain", node_id="concept:wrong-fact")["ok"] is False
    assert call(op="forget", node_id="concept:wrong-fact")["ok"] is False
    # Forget removed the node's edges but not its neighbour.
    assert call(op="explain", node_id="concept:anchor")["ok"] is True


def test_unlink_is_idempotent_and_keeps_both_nodes(bound):
    call(op="add_node", label="A", entity_type="concept")
    call(op="add_node", label="B", entity_type="concept")
    call(op="link", source_id="concept:a", target_id="concept:b", relation="depends_on")

    first = call(op="unlink", source_id="concept:a", target_id="concept:b", relation="depends_on")
    second = call(op="unlink", source_id="concept:a", target_id="concept:b", relation="depends_on")
    assert (first["ok"], first["deleted"]) == (True, True)
    assert (second["ok"], second["deleted"]) == (True, False)
    assert call(op="stats")["stats"]["nodes"] == 2


def test_scope_lifecycle_add_repoint_remove(bound, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    call(op="add_scope", label="Team Notes", path=str(tmp_path))

    repointed = call(op="set_scope_root", scope_id="team-notes", path=str(other))
    assert repointed["scope"]["root_path"] == str(other.resolve())

    assert call(op="remove_scope", scope_id="team-notes")["ok"] is True
    assert call(op="list_scopes")["custom"] == []
    assert call(op="remove_scope", scope_id="team-notes")["ok"] is False


def test_unbound_state_degrades(monkeypatch):
    monkeypatch.setattr(graph_bridge, "_shared_state", lambda: (None, None))
    result = json.loads(graph_bridge.atlas_graph_tool({"op": "search", "query": "x"}))
    assert result["ok"] is False
    assert "unavailable" in result["error"]
