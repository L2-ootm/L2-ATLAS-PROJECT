"""Tests for atlas_runtime.model_registry — live model discovery (D-017)."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from atlas_runtime import model_registry


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


@pytest.fixture()
def lock() -> threading.Lock:
    return threading.Lock()


def _fake_fetcher(ids: list[str]):
    return lambda: [{"id": i, "owned_by": "test-provider"} for i in ids]


def test_first_refresh_adds_all_models(conn, lock):
    result = model_registry.refresh(
        conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-b"])
    )
    assert result.added == ["m-a", "m-b"]
    assert result.retained == []
    assert result.deactivated == []
    assert result.total_active == 2


def test_new_model_appearing_is_added_on_refresh(conn, lock):
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a"]))
    result = model_registry.refresh(
        conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-new"])
    )
    assert result.added == ["m-new"]
    assert result.retained == ["m-a"]
    assert result.deactivated == []


def test_vanished_model_is_deactivated_not_deleted(conn, lock):
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-b"]))
    result = model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a"]))
    assert result.deactivated == ["m-b"]
    rows = model_registry.list_models(conn, active_only=False)
    assert {r["model_id"]: r["active"] for r in rows} == {"m-a": 1, "m-b": 0}


def test_returning_model_is_reactivated(conn, lock):
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-b"]))
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a"]))
    result = model_registry.refresh(
        conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-b"])
    )
    assert result.retained == ["m-a", "m-b"]
    active = model_registry.list_models(conn, active_only=True)
    assert {r["model_id"] for r in active} == {"m-a", "m-b"}


def test_sources_are_isolated(conn, lock):
    model_registry.refresh(conn, lock, source="gw1", fetcher=_fake_fetcher(["m-a"]))
    result = model_registry.refresh(conn, lock, source="gw2", fetcher=_fake_fetcher(["m-x"]))
    # gw2 refresh must not deactivate gw1's models
    assert result.deactivated == []
    active = model_registry.list_models(conn, active_only=True)
    assert {r["model_id"] for r in active} == {"m-a", "m-x"}


def test_list_models_active_only_filters(conn, lock):
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-a", "m-b"]))
    model_registry.refresh(conn, lock, source="gw", fetcher=_fake_fetcher(["m-b"]))
    assert {r["model_id"] for r in model_registry.list_models(conn)} == {"m-b"}
    assert len(model_registry.list_models(conn, active_only=False)) == 2


def test_seed_default_models_inserts_baseline(conn, lock):
    inserted = model_registry.seed_default_models(conn, lock)
    assert inserted == [m for m, _ in model_registry.DEFAULT_SEED_MODELS]
    rows = {r["model_id"]: r for r in model_registry.list_models(conn)}
    assert set(rows) == {m for m, _ in model_registry.DEFAULT_SEED_MODELS}
    assert all(r["source"] == model_registry.SEED_SOURCE for r in rows.values())


def test_seed_default_models_is_idempotent(conn, lock):
    model_registry.seed_default_models(conn, lock)
    again = model_registry.seed_default_models(conn, lock)
    assert again == []
    assert len(model_registry.list_models(conn, active_only=False)) == len(
        model_registry.DEFAULT_SEED_MODELS
    )


def test_seed_never_clobbers_discovered_model(conn, lock):
    # A real refresh discovers a model id that the seed list also contains; the
    # later seed must NOT overwrite its (gateway) source/provider.
    shared = model_registry.DEFAULT_SEED_MODELS[0][0]
    model_registry.refresh(
        conn, lock, source="gw", fetcher=lambda: [{"id": shared, "owned_by": "openrouter"}]
    )
    model_registry.seed_default_models(conn, lock)
    row = next(r for r in model_registry.list_models(conn) if r["model_id"] == shared)
    assert row["source"] == "gw"
    assert row["provider"] == "openrouter"


def test_cli_refresh_and_list(monkeypatch, conn, lock):
    from typer.testing import CliRunner
    from atlas_runtime.cli import main as cli_main

    monkeypatch.setattr(cli_main, "_get_connection", lambda: conn)
    monkeypatch.setattr(cli_main, "_get_lock", lambda: lock)
    monkeypatch.setattr(
        model_registry, "fetch_gateway_models", lambda base_url=None: [{"id": "m-cli"}]
    )
    runner = CliRunner()
    result = runner.invoke(cli_main.app, ["models", "refresh", "--gateway", "http://x/v1"])
    assert result.exit_code == 0
    assert "+ m-cli" in result.output

    result = runner.invoke(cli_main.app, ["models", "list"])
    assert result.exit_code == 0
    assert "m-cli" in result.output
