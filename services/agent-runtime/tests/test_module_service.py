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


def test_empty_bundled_modules_directory_syncs_cleanly(db, lock) -> None:
    """The base install stays lean until the operator creates a module."""
    summary = module_service.sync_modules(
        db, lock, roots=[module_service.bundled_modules_dir()]
    )
    assert summary["discovered"] == []
    assert summary["problems"] == []
