"""Foundation boot smoke (D-021 section 9).

Proves, without any LLM call or network access:
1. The vendored foundation (foundation/atlas-hermes) is importable.
2. The bundled plugins dir resolves into the vendored tree (not some other
   Hermes install).
3. Plugin discovery loads the bundled atlas_audit plugin.
4. All 6 audit hooks have at least one registered callback.

Uses a throwaway Hermes home so the operator's real ~/.hermes is never
touched. Exit 0 on success, 1 on failure.

Run: .venv\\Scripts\\python scripts\\foundation_boot_smoke.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HOOKS = (
    "on_session_start",
    "post_api_request",
    "post_llm_call",
    "post_tool_call",
    "subagent_stop",
    "post_approval_response",
)


def main() -> int:
    failures: list[str] = []

    try:
        import hermes_constants
        from hermes_cli import plugins
    except ImportError as exc:
        print(f"FAIL: foundation not importable: {exc}")
        print("Install with: python -m pip install -e foundation/atlas-hermes")
        return 1

    # Isolated Hermes home with atlas_audit enabled (standalone plugins are
    # opt-in via plugins.enabled).
    home = Path(tempfile.mkdtemp(prefix="atlas_foundation_smoke_"))
    (home / "config.yaml").write_text(
        "plugins:\n  enabled:\n    - atlas_audit\n", encoding="utf-8"
    )
    token = hermes_constants.set_hermes_home_override(home)
    try:
        bundled = Path(plugins.get_bundled_plugins_dir()).resolve()
        expected = (ROOT / "foundation" / "atlas-hermes" / "plugins").resolve()
        if bundled != expected:
            failures.append(
                f"bundled plugins dir is {bundled}, expected {expected} — "
                "is the foundation installed editable from the vendored tree?"
            )

        plugins.discover_plugins(force=True)
        mgr = plugins.get_plugin_manager()

        if "atlas_audit" not in mgr._plugins:
            failures.append(
                "atlas_audit not in loaded plugins: "
                f"{sorted(mgr._plugins.keys())}"
            )
        else:
            for hook in EXPECTED_HOOKS:
                if not mgr._hooks.get(hook):
                    failures.append(f"hook '{hook}' has no registered callback")
    finally:
        hermes_constants.reset_hermes_home_override(token)

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    print("OK: foundation boots; atlas_audit bundled plugin registered "
          f"{len(EXPECTED_HOOKS)} hooks from {bundled}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
