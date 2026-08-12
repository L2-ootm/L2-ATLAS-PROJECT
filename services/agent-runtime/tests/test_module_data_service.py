"""Tests for module capability v2: typed records, doctrine injection, tool bridge.

Contract: docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from atlas_runtime import module_bridge, module_data_service, module_service

MANIFEST = """\
id: demo
name: Demo
version: 0.2.0
description: capability v2 fixture
capabilities:
  context:
    - id: doctrine
      title: Demo doctrine
      path: context/doctrine.md
      inject: always
      max_tokens: 200
    - id: deep
      title: Deep reference
      path: context/deep.md
      inject: on_demand
    - id: matched
      title: Matched only
      path: context/matched.md
      inject: matched
      terms: [outreach]
  collections:
    - id: prospects
      title: Prospects
      label_field: name
      fields:
        - {name: name, type: text, required: true}
        - {name: tier, type: enum, options: [S, A, B], default: B}
        - {name: score, type: number, min: 0, max: 100}
        - {name: site, type: url}
        - {name: tags, type: tags}
        - {name: active, type: bool}
  workflows:
    - id: qualify
      title: Qualify
      steps: ["look", "decide"]
      done_when: a decision is recorded
  mcp:
    - name: demo-search
      command: npx
      args: ["-y", "demo-mcp"]
      env: {DEMO_KEY: "${DEMO_KEY}"}
      description: demo server
