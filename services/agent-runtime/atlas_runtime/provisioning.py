"""Build-on-the-operator's-machine provisioning for components shipped as source.

Doctrine (declared in `infra/release/payload.manifest`): the release payload
carries SOURCE for any component whose build output cannot reasonably be
shipped. Cashflow is the reference case — a Next.js app needs `node_modules`
present at runtime, so a prebuilt bundle is ~1.3 GB of `node_modules` + `.next`
against 1.18 MB of tracked source. Such components are installed and built the
first time they are actually used, not at download time.

Two invariants drive the design:

1. **Build output must never land inside the immutable release directory.**
   `packages/atlas-cli/src/paths.js` lays out `<install-root>/versions/<version>/`
   as one immutable release, and the updater deletes stale version directories.
   Anything built into the shipped tree would be destroyed by the next update and
   would make an installed release differ from the artifact CI published. When
   the source is detected inside a release bundle, it is mirrored into
   `<ATLAS home>/sidecars/<name>` first — the same location convention
   `freellmapi_control.sidecar_home()` already uses, resolved at call time so it
   honors ATLAS_DB / ATLAS_HOME.

2. **Re-provisioning is decided by content, not by a flag.** Two fingerprints
   are tracked separately: the dependency manifests gate the install step, and
   every source file gates the build step. Editing app code rebuilds without
   reinstalling; changing a lockfile does both. This is what makes repeated
   `start()` calls cheap and makes an upgrade self-healing.

In a developer checkout there is no release marker, so the workspace is the
checkout itself and builds happen in place — the existing repo workflow is
preserved. Provisioning state always lives under ATLAS_HOME, never in the
source tree, so a checkout is never dirtied by a build.

To onboard another source-shipped component, add a `Component` factory and call
`ensure_provisioned()` from that component's control module.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Callable, Iterator, Sequence

from . import db as db_module

# Never mirrored and never fingerprinted: these are dependency trees and build
# outputs, i.e. precisely what provisioning regenerates. Fingerprinting them
# would make every build change the source fingerprint and rebuild forever.
_EXCLUDED_DIRS = frozenset(
    {
        ".cache",
        ".git",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".turbo",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
    }
)

# `next build` on a cold cache is minutes, not seconds.
DEFAULT_TIMEOUT = 1800.0

Logger = Callable[[str], None]


class ProvisionError(RuntimeError):
    """A provisioning step failed; the message carries the actionable tail."""


@dataclasses.dataclass(frozen=True)
class Component:
    """A component that ships as source and is built locally on first use."""

    name: str
    source_dir: pathlib.Path
    dep_manifests: tuple[str, ...]
    # A sequence of commands, not one command: the discord bot needs its own
    # interpreter created before anything can be installed into it, and a
    # single-command field forced that kind of component to stay unprovisioned.
    install: tuple[tuple[str, ...], ...]
    build: tuple[tuple[str, ...], ...] | None = None
    # `npm ci` refuses to run when the lockfile disagrees with package.json.
    # Falling back to `npm install` keeps a stale checkout installable.
    install_fallback: tuple[tuple[str, ...], ...] | None = None
    deps_marker: str = "node_modules"
    build_marker: str | None = None


@dataclasses.dataclass(frozen=True)
class ProvisionResult:
    ok: bool
    message: str
    workspace: pathlib.Path
    installed: bool = False
    built: bool = False


def sidecars_home() -> pathlib.Path:
    """`<ATLAS home>/sidecars`, resolved at call time.

    Derived from `db.default_db_path()` rather than a frozen constant so it
    honors ATLAS_DB / ATLAS_HOME per call, matching `freellmapi_control`.
    """
    return pathlib.Path(db_module.default_db_path()).parent / "sidecars"


def release_root(start: pathlib.Path) -> pathlib.Path | None:
    """Return the release bundle root containing `start`, else None.

    The platform builders write `runtime.json` at the bundle root (see
    `scripts/ci/build-windows-runtime.ps1` and its POSIX twins). Its presence
    marks an immutable release directory that `atlas` self-update deletes
    wholesale, so nothing may be built inside it.
    """
    for candidate in (start, *start.parents):
        marker = candidate / "runtime.json"
        if not marker.is_file():
            continue
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "platform" in data and "entrypoint" in data:
            return candidate
    return None


def resolve_workspace(component: Component) -> tuple[pathlib.Path, bool]:
    """Return (workspace, mirrored). Mirrored means the source is immutable."""
    if release_root(component.source_dir) is None:
        return component.source_dir, False
    return sidecars_home() / component.name, True


def state_path(name: str) -> pathlib.Path:
    """Provisioning state lives under ATLAS_HOME, never in the source tree."""
    return sidecars_home() / f"{name}.provision.json"


def _read_state(name: str) -> dict:
    try:
        data = json.loads(state_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(name: str, state: dict) -> None:
    path = state_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _iter_source_files(root: pathlib.Path) -> Iterator[pathlib.Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDED_DIRS)
        for name in sorted(filenames):
            yield pathlib.Path(dirpath) / name


def _digest(root: pathlib.Path, paths: Sequence[pathlib.Path]) -> str:
    """Content digest over `paths`, keyed by path relative to `root`.

    Content rather than mtime: mirroring rewrites timestamps, so an mtime-based
    fingerprint would force a rebuild on every mirror.
    """
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()


def source_fingerprint(component: Component) -> str:
    root = component.source_dir
    return _digest(root, list(_iter_source_files(root)))


def deps_fingerprint(workspace: pathlib.Path, component: Component) -> str:
    present = [workspace / name for name in component.dep_manifests]
    return _digest(workspace, [p for p in present if p.is_file()])


def _mirror(source: pathlib.Path, workspace: pathlib.Path, log: Logger) -> None:
    """Refresh `workspace` from `source`, preserving regenerable directories.

    `node_modules` and `.next` are deliberately left in place: whether they need
    to be rebuilt is decided by the fingerprints, not by the mirror step, so a
    source-only change does not force a multi-minute reinstall.
    """
    log(f"mirroring {source} -> {workspace}")
    if workspace.is_dir():
        for entry in workspace.iterdir():
            if entry.name in _EXCLUDED_DIRS:
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        workspace,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(*_EXCLUDED_DIRS),
    )


def _argv(command: Sequence[str], cwd: pathlib.Path | None = None) -> list[str]:
    # A command may name an executable inside the workspace that no PATH lookup
    # will ever find — the interpreter of a venv this same install sequence just
    # created. Anything containing a separator is treated as a path, resolved
    # against the workspace, and used verbatim.
    head = command[0]
    if "/" in head or "\\" in head:
        candidate = pathlib.Path(head)
        if not candidate.is_absolute() and cwd is not None:
            candidate = cwd / candidate
        if candidate.is_file():
            return [str(candidate), *command[1:]]
        raise ProvisionError(f"{head!r} not found at {candidate}")
    exe = shutil.which(head)
    if exe is None:
        raise ProvisionError(
            f"{command[0]!r} not found on PATH; install it and retry"
        )
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        # CreateProcess cannot execute a shim script directly, and npm ships as
        # npm.cmd on Windows. Invoke it through cmd.exe with a fixed argv rather
        # than shell=True, so no argument is ever re-parsed by a shell.
        return ["cmd", "/c", exe, *command[1:]]
    return [exe, *command[1:]]


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    # Non-interactive, no telemetry handshakes, no audit/fund noise: provisioning
    # runs unattended behind a UI action or an agent tool call.
    env.setdefault("CI", "1")
    env.setdefault("NEXT_TELEMETRY_DISABLED", "1")
    env.setdefault("npm_config_audit", "false")
    env.setdefault("npm_config_fund", "false")
    env.setdefault("npm_config_progress", "false")
    return env


def _run(
    command: Sequence[str],
    cwd: pathlib.Path,
    log: Logger,
    timeout: float,
) -> None:
    printable = " ".join(command)
    log(f"$ {printable}")
    try:
        proc = subprocess.run(
            _argv(command, cwd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
    except subprocess.TimeoutExpired:
        raise ProvisionError(f"{printable} timed out after {timeout:.0f}s") from None
    if proc.returncode != 0:
        stream = (proc.stderr or "").strip() or (proc.stdout or "").strip()
        tail = " | ".join(stream.splitlines()[-12:]) or "no output"
        raise ProvisionError(f"{printable} failed (exit {proc.returncode}): {tail}")


@dataclasses.dataclass(frozen=True)
class ProvisionPlan:
    """What `ensure_provisioned` would do, computed without doing any of it.

    Callers on a latency budget use this to decide between provisioning inline
    and handing the work to a detached process. The gateway dispatches
    `atlas cashflow start` and awaits the reply, so a multi-minute first build
    must never happen on that path.
    """

    workspace: pathlib.Path
    mirrored: bool
    source_fingerprint: str
    deps_fingerprint: str
    need_mirror: bool
    need_install: bool
    need_build: bool

    @property
    def is_noop(self) -> bool:
        return not (self.need_mirror or self.need_install or self.need_build)

    @property
    def is_expensive(self) -> bool:
        """True when a package manager or bundler would actually run."""
        return self.need_install or self.need_build


def plan_provisioning(component: Component, *, force: bool = False) -> ProvisionPlan:
    """Read-only: decide what provisioning work `component` currently needs."""
    workspace, mirrored = resolve_workspace(component)
    state = _read_state(component.name)
    src_fp = source_fingerprint(component)
    need_mirror = mirrored and (
        force or not workspace.is_dir() or state.get("source_fingerprint") != src_fp
    )
    # Before the first mirror the workspace has no manifests; fingerprint the
    # source copy so the comparison is still meaningful.
    manifest_root = workspace if workspace.is_dir() else component.source_dir
    deps_fp = deps_fingerprint(manifest_root, component)
    # Adoption rule: an existing marker with no recorded fingerprint means the
    # work was already done by hand (a developer checkout that ran `npm install`
    # itself, or an install that predates provisioning). Adopt it and record the
    # baseline instead of reinstalling — in this repo a needless `npm ci` would
    # discard 885 MB of working node_modules. Drift is still caught afterwards,
    # because from then on a recorded fingerprint exists to compare against.
    # `--force` remains the escape hatch.
    need_install = force or not (workspace / component.deps_marker).exists() or (
        "deps_fingerprint" in state and state.get("deps_fingerprint") != deps_fp
    )
    need_build = component.build is not None and (
        force
        or (
            component.build_marker is not None
            and not (workspace / component.build_marker).exists()
        )
        or ("source_fingerprint" in state and state.get("source_fingerprint") != src_fp)
    )
    return ProvisionPlan(
        workspace=workspace,
        mirrored=mirrored,
        source_fingerprint=src_fp,
        deps_fingerprint=deps_fp,
        need_mirror=need_mirror,
        need_install=need_install,
        need_build=need_build,
    )


def ensure_provisioned(
    component: Component,
    *,
    force: bool = False,
    log: Logger | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> ProvisionResult:
    """Install dependencies and build `component` if content changed.

    Idempotent: with an unchanged source tree and lockfile this performs only
    two fingerprint scans and returns. Safe to call on every start.
    """
    emit: Logger = log or (lambda _message: None)
    source = component.source_dir
    if not source.is_dir():
        return ProvisionResult(
            False, f"{component.name} source not found at {source}", source
        )

    plan = plan_provisioning(component, force=force)
    workspace = plan.workspace
    src_fp = plan.source_fingerprint

    if plan.need_mirror:
        try:
            _mirror(source, workspace, emit)
        except OSError as exc:
            return ProvisionResult(
                False, f"could not mirror {component.name} to {workspace}: {exc}", workspace
            )

    # Recompute after mirroring: the workspace manifests are only authoritative
    # once the mirror has actually landed.
    deps_fp = deps_fingerprint(workspace, component)
    state = _read_state(component.name)
    need_install = plan.need_install or (
        "deps_fingerprint" in state and state.get("deps_fingerprint") != deps_fp
    )
    need_build = plan.need_build

    if not need_install and not need_build:
        # Record the baseline when adopting pre-existing artifacts, so the next
        # source or lockfile change is actually detected as drift.
        if state.get("source_fingerprint") != src_fp or state.get("deps_fingerprint") != deps_fp:
            _write_state(
                component.name,
                {
                    "source_fingerprint": src_fp,
                    "deps_fingerprint": deps_fp,
                    "workspace": str(workspace),
                    "mirrored": plan.mirrored,
                    "adopted_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                },
            )
            return ProvisionResult(
                True, f"{component.name} adopted existing build at {workspace}", workspace
            )
        return ProvisionResult(True, f"{component.name} already provisioned", workspace)

    installed = False
    built = False
    try:
        if need_install:
            emit(f"installing {component.name} dependencies (first run takes a while)")
            try:
                for step in component.install:
                    _run(step, workspace, emit, timeout)
            except ProvisionError:
                if not component.install_fallback:
                    raise
                emit("install failed; retrying with the fallback command sequence")
                for step in component.install_fallback:
                    _run(step, workspace, emit, timeout)
            installed = True
        if need_build and component.build is not None:
            emit(f"building {component.name}")
            for step in component.build:
                _run(step, workspace, emit, timeout)
            built = True
    except ProvisionError as exc:
        # Record nothing on failure: the next call must retry from scratch
        # rather than trust a half-finished workspace.
        return ProvisionResult(False, str(exc), workspace, installed, built)

    _write_state(
        component.name,
        {
            "source_fingerprint": src_fp,
            "deps_fingerprint": deps_fp,
            "workspace": str(workspace),
            "mirrored": plan.mirrored,
            "provisioned_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
    )
    steps = [s for s, done in (("installed", installed), ("built", built)) if done]
    return ProvisionResult(
        True,
        f"{component.name} {' and '.join(steps) or 'verified'} at {workspace}",
        workspace,
        installed,
        built,
    )


def cashflow_component() -> Component:
    """The vendored Next.js cashflow app.

    Resolved at call time (not import time) so ATLAS_HOME / checkout-vs-release
    detection reflects the environment of the caller.
    """
    return Component(
        name="cashflow",
        source_dir=pathlib.Path(__file__).resolve().parents[2] / "cashflow",
        dep_manifests=("package.json", "package-lock.json"),
        install=(("npm", "ci"),),
        install_fallback=(("npm", "install"),),
        build=(("npm", "run", "build"),),
        deps_marker="node_modules",
        # `.next` alone is not proof of a production build — `next dev` creates
        # it too (Next 16 writes .next/dev/). Only `next build` writes BUILD_ID,
        # and `next start` is exactly what needs it.
        build_marker=".next/BUILD_ID",
    )


def _venv_python(relative: bool = True) -> str:
    """Path to a venv's interpreter, as the platform lays it out."""
    tail = ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
    return tail if relative else str(pathlib.Path(tail).resolve())


