"""Golden and invariant tests for the deterministic ATLAS prompt compiler."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from atlas_core.schemas.agent_contract import (
    ContextEnvelope,
    ContextSource,
    ContractVersion,
    InstructionSource,
    ModelIdentity,
    SessionBootstrap,
    SurfaceIdentity,
    WorkspaceIdentity,
)
from atlas_runtime.prompt_compiler import compile_prompt

GOLDENS = Path(__file__).parent / "golden" / "prompts"
CORE_SHA = "b" * 64


def _instruction(text: str) -> tuple[InstructionSource, tuple[str, ...]]:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = InstructionSource(
        source_id="agents-root",
        path="AGENTS.md",
        sha256=digest,
        trust="project",
    )
    return source, (text,)


def _bootstrap(
    *,
    surface: str = "tui",
    provider: str = "generic",
    instructions: tuple[InstructionSource, ...] = (),
) -> SessionBootstrap:
    return SessionBootstrap(
        surface=SurfaceIdentity(kind=surface, session_id=f"{surface}-session"),
        workspace=WorkspaceIdentity(
            kind="project",
            project_id="atlas",
            root="C:/work/atlas",
        ),
        focus_id="focus-1",
        focus_title="Ship deterministic prompts",
        run_id="run-1",
        agent="native",
        model=ModelIdentity(provider=provider, model_id="model-1"),
        permission_mode="ask",
        capabilities=("file.read", "shell.exec"),
        instruction_sources=instructions,
        prompt=ContractVersion(version="1.0.0", sha256=CORE_SHA),
        tool_catalog=ContractVersion(version="1.0.0", sha256="c" * 64),
        context_policy=ContractVersion(version="1.0.0", sha256="d" * 64),
        context_budget_tokens=8000,
    )


def _context(content: str = "Current focus is prompt determinism.") -> ContextEnvelope:
    return ContextEnvelope(
        policy=ContractVersion(version="1.0.0", sha256="d" * 64),
        budget_tokens=8000,
        estimated_tokens=32,
        sources=(
            ContextSource(
                source_id="wiki:prompt",
                source_type="wiki",
                project_id="atlas",
                retrieved_at="2026-06-24T18:00:00Z",
                source_updated_at="2026-06-24T17:00:00Z",
                confidence=0.95,
                relevance=0.9,
                trust="evidence",
                content=content,
            ),
        ),
    )


def _snapshot(compilation) -> dict[str, object]:  # noqa: ANN001
    bootstrap = json.loads(compilation.bootstrap_message)
    return {
        "stable_prompt_sha256": compilation.stable_prompt_sha256,
        "bootstrap_message_sha256": hashlib.sha256(
            compilation.bootstrap_message.encode("utf-8")
        ).hexdigest(),
        "context_message_sha256": hashlib.sha256(
            compilation.context_message.encode("utf-8")
        ).hexdigest(),
        "prompt_version": compilation.prompt_version,
        "estimated_stable_tokens": compilation.estimated_stable_tokens,
        "surface": bootstrap["payload"]["surface"]["kind"],
        "provider": bootstrap["payload"]["model"]["provider"],
    }


@pytest.mark.parametrize(
    ("name", "provider_family", "surface"),
    [
        ("generic", "generic", "api"),
        ("openai-compatible", "openai-compatible", "api"),
        ("anthropic-compatible", "anthropic-compatible", "api"),
        ("tui", "generic", "tui"),
        ("webui", "generic", "webui"),
    ],
)
def test_prompt_goldens_are_byte_stable(name: str, provider_family: str, surface: str):
    source, texts = _instruction("Inspect before editing. Verify before completion.")
    compilation = compile_prompt(
        bootstrap=_bootstrap(
            surface=surface,
            provider=provider_family,
            instructions=(source,),
        ),
        context=_context(),
        provider_family=provider_family,
        workspace_instructions=texts,
    )
    expected = json.loads((GOLDENS / f"{name}.json").read_text(encoding="utf-8"))
    assert _snapshot(compilation) == expected


def test_dynamic_context_does_not_change_stable_prefix():
    bootstrap = _bootstrap()
    first = compile_prompt(bootstrap=bootstrap, context=_context("Evidence one."))
    second = compile_prompt(bootstrap=bootstrap, context=_context("Evidence two."))

    assert first.stable_prompt == second.stable_prompt
    assert first.stable_prompt_sha256 == second.stable_prompt_sha256
    assert first.context_message != second.context_message


def test_provider_adapter_cannot_replace_atlas_identity():
    for family in ("generic", "openai-compatible", "anthropic-compatible"):
        result = compile_prompt(
            bootstrap=_bootstrap(provider=family),
            context=_context(),
            provider_family=family,
        )
        text = result.stable_prompt.decode("utf-8")
        assert "You are ATLAS" in text
        assert "Hermes Agent" not in text
        assert "Nous Research" not in text
        assert text.index("[L1 ATLAS CORE]") < text.index("[L2 PROVIDER ADAPTER]")


def test_surface_only_changes_bootstrap_not_stable_prompt():
    tui = compile_prompt(bootstrap=_bootstrap(surface="tui"), context=_context())
    webui = compile_prompt(bootstrap=_bootstrap(surface="webui"), context=_context())

    assert tui.stable_prompt == webui.stable_prompt
    assert tui.bootstrap_message != webui.bootstrap_message


def test_workspace_instruction_hash_must_match_bootstrap():
    source, _ = _instruction("Expected text.")
    with pytest.raises(ValueError, match="hash"):
        compile_prompt(
            bootstrap=_bootstrap(instructions=(source,)),
            context=_context(),
            workspace_instructions=("Tampered text.",),
        )


def test_secret_in_stable_instruction_is_rejected():
    source, texts = _instruction("api_key=sk-do-not-cache-123")
    with pytest.raises(ValueError, match="secret"):
        compile_prompt(
            bootstrap=_bootstrap(instructions=(source,)),
            context=_context(),
            workspace_instructions=texts,
        )


def test_secret_in_dynamic_context_is_redacted():
    result = compile_prompt(
        bootstrap=_bootstrap(),
        context=_context("Authorization: Bearer abc.def.ghi"),
    )
    assert "abc.def.ghi" not in result.context_message
    assert "[REDACTED]" in result.context_message


def test_stable_prompt_stays_within_token_budget():
    result = compile_prompt(bootstrap=_bootstrap(), context=_context())
    assert result.estimated_stable_tokens <= 4000


def test_declared_atlas_tools_match_what_the_bridges_register():
    """The prompt must name exactly the ATLAS tools the harness registers.

    L3 previously declared the host tool_catalog (workspace, github, web_fetch,
    …) under "use only capabilities declared below". Those are reachable only
    via tool_service from the CLI and are never handed to the model, while
    atlas_actor and atlas_graph — the tools it can actually call — went
    undeclared. A compliant model had to violate the instruction to do anything.
    """
    import re

    from atlas_runtime.prompt_compiler import AGENT_FACING_TOOLS

    registered = set()
    for module in ("actor_bridge", "graph_bridge"):
        source = (
            Path(__file__).parent.parent / "atlas_runtime" / f"{module}.py"
        ).read_text(encoding="utf-8")
        registered.update(re.findall(r'ctx\.register_tool\(\s*name="([^"]+)"', source))

    assert registered == set(AGENT_FACING_TOOLS), (
        "prompt_compiler.AGENT_FACING_TOOLS drifted from the bridges: "
        f"registered={sorted(registered)} declared={sorted(AGENT_FACING_TOOLS)}"
    )


def test_l3_tells_the_model_how_to_read_a_failed_tool_result():
    """atlas_core.md never mentions failure, yet both bridges return ok:false."""
    source, texts = _instruction("Inspect before editing. Verify before completion.")
    compilation = compile_prompt(
        bootstrap=_bootstrap(instructions=(source,)),
        context=_context(),
        workspace_instructions=texts,
    )
    prompt = compilation.stable_prompt.decode("utf-8")
    assert '{"ok": false, ...}' in prompt
    assert "do not repeat the identical call" in prompt
