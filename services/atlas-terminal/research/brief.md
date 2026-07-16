# Brief: Atlas Terminal Full Functional Migration

## Goal
Produce a comprehensive analysis and execution plan for making atlas-terminal (the vendored opencode/MiMoCode TUI) fully functional, production-ready, and properly wired to the ATLAS runtime — while removing the legacy Go TUI.

## Context
- Current state: atlas-terminal boots but has event shape mismatches, missing features, and incomplete wiring
- Legacy Go TUI (services/atlas-tui/) is non-functional and should be removed
- Foundation (foundation/atlas-hermes/) has its own TUI that was the original donor
- MiMoCode (the external MIT donor) has patterns/utilities that should be reused
- Target: MiMoCode-quality TUI, fully wired to ATLAS gateway, production ready

## Approach
5 batches of parallel subagents, each producing findings files. Final output: MASTER-PLAN.md with phased execution roadmap.

### Batch 1: Legacy TUI Inventory + New TUI Current State
- 2 subagents: Go TUI feature inventory, atlas-terminal feature inventory

### Batch 2: Foundation + Donor Analysis
- 2 subagents: Foundation TUI patterns, MiMoCode donor patterns/utilities

### Batch 3: Gap Analysis + Wiring Map
- 2 subagents: Feature gaps (what's missing), wiring gaps (what's disconnected)

### Batch 4: Migration + Removal Plan
- 2 subagents: Go TUI removal plan, atlas-terminal hardening plan

### Batch 5: Synthesis + Master Plan
- 1 agent: Synthesize all findings into MASTER-PLAN.md

## Output
Each batch produces findings files in services/atlas-terminal/research/
Final: MASTER-PLAN.md with phased execution roadmap
