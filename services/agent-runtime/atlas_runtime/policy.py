"""ATLAS policy engine — workspace boundary and tool allowlist enforcement.

References:
  - D-006: Policy engine must work cross-platform (Linux bash + Windows PowerShell
    paths). Uses pathlib.Path.resolve() — never hardcodes OS path separators.
  - RUNTIME-07: Policy engine enforces cross-platform workspace/command safety.

PolicyDecision is a dataclass (not a Pydantic model) — it is an in-memory result,
not a persisted entity.

check_workspace_boundary_and_emit emits a failure AuditEvent on rejection per
success criterion 6 (CONTEXT.md).
"""

from __future__ import annotations

import ntpath
import os
import pathlib
import sqlite3
import threading
from dataclasses import dataclass
from fnmatch import fnmatchcase

from atlas_core.schemas.control_plane import (
    PermissionConfig,
    PermissionExplainReceipt,
    PermissionPolicyProfile,
    PermissionPolicyRule,
)
from atlas_runtime.audit_service import emit
from atlas_runtime.hardline_policy import match_hardline


@dataclass
class PolicyDecision:
    """Result of a policy check.

    Attributes:
        allowed: True if the action may execute immediately; False if it is
            rejected OR must first be approved (see requires_approval).
        reason: Human-readable, snake_case explanation for the decision.
        requires_approval: True when the action is not rejected but must pass
            through the operator approval gate before it can run (write/shell
            tools, Phase 10.0.4). ToolCall.requires_approval derives from this.
    """

    allowed: bool
    reason: str
    requires_approval: bool = False
    receipt: PermissionExplainReceipt | None = None


@dataclass(frozen=True)
class PolicyFacts:
    """Normalized trusted facts supplied by the runtime, never by surface UI."""

    tool: str
    risk: str
    capability: str | None = None
    command: str | None = None
    target_paths: tuple[str, ...] = ()
    workspace_root: str | None = None
    workspace: str | None = None
    project: str | None = None
    surface: str | None = None
    agent: str | None = None
    channel: str | None = None
    explicit_user_maintenance: bool = False
    smart_recommendation: str | None = None


def _receipt(
    facts: PolicyFacts,
    config: PermissionConfig,
    *,
    decision: str,
    reason: str,
    source: str,
    profile: PermissionPolicyProfile | None = None,
    matched_rule_id: str | None = None,
    maintenance_scope_used: bool = False,
) -> PermissionExplainReceipt:
    return PermissionExplainReceipt(
        decision=decision,
        reason_code=reason,
        matched_rule_id=matched_rule_id,
        source_layer=source,
        effective_preset=profile.preset if profile is not None else config.preset,
        effective_profile_id=profile.id if profile is not None else None,
        tool=facts.tool,
        capability=facts.capability,
        risk=facts.risk,
        workspace_root=facts.workspace_root,
        target_paths=facts.target_paths,
        maintenance_scope_used=maintenance_scope_used,
    )


def _result(
    facts: PolicyFacts,
    config: PermissionConfig,
    *,
    decision: str,
    reason: str,
    source: str,
    profile: PermissionPolicyProfile | None = None,
    matched_rule_id: str | None = None,
    maintenance_scope_used: bool = False,
) -> PolicyDecision:
    return PolicyDecision(
        allowed=decision == "allow",
        reason=reason,
        requires_approval=decision == "ask",
        receipt=_receipt(
            facts,
            config,
            decision=decision,
            reason=reason,
            source=source,
            profile=profile,
            matched_rule_id=matched_rule_id,
            maintenance_scope_used=maintenance_scope_used,
        ),
    )


def _matches_values(patterns: tuple[str, ...], value: str | None) -> bool:
    if not patterns:
        return True
    if value is None:
        return False
    normalized = value.casefold()
    return any(fnmatchcase(normalized, pattern.casefold()) for pattern in patterns)


def _rule_matches(rule: PermissionPolicyRule, facts: PolicyFacts) -> bool:
    selector = rule.selector
    if not rule.enabled:
        return False
    if not _matches_values(selector.tools, facts.tool):
        return False
    if not _matches_values(selector.capabilities, facts.capability):
        return False
    if selector.risks and facts.risk not in selector.risks:
        return False
    if not _matches_values(selector.surfaces, facts.surface):
        return False
    if not _matches_values(selector.agents, facts.agent):
        return False
    if not _matches_values(
        selector.workspaces, facts.workspace or facts.workspace_root
    ):
        return False
    if not _matches_values(selector.projects, facts.project):
        return False
    if not _matches_values(selector.channels, facts.channel):
        return False
    if not _matches_values(selector.command_patterns, facts.command):
        return False
    if selector.path_patterns:
        if not facts.target_paths:
            return False
        if not any(
            _matches_values(selector.path_patterns, target)
            for target in facts.target_paths
        ):
            return False
    return True


def _profile_matches(profile: PermissionPolicyProfile, facts: PolicyFacts) -> bool:
    return (
        profile.enabled
        and _matches_values(profile.surfaces, facts.surface)
        and _matches_values(
            profile.workspaces,
            facts.workspace or facts.workspace_root,
        )
        and _matches_values(profile.projects, facts.project)
        and _matches_values(profile.agents, facts.agent)
        and _matches_values(profile.channels, facts.channel)
    )


