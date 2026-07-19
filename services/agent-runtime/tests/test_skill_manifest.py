"""Tests for atlas_runtime.skill_manifest — the backend behind `atlas skills list`.

Scans the real repo skill trees (skills/atlas/, foundation/atlas-hermes/optional-skills/)
since scan_skills() has no injectable root; this exercises the actual on-disk
fixtures the frontend Skills page depends on, rather than synthetic dirs.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from atlas_runtime import skill_manifest


def test_scan_finds_known_atlas_native_skills() -> None:
    skills = skill_manifest.scan_skills()
    ids = {s["id"] for s in skills}
    assert "skills/atlas/gsd" in ids
    assert "skills/atlas/ultra" in ids


def test_frontmatter_less_skill_does_not_crash_scanner() -> None:
    # skills/atlas/gsd/SKILL.md has no YAML frontmatter (starts with "# GSD/L2...").
    skills = skill_manifest.scan_skills()
    gsd = next(s for s in skills if s["id"] == "skills/atlas/gsd")
    # parse_frontmatter returns {} gracefully; name falls back to the dir name.
    assert gsd["name"] == "gsd"
    assert gsd["description"] == ""
    assert gsd["version"] == "0.0.0"


def test_frontmatter_skill_is_parsed() -> None:
    skills = skill_manifest.scan_skills()
    ultra = next(s for s in skills if s["id"] == "skills/atlas/ultra")
    assert ultra["name"] == "ultra"
    assert ultra["description"]  # non-empty, has real frontmatter description


def test_provenance_tier_derived_by_path() -> None:
    skills = skill_manifest.scan_skills()
    by_id = {s["id"]: s for s in skills}

    atlas_native = by_id["skills/atlas/gsd"]
    assert atlas_native["provenance"] == {"tier": "original", "source": "bundled"}
    assert atlas_native["category"] == "atlas"

    hermes_skills = [s for s in skills if "optional-skills" in s["path"]]
    assert hermes_skills, "expected at least one vendored Hermes skill to be found"
    for skill in hermes_skills:
        assert skill["provenance"] == {"tier": "framework", "source": "bundled"}
        assert skill["category"] != "atlas"


def test_every_skill_has_all_frontend_contract_fields() -> None:
    # Mirrors the SkillInfo TS interface in services/web-ui-react/src/routes/SkillsPage.tsx.
    required_top_level = {
        "id", "name", "description", "version", "author", "license", "category",
        "tags", "provenance", "loading_tier", "platforms", "enabled", "pinned",
        "state", "usage", "path",
    }
    skills = skill_manifest.scan_skills()
    assert skills, "scanner found no skills at all"
    for skill in skills:
        assert required_top_level.issubset(skill.keys())
        assert set(skill["provenance"].keys()) == {"tier", "source"}
        assert set(skill["usage"].keys()) == {"use_count", "view_count", "last_used_at"}
        assert isinstance(skill["tags"], list)
        assert isinstance(skill["platforms"], list)


def test_set_skill_tier_persists_and_applies_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))

    updated = skill_manifest.set_skill_tier("skills/atlas/gsd", "name-only")
    assert updated["skills/atlas/gsd"] == "name-only"
    assert (tmp_path / "skill_tiers.json").is_file()

    skill = skill_manifest.get_skill("skills/atlas/gsd")
    assert skill is not None
    assert skill["loading_tier"] == "name-only"
    assert skill["enabled"] is True

    skill_manifest.set_skill_tier("skills/atlas/gsd", "deactivated")
    skill = skill_manifest.get_skill("skills/atlas/gsd")
    assert skill["loading_tier"] == "deactivated"
    assert skill["enabled"] is False


def test_set_skill_tier_rejects_unknown_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_HOME", str(tmp_path))
    with pytest.raises(ValueError):
        skill_manifest.set_skill_tier("skills/atlas/gsd", "bogus-tier")


def test_get_skill_returns_none_for_unknown_id() -> None:
    assert skill_manifest.get_skill("skills/atlas/does-not-exist") is None