def discord_bot_component() -> Component:
    """The vendored Discord bot sidecar.

    It runs on its OWN interpreter, not the ATLAS runtime venv: discord.py,
    langchain and chromadb are its dependencies, not ATLAS's, and installing
    them into the runtime venv would couple every ATLAS install to a bot nobody
    may be using. So the install sequence creates that venv first and then
    installs into it — the case a single-command Component could not express,
    which is why this component did not exist and `atlas discord start` told the
    operator to go build it by hand.

    `deps_marker` is the venv itself: its absence is what "not installed" means
    here, exactly as `node_modules` is for the Node components.
    """
    return Component(
        name="discord-bot",
        source_dir=pathlib.Path(__file__).resolve().parents[2] / "discord-bot",
        dep_manifests=("requirements.txt",),
        install=(
            # sys.executable, not "python": provisioning may run from a launcher
            # whose PATH python is a different (or missing) interpreter.
            (sys.executable, "-m", "venv", ".venv"),
            (_venv_python(), "-m", "pip", "install", "-r", "requirements.txt"),
        ),
        deps_marker=_venv_python(),
    )


def atlas_terminal_component() -> Component:
    """The vendored Bun/OpenTUI terminal surface.

    Install only, no build step: the launcher runs `bun run dev`, which executes
    from source and needs `node_modules` present. `bun build --compile` produces
    a standalone binary and is a packaging concern, not a prerequisite for
    running the TUI — provisioning a compiled binary on first launch would add
    minutes to it for no functional gain.
    """
    return Component(
        name="atlas-terminal",
        source_dir=pathlib.Path(__file__).resolve().parents[2] / "atlas-terminal",
        dep_manifests=("package.json", "bun.lock"),
        install=(("bun", "install"),),
        deps_marker="node_modules",
    )


__all__ = [
    "Component",
    "DEFAULT_TIMEOUT",
    "atlas_terminal_component",
    "discord_bot_component",
    "ProvisionError",
    "ProvisionPlan",
    "ProvisionResult",
    "cashflow_component",
    "deps_fingerprint",
    "ensure_provisioned",
    "plan_provisioning",
    "release_root",
    "resolve_workspace",
    "sidecars_home",
    "source_fingerprint",
    "state_path",
]
