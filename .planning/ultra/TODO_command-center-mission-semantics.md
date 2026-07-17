# TODO — Command Center mission and goal semantics

Status: operator-requested follow-up, 2026-07-16

## Problem

Chat transport currently creates a Mission row for every prompt. This makes the
Missions page an execution-history mirror instead of a register of deliberate
Command Center missions.

## Required slice

- Chat prompts create ordinary session/run records only.
- A Mission exists only when launched explicitly from Command Center, New
  Mission, or the explicit goal-launch workflow.
- Existing prompt-shaped mission rows need a safe classification/backfill plan;
  do not silently delete audit history.
- Command Center supports multiple concurrent goals as independent lanes.
- Goals may be queued for the future with a `not_before` boundary.
- Goals may depend on other goals, forming an auditable acyclic dependency graph
  for "goal after goal" execution.
- Operators can pause, reprioritize, cancel, or manually release a future goal.
- Each goal exposes state, owner/runtime, budget/policy, prerequisites, current
  run, and terminal evidence.

## Acceptance gates

1. Sending a normal Chat prompt never increases the Missions count.
2. Starting a Command Center mission creates exactly one Mission and one initial
   goal/run lane.
3. Two independent goals can run in parallel without sharing lifecycle state.
4. A dependent goal cannot start before every required predecessor settles in
   an allowed terminal state.
5. A future goal cannot start before `not_before`, survives restart, and can be
   released manually.
6. Mission, goal, run, and chat-session semantics are covered by migration,
   service, gateway, and WebUI tests.
