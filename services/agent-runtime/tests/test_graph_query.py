from __future__ import annotations

import json

from atlas_runtime import graph_bridge, graph_query


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_graph_query_search_neighbors_content_and_stats(tmp_path):
    _write(tmp_path / ".planning" / "STATE.md", "# Current State\n\nSee [Roadmap](ROADMAP.md).\n")
    _write(tmp_path / ".planning" / "ROADMAP.md", "# Roadmap\n\nPhase 12 query plane.\n")

    search = graph_query.query_graph(op="search", scope="agent", root=str(tmp_path), query="state")
    assert search["ok"] is True
    assert search["results"][0]["id"] == "STATE.md"

    neighbors = graph_query.query_graph(op="neighbors", scope="agent", root=str(tmp_path), node_id="STATE.md", depth=1)
    assert {item["node"]["id"] for item in neighbors["results"]} >= {"root", "ROADMAP.md"}

    content = graph_query.query_graph(op="content", scope="agent", root=str(tmp_path), node_id="STATE.md")
    assert "Current State" in content["content"]
    assert content["backend"] == "atlas-graphify"

    stats = graph_query.query_graph(op="stats", scope="agent", root=str(tmp_path))
    assert stats["counts"]["nodes"] == 3


def test_graph_query_rejects_unsafe_and_unbounded_inputs(tmp_path):
    _write(tmp_path / ".planning" / "SAFE.md", "# Safe\n")
    assert graph_query.query_graph(op="write", root=str(tmp_path))["ok"] is False
    assert graph_query.query_graph(op="search", scope="secret", root=str(tmp_path), query="x")["ok"] is False
    traversal = graph_query.query_graph(op="content", scope="agent", root=str(tmp_path), node_id="../SAFE.md")
    assert traversal["ok"] is False


def test_graph_bridge_returns_json(monkeypatch):
    monkeypatch.setattr(graph_bridge, "query_graph", lambda **kwargs: {"ok": True, "operation": kwargs["op"]})
    payload = json.loads(graph_bridge.atlas_graph_tool({"op": "stats"}))
    assert payload == {"ok": True, "operation": "stats"}
