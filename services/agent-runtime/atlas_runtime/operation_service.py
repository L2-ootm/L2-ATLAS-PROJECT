"""ATLAS operation service — premade autonomous instructions (WP-6, named ops).

An Operation is a built-in template that turns a plain goal into a detailed,
structured run: the operator triggers it from a cockpit button, ATLAS renders a
"military-grade" instruction, and the agent expands the goal — writing the result
back into the goal tree (tasks / sub-goals / observations) via the atlas CLI so
the structure compounds.

Operations are built-in (a registry here), not user-authored rows — fast to ship
and matches "premade". They are risk-gated: every shipped op is internal and
reversible (it only adds tasks/observations/sub-goals), so it auto-runs; an
outward-facing op would require approval before this service would dispatch it.

The rendered instruction becomes a Mission.intent; the executor prepends the
secret-redacted operator context (focus + goal tree + Operating Contract) ahead
of it (see cli.main._run_prompt), so the agent receives full context + the op.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from atlas_core.schemas.core import Focus, Goal

# How the agent invokes the atlas CLI from the repo root (no console script on the
# Hermes venv — see atlas-local-run-recipe). The agent has a terminal tool.
_CLI = "python -m atlas_runtime.cli.main"


class OperationError(ValueError):
    """Raised for an unknown operation id or an op that cannot run."""


@dataclass(frozen=True)
class Operation:
    id: str
    label: str
    description: str
    agent: str = "native"
    risk: str = "internal"  # "internal" (auto) | "outward" (needs approval)


_OPERATIONS: tuple[Operation, ...] = (
    Operation(
        id="elaborate",
        label="Elaborate Goal",
        description="Expand a plain goal into concrete tasks, constraints, blockers, current state, and context.",
    ),
    Operation(
        id="recon",
        label="Recon / State Report",
        description="Survey the project's current state, what exists, what's missing, and relevant context.",
    ),
    Operation(
        id="blockers",
        label="Find Blockers",
        description="Identify what blocks this goal and its dependencies; record each blocker.",
    ),
    Operation(
        id="decompose",
        label="Decompose into Sub-goals",
        description="Break a large goal into a tree of well-scoped sub-goals.",
    ),
)
_BY_ID = {op.id: op for op in _OPERATIONS}


def list_operations() -> list[Operation]:
    return list(_OPERATIONS)


def get_operation(op_id: str) -> Optional[Operation]:
    return _BY_ID.get(op_id)


def _writeback(op_id: str, goal_id: str, focus_id: Optional[str]) -> str:
    """Shared write-back contract — how the agent persists structure via the CLI."""
    focus_flag = f" --focus {focus_id}" if focus_id else ""
    return (
        "## Write-back (use your terminal, run from the repository root)\n"
        f"The goal id is `{goal_id}`. Persist everything into ATLAS so the next run inherits it:\n"
        f'- Add a concrete task:  `{_CLI} task add --goal {goal_id} --title "<imperative task>"`\n'
        f'- Record a constraint / blocker / state note:  `{_CLI} observe add --goal {goal_id} '
        f'--source operation:{op_id} --body "<finding>"`\n'
        f'- Create a sub-goal:  `{_CLI} goal create --title "<sub-goal>"{focus_flag} --parent {goal_id}`\n'
        "Keep titles short and imperative. Persist as you go, not only at the end."
    )


def build_intent(op_id: str, *, goal: Goal, focus: Optional[Focus]) -> str:
    """Render the operation instruction (the Mission.intent) for a goal."""
    op = get_operation(op_id)
    if op is None:
        raise OperationError(f"unknown operation {op_id!r}")
    if op.risk != "internal":
        # Defense-in-depth: only internal/reversible ops are dispatchable here.
        raise OperationError(f"operation {op_id!r} is {op.risk!r} and requires approval")

    focus_id = goal.focus_id or (focus.id if focus is not None else None)
    header = (
        f"# Operation: {op.label}\n\n"
        f"Target goal: **{goal.title}**"
        + (f"\n\nGoal description: {goal.description}" if goal.description else "")
        + "\n\n"
    )

    if op_id == "elaborate":
        body = (
            "Transform this goal into a detailed, military-grade operation. Produce:\n"
            "1. **Tasks** — the concrete, ordered steps required to achieve the goal.\n"
            "2. **Constraints** — technical, product, and project constraints that bound the work.\n"
            "3. **Blockers** — anything currently preventing or risking progress.\n"
            "4. **Current state** — what already exists relevant to this goal.\n"
            "5. **Context** — the background an executor needs to start without re-deriving it.\n\n"
            "Investigate the codebase as needed before writing. Add each task and record each "
            "constraint/blocker/state/context note via the write-back commands below."
        )
    elif op_id == "recon":
        body = (
            "Run reconnaissance for this goal. Survey the project and report:\n"
            "- Current state: what exists and works, relevant to the goal.\n"
            "- Gaps: what is missing or incomplete.\n"
            "- Dependencies and key context an executor must know.\n\n"
            "Record each finding as an observation via the write-back commands below. "
            "This is a read/survey operation — do not modify project files."
        )
    elif op_id == "blockers":
        body = (
            "Identify everything blocking this goal: unmet dependencies, missing decisions, "
            "broken or absent prerequisites, and risks that could stall it. For each blocker, "
            "record a concise observation (what it is, why it blocks, what would unblock it) via "
            "the write-back commands below."
        )
    elif op_id == "decompose":
        body = (
            "Break this goal into a tree of well-scoped sub-goals — each independently "
            "completable, in a sensible order. Create each as a sub-goal via the write-back "
            "commands below. Prefer 3–7 sub-goals; add a short description to each if useful."
        )
    else:  # pragma: no cover — guarded by get_operation above
        raise OperationError(f"no template for operation {op_id!r}")

    return f"{header}{body}\n\n{_writeback(op_id, goal.id, focus_id)}\n"
