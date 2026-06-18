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
