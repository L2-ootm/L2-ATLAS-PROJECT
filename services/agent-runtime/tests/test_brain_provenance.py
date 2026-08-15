"""The write boundary: what may enter the graph, and what happens when it disagrees.

Before this, `brain_nodes` carried one quality signal — a `confidence` the
writing agent chose for itself, defaulting to 0.8 — and node ids derive from
(entity_type, label), so re-asserting an entity silently overwrote it. A later
guess could replace an earlier checked fact and leave no trace that the two had
ever disagreed.
"""
from __future__ import annotations

import json
import uuid

import pytest

from atlas_core.schemas import provenance
from atlas_core.schemas.brain import BrainNode
from atlas_runtime import brain_service


def _node(label: str, *, grade: str, summary: str = "", entity_type: str = "concept") -> BrainNode:
    return BrainNode(
        id=brain_service_node_id(entity_type, label),
        entity_type=entity_type,
        label=label,
        source_id="run:" + uuid.uuid4().hex,
        source_version="2026-08-15T00:00:00Z",
        updated_at="2026-08-15T00:00:00Z",
        confidence=0.8,
        grade=grade,
        metadata_json=json.dumps({"summary": summary} if summary else {}),
    )


def brain_service_node_id(entity_type: str, label: str) -> str:
    from atlas_runtime.graph_bridge import node_id_for

    return node_id_for(entity_type, label)


def _conflicts(db) -> list[dict]:
    return [
        dict(zip(("node_id", "incumbent_grade", "incoming_grade", "needs_operator"), row))
        for row in db.execute(
            "SELECT node_id, incumbent_grade, incoming_grade, needs_operator "
            "FROM brain_node_conflicts ORDER BY id"
        )
    ]


def test_a_node_is_stored_with_the_grade_it_was_written_at(db):
    outcome = brain_service.upsert_node_checked(db, _node("Gateway", grade=provenance.OBSERVED))
    assert outcome.written
    assert brain_service.explain(db, outcome.node.id).grade == provenance.OBSERVED


def test_a_weaker_contradiction_is_refused_and_the_stronger_claim_stands(db):
    """The live defect. A guess must not overwrite a checked fact."""
    fact = _node("Gateway", grade=provenance.VERIFIED, summary="listens on 8080")
    brain_service.upsert_node_checked(db, fact)

    guess = _node("Gateway", grade=provenance.ASSERTED, summary="listens on 9090")
    outcome = brain_service.upsert_node_checked(db, guess)

    assert not outcome.written
    assert "8080" in brain_service.explain(db, fact.id).metadata_json
    assert brain_service.explain(db, fact.id).grade == provenance.VERIFIED


def test_the_losing_claim_is_kept_rather_than_discarded(db):
    """Two sources disagreeing is information; one of them vanishing is not."""
    brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.VERIFIED, summary="listens on 8080")
    )
    brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.ASSERTED, summary="listens on 9090")
    )

    recorded = _conflicts(db)
    assert len(recorded) == 1
    assert recorded[0]["incumbent_grade"] == provenance.VERIFIED
    assert recorded[0]["incoming_grade"] == provenance.ASSERTED
    assert not recorded[0]["needs_operator"]


def test_a_stronger_claim_overwrites_and_still_leaves_a_trace(db):
    """Winning is not a reason to erase what it replaced."""
    brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.DERIVED, summary="probably 9090")
    )
    outcome = brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.VERIFIED, summary="listens on 8080")
    )

    assert outcome.written
    assert "8080" in brain_service.explain(db, outcome.node.id).metadata_json
    assert len(_conflicts(db)) == 1


def test_repeating_the_same_claim_is_corroboration_not_a_dispute(db):
    """Otherwise every repeat observation would register as a disagreement."""
    brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.OBSERVED, summary="listens on 8080")
    )
    outcome = brain_service.upsert_node_checked(
        db, _node("Gateway", grade=provenance.ASSERTED, summary="listens on 8080")
    )

    assert outcome.written  # same claim, weaker source — nothing is contested
    assert _conflicts(db) == []


def test_a_fact_against_an_intent_is_escalated_and_neither_side_wins(db):
    """The one contradiction ATLAS refuses to resolve on the operator's behalf."""
    intent = _node("Release date", grade=provenance.STATED, summary="ship on friday")
    brain_service.upsert_node_checked(db, intent)

    reality = _node("Release date", grade=provenance.VERIFIED, summary="build is broken")
    outcome = brain_service.upsert_node_checked(db, reality)

    assert not outcome.written, "a verified fact must not silently delete the operator's intent"
    assert "friday" in brain_service.explain(db, intent.id).metadata_json
    recorded = _conflicts(db)
    assert len(recorded) == 1
    assert recorded[0]["needs_operator"] == 1


@pytest.mark.parametrize(
    "incumbent,incoming",
    [
        (provenance.OBSERVED, provenance.OBSERVED),
        (provenance.DERIVED, provenance.DERIVED),
        (provenance.STATED, provenance.STATED),
    ],
)
def test_equal_standing_resolves_by_recency(db, incumbent, incoming):
    """Once provenance is exhausted, recency is the only signal left."""
    brain_service.upsert_node_checked(db, _node("Port", grade=incumbent, summary="8080"))
    outcome = brain_service.upsert_node_checked(db, _node("Port", grade=incoming, summary="9090"))

    assert outcome.written
    assert "9090" in brain_service.explain(db, outcome.node.id).metadata_json


def test_curation_corrects_what_a_node_says_not_how_it_came_to_be_known(db):
    """Fixing a typo by hand must not promote a guess into an observation."""
    node = _node("Gatway", grade=provenance.ASSERTED, summary="typo in the label")
    brain_service.upsert_node_checked(db, node)

    updated = brain_service.update_node(db, node.id, label="Gateway")

    assert updated.grade == provenance.ASSERTED
