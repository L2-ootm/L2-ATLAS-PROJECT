from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_powershell_installer_builds_go_tui_into_atlas_home() -> None:
    script = (REPO_ROOT / "scripts" / "install-atlas-cli.ps1").read_text(
        encoding="utf-8"
    )
    assert "services/atlas-tui" in script
    assert "ATLAS_HOME" in script
    assert "atlas-tui.exe" in script
    assert "go build" in script
    assert "foundation/atlas-hermes/ui-tui" not in script
    assert "ATLAS_TUI_BIN" in script


def test_posix_installer_builds_go_tui_into_atlas_home() -> None:
    script = (REPO_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "services/atlas-tui" in script
    assert "ATLAS_HOME" in script
    assert 'atlas_home/bin/atlas-tui' in script
    assert "go build" in script
    assert "foundation/atlas-hermes/ui-tui" not in script
    assert "ATLAS_TUI_BIN" in script
