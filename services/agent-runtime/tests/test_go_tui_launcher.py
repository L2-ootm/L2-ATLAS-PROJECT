from __future__ import annotations

import os
import pathlib
import time
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
    tui = repo / "services" / "atlas-tui"
    tui.mkdir(parents=True)
    (tui / "go.mod").write_text("module atlas-tui\n", encoding="utf-8")
    checkout = _touch_binary(
        tui / go_tui.binary_name()
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
    (tui / "go.mod").unlink()
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
    monkeypatch.setattr(
        go_tui.shutil, "which", lambda name: "go" if name == "go" else None
    )

    with pytest.raises(go_tui.TUILaunchError) as caught:
        go_tui.resolve_binary()

    message = str(caught.value)
    assert "atlas-tui binary not found" in message
    assert "scripts/install-atlas-cli.ps1" in message
    assert "scripts/setup.sh" in message


def test_stale_checkout_binary_is_rebuilt_before_resolution(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    tui = repo / "services" / "atlas-tui"
    tui.mkdir(parents=True)
    source = tui / "main.go"
    source.write_text("package main\n", encoding="utf-8")
    (tui / "go.mod").write_text("module atlas-tui\n", encoding="utf-8")
    binary = _touch_binary(tui / go_tui.binary_name())
    old = time.time() - 60
    os.utime(binary, (old, old))

    def build(argv: list[str], **kwargs: object) -> SimpleNamespace:
        assert argv[:3] == ["go", "build", "-trimpath"]
        assert kwargs["cwd"] == tui
        binary.write_bytes(b"rebuilt")
        return SimpleNamespace(returncode=0, stderr="")

    run = MagicMock(side_effect=build)
    monkeypatch.delenv("ATLAS_TUI_BIN", raising=False)
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "missing-home"))
    monkeypatch.setattr(go_tui, "_repo_root", lambda: repo)
    monkeypatch.setattr(go_tui.subprocess, "run", run)
    monkeypatch.setattr(
        go_tui.shutil, "which", lambda name: "go" if name == "go" else None
    )

    assert go_tui.resolve_binary() == binary
    assert binary.read_bytes() == b"rebuilt"
    run.assert_called_once()


def test_fresh_checkout_binary_does_not_rebuild(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    tui = repo / "services" / "atlas-tui"
    tui.mkdir(parents=True)
    (tui / "main.go").write_text("package main\n", encoding="utf-8")
    (tui / "go.mod").write_text("module atlas-tui\n", encoding="utf-8")
    binary = _touch_binary(tui / go_tui.binary_name())
    future = time.time() + 60
    os.utime(binary, (future, future))

    run = MagicMock()
    monkeypatch.delenv("ATLAS_TUI_BIN", raising=False)
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path / "missing-home"))
    monkeypatch.setattr(go_tui, "_repo_root", lambda: repo)
    monkeypatch.setattr(go_tui.subprocess, "run", run)
    monkeypatch.setattr(go_tui.shutil, "which", lambda _name: None)

    assert go_tui.resolve_binary() == binary
    run.assert_not_called()


def test_source_commit_uses_repository_head(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    run = MagicMock(
        return_value=SimpleNamespace(returncode=0, stdout="abc1234\n", stderr="")
    )
    monkeypatch.setattr(go_tui.shutil, "which", lambda name: name)
    monkeypatch.setattr(go_tui.subprocess, "run", run)

    assert go_tui._source_commit(repo) == "abc1234"
    run.assert_called_once()
