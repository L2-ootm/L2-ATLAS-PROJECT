# Deferred / Out-of-Scope Items — Phase 10.5

## Discovered during Plan 10.5-02 (schema/config foundation)

### test_surface_events.py::test_kind_map_covers_every_audit_event_type — FAILING (pre-existing, out of scope)

- **Status:** Pre-existing failure. Confirmed failing on parent commit `561c717`
  (Wave 0), before any 10.5-02 change.
- **Cause:** `surface_events._KIND_MAP` does not cover five `AuditEvent.event_type`
  Literal values introduced by Phase 10.4 (control plane / model control):
  `auth_change`, `config_change`, `model_call_start`, `model_call_end`,
  `provider_fallback`.
- **Why deferred:** Unrelated to the permission-broker schema/config work. This plan
  touched neither the `AuditEvent.event_type` Literal nor `surface_events._KIND_MAP`.
  Fixing it is a Phase 10.4 follow-up (extend `_KIND_MAP` with kinds for the five
  control-plane event types), not a permission-broker concern.
- **Remediation owner:** A later 10.5 wave that touches surface_events, or a 10.4
  maintenance pass. Add `_KIND_MAP` entries for the five event types above.
