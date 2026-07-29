"""TEST-03 deterministic quality gates for the real memory router."""
from __future__ import annotations


def test_quality_fixture_measures_every_frozen_dimension() -> None:
    report = evaluate_quality_fixture()
    assert report["precision"] >= 0.80
