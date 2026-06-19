from __future__ import annotations

from atlas_runtime import graph_service


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_graph_empty_when_no_planning(tmp_path):
    result = graph_service.build_graph(root=str(tmp_path))
    assert result["nodes"] == []
    assert result["links"] == []


def test_build_graph_nodes_links_and_refs(tmp_path):
    planning = tmp_path / ".planning"
    _write(planning / "ROADMAP.md", "# Roadmap\n\nDecision D-021 governs sequencing.\n")
    _write(planning / "STATE.md", "# State\n\nSee D-021 and Phase 10.0.3.\n")
    _write(
        planning / "phases" / "10.0.3-cockpit" / "PLAN.md",
        "# Cockpit Plan\n\nImplements [STATE](../../STATE.md).\n",
    )

    result = graph_service.build_graph(root=str(tmp_path))
    ids = {n["id"] for n in result["nodes"]}

    # Files + folder hubs + root hub are all present.
    assert "ROADMAP.md" in ids
    assert "STATE.md" in ids
    assert "phases/10.0.3-cockpit/PLAN.md" in ids
    assert "dir:phases/10.0.3-cockpit" in ids
    assert "root" in ids

    link_kinds = {link["kind"] for link in result["links"]}
    assert "contains" in link_kinds  # structural backbone
    assert "decision" in link_kinds  # D-021 mentions resolve to a definer
    assert "phase" in link_kinds     # "Phase 10.0.3" resolves to the phase hub

    # Relative markdown link STATE.md -> resolved cross-reference edge exists.
    assert any(
        link["target"] == "STATE.md" and link["kind"] == "link" for link in result["links"]
    )

    # No isolated nodes — every node touches at least one edge.
    degree = {n["id"]: 0 for n in result["nodes"]}
    for link in result["links"]:
        degree[link["source"]] += 1
        degree[link["target"]] += 1
    assert all(d > 0 for d in degree.values())
