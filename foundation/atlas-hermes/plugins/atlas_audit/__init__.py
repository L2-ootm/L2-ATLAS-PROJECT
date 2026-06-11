"""ATLAS audit bus — bundled foundation plugin (DIV-F-002, D-021 §9).

Thin shim: the canonical implementation lives in the ``atlas_audit`` package
under ``services/agent-runtime/``. This shim makes the audit bus a bundled
plugin of the evolved ATLAS/Hermes foundation so it loads on every boot
without per-machine project-plugin opt-in.

Requires ``atlas-runtime`` installed in the same environment as the
foundation (see foundation/README.md).
"""
from atlas_audit import register  # noqa: F401