def _foreign_flavor_absolute(path: str) -> bool:
    """True when `path` is absolute only in the non-native path flavor —
    e.g. 'C:\\x' or 'C:/x' checked on a POSIX host. Native pathlib treats
    such a string as one odd relative filename, so a naive join+relative_to
    check would wrongly place it inside the workspace (RUNTIME-07: the
    boundary must reject Windows-style escapes on Linux too)."""
    if pathlib.Path(path).is_absolute():
        return False  # native-absolute: the normal resolve/relative_to path handles it
    return (
        pathlib.PureWindowsPath(path).is_absolute()
        or pathlib.PurePosixPath(path).is_absolute()
    )


def _windows_style(path: str) -> bool:
    """Drive-lettered (C:...) or UNC (\\\\server\\share) — a Windows-flavor string."""
    return bool(pathlib.PureWindowsPath(path).drive)


def _within(path: str, root: str) -> bool:
    try:
        if os.name != "nt" and (_windows_style(path) or _windows_style(root)):
            # Windows-flavor strings on a POSIX host (frozen policy fixtures,
            # cross-machine configs, RUNTIME-07): native resolve() would read
            # the whole string as one relative filename — wrongly placing an
            # absolute C:\ escape INSIDE the workspace — so containment is
            # decided lexically in Windows semantics instead.
            target = path if ntpath.isabs(path) else ntpath.join(root, path)
            target_n = ntpath.normcase(ntpath.normpath(target))
            root_n = ntpath.normcase(ntpath.normpath(root))
            return target_n == root_n or target_n.startswith(root_n.rstrip("\\") + "\\")
        root_path = pathlib.Path(root).resolve()
        target = pathlib.Path(path)
        if not target.is_absolute():
            target = root_path / target
        target.resolve().relative_to(root_path)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


_MAINTENANCE_CAPABILITIES = frozenset(
    {
        "atlas.config.write",
        "atlas.install.write",
        "atlas.self.modify",
        "atlas.update",
    }
)


def _maintenance_applies(
    config: PermissionConfig,
    facts: PolicyFacts,
) -> bool:
    return bool(
        config.atlas_maintenance_enabled
        and facts.explicit_user_maintenance
        and facts.capability in _MAINTENANCE_CAPABILITIES
        and facts.target_paths
        and config.maintenance_roots
        and all(
            any(_within(target, root) for root in config.maintenance_roots)
            for target in facts.target_paths
        )
    )


def _default_decision(
    preset: str,
    facts: PolicyFacts,
) -> tuple[str, str]:
    if facts.risk == "read":
        return "allow", "read_class_allowed"
    if preset == "full_autonomy":
        return "allow", "full_autonomy_allowed"
    if preset == "smart":
        if facts.smart_recommendation == "allow":
            return "allow", "smart_advisor_allowed"
        if facts.smart_recommendation == "deny":
            return "deny", "smart_advisor_denied"
        if facts.smart_recommendation == "unavailable":
            return "deny", "smart_advisor_unavailable"
        return "ask", "smart_review_required"
    return "ask", "manual_approval_required"


