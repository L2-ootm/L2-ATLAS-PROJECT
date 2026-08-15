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


# ---------------------------------------------------------------------------
# `brain remember` — teaching ATLAS how this operator works
# ---------------------------------------------------------------------------


def test_remember_records_one_sentence_as_stated(cli):
    """`brain add` wants a label, a type and a summary before it records anything.

    That is three decisions too many for the thing an operator most wants to
    capture: a preference, said once, in passing.
    """
    node = payload(cli("remember", "keep commits atomic"))

    assert node["entity_type"] == "preference"
    assert node["grade"] == "stated"
    assert node["metadata"]["summary"] == "keep commits atomic"


def test_an_operator_statement_outranks_what_an_agent_inferred(db, cli):
    """The point of `stated`: an inference can never quietly replace it."""
    from atlas_core.schemas import provenance
    from atlas_core.schemas.brain import BrainNode
    from atlas_runtime import brain_service

    stated = payload(cli("remember", "never force push"))
    guess = BrainNode(
        id=stated["id"],
        entity_type="preference",
        label="never force push",
        source_id="run:r1",
        source_version="2026-08-15T01:00:00Z",
        updated_at="2026-08-15T01:00:00Z",
        confidence=1.0,
        grade=provenance.DERIVED,
        metadata_json=json.dumps({"summary": "force pushing seems fine actually"}),
    )

    outcome = brain_service.upsert_node_checked(db, guess)

    assert not outcome.written
    assert "never force push" in brain_service.explain(db, stated["id"]).metadata_json


def test_remember_refuses_an_unknown_kind(cli):
    """A vocabulary the operator has to guess at is one they stop using."""
    result = cli("remember", "something", "--kind", "vibes")
    assert result.exit_code == 1
    assert "preference" in result.output


def test_remember_redacts_before_storing(cli, db):
    """The operator can paste a key into a sentence as easily as an agent can."""
    node = payload(cli("remember", "auth with api_key=sk-operator-leak-1"))

    stored = db.execute(
        "SELECT metadata_json, label FROM brain_nodes WHERE id=?", (node["id"],)
    ).fetchone()
    assert "sk-operator-leak-1" not in stored[0]
    assert "sk-operator-leak-1" not in stored[1]


def test_a_long_sentence_keeps_its_full_text_in_the_summary(cli):
    """The label is trimmed so the graph can key on it; nothing is lost."""
    sentence = "always " + "and ".join(f"thing{i} " for i in range(40))
    node = payload(cli("remember", sentence, "--kind", "convention"))

    assert len(node["label"]) <= 80
    assert node["metadata"]["summary"].startswith("always thing0")


# ---------------------------------------------------------------------------
# `brain conflicts` — the escalation path stops ending in a table
# ---------------------------------------------------------------------------


def _contested(db, cli) -> None:
    """Make the operator state an intent, then have reality contradict it."""
    from atlas_core.schemas import provenance
    from atlas_core.schemas.brain import BrainNode
    from atlas_runtime import brain_service, graph_bridge

    payload(cli("remember", "ship on friday", "--kind", "intent"))
    node_id = graph_bridge.node_id_for("intent", "ship on friday")
    brain_service.upsert_node_checked(db, BrainNode(
        id=node_id, entity_type="intent", label="ship on friday",
        source_id="run:r1", source_version="2026-08-15T01:00:00Z",
        updated_at="2026-08-15T01:00:00Z", confidence=1.0,
        grade=provenance.VERIFIED,
        metadata_json=json.dumps({"summary": "the build is broken"}),
    ))


def test_conflicts_lists_what_lost_and_what_was_kept(cli, db):
    _contested(db, cli)

    rows = payload(cli("conflicts"))

    assert len(rows) == 1
    assert rows[0]["kept"]["grade"] == "stated"
    assert rows[0]["rejected"]["grade"] == "verified"
    assert rows[0]["needs_operator"] is True


def test_conflicts_can_show_only_what_atlas_refused_to_decide(cli, db):
    """Ordinary rank losses are noise next to a decision the operator owes."""
    from atlas_core.schemas import provenance

    from atlas_core.schemas.brain import BrainNode
    from atlas_runtime import brain_service, graph_bridge

    _contested(db, cli)
    # An ordinary rank loss: a guess contradicting an observation.
    for grade, summary in (
        (provenance.OBSERVED, "port 8080"), (provenance.ASSERTED, "port 9090"),
    ):
        brain_service.upsert_node_checked(db, BrainNode(
            id=graph_bridge.node_id_for("concept", "Port"), entity_type="concept",
            label="Port", source_id="run:r2", source_version="2026-08-15T02:00:00Z",
            updated_at="2026-08-15T02:00:00Z", confidence=0.8, grade=grade,
            metadata_json=json.dumps({"summary": summary}),
        ))

    assert len(payload(cli("conflicts"))) == 2
    only_escalated = payload(cli("conflicts", "--needs-operator"))
    assert len(only_escalated) == 1
    assert only_escalated[0]["needs_operator"] is True


def test_a_conflict_can_be_acked_once_it_has_been_acted_on(cli, db):
    """A list the operator cannot clear stops being read."""
    _contested(db, cli)
    conflict_id = payload(cli("conflicts"))[0]["id"]

    assert payload(cli("conflicts", "--ack", str(conflict_id)))["acked"] == conflict_id
    assert payload(cli("conflicts")) == []


def test_acking_an_unknown_conflict_is_an_error_not_a_silent_success(cli):
    result = cli("conflicts", "--ack", "9999")
    assert result.exit_code == 1
