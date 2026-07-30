"""Tests for atlas_runtime.provisioning — build-on-the-operator's-machine.

Cashflow and its siblings ship as source (infra/release/payload.manifest), so
these tests pin the two invariants that make that safe:

  1. Nothing is ever built inside an immutable release directory, because
     `atlas` self-update deletes stale version directories wholesale.
  2. Re-provisioning is decided by content fingerprints, so repeated starts are
     cheap and a changed lockfile or source file is actually noticed.

No real npm runs here: components are driven with the test interpreter, which
makes install/build observable and fast while exercising the identical code path.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import pytest

from atlas_runtime import provisioning
from atlas_runtime.secure_store import file_lock
# `next build` writes .next/BUILD_ID; the fake build mirrors that shape so the
# nested-marker logic is covered too.
_INSTALL_CODE = "import pathlib; pathlib.Path('node_modules').mkdir(exist_ok=True)"
_BUILD_CODE = (
    "import pathlib; p = pathlib.Path('.next'); p.mkdir(exist_ok=True); "
    "(p / 'BUILD_ID').write_text('built')"
)
_FAIL_CODE = "raise SystemExit(3)"


def _wait_for_path(path: pathlib.Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert path.exists(), f"timed out waiting for {path}"


def _start_lock_holder(lock_path: pathlib.Path, tmp_path: pathlib.Path):
    ready = tmp_path / f"{lock_path.stem}.ready"
    release = tmp_path / f"{lock_path.stem}.release"
    code = (
        "import pathlib,sys,time;"
        "from atlas_runtime.secure_store import file_lock;"
        "lock,ready,release=map(pathlib.Path,sys.argv[1:]);"
        "\nwith file_lock(lock,timeout_seconds=5.0):"
        "\n ready.write_text('ready',encoding='utf-8')"
        "\n while not release.exists(): time.sleep(0.02)"
    )
    process = subprocess.Popen([sys.executable, "-c", code, str(lock_path), str(ready), str(release)])
    _wait_for_path(ready)
    return process, release


@pytest.fixture(autouse=True)
def _isolated_atlas_home(tmp_path, monkeypatch):
    """Point ATLAS_HOME (and the DB it is derived from) at a scratch dir."""
    home = tmp_path / "atlas-home"
    home.mkdir()
    monkeypatch.setenv("ATLAS_HOME", str(home))
    monkeypatch.setenv("ATLAS_DB", str(home / "atlas.db"))
    return home


def _write_source(root: pathlib.Path) -> pathlib.Path:
    """Create a component source tree that already carries regenerable junk."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name":"fake"}', encoding="utf-8")
    (root / "lock.json").write_text('{"lockfileVersion":1}', encoding="utf-8")
    (root / "app").mkdir(exist_ok=True)
    (root / "app" / "page.txt").write_text("v1", encoding="utf-8")
    # Must never be mirrored: provisioning regenerates these.
    (root / "node_modules").mkdir(exist_ok=True)
    (root / "node_modules" / "junk.txt").write_text("stale", encoding="utf-8")
    (root / ".next").mkdir(exist_ok=True)
    (root / ".next" / "BUILD_ID").write_text("stale", encoding="utf-8")
    return root


def _component(
    source: pathlib.Path,
    *,
    build: bool = True,
    name: str = "fake",
) -> provisioning.Component:
    return provisioning.Component(
        name=name,
        source_dir=source,
        dep_manifests=("package.json", "lock.json"),
        install=((sys.executable, "-c", _INSTALL_CODE),),
        build=((sys.executable, "-c", _BUILD_CODE),) if build else None,
        deps_marker="node_modules",
        build_marker=".next/BUILD_ID",
    )