"""


def _install(tmp_path, db, lock, *, manifest_text: str = MANIFEST, activate: bool = True):
    root = tmp_path / "modules"
    module_dir = root / "demo"
    (module_dir / "context").mkdir(parents=True)
    (module_dir / "module.yaml").write_text(manifest_text, encoding="utf-8")
    (module_dir / "context" / "doctrine.md").write_text("Always follow the demo rules.", encoding="utf-8")
    (module_dir / "context" / "deep.md").write_text("Deep reference material.", encoding="utf-8")
    (module_dir / "context" / "matched.md").write_text("Only when outreach is in play.", encoding="utf-8")
    module_service.sync_modules(db, lock, roots=[root])
    if activate:
        module_service.set_active(db, lock, module_id="demo", active=True)
    return module_dir


# --- manifest v2 validation -------------------------------------------------


def test_manifest_v2_capabilities_parse(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    manifest = module_service.active_manifest(db, "demo")
    assert manifest is not None
    assert [c["id"] for c in module_service.capability(manifest, "collections")] == ["prospects"]
    assert [w["id"] for w in module_service.capability(manifest, "workflows")] == ["qualify"]
    assert module_service.capability(manifest, "mcp")[0]["name"] == "demo-search"


@pytest.mark.parametrize(
    "bad, message",
    [
        ("capabilities:\n  collections:\n    - id: x\n      fields: []\n", "no fields"),
        (
            "capabilities:\n  collections:\n    - id: x\n      fields:\n"
            "        - {name: f, type: nope}\n",
            "unknown type",
        ),
        (
            "capabilities:\n  context:\n    - {id: c, path: ../../etc/passwd}\n",
            "inside the module",
        ),
        (
            "capabilities:\n  context:\n    - {id: c, path: a.md, inject: matched}\n",
            "needs terms",
        ),
        ("capabilities:\n  workflows:\n    - {id: w, steps: []}\n", "no steps"),
        (
            "capabilities:\n  mcp:\n    - {name: s, transport: http}\n",
            "needs a url",
        ),
    ],
)
def test_invalid_manifests_are_rejected(bad: str, message: str) -> None:
    import yaml

    text = f"id: bad\nname: Bad\n{bad}"
    with pytest.raises(ValueError, match=message):
        module_service.validate_manifest(yaml.safe_load(text), source="test")


def test_literal_secret_in_mcp_env_is_rejected() -> None:
    import yaml

    text = (
        "id: bad\nname: Bad\ncapabilities:\n  mcp:\n"
        "    - name: s\n      command: x\n      env: {OPENAI_API_KEY: 'sk-abcdefghijklmnopqrstuvwxyz0123456789'}\n"
    )
    with pytest.raises(ValueError, match="literal secret"):
        module_service.validate_manifest(yaml.safe_load(text), source="test")


# --- context injection ------------------------------------------------------


def test_always_context_injected_matched_only_on_terms(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    blocks = module_service.active_context_blocks(db)
    assert [b["id"] for b in blocks] == ["doctrine"]

    blocks = module_service.active_context_blocks(db, terms=("outreach",))
    assert [b["id"] for b in blocks] == ["doctrine", "matched"]


def test_on_demand_context_never_auto_injects(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    blocks = module_service.active_context_blocks(db, terms=("deep", "reference"))
    assert "deep" not in [b["id"] for b in blocks]


def test_inactive_module_injects_nothing(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock, activate=False)
    assert module_service.active_context_blocks(db) == []


def test_context_respects_the_token_budget(tmp_path, db, lock) -> None:
    module_dir = _install(tmp_path, db, lock)
    (module_dir / "context" / "doctrine.md").write_text("word " * 4000, encoding="utf-8")
    module_service.sync_modules(db, lock, roots=[module_dir.parent])
    blocks = module_service.active_context_blocks(db, token_budget=100)
    # max_tokens=200 truncates the file; the block still fits because the first
    # block is always admitted (never emit an empty doctrine section silently).
    assert blocks and blocks[0]["tokens"] <= 210
    assert "truncated" in blocks[0]["text"]


def test_context_service_renders_module_doctrine(tmp_path, db, lock) -> None:
    from atlas_runtime import context_service

    _install(tmp_path, db, lock)
    context = context_service.assemble_context(db)
    assert "Active Module Doctrine" in context.markdown
    assert "Always follow the demo rules." in context.markdown
    assert "module:demo:doctrine" in context.sources


# --- records ----------------------------------------------------------------


def test_create_validates_and_defaults(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    record = module_data_service.create_record(
        db, lock, module_id="demo", collection_id="prospects",
        data={"name": "Acme Corp", "score": 80, "site": "acme.com", "tags": "a, b"},
    )
    assert record["id"] == "acme-corp"
    assert record["data"]["tier"] == "B"  # default applied
    assert record["data"]["site"] == "https://acme.com"  # url normalized
    assert record["data"]["tags"] == ["a", "b"]


def test_required_field_and_enum_are_enforced(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    with pytest.raises(module_data_service.ModuleDataError, match="required"):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects", data={"score": 1}
        )
    with pytest.raises(module_data_service.ModuleDataError, match="must be one of"):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects",
            data={"name": "X", "tier": "Z"},
        )
    with pytest.raises(module_data_service.ModuleDataError, match="unknown field"):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects",
            data={"name": "X", "stage": "ready"},
        )


def test_number_bounds_enforced(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    with pytest.raises(module_data_service.ModuleDataError, match="<= 100"):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects",
            data={"name": "X", "score": 101},
        )


def test_create_is_idempotent_on_the_same_id(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    first = module_data_service.create_record(
        db, lock, module_id="demo", collection_id="prospects", data={"name": "Acme"}
    )
    second = module_data_service.create_record(
        db, lock, module_id="demo", collection_id="prospects",
        data={"name": "Acme", "score": 42},
    )
    assert first["id"] == second["id"]
    assert second["data"]["score"] == 42
    assert module_data_service.count_records(db, "demo", "prospects") == 1


def test_update_merges_and_delete_is_soft(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    module_data_service.create_record(
        db, lock, module_id="demo", collection_id="prospects",
        data={"name": "Acme", "score": 10},
    )
    updated = module_data_service.update_record(
        db, lock, module_id="demo", collection_id="prospects",
        record_id="acme", data={"score": 90},
    )
    assert updated["data"] == {"name": "Acme", "score": 90, "tier": "B"}

    removed = module_data_service.delete_record(
        db, lock, module_id="demo", collection_id="prospects", record_id="acme"
    )
    assert removed["data"]["name"] == "Acme"  # undo record returned
    assert module_data_service.get_record(db, "demo", "prospects", "acme") is None
    row = db.execute("SELECT deleted_at FROM module_records WHERE id='acme'").fetchone()
    assert row[0] is not None  # payload retained


def test_query_filters_and_search(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    for name, tier in (("Alpha", "S"), ("Beta", "A"), ("Gamma", "S")):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects",
            data={"name": name, "tier": tier},
        )
    tier_s = module_data_service.query_records(db, "demo", "prospects", where={"tier": "S"})
    assert {r["id"] for r in tier_s} == {"alpha", "gamma"}
    found = module_data_service.query_records(db, "demo", "prospects", search="bet")
    assert [r["id"] for r in found] == ["beta"]


def test_records_unreachable_while_module_is_inactive(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    module_data_service.create_record(
        db, lock, module_id="demo", collection_id="prospects", data={"name": "Acme"}
    )
    module_service.set_active(db, lock, module_id="demo", active=False)
    with pytest.raises(module_data_service.ModuleDataError, match="not active"):
        module_data_service.query_records(db, "demo", "prospects")
    # ...but the data survives deactivation and returns with it.
    module_service.set_active(db, lock, module_id="demo", active=True)
    assert module_data_service.count_records(db, "demo", "prospects") == 1


def test_payload_size_is_bounded(tmp_path, db, lock) -> None:
    _install(tmp_path, db, lock)
    with pytest.raises(module_data_service.ModuleDataError, match="exceeds"):
        module_data_service.create_record(
            db, lock, module_id="demo", collection_id="prospects",
            data={"name": "x" * (module_data_service.MAX_PAYLOAD_BYTES + 10)},
        )


# --- the agent tool ---------------------------------------------------------


@pytest.fixture()
def bound_bridge(monkeypatch, db: sqlite3.Connection, lock: threading.Lock):
    """Bind the bridge's shared-state resolver to the test DB."""
    monkeypatch.setattr(module_bridge, "_shared_state", lambda: (db, lock))
    monkeypatch.setattr(module_bridge, "_current_run_id", lambda *a, **k: None)
    return module_bridge


