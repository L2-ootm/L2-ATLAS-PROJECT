from __future__ import annotations

import os
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from atlas_runtime.cli import go_tui


def _touch_binary(path: pathlib.Path) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"binary")
    return path


def test_resolution_order_env_then_atlas_home_then_checkout_then_path(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = _touch_binary(tmp_path / "override" / go_tui.binary_name())
    owned = _touch_binary(tmp_path / "atlas-home" / "bin" / go_tui.binary_name())
    repo = tmp_path / "repo"
    checkout = _touch_binary(
        repo / "services" / "atlas-tui" / go_tui.binary_name()
    )
    on_path = _touch_binary(tmp_path / "path" / go_tui.binary_name())
    monkeypatch.setattr(go_tui, "_repo_root", lambda: repo)
    monkeypatch.setattr(go_tui.shutil, "which", lambda _name: str(on_path))
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "atlas-home"))
    monkeypatch.setenv("ATLAS_TUI_BIN", str(override))

    assert go_tui.resolve_binary() == override
    override.unlink()
    assert go_tui.resolve_binary() == owned
    owned.unlink()
    assert go_tui.resolve_binary() == checkout
    checkout.unlink()
    assert go_tui.resolve_binary() == on_path


def test_launch_uses_argv_inherited_tty_and_forwarded_gateway(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = _touch_binary(tmp_path / go_tui.binary_name())
    run = MagicMock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(go_tui, "resolve_binary", lambda: binary)
    monkeypatch.setattr(go_tui.subprocess, "run", run)

    code = go_tui.launch("http://127.0.0.1:9494")

    assert code == 0
    run.assert_called_once_with(
        [os.fspath(binary), "--gateway", "http://127.0.0.1:9494"],
        check=False,
    )


def test_launch_defaults_to_gateway_env(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary = _touch_binary(tmp_path / go_tui.binary_name())
    run = MagicMock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(go_tui, "resolve_binary", lambda: binary)
    monkeypatch.setattr(go_tui.subprocess, "run", run)
    monkeypatch.setenv("ATLAS_GATEWAY_URL", "http://127.0.0.1:8584")

    assert go_tui.launch() == 0
    assert run.call_args.args[0][-1] == "http://127.0.0.1:8584"


def test_missing_binary_has_exact_install_remediation(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_TUI_BIN", raising=False)
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "missing-home"))
    monkeypatch.setattr(go_tui, "_repo_root", lambda: tmp_path / "missing-repo")
    monkeypatch.setattr(go_tui.shutil, "which", lambda _name: None)

    with pytest.raises(go_tui.TUILaunchError) as caught:
        go_tui.resolve_binary()

    message = str(caught.value)
    assert "atlas-tui binary not found" in message
    assert "scripts/install-atlas-cli.ps1" in message
    assert "scripts/setup.sh" in message
