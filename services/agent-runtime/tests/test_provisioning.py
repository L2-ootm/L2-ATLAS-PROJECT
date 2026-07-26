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
import pathlib
import sys

import pytest

from atlas_runtime import provisioning


# `next build` writes .next/BUILD_ID; the fake build mirrors that shape so the
# nested-marker logic is covered too.
_INSTALL_CODE = "import pathlib; pathlib.Path('node_modules').mkdir(exist_ok=True)"
_BUILD_CODE = (
    "import pathlib; p = pathlib.Path('.next'); p.mkdir(exist_ok=True); "
    "(p / 'BUILD_ID').write_text('built')"
)
_FAIL_CODE = "raise SystemExit(3)"


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


def _component(source: pathlib.Path, *, build: bool = True) -> provisioning.Component:
    return provisioning.Component(
        name="fake",
        source_dir=source,
        dep_manifests=("package.json", "lock.json"),
        install=(sys.executable, "-c", _INSTALL_CODE),
        build=(sys.executable, "-c", _BUILD_CODE) if build else None,
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


# --- failure handling -------------------------------------------------------


def test_failure_is_reported_and_leaves_no_baseline(tmp_path):
    """A failed build must not be recorded as provisioned."""
    bundle = _release_bundle(tmp_path)
    source = _write_source(bundle / "services" / "fake")
    component = provisioning.Component(
        name="fake",
        source_dir=source,
        dep_manifests=("package.json",),
        install=(sys.executable, "-c", _INSTALL_CODE),
        build=(sys.executable, "-c", _FAIL_CODE),
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
        install=("definitely-not-a-real-binary-xyz",),
        build=None,
        deps_marker="does-not-exist",
    )
    result = provisioning.ensure_provisioned(component)
    assert result.ok is False
    assert "not found on PATH" in result.message
