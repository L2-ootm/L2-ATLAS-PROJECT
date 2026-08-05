"""Registry-complete TEST-01 prompt-golden contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from atlas_core.schemas.agent_contract import (
    ContextEnvelope,
    ContextSource,
    ContractVersion,
    ModelIdentity,
    SessionBootstrap,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_runtime.prompt_compiler import _PROVIDER_ADAPTERS, compile_prompt


FIXTURE = Path(__file__).parent / "fixtures" / "prompt_golden_matrix.json"
SURFACES = {
    "go_tui": "tui",
    "atlas_terminal": "cli",
    "cockpit": "webui",
}
WORKSPACES = ("global", "registered_project")
PERMISSION_MODES = ("deny", "ask", "allow")
CONTEXT_STATES = (False, True)


def _bootstrap(*, surface: str, workspace: str, permission_mode: str, provider: str) -> SessionBootstrap:
    return SessionBootstrap(
        surface=SurfaceIdentity(kind=surface, session_id=f"{surface}-matrix"),
        workspace=WorkspaceIdentity(
            kind="global" if workspace == "global" else "project",
            project_id=None if workspace == "global" else "atlas",
            root="C:/work/global" if workspace == "global" else "C:/work/atlas",
        ),
        focus_id="focus-matrix",
        focus_title="Freeze prompt conformance",
        run_id="run-matrix",
        agent="native",
        model=ModelIdentity(provider=provider, model_id="matrix-model"),
        permission_mode=permission_mode,
        capabilities=("file.read", "shell.exec"),
        prompt=ContractVersion(version="1.0.0", sha256="b" * 64),
        tool_catalog=ContractVersion(version="1.0.0", sha256="c" * 64),
        context_policy=ContractVersion(version="1.0.0", sha256="d" * 64),
        context_budget_tokens=8192,
    )


def _context(present: bool) -> ContextEnvelope:
    return ContextEnvelope(
        policy=ContractVersion(version="1.0.0", sha256="d" * 64),
        budget_tokens=8192,
        estimated_tokens=16 if present else 0,
        sources=()
        if not present
        else (
            ContextSource(
                source_id="wiki:matrix",
                source_type="wiki",
                project_id="atlas",
                retrieved_at="2026-07-29T00:00:00Z",
                source_updated_at="2026-07-29T00:00:00Z",
                confidence=0.9,
                relevance=0.9,
                trust="evidence",
                content="Dynamic matrix evidence.",
            ),
        ),
    )


def _case_id(case: dict[str, object]) -> str:
    return "/".join(str(case[key]) for key in ("provider", "surface", "workspace", "permission_mode", "context_present"))


def test_registry_complete_prompt_golden_matrix() -> None:
    matrix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == 1
    assert set(matrix["provider_families"]) == set(_PROVIDER_ADAPTERS), "provider registry drift"
    assert matrix["surfaces"] == SURFACES

    expected = {
        (provider, surface, workspace, permission_mode, context_present)
        for provider in _PROVIDER_ADAPTERS
        for surface in SURFACES
        for workspace in WORKSPACES
        for permission_mode in PERMISSION_MODES
        for context_present in CONTEXT_STATES
    }
    actual = {
        (case["provider"], case["surface"], case["workspace"], case["permission_mode"], case["context_present"])
        for case in matrix["cases"]
    }
    assert actual == expected, f"matrix combinations drift: missing={sorted(expected - actual)!r}; extra={sorted(actual - expected)!r}"

    serialized = json.dumps(matrix, sort_keys=True)
    assert "sk-" not in serialized and "Authorization:" not in serialized, "golden matrix contains a raw credential"

    for case in matrix["cases"]:
        case_id = _case_id(case)
        bootstrap = _bootstrap(
            surface=SURFACES[case["surface"]],
            workspace=case["workspace"],
            permission_mode=case["permission_mode"],
            provider=case["provider"],
        )
        absent = compile_prompt(bootstrap=bootstrap, context=_context(False), provider_family=case["provider"])
        present = compile_prompt(bootstrap=bootstrap, context=_context(True), provider_family=case["provider"])
        prefix = absent.stable_prompt.decode("utf-8")

        assert absent.stable_prompt == present.stable_prompt, f"{case_id}: stable-prefix section drifted"
        assert absent.stable_prompt_sha256 == present.stable_prompt_sha256, f"{case_id}: stable-prefix hash drifted"
        assert hashlib.sha256(absent.stable_prompt).hexdigest() == case["stable_prompt_sha256"], f"{case_id}: stable-prefix golden drifted"
        assert _PROVIDER_ADAPTERS[case["provider"]] in prefix, f"{case_id}: provider-adapter section drifted"
        assert present.context_message != absent.context_message, f"{case_id}: dynamic-context section did not change"
        assert "[REDACTED]" not in prefix, f"{case_id}: dynamic context leaked into stable-prefix section"
