"""Tests for the MCP registry and its projection onto the foundation config.

Contract: docs/plans/2026-08-12-module-capabilities-v2-and-outreach-design.md
"""
from __future__ import annotations

import pytest
import yaml

from atlas_runtime import mcp_service, module_service

MANIFEST = """\
id: demo
name: Demo
version: 0.1.0
capabilities:
  mcp:
    - name: demo-search
      command: npx
      args: ["-y", "demo-mcp"]
      env: {DEMO_TOKEN: "${DEMO_TOKEN}"}
      description: demo server
    - name: demo-http
      transport: http
      url: https://mcp.example/mcp
      enabled: true
"""


def _install_module(tmp_path, db, lock, *, activate: bool = True):
    root = tmp_path / "modules"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "module.yaml").write_text(MANIFEST, encoding="utf-8")
    module_service.sync_modules(db, lock, roots=[root])
    if activate:
        module_service.set_active(db, lock, module_id="demo", active=True)


def test_operator_server_roundtrip(db, lock) -> None:
    server = mcp_service.upsert_server(
        db, lock, name="local-fs", command="npx", args=["-y", "fs-mcp"],
        description="files", enabled=True,
    )
    assert server["enabled"] is True
    assert server["args"] == ["-y", "fs-mcp"]
    assert [s["name"] for s in mcp_service.list_servers(db)] == ["local-fs"]

    mcp_service.set_enabled(db, lock, name="local-fs", enabled=False)
    assert mcp_service.get_server(db, "local-fs")["enabled"] is False
    assert mcp_service.remove_server(db, lock, name="local-fs") is True


def test_invalid_declarations_rejected(db, lock) -> None:
    with pytest.raises(mcp_service.McpError, match="needs a command"):
        mcp_service.upsert_server(db, lock, name="broken")
    with pytest.raises(mcp_service.McpError, match="needs a url"):
        mcp_service.upsert_server(db, lock, name="broken", transport="http")
    with pytest.raises(mcp_service.McpError, match="invalid mcp server name"):
        mcp_service.upsert_server(db, lock, name="Bad Name", command="x")


def test_module_sync_registers_without_enabling(tmp_path, db, lock) -> None:
    _install_module(tmp_path, db, lock)
    summary = mcp_service.sync_module_servers(db, lock)
    assert summary["registered"] == ["demo-http", "demo-search"]
    # `enabled: true` in the manifest is honored on first registration only;
    # the default (absent) stays off so installing never starts a process.
    assert mcp_service.get_server(db, "demo-search")["enabled"] is False
    assert mcp_service.get_server(db, "demo-http")["enabled"] is True


def test_operator_enablement_survives_resync(tmp_path, db, lock) -> None:
    _install_module(tmp_path, db, lock)
    mcp_service.sync_module_servers(db, lock)
    mcp_service.set_enabled(db, lock, name="demo-search", enabled=True)
    mcp_service.sync_module_servers(db, lock)
    assert mcp_service.get_server(db, "demo-search")["enabled"] is True


def test_deactivating_a_module_retracts_its_servers(tmp_path, db, lock) -> None:
    _install_module(tmp_path, db, lock)
    mcp_service.sync_module_servers(db, lock)
    assert {s["name"] for s in mcp_service.enabled_servers(db)} == {"demo-http"}

    module_service.set_active(db, lock, module_id="demo", active=False)
    assert mcp_service.enabled_servers(db) == []
    # The registry row survives, so re-activation restores the wiring.
    module_service.set_active(db, lock, module_id="demo", active=True)
    assert {s["name"] for s in mcp_service.enabled_servers(db)} == {"demo-http"}


def test_env_references_resolve_from_the_process_env(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TOKEN", "resolved-value")
    resolved, missing = mcp_service.resolve_env({"DEMO_TOKEN": "${DEMO_TOKEN}"})
    assert resolved == {"DEMO_TOKEN": "resolved-value"} and missing == []

    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    _, missing = mcp_service.resolve_env({"DEMO_TOKEN": "${DEMO_TOKEN}"})
    assert missing == ["DEMO_TOKEN"]


def test_projection_writes_only_atlas_managed_entries(tmp_path, db, lock) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "mcp_servers": {
                    "operator-owned": {"command": "hand-written"},
                    "stale-atlas": {"command": "old", "managed_by": "atlas"},
                }
            }
        ),
        encoding="utf-8",
    )
    mcp_service.upsert_server(
        db, lock, name="fresh", command="npx", args=["-y", "x"], enabled=True
    )
    report = mcp_service.apply_managed_servers(db, config_path=config_path)
    assert report["applied"] is True
    assert report["written"] == ["fresh"]
    assert report["removed"] == ["stale-atlas"]

    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))["mcp_servers"]
    assert written["operator-owned"] == {"command": "hand-written"}  # untouched
    assert written["fresh"]["managed_by"] == "atlas"
    assert "stale-atlas" not in written


def test_projection_skips_servers_with_unset_env(tmp_path, db, lock, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_TOKEN", raising=False)
    config_path = tmp_path / "config.yaml"
    mcp_service.upsert_server(
        db, lock, name="needs-env", command="npx", env={"DEMO_TOKEN": "${DEMO_TOKEN}"},
        enabled=True,
    )
    report = mcp_service.apply_managed_servers(db, config_path=config_path)
    assert "needs-env" in report["skipped"]
    assert "DEMO_TOKEN" in report["skipped"]["needs-env"]
    assert not config_path.exists() or "needs-env" not in config_path.read_text(encoding="utf-8")


def test_projection_never_collides_with_an_operator_entry(tmp_path, db, lock) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"mcp_servers": {"shared": {"command": "operator"}}}), encoding="utf-8"
    )
    mcp_service.upsert_server(db, lock, name="shared", command="atlas", enabled=True)
    report = mcp_service.apply_managed_servers(db, config_path=config_path)
    assert "shared" in report["skipped"]
    written = yaml.safe_load(config_path.read_text(encoding="utf-8"))["mcp_servers"]
    assert written["shared"] == {"command": "operator"}


def test_projection_reports_instead_of_raising(db) -> None:
    report = mcp_service.apply_managed_servers(db, config_path=None)
    # With no foundation on the path this reports a reason; it must never raise.
    assert isinstance(report, dict) and "applied" in report