def _call(bridge, **kwargs) -> dict:
    return json.loads(bridge.atlas_module_tool(kwargs))


def test_tool_lists_only_active_modules(tmp_path, db, lock, bound_bridge) -> None:
    _install(tmp_path, db, lock, activate=False)
    assert _call(bound_bridge, op="list")["count"] == 0
    module_service.set_active(db, lock, module_id="demo", active=True)
    listed = _call(bound_bridge, op="list")
    assert listed["modules"][0]["id"] == "demo"
    assert listed["modules"][0]["collections"][0]["id"] == "prospects"


def test_tool_record_roundtrip(tmp_path, db, lock, bound_bridge) -> None:
    _install(tmp_path, db, lock)
    created = _call(
        bound_bridge, op="create", module="demo", collection="prospects",
        data={"name": "Acme", "tier": "S"},
    )
    assert created["ok"] and created["record"]["id"] == "acme"

    queried = _call(bound_bridge, op="query", module="demo", collection="prospects")
    assert queried["count"] == 1

    updated = _call(
        bound_bridge, op="update", module="demo", collection="prospects",
        record_id="acme", data={"score": 71},
    )
    assert updated["record"]["data"]["score"] == 71

    deleted = _call(
        bound_bridge, op="delete", module="demo", collection="prospects", record_id="acme"
    )
    assert deleted["ok"] and deleted["removed"]["id"] == "acme"


def test_tool_errors_are_actionable_never_raised(tmp_path, db, lock, bound_bridge) -> None:
    _install(tmp_path, db, lock)
    unknown = _call(bound_bridge, op="query", module="ghost", collection="x")
    assert unknown["ok"] is False and "not active" in unknown["error"]

    bad_collection = _call(bound_bridge, op="query", module="demo", collection="ghosts")
    assert bad_collection["ok"] is False and "prospects" in bad_collection["error"]

    bad_op = _call(bound_bridge, op="teleport", module="demo")
    assert bad_op["ok"] is False


def test_tool_context_and_workflow(tmp_path, db, lock, bound_bridge) -> None:
    _install(tmp_path, db, lock)
    ctx = _call(bound_bridge, op="context", module="demo", context_id="deep")
    assert ctx["context"][0]["text"].startswith("Deep reference")

    flows = _call(bound_bridge, op="workflow", module="demo")
    assert flows["workflows"][0]["id"] == "qualify"
    one = _call(bound_bridge, op="workflow", module="demo", workflow_id="qualify")
    assert one["workflow"]["steps"] == ["look", "decide"]
