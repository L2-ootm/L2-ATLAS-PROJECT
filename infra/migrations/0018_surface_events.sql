-- 0018_surface_events.sql — persisted per-session SurfaceEvent projection cache (TUI-04).
--
-- Mirrors atlas_core.schemas.surface_session.SurfaceEvent field-for-field. This table is
-- the durable, pollable read-side that atlas_runtime.tui.transcript.poll_and_render reads
-- from directly: each row is one already-normalized, already-redacted SurfaceEvent (D-013).
-- `seq` is monotonic PER session_id (assigned by the writer, mirroring
-- surface_events.normalize_surface_events' start_seq convention) so
-- `replay_since(last_seq)` gap-detection is a plain seq > last_seq filter. No FK on
-- session_id (soft link, mirrors the surface_sessions/runs precedent) so historical/
-- detached sessions are never blocked from being read.

CREATE TABLE IF NOT EXISTS surface_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    kind            TEXT NOT NULL,
    run_id          TEXT,
    occurred_at     TEXT NOT NULL,
    payload_json    TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_surface_events_session_seq
    ON surface_events(session_id, seq);
