"""Skill manifest — scans ATLAS-native and Hermes-framework skill directories.

Feeds ``atlas skills list`` / the gateway's ``GET /api/skills`` route (the
gateway is dispatch-only per D-022 and shells out to the CLI; this module is
the actual scanning/parsing logic behind it, kept out of the thin CLI layer).

Two skill source trees are scanned:
  - ``skills/atlas/``                                ATLAS-native skills
  - ``foundation/atlas-hermes/optional-skills/``      vendored Hermes skills

No usage-tracking subsystem exists yet, so ``usage`` counters default to zero
and ``loading_tier``/``enabled``/``pinned``/``state`` default to sane values.
A skill's loading tier can be overridden via :func:`set_skill_tier`, persisted
as a flat JSON map at ``<ATLAS_HOME>/skill_tiers.json`` — there is no existing
place in the versioned ``AtlasConfig`` schema (see
``packages/atlas-core/atlas_core/schemas/control_plane.py``) for this, and
widening that locked schema for a single stub field is out of scope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from atlas_runtime.config_service import atlas_home
from atlas_runtime.db import MIGRATIONS_DIR
from atlas_runtime.secure_store import durable_replace_text

# db.py lives at services/agent-runtime/atlas_runtime/db.py; MIGRATIONS_DIR is
# <repo_root>/infra/migrations, so .parent.parent is the repo root. Reuses the
# same resolution already established in cli/main.py's terminal_status_cmd.
REPO_ROOT = MIGRATIONS_DIR.parent.parent
ATLAS_SKILLS_DIR = REPO_ROOT / "skills" / "atlas"
HERMES_SKILLS_DIR = REPO_ROOT / "foundation" / "atlas-hermes" / "optional-skills"

_TIER_STORE_FILENAME = "skill_tiers.json"
VALID_TIERS = frozenset({"full", "name-only", "deactivated"})


# ---------------------------------------------------------------------------
# foundation import bridge (same pattern as subagent_service._foundation_on_path)
# ---------------------------------------------------------------------------


def _foundation_on_path() -> bool:
    """Put foundation/atlas-hermes on sys.path so ``agent.skill_utils`` imports."""
    from atlas_runtime.agents.native import _find_foundation  # noqa: PLC0415

    foundation = _find_foundation()
    if foundation is None:
        return False
    path = str(foundation)
    if path not in sys.path:
        sys.path.insert(0, path)
    return True


def _skill_utils():
    if not _foundation_on_path():
        raise RuntimeError(
            "foundation/atlas-hermes not found on this machine; cannot scan skills"
        )
    from agent import skill_utils  # noqa: PLC0415

    return skill_utils


# ---------------------------------------------------------------------------
# loading-tier override store
# ---------------------------------------------------------------------------


def _tier_store_path() -> Path:
    return atlas_home() / _TIER_STORE_FILENAME


def _load_tier_overrides() -> dict[str, str]:
    path = _tier_store_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def set_skill_tier(skill_id: str, tier: str) -> dict[str, str]:
    """Persist a loading-tier override for *skill_id*. Returns the updated map."""
    if tier not in VALID_TIERS:
        raise ValueError(
            f"unknown loading tier {tier!r}; expected one of {sorted(VALID_TIERS)}"
        )
    overrides = _load_tier_overrides()
    overrides[skill_id] = tier
    durable_replace_text(
        _tier_store_path(), json.dumps(overrides, indent=2, sort_keys=True) + "\n"
    )
    return overrides


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------


def _relative_to_repo(path: Path) -> Path:
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return path


def _derive_provenance(skill_md_path: Path) -> dict[str, str]:
    parts = _relative_to_repo(skill_md_path).parts
    if "optional-skills" in parts:
        return {"tier": "framework", "source": "bundled"}
    return {"tier": "original", "source": "bundled"}


def _category_for(skill_md_path: Path) -> str:
    """optional-skills/<category>/.../SKILL.md -> <category>; else 'atlas'."""
    parts = _relative_to_repo(skill_md_path).parts
    if "optional-skills" in parts:
        idx = parts.index("optional-skills")
        if idx + 1 < len(parts):
            return parts[idx + 1]
        return "framework"
    return "atlas"


def _skill_id(skill_md_path: Path) -> str:
    """Stable, unique id: the skill's own directory, relative to repo root."""
    return _relative_to_repo(skill_md_path.parent).as_posix()


def _tags_from(frontmatter: dict[str, Any]) -> list[str]:
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        return []
    hermes = metadata.get("hermes")
    if not isinstance(hermes, dict):
        return []
    raw = hermes.get("tags")
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return []


def _list_from(frontmatter: dict[str, Any], key: str) -> list[str]:
    raw = frontmatter.get(key)
    if not raw:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(v) for v in raw]
    return []


def _description_from(frontmatter: dict[str, Any]) -> str:
    # Deliberately not skill_utils.extract_skill_description(): that helper
    # truncates to 60 chars for a narrow CLI-banner display, which would
    # needlessly clip the full descriptions the Skills page card renders.
    raw = frontmatter.get("description", "")
    return str(raw).strip().strip("'\"") if raw else ""


def _scan_dir(skills_dir: Path, skill_utils_mod) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not skills_dir.is_dir():
        return results
    for skill_md in skill_utils_mod.iter_skill_index_files(skills_dir, "SKILL.md"):
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        frontmatter, _body = skill_utils_mod.parse_frontmatter(raw)
        name = str(frontmatter.get("name") or skill_md.parent.name)
        results.append(
            {
                "id": _skill_id(skill_md),
                "name": name,
                "description": _description_from(frontmatter),
                "version": str(frontmatter.get("version") or "0.0.0"),
                "author": str(frontmatter.get("author") or "unknown"),
                "license": str(frontmatter.get("license") or "unknown"),
                "category": _category_for(skill_md),
                "tags": _tags_from(frontmatter),
                "provenance": _derive_provenance(skill_md),
                "loading_tier": "full",
                "platforms": _list_from(frontmatter, "platforms"),
                "enabled": True,
                "pinned": False,
                "state": "active",
                "usage": {"use_count": 0, "view_count": 0, "last_used_at": None},
                "path": skill_md.as_posix(),
            }
        )
    return results


def scan_skills() -> list[dict[str, Any]]:
    """Scan ATLAS-native + Hermes-framework skill trees; apply tier overrides."""
    skill_utils_mod = _skill_utils()
    items = _scan_dir(ATLAS_SKILLS_DIR, skill_utils_mod) + _scan_dir(
        HERMES_SKILLS_DIR, skill_utils_mod
    )
    overrides = _load_tier_overrides()
    for item in items:
        tier = overrides.get(item["id"])
        if tier in VALID_TIERS:
            item["loading_tier"] = tier
            item["enabled"] = tier != "deactivated"
    items.sort(key=lambda s: (s["category"], s["name"]))
    return items


def get_skill(skill_id: str) -> dict[str, Any] | None:
    """Return one skill by id, or None. Simple linear scan (small corpus)."""
    for item in scan_skills():
        if item["id"] == skill_id:
            return item
    return None
