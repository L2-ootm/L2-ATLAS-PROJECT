"""Tests for the optional-modules registry (atlas_runtime.module_service).

Uses the shared `db` fixture (applies all migrations incl. 0007, which seeds the
cashflow module as inactive).
"""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import module_service
from atlas_core.schemas.core import Module


def test_seed_cashflow_present_and_inactive(db: sqlite3.Connection) -> None:
    mods = module_service.list_modules(db)
    assert any(m.id == "cashflow" for m in mods)
    cashflow = module_service.get_module(db, "cashflow")
    assert isinstance(cashflow, Module)
    assert cashflow.status == "inactive"
    assert cashflow.activated_at is None


def test_activate_then_deactivate(db: sqlite3.Connection, lock: threading.Lock) -> None:
    activated = module_service.set_active(db, lock, module_id="cashflow", active=True)
    assert activated.status == "active"
    assert activated.activated_at is not None
    # persisted
    assert module_service.get_module(db, "cashflow").status == "active"

    deactivated = module_service.set_active(db, lock, module_id="cashflow", active=False)
    assert deactivated.status == "inactive"
    assert deactivated.activated_at is None


def test_activate_is_idempotent(db: sqlite3.Connection, lock: threading.Lock) -> None:
    module_service.set_active(db, lock, module_id="cashflow", active=True)
    again = module_service.set_active(db, lock, module_id="cashflow", active=True)
    assert again.status == "active"


def test_unknown_module_raises(db: sqlite3.Connection, lock: threading.Lock) -> None:
    with pytest.raises(module_service.ModuleError):
        module_service.set_active(db, lock, module_id="nope", active=True)


# --- manifest modules (framework slice 1) ------------------------------------


VALID_MANIFEST = """\
id: demo-mod
name: Demo Mod
version: 1.2.3
description: demo
capabilities:
  commands:
    - name: demo
      description: demo command
      template: "Do the demo thing. $ARGUMENTS"
  pages:
    - id: main
      title: Demo
      blocks:
        - kind: heading
          text: Demo
"""


def _write_module(root, module_id: str, body: str = VALID_MANIFEST):
    target = root / module_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "module.yaml").write_text(body, encoding="utf-8")
    return target


def test_discover_and_sync(db, lock, tmp_path) -> None:
    _write_module(tmp_path, "demo-mod")
    summary = module_service.sync_modules(db, lock, roots=[tmp_path])
    assert summary["discovered"] == ["demo-mod"]
    assert summary["problems"] == []
    mod = module_service.get_module(db, "demo-mod")
    assert mod is not None
    assert mod.status == "inactive"  # new modules start off
    assert mod.version == "1.2.3"
    assert not mod.missing


def test_sync_preserves_activation_and_flags_missing(db, lock, tmp_path) -> None:
    _write_module(tmp_path, "demo-mod")
    module_service.sync_modules(db, lock, roots=[tmp_path])
    module_service.set_active(db, lock, module_id="demo-mod", active=True)

    # re-sync: still active
    module_service.sync_modules(db, lock, roots=[tmp_path])
    assert module_service.get_module(db, "demo-mod").status == "active"

    # source vanishes: flagged missing, state kept, commands hidden
    summary = module_service.sync_modules(db, lock, roots=[tmp_path / "empty"])
    assert "demo-mod" in summary["missing"]
    mod = module_service.get_module(db, "demo-mod")
    assert mod.missing and mod.status == "active"
    assert module_service.module_commands(db) == []

    # reappears: flag clears
    module_service.sync_modules(db, lock, roots=[tmp_path])
    assert not module_service.get_module(db, "demo-mod").missing


def test_invalid_manifest_reported_not_fatal(db, lock, tmp_path) -> None:
    _write_module(tmp_path, "demo-mod")
    _write_module(tmp_path, "broken", "id: BAD ID\nname: x\n")
    summary = module_service.sync_modules(db, lock, roots=[tmp_path])
    assert summary["discovered"] == ["demo-mod"]
    assert len(summary["problems"]) == 1


def test_module_commands_only_active_and_no_shadowing(db, lock, tmp_path) -> None:
    _write_module(tmp_path, "demo-mod")
    shadow = VALID_MANIFEST.replace("demo-mod", "shadow-mod").replace(
        "name: demo", "name: review"
    )
    _write_module(tmp_path, "shadow-mod", shadow)
    module_service.sync_modules(db, lock, roots=[tmp_path])

    # inactive: no commands at all
    assert module_service.module_commands(db) == []

    module_service.set_active(db, lock, module_id="demo-mod", active=True)
    module_service.set_active(db, lock, module_id="shadow-mod", active=True)
    commands = module_service.module_commands(db)
    names = [c["name"] for c in commands]
    assert "demo" in names
    assert "review" not in names  # built-in name never shadowed
    demo = next(c for c in commands if c["name"] == "demo")
    assert demo["module"] == "demo-mod"
    assert "$ARGUMENTS" in demo["template"]