def decide(
    manifest,
    mode: str = "read_only",
    *,
    config: PermissionConfig | None = None,
    facts: PolicyFacts | None = None,
    scoped_allow_rule_id: str | None = None,
) -> "PolicyDecision":
    """Evaluate one action through the shared hardline/master/profile authority.

    Precedence is immutable hardline, explicit master deny, master ceiling,
    narrowing profile, scoped allow, then the effective default. A later stage
    never overturns a deny.
    """
    legacy_default = config is None and facts is None and mode == "read_only"
    if config is None:
        if mode == "allow":
            config = PermissionConfig(preset="full_autonomy")
        else:
            config = PermissionConfig()
    permissions = getattr(manifest, "permissions", ())
    capability = permissions[0] if permissions else None
    facts = facts or PolicyFacts(
        tool=manifest.name,
        risk=manifest.risk_level,
        capability=capability,
    )

    hardline = match_hardline(
        command=facts.command,
        target_paths=facts.target_paths,
    )
    if hardline is not None:
        return _result(
            facts,
            config,
            decision="deny",
            reason=hardline.reason_code,
            source="hardline",
            matched_rule_id=hardline.rule_id,
        )

    if mode == "deny":
        return _result(
            facts,
            config,
            decision="deny",
            reason="legacy_mode_denied",
            source="master",
        )

    for rule in config.rules:
        if rule.effect == "deny" and _rule_matches(rule, facts):
            return _result(
                facts,
                config,
                decision="deny",
                reason="master_rule_denied",
                source="master",
                matched_rule_id=rule.id,
            )

    profile = next(
        (
            candidate
            for candidate in config.profiles
            if _profile_matches(candidate, facts)
        ),
        None,
    )
    workspace_only = config.workspace_only or bool(
        profile is not None and profile.workspace_only
    )
    maintenance_used = _maintenance_applies(config, facts)
    if workspace_only and facts.target_paths and not maintenance_used:
        if not facts.workspace_root or not all(
            _within(path, facts.workspace_root) for path in facts.target_paths
        ):
            return _result(
                facts,
                config,
                decision="deny",
                reason="path_outside_workspace",
                source="profile" if profile is not None else "master",
                profile=profile,
            )

    master_decision, master_reason = _default_decision(config.preset, facts)
    master_rule: PermissionPolicyRule | None = None
    for rule in config.rules:
        if rule.effect != "deny" and _rule_matches(rule, facts):
            master_rule = rule
            master_decision = rule.effect
            master_reason = (
                "master_rule_allowed"
                if rule.effect == "allow"
                else "master_rule_approval_required"
            )
            break

    decision = master_decision
    reason = master_reason
    source = "master" if master_rule is not None else "default"
    matched_rule_id = master_rule.id if master_rule is not None else None

    if profile is not None:
        for rule in profile.rules:
            if rule.effect == "deny" and _rule_matches(rule, facts):
                return _result(
                    facts,
                    config,
                    decision="deny",
                    reason="profile_rule_denied",
                    source="profile",
                    profile=profile,
                    matched_rule_id=rule.id,
                    maintenance_scope_used=maintenance_used,
                )
        profile_decision, profile_reason = _default_decision(profile.preset, facts)
        profile_rule: PermissionPolicyRule | None = None
        for rule in profile.rules:
            if rule.effect != "deny" and _rule_matches(rule, facts):
                profile_rule = rule
                profile_decision = rule.effect
                profile_reason = (
                    "profile_rule_allowed"
                    if rule.effect == "allow"
                    else "profile_rule_approval_required"
                )
                break
        rank = {"deny": 0, "ask": 1, "allow": 2}
        if rank[profile_decision] < rank[decision]:
            decision = profile_decision
            reason = profile_reason
            source = "profile" if profile_rule is not None else "default"
            matched_rule_id = profile_rule.id if profile_rule is not None else None

    if decision == "ask" and scoped_allow_rule_id:
        decision = "allow"
        reason = "scoped_allow_matched"
        source = "scoped_allow"
        matched_rule_id = scoped_allow_rule_id

    if legacy_default and decision == "ask" and reason == "manual_approval_required":
        reason = f"{facts.risk}_requires_approval"

    return _result(
        facts,
        config,
        decision=decision,
        reason=reason,
        source=source,
        profile=profile,
        matched_rule_id=matched_rule_id,
        maintenance_scope_used=maintenance_used,
    )


def check_workspace_boundary(
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Return a PolicyDecision for whether target_path is within workspace_root.

    Uses pathlib.Path.resolve() for cross-platform normalization — handles both
    Windows (C:\\...) and POSIX (/home/...) path strings transparently.

    Resolves target relative to workspace_root to prevent CWD-escape attacks
    (Pitfall 3 in 05-RESEARCH.md): relative paths are pinned to workspace_root
    before resolving, so '../outside' cannot escape the workspace root.

    An absolute path outside the workspace (e.g. 'C:\\Users\\other\\file.txt')
    causes pathlib to discard the workspace_root prefix on join, resulting in
    a path that fails the relative_to() check — correctly rejected.
    """
    try:
        if _foreign_flavor_absolute(target_path):
            raise ValueError(target_path)
        resolved_root = pathlib.Path(workspace_root).resolve()
        # Pin relative paths to workspace_root to prevent CWD-escape.
        # For absolute target_path values, pathlib discards resolved_root on join,
        # so absolute paths outside the workspace fall through to relative_to() failure.
        resolved_target = (resolved_root / target_path).resolve()
        resolved_target.relative_to(resolved_root)
        return PolicyDecision(allowed=True, reason="within_workspace")
    except ValueError:
        return PolicyDecision(
            allowed=False,
            reason=f"path_outside_workspace: {target_path!r} not under {workspace_root!r}",
        )


def check_workspace_boundary_and_emit(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    run_id: str,
    target_path: str,
    workspace_root: str,
) -> PolicyDecision:
    """Check workspace boundary and emit a failure AuditEvent on rejection.

    Delegates boundary check to check_workspace_boundary(). If rejected, emits
    an AuditEvent with event_type="failure" and policy_result set to the reason.

    emit() acquires the lock internally — never call this while holding the lock.
    """
    decision = check_workspace_boundary(target_path, workspace_root)
    if not decision.allowed:
        emit(
            conn,
            lock,
            run_id=run_id,
            event_type="failure",
            data={"reason": decision.reason, "target_path": target_path},
            policy_result=decision.reason,
        )
    return decision


def check_tool_allowed(
    tool_name: str,
    allowed_tools: list[str],
) -> PolicyDecision:
    """Return a PolicyDecision for whether tool_name is in the allowed list (D-008).

    Unclassified tools (not in allowed_tools) are rejected — skills must be
    classified before ATLAS-grade use (D-008).
    """
    if tool_name in allowed_tools:
        return PolicyDecision(allowed=True, reason="tool_in_allowlist")
    return PolicyDecision(
        allowed=False,
        reason=f"tool_not_allowed: {tool_name!r} not in allowlist",
    )
