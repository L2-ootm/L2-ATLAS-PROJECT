"""Tests for atlas_runtime.component_service (optional SDK components)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from atlas_runtime import component_service as cs


def test_list_components_reports_both_sdks():
    rows = {row["name"]: row for row in cs.list_components()}
    assert set(rows) == {"claude", "codex"}
    for row in rows.values():
        assert {"installed", "cli_present", "agent_runtime", "pip_requirement"} <= set(row)
    assert rows["claude"]["agent_runtime"] == "claude_code"
    assert rows["codex"]["agent_runtime"] == "codex"


def test_unknown_component_rejected():
    with pytest.raises(cs.ComponentError):
        cs.install_component("martian")
    with pytest.raises(cs.ComponentError):
        cs.uninstall_component("martian")


def test_install_is_idempotent_when_already_available(monkeypatch):
    monkeypatch.setattr(cs, "_module_available", lambda module: True)
    calls: list[list[str]] = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = cs.install_component("codex", runner=runner)
    assert result["changed"] is False
    assert calls == []  # no pip invocation


def test_uninstall_is_idempotent_when_absent(monkeypatch):
    monkeypatch.setattr(cs, "_module_available", lambda module: False)
    calls: list[list[str]] = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = cs.uninstall_component("codex", runner=runner)
    assert result["changed"] is False
    assert calls == []


def test_install_invokes_pinned_pip_and_verifies(monkeypatch):
    state = {"installed": False}
    monkeypatch.setattr(
        cs, "_module_available", lambda module: state["installed"]
    )
    seen: list[list[str]] = []

    def runner(cmd, **kwargs):
        seen.append(cmd)
        state["installed"] = True  # pip made it importable
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = cs.install_component("codex", runner=runner)
    assert result["changed"] is True
    assert len(seen) == 1
    assert "install" in seen[0]
    assert "openai-codex>=0.1.0b3,<0.2" in seen[0]
    assert seen[0][0].endswith("python.exe") or "python" in seen[0][0].lower()


def test_install_fails_when_import_still_missing(monkeypatch):
    monkeypatch.setattr(cs, "_module_available", lambda module: False)

    def runner(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(cs.ComponentError, match="still not importable"):
        cs.install_component("claude", runner=runner)


def test_pip_failure_surfaces_stderr_tail(monkeypatch):
    monkeypatch.setattr(cs, "_module_available", lambda module: False)

    def runner(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom: no network")

    with pytest.raises(cs.ComponentError, match="no network"):
        cs.install_component("claude", runner=runner)


def test_uninstall_invokes_pip_uninstall_yes(monkeypatch):
    state = {"installed": True}
    monkeypatch.setattr(cs, "_module_available", lambda module: state["installed"])
    seen: list[list[str]] = []

    def runner(cmd, **kwargs):
        seen.append(cmd)
        state["installed"] = False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = cs.uninstall_component("claude", runner=runner)
    assert result["changed"] is True
    assert "uninstall" in seen[0] and "--yes" in seen[0]
    assert "claude-agent-sdk" in seen[0]
