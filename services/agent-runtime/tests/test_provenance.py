"""The provenance ladder — the rules a grade has to obey to be worth carrying."""
from __future__ import annotations

import pytest

from atlas_core.schemas import provenance as prov


def test_every_grade_has_a_rank_and_a_licence():
    """A grade nothing can rank and nothing can explain is decoration.

    Adding a seventh grade without deciding where it sits or what it permits
    would silently sink it to the floor and render it without a licence line.
    """
    for grade in prov.GRADES:
        assert grade in prov.RANK, f"{grade} has no rank"
        assert prov.LICENCE.get(grade), f"{grade} has no licence line"
    assert len(set(prov.RANK.values())) == len(prov.GRADES), "ranks must be distinct"


def test_the_ladder_orders_evidence_above_claims():
    """The whole point: a checked fact beats a guess, and a guess beats nothing."""
    assert prov.rank(prov.VERIFIED) > prov.rank(prov.STATED)
    assert prov.rank(prov.STATED) > prov.rank(prov.OBSERVED)
    assert prov.rank(prov.OBSERVED) > prov.rank(prov.DERIVED)
    assert prov.rank(prov.DERIVED) > prov.rank(prov.REPORTED)
    assert prov.rank(prov.REPORTED) > prov.rank(prov.ASSERTED)


def test_an_unknown_grade_sinks_instead_of_raising():
    """A bad grade must never take down a run, and sinking is the safe direction.

    Sinking can only cost an item a contest it should not have won; floating
    would let an unrecognised string overwrite a verified fact.
    """
    assert prov.rank("nonsense") == 0
    assert prov.rank("") == 0
    # It lands level with the floor, so it loses to everything above it...
    assert not prov.outranks("nonsense", prov.DERIVED)
    # ...and only ties with `asserted`, where recency decides.
    assert prov.outranks("nonsense", prov.ASSERTED)


@pytest.mark.parametrize("lower", [prov.DERIVED, prov.REPORTED, prov.ASSERTED])
def test_a_weaker_claim_cannot_overwrite_a_verified_fact(lower):
    """The live defect this exists to stop.

    brain node ids derive from (entity_type, label), so re-asserting an entity
    upserts over it. Without a rank check a self-graded guess silently replaces
    a checked fact and nothing surfaces the contradiction.
    """
    assert not prov.outranks(lower, prov.VERIFIED)
    assert prov.outranks(prov.VERIFIED, lower)


def test_equal_standing_resolves_by_recency():
    """Once provenance is exhausted, recency is the only signal left."""
    for grade in prov.GRADES:
        assert prov.outranks(grade, grade)


def test_a_fact_contradicting_an_intent_is_never_resolved_in_code():
    """`verified` against `stated` is a decision for the operator, not a merge.

    Overwriting drops what the operator asked for; refusing hides what is true.
    ATLAS is entitled to neither, so it keeps both and says so.
    """
    assert prov.is_conflict_for_operator(prov.VERIFIED, prov.STATED)
    assert prov.is_conflict_for_operator(prov.STATED, prov.VERIFIED)


@pytest.mark.parametrize(
    "candidate,incumbent",
    [
        (prov.VERIFIED, prov.OBSERVED),
        (prov.STATED, prov.DERIVED),
        (prov.OBSERVED, prov.OBSERVED),
        (prov.STATED, prov.STATED),
        (prov.VERIFIED, prov.VERIFIED),
    ],
)
def test_ordinary_pairs_are_resolved_without_bothering_the_operator(candidate, incumbent):
    """Escalation has to be rare or it becomes noise the operator learns to skip."""
    assert not prov.is_conflict_for_operator(candidate, incumbent)


def test_the_retrieval_floor_admits_claims_but_not_unbacked_assertions():
    """`asserted` is a holding pen. Everything at or above the floor is evidence."""
    assert prov.rank(prov.DEFAULT_FLOOR) > prov.rank(prov.ASSERTED)
    admitted = [g for g in prov.GRADES if prov.rank(g) >= prov.rank(prov.DEFAULT_FLOOR)]
    assert prov.ASSERTED not in admitted
    assert set(admitted) == {
        prov.STATED, prov.VERIFIED, prov.OBSERVED, prov.DERIVED, prov.REPORTED
    }
