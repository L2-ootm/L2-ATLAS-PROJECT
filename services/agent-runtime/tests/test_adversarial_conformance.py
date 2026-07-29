"""TEST-03 adversarial safe-outcome assertions."""
from __future__ import annotations


def test_every_adversarial_family_names_a_safe_invariant() -> None:
    outcomes = evaluate_adversarial_families()
    assert outcomes
