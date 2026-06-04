# Phase 9: Skill Inventory & Classification

**Phase number:** 9
**Name:** Skill Inventory & Classification
**Status:** Pending

---

## Goal

Produce a complete, classified skill inventory so ATLAS can ship with a curated default skill pack rather than an undifferentiated dump of every existing skill.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| SKILLS-01 | Skill inventory document: name, path, description, class, public-safe flag, polish-required flag, ATLAS relevance |
| SKILLS-02 | Core ATLAS skill pack with required metadata (name, version, class, autonomy_level, risk, requires_tools, requires_secrets, verification, public_safe) |
| SKILLS-03 | Developer Operator Pack classified with same metadata schema |
| SKILLS-04 | L2 Systems Pack classified as l2-internal (not public default) |

---

## Success Criteria

1. `docs/imports/SKILL_INVENTORY.md` exists with every skill from Hermes skills dir, l2-agent-skills, and OpenClaw/GSD imports listed with: name, path, description, class (core/operator/l2-internal/personal-private/experimental/deprecated), public-safe flag, polish-required flag.
2. Core ATLAS Pack skills have complete metadata (name, version, class, autonomy_level, risk, requires_tools, requires_secrets, verification steps, public_safe: true).
3. Developer Operator Pack skills have the same metadata and are marked public_safe: true.
4. L2 Systems Pack skills classified l2-internal and public_safe: false.
5. No personal/private skill paths are referenced in any public-facing manifest.
6. Skill registry loads all core + operator pack skills without error on a clean Hermes install.

---

## Key Decisions Applicable

- **D-008** (locked): Existing skills must be classified and polished before becoming ATLAS-grade. Classes: core, operator, l2-internal, personal/private, experimental, deprecated.
- **D-001** (locked): Hermes is used directly — skill classification must account for Hermes native skill format; ATLAS skills extend, not replace.
- Phase 1 dependency: The Hermes extension-point audit (Phase 1) identifies the skills surface and format — use that as the authoritative list of Hermes skills to classify.
- Skill sources: Hermes skills dir, `l2-agent-skills` repo, OpenClaw/GSD imports. Do not import from `C:/Users/Davi/AppData/Local/hermes/` — contains personal/private skills.
- Parallel execution: This phase can run alongside Phases 4–8 since it produces docs, not service code. It must complete before v1.0 ships.

---

## What NOT to Build

- Do not implement new skills in this phase — classify existing ones.
- Do not build a skill UI or skill marketplace — that is future work.
- Do not write a skill auto-discovery service — the inventory is a manually curated document.
- Do not ship personal/private skills in any public manifest — classify them as personal/private and exclude from public-facing outputs.
- Do not create new skill classes beyond the defined taxonomy: core, operator, l2-internal, personal/private, experimental, deprecated.
- Do not implement skill versioning infrastructure — version metadata in the inventory doc is sufficient for v1.0.
