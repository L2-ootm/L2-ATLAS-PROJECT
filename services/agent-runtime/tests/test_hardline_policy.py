"""Adversarial corpus for the immutable Phase 10.7 hardline floor."""

from __future__ import annotations

import pytest

from atlas_core.schemas.control_plane import PermissionConfig
from atlas_core.schemas.tool import ToolManifest
from atlas_runtime.hardline_policy import HARDLINE_VERSION
from atlas_runtime.policy import PolicyFacts, decide


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("rm -rf /", "hardline_filesystem_root"),
        ("rm -rf /*", "hardline_filesystem_root"),
        ("Remove-Item -Recurse -Force C:\\", "hardline_filesystem_root"),
        ("format C: /Q", "hardline_block_device"),
        ("mkfs.ext4 /dev/sda", "hardline_block_device"),
        ("dd if=/dev/zero of=/dev/sda", "hardline_block_device"),
        ("diskpart /s clean-all.txt", "hardline_block_device"),
        ("shutdown /s /t 0", "hardline_system_shutdown"),
        ("reboot now", "hardline_system_shutdown"),
        ("Stop-Computer -Force", "hardline_system_shutdown"),
        (":(){ :|:& };:", "hardline_fork_bomb"),
    ],
)
@pytest.mark.parametrize("preset", ["manual", "smart", "full_autonomy"])
def test_hardline_corpus_denied_under_every_preset(
    command: str,
    reason: str,
    preset: str,
) -> None:
    result = decide(
        ToolManifest(
            name="shell",
            risk_level="shell",
            permissions=["command.execute"],
        ),
        config=PermissionConfig(preset=preset),
        facts=PolicyFacts(
            tool="shell",
            risk="shell",
            capability="command.execute",
            command=command,
        ),
        scoped_allow_rule_id="forged-always-allow",
    )

    assert result.allowed is False
    assert result.requires_approval is False
    assert result.reason == reason
    assert result.receipt.source_layer == "hardline"
    assert result.receipt.matched_rule_id.startswith("hardline:")


def test_hardline_version_is_the_configured_floor() -> None:
    assert HARDLINE_VERSION == PermissionConfig().hardline_version


def test_benign_near_matches_are_not_hardline() -> None:
    for command in (
        "rm -rf ./dist",
        "format README.md",
        "git clean -fd",
        "shutdown-handler --dry-run",
        "echo ':(){ :|:& };:'",
    ):
        result = decide(
            ToolManifest(
                name="shell",
                risk_level="shell",
                permissions=["command.execute"],
            ),
            config=PermissionConfig(preset="full_autonomy"),
            facts=PolicyFacts(
                tool="shell",
                risk="shell",
                capability="command.execute",
                command=command,
            ),
        )
        assert result.allowed is True, command
