"""The provenance ladder — how good a piece of ATLAS's memory is, and who says so.

ATLAS used to carry exactly one quality signal on retrieved knowledge: a
``confidence`` float derived from ``MemorySnippet.score``, a value its own
docstring documents as a *private sort key*. Most retrievers emit a negated list
index, so that confidence was ``0.0`` for nearly everything in the system, it was
never rendered, and every snippet reached the model tagged ``trust="evidence"``
regardless of where it came from. The operator's own words and an unbacked guess
were typographically identical in the brief. A model given no way to tell them
apart weighs them the same — which is the reported behaviour, and not a model
defect.

The fix is not a better number. A number invites the writer to choose it, and a
writer that grades its own homework grades generously. **A grade is a fact about
an item's origin, so the code that knows the origin assigns it and nothing else
may.** Retrievers set the grade because a retriever knows which table it read;
the write bridge derives it from citations it resolves itself. There is
deliberately no code path by which a model's output chooses its own grade.

Two axes are collapsed into one ladder. ``stated`` outranks ``verified`` on what
the operator *wants*; ``verified`` outranks ``stated`` on what is *true*. Rather
than model both, :data:`RANK` orders them once and doctrine carries the single
exception: a ``verified`` fact contradicting a ``stated`` intent is surfaced to
the operator, never auto-resolved. The world disagreeing with what you want is a
decision, not a merge.

:data:`RANK` exists for contradiction resolution and retrieval floors. It is not
a relevance score and must never be compared against one — that conflation is the
mistake ``MemorySnippet.score`` already made once.
"""
from __future__ import annotations

from typing import Final, Literal

Grade = Literal["stated", "verified", "observed", "derived", "reported", "asserted"]

#: The operator typed it. Authoritative about intent; never overridden by inference.
STATED: Final[Grade] = "stated"
#: A check ran and passed against it. Authoritative about fact.
VERIFIED: Final[Grade] = "verified"
#: A tool returned it — a file read, an exit code, a database row. True at its
#: timestamp, and therefore the one grade that decays.
OBSERVED: Final[Grade] = "observed"
#: The agent concluded it from sources it cited. Only as good as what it cites.
DERIVED: Final[Grade] = "derived"
#: A subagent, actor or module returned it. A claim, per skills/atlas/delegation.md.
REPORTED: Final[Grade] = "reported"
#: Nothing traceable backs it. The floor: usable, never citable.
ASSERTED: Final[Grade] = "asserted"

GRADES: Final[tuple[Grade, ...]] = (STATED, VERIFIED, OBSERVED, DERIVED, REPORTED, ASSERTED)

RANK: Final[dict[Grade, int]] = {
    VERIFIED: 5,
    STATED: 4,
    OBSERVED: 3,
    DERIVED: 2,
    REPORTED: 1,
    ASSERTED: 0,
}

#: Grades that never reach the model as evidence unless explicitly asked for.
#: ``asserted`` is a holding pen, not knowledge — it is promotable on later
#: citation, but until then it is exactly the "shitty data" the ladder exists to
#: keep out of a run's context.
DEFAULT_FLOOR: Final[Grade] = REPORTED

#: What each grade licenses, rendered into the brief beside the evidence itself
#: rather than declared once in the L1 prompt 20k tokens earlier. Doctrine that
#: does not arrive next to the claim it governs is a document, not a rule.
LICENCE: Final[dict[Grade, str]] = {
    STATED: "the operator said this — authoritative about intent, not about the world",
    VERIFIED: "a check passed against this — authoritative about fact",
    OBSERVED: "a tool witnessed this at the time shown — re-check before relying on it",
    DERIVED: "the agent concluded this from cited sources — no better than they are",
    REPORTED: "someone else claims this — it has not been checked here",
    ASSERTED: "nothing backs this — do not cite it",
}


def rank(grade: Grade | str) -> int:
    """Rank for contradiction resolution. Unknown grades sink to the floor.

    An unrecognised grade is treated as ``asserted`` rather than raising: a bad
    grade must never take down a run, and sinking is the safe direction — it can
    only cause an item to lose a contest it should not have won.
    """
    return RANK.get(grade, 0)  # type: ignore[arg-type]


def outranks(candidate: Grade | str, incumbent: Grade | str) -> bool:
    """Whether ``candidate`` may overwrite ``incumbent`` on contradiction.

    Ties overwrite: two items of equal standing are resolved by recency, which is
    the only signal left once provenance has been exhausted.
    """
    return rank(candidate) >= rank(incumbent)


def is_conflict_for_operator(candidate: Grade | str, incumbent: Grade | str) -> bool:
    """A fact contradicting an intent — the one case never resolved in code.

    ``verified`` against ``stated`` means reality disagrees with what the operator
    asked for. Overwriting drops the operator's intent; refusing hides the truth.
    Neither is ATLAS's call, so both are kept and the operator is told.
    """
    pair = {candidate, incumbent}
    return pair == {VERIFIED, STATED}


__all__ = [
    "ASSERTED",
    "DEFAULT_FLOOR",
    "DERIVED",
    "GRADES",
    "Grade",
    "LICENCE",
    "OBSERVED",
    "RANK",
    "REPORTED",
    "STATED",
    "VERIFIED",
    "is_conflict_for_operator",
    "outranks",
    "rank",
]
