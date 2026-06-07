"""Stub tests for atlas_runtime.audit_service — Wave 1 implements the module.

All tests are skipped at collection time until atlas_runtime.audit_service exists.
pytestmark xfail is applied as defense-in-depth for any test that slips through.
"""

import pytest

try:
    from atlas_runtime.audit_service import emit, get_events_for_run, export_jsonl  # noqa: F401
except ImportError:
    pytest.skip("atlas_runtime.audit_service not implemented", allow_module_level=True)

pytestmark = pytest.mark.xfail(reason="Wave 1 not implemented", strict=False)


def test_emit_tool_call(db, run_id, lock):
    pass


def test_emit_llm_call(db, run_id, lock):
    pass


def test_emit_artifact(db, run_id, lock):
    pass


def test_emit_redacts_secret_in_data(db, run_id, lock):
    pass


def test_emit_invalid_event_type_raises_no_orphan(db, run_id, lock):
    pass


def test_get_events_for_run_ordered(db, run_id, lock):
    pass


def test_export_jsonl_valid(db, run_id, lock):
    pass
