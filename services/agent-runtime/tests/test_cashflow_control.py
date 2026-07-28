"""Tests for cashflow_control — the vendored-module process primitive.

Only the deterministic pieces (no real Next.js process is started).
"""
from __future__ import annotations

from atlas_runtime import cashflow_control as cc


def test_invalid_backend_rejected() -> None:
    ok, msg = cc.start(backend="bogus")
    assert ok is False
    assert "unknown backend" in msg


def test_cashflow_dir_is_vendored_module() -> None:
    assert cc.CASHFLOW_DIR.name == "cashflow"
    assert cc.CASHFLOW_DIR.exists(), f"expected vendored cashflow at {cc.CASHFLOW_DIR}"


def test_current_backend_defaults_local(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    assert cc.current_backend() == "local"


def test_status_shape(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    st = cc.status()
    # `phase` and `runtime_dir` were added when cashflow moved to
    # ship-source/build-locally: a caller has to distinguish "stopped" from
    # "still installing and building", and needs to know where it is built.
    assert {"running", "backend", "url", "phase", "runtime_dir"} <= set(st)
    assert st["backend"] == "local"
    assert isinstance(st["running"], bool)
    assert st["phase"] in {cc.PHASE_IDLE, cc.PHASE_PROVISIONING, cc.PHASE_RUNNING}


def test_state_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    cc._write_state({"backend": "supabase", "pid": 1234})
    assert cc.current_backend() == "supabase"
    assert cc._read_state()["pid"] == 1234


def test_start_never_provisions_inline(tmp_path, monkeypatch) -> None:
    """A first-run install/build must be detached, not awaited.

    `start()` is reached via the gateway's `dispatch_atlas(["cashflow","start"])`,
    which awaits the reply — so a multi-minute `npm ci` + `next build` on that
    path would read as a failed button press.
    """
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    monkeypatch.setattr(cc, "health_ok", lambda timeout=1.0: False)
    monkeypatch.setattr(cc, "_npm_available", lambda: True)

    expensive = cc.provisioning.ProvisionPlan(
        workspace=tmp_path / "ws",
        mirrored=True,
        source_fingerprint="a",
        deps_fingerprint="b",
        need_mirror=True,
        need_install=True,
        need_build=True,
    )
    monkeypatch.setattr(
        cc.provisioning, "plan_provisioning", lambda component, force=False: expensive
    )

    def _fail_if_called(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("start() must not provision synchronously")

    monkeypatch.setattr(cc.provisioning, "ensure_provisioned", _fail_if_called)
    monkeypatch.setattr(
        cc, "_spawn_bootstrap", lambda backend: (True, f"bootstrapping {backend}")
    )

    ok, message = cc.start(backend="local")

    assert ok is True
    assert "bootstrapping local" in message


def test_start_serves_prebuilt_bundle_without_bootstrap(tmp_path, monkeypatch) -> None:
    """When nothing needs building, the server starts directly."""
    monkeypatch.setattr(cc, "STATE_FILE", tmp_path / "cashflow.json")
    monkeypatch.setattr(cc, "health_ok", lambda timeout=1.0: False)
    monkeypatch.setattr(cc, "_npm_available", lambda: True)

    cheap = cc.provisioning.ProvisionPlan(
        workspace=tmp_path / "ws",
        mirrored=False,
        source_fingerprint="a",
        deps_fingerprint="b",
        need_mirror=False,
        need_install=False,
        need_build=False,
    )
    monkeypatch.setattr(
        cc.provisioning, "plan_provisioning", lambda component, force=False: cheap
    )
    monkeypatch.setattr(
        cc.provisioning,
        "ensure_provisioned",
        lambda component, **kwargs: cc.provisioning.ProvisionResult(
            True, "already provisioned", tmp_path / "ws"
        ),
    )
    monkeypatch.setattr(
        cc, "_spawn_bootstrap", lambda backend: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(cc, "_spawn_server", lambda backend, workdir: 4321)

    ok, message = cc.start(backend="local")

    assert ok is True
    assert "4321" in message
    assert cc._read_state()["pid"] == 4321