def _release_bundle(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory shaped like a published platform bundle."""
    bundle = tmp_path / "install-root" / "versions" / "0.1.1"
    bundle.mkdir(parents=True)
    (bundle / "runtime.json").write_text(
        json.dumps(
            {
                "version": "0.1.1",
                "platform": "win32-x64",
                "entrypoint": "bin/atlas.js",
                "python": "3.13.11",
            }
        ),
        encoding="utf-8",
    )
    return bundle


# --- release detection ------------------------------------------------------


def test_release_root_detects_bundle(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    assert provisioning.release_root(source) == bundle


def test_release_root_none_for_plain_checkout(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    assert provisioning.release_root(source) is None


def test_release_root_ignores_unrelated_runtime_json(tmp_path):
    """A stray runtime.json without bundle keys must not fake a release."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "runtime.json").write_text('{"hello":"world"}', encoding="utf-8")
    source = _write_source(root / "services" / "fake")
    assert provisioning.release_root(source) is None


# --- workspace selection ----------------------------------------------------


def test_checkout_builds_in_place(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    workspace, mirrored = provisioning.resolve_workspace(_component(source))
    assert workspace == source
    assert mirrored is False


def test_release_builds_outside_the_immutable_bundle(tmp_path, _isolated_atlas_home):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    workspace, mirrored = provisioning.resolve_workspace(_component(source))
    assert mirrored is True
    assert workspace == _isolated_atlas_home / "sidecars" / "fake"
    # The critical assertion: the updater deletes versions/<version>/ wholesale.
    assert bundle not in workspace.parents and workspace != bundle


def test_state_never_written_into_the_source_tree(tmp_path, _isolated_atlas_home):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    provisioning.ensure_provisioned(_component(source))
    assert provisioning.state_path("fake").is_relative_to(_isolated_atlas_home)
    assert not (source / ".atlas-provision.json").exists()


def test_component_lock_lives_under_atlas_home(tmp_path, _isolated_atlas_home):
    path = provisioning.provisioning_lock_path("fake/component")
    assert path.parent == _isolated_atlas_home / "locks" / "provisioning"
    assert path.name.startswith("fake-component-")


# --- mirroring --------------------------------------------------------------


def test_mirror_copies_source_and_omits_regenerable_dirs(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)

    result = provisioning.ensure_provisioned(component)

    assert result.ok, result.message
    workspace = result.workspace
    assert (workspace / "package.json").is_file()
    assert (workspace / "app" / "page.txt").read_text(encoding="utf-8") == "v1"
    # The stale copies from the source tree must not have been carried over;
    # node_modules exists only because the install step created it.
    assert not (workspace / "node_modules" / "junk.txt").exists()
    assert (workspace / ".next" / "BUILD_ID").read_text(encoding="utf-8") == "built"


# --- fingerprint-driven work -----------------------------------------------


def test_first_run_installs_and_builds(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")

    result = provisioning.ensure_provisioned(_component(source))

    assert result.ok, result.message
    assert result.installed is True
    assert result.built is True


def test_second_run_does_no_work(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    assert provisioning.ensure_provisioned(component).ok

    plan = provisioning.plan_provisioning(component)
    again = provisioning.ensure_provisioned(component)

    assert plan.is_expensive is False
    assert again.ok
    assert (again.installed, again.built) == (False, False)


def test_source_change_rebuilds_without_reinstalling(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    assert provisioning.ensure_provisioned(component).ok

    (source / "app" / "page.txt").write_text("v2", encoding="utf-8")
    plan = provisioning.plan_provisioning(component)
    result = provisioning.ensure_provisioned(component)

    assert (plan.need_install, plan.need_build) == (False, True)
    assert result.ok, result.message
    assert (result.installed, result.built) == (False, True)
    assert (result.workspace / "app" / "page.txt").read_text(encoding="utf-8") == "v2"


def test_dependency_manifest_change_reinstalls(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    assert provisioning.ensure_provisioned(component).ok

    (source / "lock.json").write_text('{"lockfileVersion":2}', encoding="utf-8")
    result = provisioning.ensure_provisioned(component)

    assert result.ok, result.message
    assert result.installed is True


def test_existing_artifacts_are_adopted_not_rebuilt(tmp_path):
    """A checkout that already ran its own install must not be reinstalled.

    In the real repo that would discard ~885 MB of working node_modules.
    """
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    component = _component(source)

    plan = provisioning.plan_provisioning(component)
    result = provisioning.ensure_provisioned(component)

    assert plan.is_expensive is False
    assert result.ok, result.message
    assert (result.installed, result.built) == (False, False)
    assert "adopted" in result.message
    # Adoption records a baseline, so later drift is still detected.
    assert provisioning.state_path("fake").is_file()
    (source / "app" / "page.txt").write_text("v2", encoding="utf-8")
    assert provisioning.plan_provisioning(component).need_build is True


def test_force_reprovisions_even_when_current(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    assert provisioning.ensure_provisioned(component).ok

    result = provisioning.ensure_provisioned(component, force=True)

    assert result.ok, result.message
    assert (result.installed, result.built) == (True, True)


# --- process exclusion ------------------------------------------------------


def test_two_processes_install_the_same_component_only_once(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "process-race")
    counter = tmp_path / "install-count.txt"
    code = (
        "import json,pathlib,sys,time;"
        "from atlas_runtime import provisioning;"
        "source,counter,result=map(pathlib.Path,sys.argv[1:]);"
        "install=\"import pathlib,time;time.sleep(0.35);"
        "p=pathlib.Path(__import__('os').environ['ATLAS_TEST_COUNTER']);"
        "h=p.open('a',encoding='utf-8');h.write('install\\\\n');h.close();"
        "pathlib.Path('node_modules').mkdir(exist_ok=True)\";"
        "component=provisioning.Component(name='process-race',source_dir=source,"
        "dep_manifests=('package.json','lock.json'),"
        "install=((sys.executable,'-c',install),),build=None,deps_marker='node_modules');"
        "out=provisioning.ensure_provisioned(component,timeout=10.0,lock_timeout=10.0);"
        "result.write_text(json.dumps([out.ok,out.installed,out.message]),encoding='utf-8')"
    )
    result_paths = [tmp_path / f"result-{index}.json" for index in range(2)]
    child_env = {**os.environ, "ATLAS_TEST_COUNTER": str(counter)}
    contenders = [
        subprocess.Popen(
            [sys.executable, "-c", code, str(source), str(counter), str(result)],
            env=child_env,
        )
        for result in result_paths
    ]
    exit_codes = [contender.wait(timeout=15.0) for contender in contenders]

    assert exit_codes == [0, 0]
    results = [json.loads(result.read_text(encoding="utf-8")) for result in result_paths]
    assert all(result[0] for result in results), results
    assert sorted(result[1] for result in results) == [False, True]
    assert counter.read_text(encoding="utf-8").splitlines() == ["install"]


def test_lock_timeout_returns_bounded_failure(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    lock_path = provisioning.provisioning_lock_path("fake")
    holder, release = _start_lock_holder(lock_path, tmp_path)

    started = time.monotonic()
    result = provisioning.ensure_provisioned(
        _component(source),
        lock_timeout=0.05,
    )
    elapsed = time.monotonic() - started
    release.write_text("release", encoding="utf-8")
    holder.wait(timeout=5.0)

    assert holder.returncode == 0
    assert result.ok is False
    assert "lock unavailable" in result.message
    assert elapsed < 1.0


def test_different_component_is_not_blocked_by_held_lock(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    holder, release = _start_lock_holder(
        provisioning.provisioning_lock_path("fake"), tmp_path
    )

    result = provisioning.ensure_provisioned(
        _component(source, name="other"),
        lock_timeout=0.05,
    )
    release.write_text("release", encoding="utf-8")
    holder.wait(timeout=5.0)

    assert holder.returncode == 0
    assert result.ok, result.message


def test_process_crash_releases_component_lock(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    lock_path = provisioning.provisioning_lock_path("fake")
    holder, _release = _start_lock_holder(lock_path, tmp_path)
    holder.terminate()
    holder.wait(timeout=5.0)
    assert holder.returncode is not None

    result = provisioning.ensure_provisioned(
        _component(source),
        lock_timeout=1.0,
    )

    assert result.ok, result.message


def test_next_provision_restores_unique_backup_after_pre_activation_crash(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    first = provisioning.ensure_provisioned(component)
    assert first.ok, first.message
    workspace = first.workspace
    backup = workspace.parent / ".fake.backup-crashed"
    staging = workspace.parent / ".fake.staging-crashed"
    staging.mkdir()
    (staging / "incomplete.txt").write_text("candidate", encoding="utf-8")
    os.replace(workspace, backup)

    recovered = provisioning.ensure_provisioned(component)

    assert recovered.ok, recovered.message
    assert workspace.is_dir()
    assert (workspace / "app" / "page.txt").read_text(encoding="utf-8") == "v1"
    assert not backup.exists()


def test_next_provision_cleans_stale_backup_after_post_activation_crash(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    first = provisioning.ensure_provisioned(component)
    assert first.ok, first.message
    workspace = first.workspace
    backup = workspace.parent / ".fake.backup-crashed"
    shutil.copytree(workspace, backup)
    old = time.time() - provisioning.STALE_BACKUP_SECONDS - 1
    os.utime(backup, (old, old))

    recovered = provisioning.ensure_provisioned(component)

    assert recovered.ok, recovered.message
    assert workspace.is_dir()
    assert not backup.exists()


def test_state_commit_uses_a_unique_temporary_file(tmp_path, monkeypatch):
    replaced_from: list[pathlib.Path] = []
    real_replace = os.replace

    def record_replace(source, destination):
        replaced_from.append(pathlib.Path(source))
        real_replace(source, destination)

    monkeypatch.setattr(provisioning.os, "replace", record_replace)
    provisioning._write_state("fake", {"version": 1})
    provisioning._write_state("fake", {"version": 2})

    assert len(replaced_from) == 2
    assert replaced_from[0] != replaced_from[1]
    assert all(path.name.endswith(".tmp") for path in replaced_from)
    assert not any(path.exists() for path in replaced_from)
    assert provisioning._read_state("fake") == {"version": 2}


def test_state_write_failure_is_reported_and_releases_lock(tmp_path, monkeypatch):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")

    def fail_state_write(_name, _state):
        raise OSError("disk full")

    monkeypatch.setattr(provisioning, "_write_state", fail_state_write)
    result = provisioning.ensure_provisioned(_component(source))

    assert result.ok is False
    assert "could not record" in result.message
    assert "disk full" in result.message
    with file_lock(provisioning.provisioning_lock_path("fake"), timeout_seconds=0.1):
        pass


# --- failure handling -------------------------------------------------------


def test_failed_rebuild_preserves_active_workspace_and_cleans_staging(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = _component(source)
    first = provisioning.ensure_provisioned(component)
    assert first.ok, first.message
    workspace = first.workspace

    (source / "app" / "page.txt").write_text("v2", encoding="utf-8")
    failing = provisioning.Component(
        name="fake",
        source_dir=source,
        dep_manifests=("package.json", "lock.json"),
        install=((sys.executable, "-c", _INSTALL_CODE),),
        build=((sys.executable, "-c", _FAIL_CODE),),
        deps_marker="node_modules",
        build_marker=".next/BUILD_ID",
    )
    result = provisioning.ensure_provisioned(failing)

    assert result.ok is False
    assert (workspace / "app" / "page.txt").read_text(encoding="utf-8") == "v1"
    assert not list(workspace.parent.glob(".fake.staging-*"))


def test_old_staging_workspace_is_cleaned_conservatively(tmp_path):
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    workspace, _mirrored = provisioning.resolve_workspace(_component(source))
    workspace.parent.mkdir(parents=True)
    stale = workspace.parent / ".fake.staging-abandoned"
    stale.mkdir()
    old = time.time() - provisioning.STALE_STAGING_SECONDS - 1
    os.utime(stale, (old, old))

    result = provisioning.ensure_provisioned(_component(source))

    assert result.ok, result.message
    assert not stale.exists()


def test_failure_is_reported_and_leaves_no_baseline(tmp_path):
    """A failed build must not be recorded as provisioned."""
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = provisioning.Component(
        name="fake",
        source_dir=source,
        dep_manifests=("package.json",),
        install=((sys.executable, "-c", _INSTALL_CODE),),
        build=((sys.executable, "-c", _FAIL_CODE),),
        deps_marker="node_modules",
        build_marker=".next/BUILD_ID",
    )

    result = provisioning.ensure_provisioned(component)

    assert result.ok is False
    assert "exit 3" in result.message
    assert not provisioning.state_path("fake").exists()
    # The next attempt must therefore retry rather than trust the workspace.
    assert provisioning.plan_provisioning(component).need_build is True


def test_missing_source_is_reported_cleanly(tmp_path):
    component = _component(tmp_path / "nope" / "services" / "fake")
    result = provisioning.ensure_provisioned(component)
    assert result.ok is False
    assert "source not found" in result.message


def test_missing_tool_is_reported_as_actionable(tmp_path):
    source = _write_source(tmp_path / "checkout" / "services" / "fake")
    component = provisioning.Component(
        name="fake",
        source_dir=source,
        dep_manifests=("package.json",),
        install=(("definitely-not-a-real-binary-xyz",),),
        build=None,
        deps_marker="does-not-exist",
    )
    result = provisioning.ensure_provisioned(component)
    assert result.ok is False
    assert "not found on PATH" in result.message


# --- the other source-shipped sidecars ----------------------------------------


def test_discord_bot_release_component_uses_embedded_pip_target(tmp_path):
    """Embedded release Python has pip but no venv; dependencies stay sidecar-local."""
    source = tmp_path / "discord-bot"
    source.mkdir()
    component = provisioning.discord_bot_component(source)
    assert component.name == "discord-bot"
    assert component.dep_manifests == ("requirements.txt",)
    assert len(component.install) == 1
    assert component.install[0][:3] == (sys.executable, "-m", "pip")
    assert component.install[0][-4:] == (
        "--target",
        ".deps",
        "-r",
        "requirements.txt",
    )
    assert component.deps_marker == ".deps/discord/__init__.py"
    assert component.build is None


def test_discord_bot_checkout_reuses_existing_venv(tmp_path):
    source = tmp_path / "discord-bot"
    marker = source / provisioning._venv_python()
    marker.parent.mkdir(parents=True)
    marker.write_text("", encoding="utf-8")
    component = provisioning.discord_bot_component(source)
    assert component.deps_marker == provisioning._venv_python()
    assert component.install == ((sys.executable, "-m", "pip", "--version"),)


def test_atlas_terminal_component_installs_without_a_build_step():
    component = provisioning.atlas_terminal_component()
    assert component.name == "atlas-terminal"
    assert component.dep_manifests == ("package.json", "bun.lock")
    assert component.install == (("bun", "install"),)
    assert component.deps_marker == "node_modules"
    # `bun run dev` executes from source; compiling is packaging, not a
    # prerequisite for launching.
    assert component.build is None


def test_both_sidecars_point_at_their_shipped_source_trees():
    for component in (
        provisioning.discord_bot_component(),
        provisioning.atlas_terminal_component(),
    ):
        assert component.source_dir.name == component.name.replace("-bot", "-bot")
        assert component.source_dir.parent.name == "services"


def test_a_workspace_relative_executable_resolves_against_the_workspace(tmp_path):
    """The venv interpreter exists only inside the workspace being provisioned."""
    exe = tmp_path / "tool.py"
    exe.write_text("", encoding="utf-8")
    argv = provisioning._argv(("tool.py/../tool.py", "--flag"), tmp_path)
    assert argv[0].endswith("tool.py")
    assert argv[1] == "--flag"


def test_a_missing_workspace_relative_executable_is_a_named_failure(tmp_path):
    with pytest.raises(provisioning.ProvisionError, match="not found at"):
        provisioning._argv((".venv/bin/python", "-V"), tmp_path)
