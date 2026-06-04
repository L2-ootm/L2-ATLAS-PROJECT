# L2 ATLAS PROJECT

AI Company Operating Cockpit: mission control, agent runtime, persistent knowledge, integrations, pulse monitoring, and operator-grade autonomy.

## Current phase

Phase 0 — structure, inventory, and consolidation map.

## First ship target

ATLAS Operator Cockpit MVP:

1. Create mission.
2. Execute through enhanced ATLAS/Hermes runtime.
3. Persist run/audit/artifacts.
4. File valuable output into LLM Wiki.
5. Display state in cockpit.

## Rules

- Use Hermes as the foundation codebase. ATLAS enhances the Hermes framework directly; avoid a thin external wrapper as the final architecture.
- Raw sources are immutable.
- Every autonomous action is auditable.
- LLM Wiki compounds knowledge; RAG alone is not enough.
- Existing L2 repos are source assets, not blindly merged code.
