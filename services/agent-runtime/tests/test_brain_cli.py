"""Tests for `atlas brain` — the operator's surface on the durable knowledge graph.

The agent reaches the same graph through the `atlas_graph` tool (graph_bridge);
these cover the human/gateway path. Every command prints JSON so the gateway can
dispatch to it (D-022) and a human can pipe it.

Fixtures from conftest.py (injected by name — do NOT import):
  db      — in-memory SQLite with all migrations applied
  lock    — threading.Lock()
"""
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from atlas_runtime.cli.main import app

runner = CliRunner()


@pytest.fixture(name="cli")
def cli_fixture(db, lock, monkeypatch):
    """Bind the CLI's connection factories to the test DB and return an invoker."""
    import atlas_runtime.cli.main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: db)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)

    def invoke(*args: str):
        return runner.invoke(app, ["brain", *args])

    return invoke


def payload(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output.strip())


def test_add_is_idempotent_and_derives_the_id(cli):
    first = payload(cli("add", "--label", "Retry Safety", "--type", "concept", "--summary", "x"))
    assert first["id"] == "concept:retry-safety"
    assert first["metadata"]["summary"] == "x"
    cli("add", "--label", "Retry Safety", "--type", "concept")
    assert payload(cli("stats"))["nodes"] == 1


def test_list_search_and_show_round_trip(cli):
    cli("add", "--label", "Alpha System", "--type", "system")
    cli("add", "--label", "Beta Concept", "--type", "concept")
    cli("link", "--from", "system:alpha-system", "--to", "concept:beta-concept",
        "--relation", "depends_on")

    assert [n["id"] for n in payload(cli("list", "--type", "system"))] == ["system:alpha-system"]
    assert [n["id"] for n in payload(cli("search", "Alpha"))] == ["system:alpha-system"]

    shown = payload(cli("show", "system:alpha-system"))
    assert shown["node"]["label"] == "Alpha System"
    assert shown["edges"][0]["target_id"] == "concept:beta-concept"


def test_stats_inventories_the_graph(cli):
    cli("add", "--label", "A", "--type", "concept")
    cli("add", "--label", "B", "--type", "decision")
    cli("link", "--from", "concept:a", "--to", "decision:b")

    stats = payload(cli("stats"))
    assert stats["nodes"] == 2
    assert stats["edges"] == 1
    assert stats["by_entity_type"] == {"concept": 1, "decision": 1}
    assert stats["by_relation"] == {"relates_to": 1}


def test_update_rekeys_on_rename_and_carries_edges(cli):
    cli("add", "--label", "Retry Safety", "--type", "concept")
    cli("add", "--label", "Queues", "--type", "concept")
    cli("link", "--from", "concept:queues", "--to", "concept:retry-safety")

    renamed = payload(cli("update", "concept:retry-safety", "--label", "Idempotency"))
    assert renamed["node"]["id"] == "concept:idempotency"
    assert renamed["renamed_from"] == "concept:retry-safety"

    edges = payload(cli("show", "concept:idempotency"))["edges"]
    assert edges[0]["source_id"] == "concept:queues"
    assert cli("show", "concept:retry-safety").exit_code == 1


def test_update_requires_a_field_and_a_known_node(cli):
    cli("add", "--label", "A", "--type", "concept")
    assert cli("update", "concept:a").exit_code == 1
    assert cli("update", "concept:ghost", "--confidence", "0.1").exit_code == 1


def test_forget_refuses_without_yes_and_prints_the_undo_record(cli):
    cli("add", "--label", "Wrong Fact", "--type", "concept")
    cli("add", "--label", "Anchor", "--type", "concept")
    cli("link", "--from", "concept:anchor", "--to", "concept:wrong-fact")

    refused = cli("forget", "concept:wrong-fact")
    assert refused.exit_code == 1
    assert "--yes" in refused.output
    assert payload(cli("stats"))["nodes"] == 2

    removed = payload(cli("forget", "concept:wrong-fact", "--yes"))
    assert removed["node"]["label"] == "Wrong Fact"
    assert removed["edges"][0]["source_id"] == "concept:anchor"
    assert payload(cli("stats"))["nodes"] == 1
    assert cli("forget", "concept:wrong-fact", "--yes").exit_code == 1


def test_unlink_is_safe_to_retry(cli):
    cli("add", "--label", "A", "--type", "concept")
    cli("add", "--label", "B", "--type", "concept")
    cli("link", "--from", "concept:a", "--to", "concept:b", "--relation", "depends_on")

    args = ("unlink", "--from", "concept:a", "--to", "concept:b", "--relation", "depends_on")
    assert payload(cli(*args))["deleted"] is True
    assert payload(cli(*args))["deleted"] is False
    assert payload(cli("stats"))["nodes"] == 2


def test_link_rejects_missing_endpoints(cli):
    result = cli("link", "--from", "concept:ghost", "--to", "concept:other")
    assert result.exit_code == 1
    assert "exist" in result.output


def test_path_finds_and_reports_absence(cli):
    for label in ("A", "B", "C"):
        cli("add", "--label", label, "--type", "concept")
    cli("link", "--from", "concept:a", "--to", "concept:b")
    cli("link", "--from", "concept:b", "--to", "concept:c")

    found = payload(cli("path", "--from", "concept:a", "--to", "concept:c"))
    assert found == {"path": ["concept:a", "concept:b", "concept:c"], "found": True}
    assert payload(cli("path", "--from", "concept:c", "--to", "concept:a"))["found"] is False


def test_export_import_round_trips_through_a_file(cli, db, tmp_path):
    cli("add", "--label", "A", "--type", "concept")
    cli("add", "--label", "B", "--type", "concept")
    cli("link", "--from", "concept:a", "--to", "concept:b")

    out = tmp_path / "brain.json"
    written = payload(cli("export", "--out", str(out)))
    assert written["counts"] == {"nodes": 2, "edges": 1}

    db.execute("DELETE FROM brain_edges")
    db.execute("DELETE FROM brain_nodes")
    assert payload(cli("stats"))["nodes"] == 0

    restored = payload(cli("import", str(out)))
    assert (restored["nodes"], restored["edges"]) == (2, 1)
    assert payload(cli("stats"))["nodes"] == 2

    # Re-importing the same file converges rather than duplicating.
    cli("import", str(out))
    assert payload(cli("stats"))["nodes"] == 2


def test_import_reports_bad_input_instead_of_tracebacking(cli, tmp_path):
    missing = cli("import", str(tmp_path / "nope.json"))
    assert missing.exit_code == 1
    assert "not found" in missing.output

    garbage = tmp_path / "garbage.json"
    garbage.write_text("[]", encoding="utf-8")
    assert cli("import", str(garbage)).exit_code == 1


def test_export_to_stdout_is_valid_json(cli):
    cli("add", "--label", "A", "--type", "concept")
    exported = payload(cli("export"))
    assert exported["version"] == 1
    assert [n["id"] for n in exported["nodes"]] == ["concept:a"]
