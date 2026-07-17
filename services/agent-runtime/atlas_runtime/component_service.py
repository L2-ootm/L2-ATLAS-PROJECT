"""ATLAS optional-component service — install/uninstall SDK components.

The self-contained npm runtime ships lean: the Claude Agent SDK is embedded,
the Codex SDK (~95 MB, bundles a pinned CLI) is not. This service lets the
operator manage those optional components after installation:

  atlas components list                — availability report (importable SDK,
                                        provider CLI on PATH, pip pin)
  atlas components install <name>     — pip-install the pinned package into
                                        the running interpreter's environment
  atlas components uninstall <name>   — pip-uninstall it

Surfaces consume the availability report (gateway /v1/components) to hide
agent runtimes whose component is absent, so an uninstalled SDK disappears
from pickers instead of failing at execute time.

Idempotency: install on an installed component and uninstall on an absent one
are no-ops reported as such, never errors. Pip runs through the *current*
interpreter (`sys.executable -m pip`), which is the embedded Python in npm
installs and the venv in source checkouts — the same environment the lazy
adapter imports resolve against.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

_PIP_TIMEOUT_SECONDS = 900


class ComponentError(ValueError):
    """Raised for unknown component names or failed pip operations."""


@dataclass(frozen=True)
class Component:
    """One optional, operator-manageable ATLAS component."""

    name: str
    description: str
    pip_requirement: str
    pip_package: str
    import_probe: str
    agent_runtime: str
    cli_probe: str


# Pins mirror services/agent-runtime/pyproject.toml optional extras; the exact
# claude pin matches scripts/ci/build-windows-runtime.ps1 so a reinstall
# converges with what the release bundle embeds.
COMPONENTS: dict[str, Component] = {
    "claude": Component(
        name="claude",
        description="Claude Agent SDK — drives the operator's local Claude Code session",
        pip_requirement="claude-agent-sdk==0.2.104",
        pip_package="claude-agent-sdk",
        import_probe="claude_agent_sdk",
        agent_runtime="claude_code",
        cli_probe="claude",
    ),
    "codex": Component(
        name="codex",
        description="OpenAI Codex SDK — drives the operator's local Codex CLI login",
        pip_requirement="openai-codex>=0.1.0b3,<0.2",
        pip_package="openai-codex",
        import_probe="openai_codex",
        agent_runtime="codex",
        cli_probe="codex",
    ),
}


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def component_status(component: Component) -> dict:
    """Availability report for one component (no side effects)."""
    return {
        "name": component.name,
        "description": component.description,
        "agent_runtime": component.agent_runtime,
        "pip_requirement": component.pip_requirement,
        "installed": _module_available(component.import_probe),
        "cli_present": shutil.which(component.cli_probe) is not None,
    }


def list_components() -> list[dict]:
    """Availability report for every managed component."""
    return [component_status(c) for c in COMPONENTS.values()]


def _get(name: str) -> Component:
    component = COMPONENTS.get(name.strip().lower())
    if component is None:
        known = ", ".join(sorted(COMPONENTS))
        raise ComponentError(f"unknown component {name!r} (known: {known})")
    return component


def _run_pip(args: list[str], runner: Optional[Callable] = None) -> None:
    """Invoke pip via the current interpreter; raise ComponentError on failure."""
    cmd = [sys.executable, "-m", "pip", *args, "--disable-pip-version-check"]
    run = runner or subprocess.run
    try:
        proc = run(cmd, capture_output=True, text=True, timeout=_PIP_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ComponentError(f"pip invocation failed: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
        raise ComponentError(
            "pip {} failed (exit {}): {}".format(args[0], proc.returncode, " | ".join(tail))
        )


def install_component(name: str, *, runner: Optional[Callable] = None) -> dict:
    """Install the pinned package for a component; idempotent."""
    component = _get(name)
    if _module_available(component.import_probe):
        return {**component_status(component), "changed": False}
    _run_pip(["install", component.pip_requirement], runner=runner)
    importlib.invalidate_caches()
    status = component_status(component)
    if not status["installed"]:
        raise ComponentError(
            f"pip install reported success but {component.import_probe!r} is still not importable"
        )
    return {**status, "changed": True}


def uninstall_component(name: str, *, runner: Optional[Callable] = None) -> dict:
    """Uninstall a component's package; idempotent."""
    component = _get(name)
    if not _module_available(component.import_probe):
        return {**component_status(component), "changed": False}
    _run_pip(["uninstall", "--yes", component.pip_package], runner=runner)
    importlib.invalidate_caches()
    status = component_status(component)
    if status["installed"]:
        raise ComponentError(
            f"pip uninstall reported success but {component.import_probe!r} is still importable"
        )
    return {**status, "changed": True}
