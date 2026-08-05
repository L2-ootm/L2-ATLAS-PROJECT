"""Contract tests for atlas-terminal source/workspace resolution and status."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

from atlas_runtime import gateway_control, provisioning
from atlas_runtime.cli import atlas_terminal
from atlas_runtime.cli.main import app


runner = CliRunner()


def _source(path, *, package: str = '{"version": "9.8.7"}'):
    path.mkdir(parents=True)
    (path / "package.json").write_text(package, encoding="utf-8")
    (path / "bun.lock").write_text("", encoding="utf-8")
    return path


def _status(monkeypatch, layout):
    monkeypatch.setattr(atlas_terminal, "resolve_terminal_layout", lambda: layout)
    monkeypatch.setattr(gateway_control, "health_ok", lambda: False)

    def _must_not_provision(*_args, **_kwargs):
        raise AssertionError("status must not provision")

    monkeypatch.setattr(provisioning, "ensure_provisioned", _must_not_provision)
    result = runner.invoke(app, ["terminal", "status", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_override_is_authoritative_and_component_preserves_it(tmp_path, monkeypatch):
    selected = tmp_path / "selected-terminal"
    monkeypatch.setenv("ATLAS_TERMINAL_DIR", str(selected))

    layout = atlas_terminal.resolve_terminal_layout()

    assert layout.source_dir == selected
    assert layout.component.source_dir == selected
    assert layout.workspace == selected
    assert layout.mirrored is False


def test_release_workspace_honors_late_atlas_home_and_db_changes(tmp_path, monkeypatch):
    release = tmp_path / "versions" / "0.1.5"
    (release / "runtime.json").parent.mkdir(parents=True)
    (release / "runtime.json").write_text(
        '{"platform": "windows-x64", "entrypoint": "python.exe"}',
        encoding="utf-8",
    )
    source = _source(release / "services" / "atlas-terminal")
    monkeypatch.setenv("ATLAS_TERMINAL_DIR", str(source))

    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "one" / "atlas.db"))
    first = atlas_terminal.resolve_terminal_layout()
    monkeypatch.setenv("ATLAS_DB", str(tmp_path / "two" / "atlas.db"))
    second = atlas_terminal.resolve_terminal_layout()
    monkeypatch.delenv("ATLAS_DB")
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "three"))
    third = atlas_terminal.resolve_terminal_layout()

    assert first.workspace == tmp_path / "one" / "sidecars" / "atlas-terminal"
    assert second.workspace == tmp_path / "two" / "sidecars" / "atlas-terminal"
    assert third.workspace == tmp_path / "three" / "sidecars" / "atlas-terminal"
    assert first.mirrored is second.mirrored is third.mirrored is True


def test_launch_provisions_and_runs_the_shared_resolved_workspace(
    tmp_path, monkeypatch
):
    source = _source(tmp_path / "source")
    workspace = tmp_path / "sidecar"
    component = provisioning.atlas_terminal_component(source)
    layout = atlas_terminal.TerminalLayout(component, source, workspace, True)
    seen = {}

    monkeypatch.setattr(atlas_terminal, "resolve_terminal_layout", lambda: layout)

    def _ensure(selected):
        seen["component"] = selected
        return provisioning.ProvisionResult(True, "ok", workspace)

    monkeypatch.setattr(provisioning, "ensure_provisioned", _ensure)
    monkeypatch.setattr(atlas_terminal.shutil, "which", lambda _name: "bun")

    def _run(argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs["cwd"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atlas_terminal.subprocess, "run", _run)

    assert atlas_terminal.launch() == 0
    assert seen["component"] is component
    assert seen["cwd"] == str(workspace)
    assert seen["argv"] == ["bun", "run", "dev"]


def test_status_reports_checkout_workspace_and_legacy_keys(tmp_path, monkeypatch):
    source = _source(tmp_path / "checkout")
    (source / "node_modules").mkdir()
    component = provisioning.atlas_terminal_component(source)
    layout = atlas_terminal.TerminalLayout(component, source, source, False)

    report = _status(monkeypatch, layout)

    assert {"present", "built", "version", "gateway_reachable"} <= report.keys()
    assert report["present"] is True
    assert report["built"] is True
    assert report["version"] == "9.8.7"
    assert report["source_dir"] == str(source)
    assert report["workspace"] == str(source)
    assert report["package_valid"] is True


def test_status_reports_missing_release_sidecar_without_creating_it(
    tmp_path, monkeypatch
):
    source = _source(tmp_path / "release" / "services" / "atlas-terminal")
    workspace = tmp_path / "atlas-home" / "sidecars" / "atlas-terminal"
    component = provisioning.atlas_terminal_component(source)
    layout = atlas_terminal.TerminalLayout(component, source, workspace, True)

    report = _status(monkeypatch, layout)

    assert report["present"] is True
    assert report["workspace_present"] is False
    assert report["built"] is False
    assert report["version"] == "9.8.7"
    assert not workspace.exists()


def test_status_exposes_malformed_package_and_missing_dependencies(
    tmp_path, monkeypatch
):
    source = _source(tmp_path / "checkout", package="{not-json")
    component = provisioning.atlas_terminal_component(source)
    layout = atlas_terminal.TerminalLayout(component, source, source, False)

    report = _status(monkeypatch, layout)

    assert report["present"] is True
    assert report["built"] is False
    assert report["version"] is None
    assert report["package_valid"] is False
    assert report["package_error"]
