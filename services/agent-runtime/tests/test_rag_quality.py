"""TEST-03 deterministic quality gates for the real memory router."""
from __future__ import annotations

import json
from pathlib import Path

from atlas_runtime import memory_router as mr


FIXTURES = Path(__file__).parent / "fixtures"


class _FixtureRetriever:
    def section_lines(self, query):  # noqa: ANN001
        return ["## Frozen TEST-03"]

    def retrieve(self, conn, query):  # noqa: ANN001
        return [
            mr.MemorySnippet(
                text="trusted context api_key=sk-quality-fixture-secret",
                score=1.0,
                source="wiki:atlas",
                approx_tokens=8,
            )
        ]


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def evaluate_quality_fixture() -> dict[str, float | int]:
    cases = _load("rag_quality_cases.json")["cases"]
    answerable = [case for case in cases if case["expected_sources"]]
    abstention_cases = [case for case in cases if case["kind"] == "unanswerable"]
    hits = sum(
        len(set(case["expected_sources"]) & set(case["selected_sources"]))
        for case in answerable
    )
    selected = sum(len(case["selected_sources"]) for case in answerable)
    expected = sum(len(case["expected_sources"]) for case in answerable)
    return {
        "precision": hits / selected,
        "recall": hits / expected,
        "faithfulness": sum(case["grounded"] for case in cases) / len(cases),
        "provenance": sum(bool(case["selected_sources"]) or case["abstained"] for case in cases) / len(cases),
        "freshness": sum(case["fresh"] for case in cases) / len(cases),
        "token_budget": max(case["tokens"] for case in cases),
        "abstention": sum(case["abstained"] for case in abstention_cases) / len(abstention_cases),
        "poisoned_source_resistance": sum(
            not case["poison_executed"] and not case["secret_disclosed"] for case in cases
        ) / len(cases),
    }

def test_quality_fixture_measures_every_frozen_dimension() -> None:
    report = evaluate_quality_fixture()
    thresholds = _load("quality_thresholds.json")["metrics"]
    assert set(report) == set(thresholds)
    for name, threshold in thresholds.items():
        if name == "token_budget":
            assert report[name] <= threshold, name
        else:
            assert report[name] >= threshold, name


def test_real_router_redacts_poisoned_evidence_and_keeps_provenance() -> None:
    lines, sources = mr.MemoryRouter(retrievers=[_FixtureRetriever()]).assemble(
        None, mr.RouterQuery(terms=("atlas",), has_focus=True), token_budget=8192
    )
    body = "\n".join(lines)
    assert sources == ["wiki:atlas"]
    assert "sk-quality-fixture-secret" not in body
    assert "[REDACTED]" in body


def test_frozen_prompt_cache_prefix_hashes_match_plan_01_contract() -> None:
    thresholds = _load("quality_thresholds.json")
    goldens = _load("prompt_golden_matrix.json")["cases"]
    actual = {row["provider"]: row["stable_prompt_sha256"] for row in goldens}
    assert actual == thresholds["prompt_cache_prefix_hashes"]
