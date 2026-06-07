"""Stub tests for atlas_audit plugin hooks — Wave 2 implements the callbacks.

All tests are skipped at collection time until atlas_audit hook functions exist.
pytestmark xfail is applied as defense-in-depth for any test that slips through.
"""

import pytest

try:
    from atlas_audit import on_post_tool_call, on_post_api_request, on_subagent_stop  # noqa: F401
except ImportError:
    pytest.skip("atlas_audit hook functions not implemented", allow_module_level=True)

pytestmark = pytest.mark.xfail(reason="Wave 2 not implemented", strict=False)


def test_post_tool_call_emits_audit_and_tool_call_rows(db, run_id):
    pass


def test_post_api_request_emits_llm_call_row(db, run_id):
    pass


def test_subagent_stop_emits_subagent_run_row(db, run_id):
    pass


def test_hook_callback_does_not_reraise_on_error(db, run_id):
    pass
