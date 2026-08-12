"""The bundled outreach module, exercised through the real capability paths.

These are contract tests for a shipped module: they run against
`modules/outreach/module.yaml` as it exists on disk, so a manifest edit that
breaks the CRM, the doctrine budget or a workflow fails here rather than in a
live outreach session.
"""
from __future__ import annotations

import json

import pytest

from atlas_runtime import (
    context_service,
    mcp_service,
    module_bridge,
    module_data_service,
    module_service,
)


@pytest.fixture()
def outreach(db, lock):
    """Sync the real bundled modules and activate outreach."""
    module_service.sync_modules(db, lock, roots=[module_service.bundled_modules_dir()])
    module_service.set_active(db, lock, module_id="outreach", active=True)
    return module_service.active_manifest(db, "outreach")


def test_manifest_declares_the_full_capability_surface(outreach) -> None:
    caps = module_service.capability
    assert {c["id"] for c in caps(outreach, "collections")} == {
        "prospects", "signals", "touches", "gates",
        "sequences", "objections", "experiments",
    }
    assert {w["id"] for w in caps(outreach, "workflows")} >= {
        "research_prospect", "gate_prospect", "draft_opening",
        "handle_reply", "daily_queue", "weekly_review",
    }
    assert [c["name"] for c in caps(outreach, "commands")][0] == "outreach"


def test_doctrine_and_compliance_are_always_injected(db, lock, outreach) -> None:
    blocks = module_service.active_context_blocks(db)
    assert [b["id"] for b in blocks] == ["doctrine", "compliance"]
    text = "\n".join(b["text"] for b in blocks)
    # The two constraints that make this module safe to run at all.
    assert "human sends" in text.lower()
    assert "cold-dm" in text.lower() or "cold dm" in text.lower()


def test_always_injected_doctrine_fits_the_budget(db, lock, outreach) -> None:
    """Activating outreach must not eat the run's context budget."""
    blocks = module_service.active_context_blocks(db)
    assert sum(b["tokens"] for b in blocks) <= 1200
    assert all("truncated" not in b["text"] for b in blocks)


def test_matched_doctrine_appears_only_for_its_terms(db, lock, outreach) -> None:
    ids = [b["id"] for b in module_service.active_context_blocks(db, terms=("draft", "reply"))]
    assert "messaging" in ids and "qualification" not in ids

    ids = [b["id"] for b in module_service.active_context_blocks(db, terms=("gate", "score"))]
    assert "qualification" in ids and "messaging" not in ids


def test_on_demand_doctrine_is_reachable_but_never_auto_injected(db, lock, outreach) -> None:
    auto = [b["id"] for b in module_service.active_context_blocks(db, terms=("research",))]
    assert "research" not in auto

    # Reachable on request — the tool path is covered in the tool-surface test.
    entry = next(
        c for c in module_service.capability(outreach, "context") if c["id"] == "research"
    )
    assert module_service.read_context_file(outreach, entry).startswith("# Research protocol")


def test_run_context_carries_the_doctrine(db, lock, outreach) -> None:
    context = context_service.assemble_context(db)
    assert "Active Module Doctrine" in context.markdown
    assert "module:outreach:doctrine" in context.sources
    assert "module:outreach:compliance" in context.sources


def test_deactivating_outreach_removes_it_from_the_prompt(db, lock, outreach) -> None:
    module_service.set_active(db, lock, module_id="outreach", active=False)
    context = context_service.assemble_context(db)
    assert "Active Module Doctrine" not in context.markdown


def test_the_crm_accepts_a_realistic_pipeline_record(db, lock, outreach) -> None:
    prospect = module_data_service.create_record(
        db, lock, module_id="outreach", collection_id="prospects",
        data={
            "name": "Programa Folego",
            "handle": "@programafolego",
            "niche": "Running media",
            "tier": "A",
            "relationship": "cold",
            "stage": "research",
            "score": 71,
            "current_offer": "Content, Telegram offers, book, sponsorships.",
            "gap_hypothesis": "No recurring community product.",
            "evidence_level": "reported",
            "next_action": "Confirm no equivalent recurring product exists.",
            "next_action_at": "2026-08-13",
            "links": ["https://programafolego.com.br/"],
        },
    )
    assert prospect["id"] == "programa-folego"

    signal = module_data_service.create_record(
        db, lock, module_id="outreach", collection_id="signals",
        data={
            "label": "Sells a book and sponsorships",
            "prospect": "programa-folego",
            "confidence": "verified",
            "kind": "offer",
            "url": "https://programafolego.com.br/",
            "captured_at": "2026-08-12",
        },
    )
    assert signal["data"]["confidence"] == "verified"

    touch = module_data_service.create_record(
        db, lock, module_id="outreach", collection_id="touches",
        data={
            "summary": "Opening DM drafted",
            "prospect": "programa-folego",
            "channel": "dm",
            "direction": "outbound",
            "outcome": "drafted",
            "variant": "v1-observation",
            "at": "2026-08-12",
        },
    )
    assert touch["data"]["outcome"] == "drafted"

    gate = module_data_service.create_record(
        db, lock, module_id="outreach", collection_id="gates",
        data={
            "label": "Folego demand gate",
            "prospect": "programa-folego",
            "gate": "g1-demand",
            "decision": "hold",
            "evidence": "Only reported-class demand so far.",
            "rationale": "No captured audience requests yet.",
            "decided_at": "2026-08-12",
        },
    )
    assert gate["data"]["decision"] == "hold"

    stats = {s["id"]: s["count"] for s in module_data_service.collection_stats(db, "outreach")}
    assert stats["prospects"] == 1 and stats["signals"] == 1
    assert stats["touches"] == 1 and stats["gates"] == 1


def test_the_crm_rejects_an_invalid_stage(db, lock, outreach) -> None:
    with pytest.raises(module_data_service.ModuleDataError, match="must be one of"):
        module_data_service.create_record(
            db, lock, module_id="outreach", collection_id="prospects",
            data={"name": "X", "stage": "won"},
        )


def test_mcp_templates_register_disabled(db, lock, outreach) -> None:
    """Shipping MCP declarations must never start talking to a third party."""
    summary = mcp_service.sync_module_servers(db, lock)
    assert "outreach-web" in summary["registered"]
    for name in ("outreach-web", "outreach-crm-bridge"):
        assert mcp_service.get_server(db, name)["enabled"] is False
    assert mcp_service.enabled_servers(db) == []


def test_tool_surface_reaches_the_module(monkeypatch, db, lock, outreach) -> None:
    monkeypatch.setattr(module_bridge, "_shared_state", lambda: (db, lock))
    monkeypatch.setattr(module_bridge, "_current_run_id", lambda *a, **k: None)

    listed = json.loads(module_bridge.atlas_module_tool({"op": "list"}))
    assert listed["modules"][0]["id"] == "outreach"

    workflow = json.loads(
        module_bridge.atlas_module_tool(
            {"op": "workflow", "module": "outreach", "workflow_id": "draft_opening"}
        )
    )
    steps = " ".join(workflow["workflow"]["steps"]).lower()
    assert "does not send" in steps or "human" in workflow["workflow"]["done_when"].lower()

    on_demand = json.loads(
        module_bridge.atlas_module_tool(
            {"op": "context", "module": "outreach", "context_id": "research"}
        )
    )
    assert on_demand["context"][0]["text"].startswith("# Research protocol")