def test_scaffold_creates_valid_module(db, lock, tmp_path) -> None:
    target = module_service.create_module_scaffold(
        "voice-notes", target_root=tmp_path
    )
    assert (target / "module.yaml").is_file()
    summary = module_service.sync_modules(db, lock, roots=[tmp_path])
    assert summary["discovered"] == ["voice-notes"]
    assert summary["problems"] == []
    with pytest.raises(ValueError):
        module_service.create_module_scaffold("voice-notes", target_root=tmp_path)
    with pytest.raises(ValueError):
        module_service.create_module_scaffold("Bad Id!", target_root=tmp_path)


def test_bundled_modules_are_exactly_the_first_party_set(db, lock) -> None:
    """The base install ships only first-party modules, no toys.

    The bundled example module was removed deliberately. GSD/L2 (execution
    doctrine), Outreach (evidence-gated outbound) and Admissions (the college
    application campaign) are real product surfaces and are the sanctioned
    bundled entries. Anything else appearing here is scope creep — extend this
    list only with an explicit product decision.

    Admissions was added 2026-08-13, deliberately: it is the first module whose
    records live outside ATLAS entirely (Pattern Forge owns them), which is the
    shape every future integration with an external product will take. It is
    bundled rather than operator-installed so its doctrine is version-controlled
    and reviewable; like the others it ships inactive.
    """
    summary = module_service.sync_modules(
        db, lock, roots=[module_service.bundled_modules_dir()]
    )
    assert summary["discovered"] == ["admissions", "gsd", "outreach"]
    assert summary["problems"] == []


def test_bundled_modules_start_inactive(db, lock) -> None:
    """Shipping a module must never switch it on — the base install stays lean."""
    module_service.sync_modules(db, lock, roots=[module_service.bundled_modules_dir()])
    for module_id in ("admissions", "gsd", "outreach"):
        module = module_service.get_module(db, module_id)
        assert module is not None and module.status == "inactive"


# --- the admissions module -------------------------------------------------
#
# A doctrine file with no delivery test rots silently: it stays on disk, reads
# well, and reaches no run. These assert against the REAL bundled manifest and
# the REAL retrieval path rather than a fixture, because a fixture would agree
# with whoever wrote it.


def _admissions_active(db, lock):
    module_service.sync_modules(db, lock, roots=[module_service.bundled_modules_dir()])
    module_service.set_active(db, lock, module_id="admissions", active=True)


def test_admissions_always_doctrine_reaches_every_run(db, lock) -> None:
    """The two rules a run cannot be correct without arrive with no term match."""
    _admissions_active(db, lock)
    ids = [b.get("id") for b in module_service.active_context_blocks(db, terms=())]
    assert "doctrine" in ids, "the RFA rule and the no-chancing rule must always be present"
    assert "limits" in ids


def test_admissions_matched_doctrine_routes_by_subject(db, lock) -> None:
    _admissions_active(db, lock)

    essay_ids = [b.get("id") for b in module_service.active_context_blocks(db, terms=("essay", "draft"))]
    assert "essays" in essay_ids
    assert "list" not in essay_ids, "list doctrine on an essay run is budget spent on nothing"

    list_ids = [b.get("id") for b in module_service.active_context_blocks(db, terms=("list", "aid"))]
    assert "list" in list_ids
    assert "essays" not in list_ids


def test_admissions_never_declares_its_own_collections(db, lock) -> None:
    """Pattern Forge owns the record. A collection here would be a second writer.

    This is the property the whole integration rests on, so it is asserted rather
    than left to the manifest comment that explains it.
    """
    module_service.sync_modules(db, lock, roots=[module_service.bundled_modules_dir()])
    manifest = module_service.get_manifest(db, "admissions")
    assert manifest is not None
    assert module_service.capability(manifest, "collections") == []


def test_admissions_mcp_ships_disabled_and_references_its_credential(db, lock) -> None:
    """A bundled MCP server must not be live, and must not carry a literal key."""
    _admissions_active(db, lock)
    declared = [
        d for d in module_service.module_mcp_declarations(db)
        if d.get("name") == "pattern-forge-application"
    ]
    assert len(declared) == 1
    assert declared[0].get("enabled") is False
    for value in (declared[0].get("env") or {}).values():
        assert str(value).startswith("${"), "a literal-looking credential must never ship"


def test_admissions_doctrine_refuses_to_estimate_chances(db, lock) -> None:
    """The one rule whose absence would be actively harmful, pinned to the text.

    Headline admit rates are the wrong denominator for an applicant the pool does
    not describe, so a chancing number would be confidently wrong in the direction
    that causes harm. If this rule is ever softened it should be a deliberate edit
    that fails this test, not a quiet rewrite.
    """
    _admissions_active(db, lock)
    blocks = module_service.active_context_blocks(db, terms=())
    doctrine = next(b for b in blocks if b.get("id") == "doctrine")
    assert "do not estimate admission chances" in doctrine["text"].lower()
