//! Evidence Plane API contracts for Phase 10.8 plan 08.

use atlas_gateway::db::{self, AuditEventFilters, ChangeSetScope, ContentRange, EvidenceCursor};
use std::path::{Path, PathBuf};

const MIGRATION_0001: &str = include_str!("../../../../../infra/migrations/0001_core.sql");
const MIGRATION_0006: &str = include_str!("../../../../../infra/migrations/0006_agent_runtime.sql");
const MIGRATION_0016: &str =
    include_str!("../../../../../infra/migrations/0016_surface_sessions.sql");
const MIGRATION_0019: &str =
    include_str!("../../../../../infra/migrations/0019_performance_indexes.sql");
const MIGRATION_0022: &str = include_str!("../../../../../infra/migrations/0022_actors.sql");
const MIGRATION_0033: &str =
    include_str!("../../../../../infra/migrations/0033_evidence_plane.sql");

fn seeded_evidence_db(dir: &tempfile::TempDir) -> PathBuf {
    let path = dir.path().join("atlas.db");
    let conn = rusqlite::Connection::open(&path).unwrap();
    for migration in [
        MIGRATION_0001,
        MIGRATION_0006,
        MIGRATION_0016,
        MIGRATION_0019,
        MIGRATION_0022,
        MIGRATION_0033,
    ] {
        conn.execute_batch(migration).unwrap();
    }
    conn.execute_batch(
        r#"
        INSERT INTO missions
            (id, title, intent, status, project, created_at, updated_at)
        VALUES
            ('mission-1', 'One', '', 'completed', 'atlas',
             '2026-07-29T10:00:00Z', '2026-07-29T10:00:00Z');
        INSERT INTO runs
            (id, mission_id, session_id, status, started_at, finished_at, summary)
        VALUES
            ('run-1', 'mission-1', 'surface-1', 'succeeded',
             '2026-07-29T10:00:00Z', '2026-07-29T10:01:00Z', ''),
            ('run-2', 'mission-1', 'surface-1', 'succeeded',
             '2026-07-29T10:02:00Z', '2026-07-29T10:03:00Z', '');
        INSERT INTO surface_sessions
            (id, surface_kind, surface_session_id, workspace_kind, workspace_root,
             agent, model_provider, model_id, permission_mode, prompt_version,
             tool_catalog_version, context_policy_version, state, owner_token,
             heartbeat_at, created_at, updated_at)
        VALUES
            ('surface-1', 'webui', 'browser-1', 'project', 'C:/atlas',
             'native', 'mock', 'mock', 'ask', '1', '1', '1', 'active', 'owner-1',
             '2026-07-29T10:00:00Z', '2026-07-29T10:00:00Z',
             '2026-07-29T10:00:00Z');
        INSERT INTO audit_events
            (id, run_id, session_id, event_type, tool_name, timestamp, data)
        VALUES
            ('event-1', 'run-1', 'surface-1', 'tool_call', 'write_file',
             '2026-07-29T10:00:01Z', '{"evidence_id":"change-1"}'),
            ('event-2', 'run-2', 'surface-1', 'artifact', 'write_file',
             '2026-07-29T10:02:01Z', '{"evidence_id":"change-2"}');
        INSERT INTO evidence_blobs
            (id, sha256, media_type, size_bytes, chunk_count, availability,
             redaction_count, created_at)
        VALUES
            ('blob-patch', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
             'text/x-diff', 12, 1, 'available', 0, '2026-07-29T10:00:01Z'),
            ('blob-result', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
             'text/plain', 12, 1, 'available', 0, '2026-07-29T10:00:02Z');
        INSERT INTO evidence_blob_chunks (blob_id, chunk_index, content)
        VALUES
            ('blob-patch', 0, X'4061202D6F6C640A2B6E6577'),
            ('blob-result', 0, X'303132333435363738396162');
        INSERT INTO evidence_change_sets
            (id, run_id, session_id, actor_id, coverage, status, created_at)
        VALUES
            ('change-1', 'run-1', 'surface-1', 'actor-1', 'complete', 'captured',
             '2026-07-29T10:00:01Z'),
            ('change-2', 'run-2', 'surface-1', NULL, 'partial', 'partial',
             '2026-07-29T10:02:01Z');
        INSERT INTO evidence_file_changes
            (id, change_set_id, path, operation, availability, additions, deletions,
             patch_blob_id)
        VALUES
            ('file-1', 'change-1', 'src/a.rs', 'edit', 'available', 1, 1,
             'blob-patch'),
            ('file-2', 'change-1', 'src/b.rs', 'create', 'redacted', 1, 0, NULL);
        INSERT INTO evidence_hunks
            (id, file_change_id, hunk_index, old_start, old_lines, new_start,
             new_lines, patch_start_byte, patch_bytes, redacted)
        VALUES
            ('hunk-1', 'file-1', 0, 1, 1, 1, 1, 0, 12, 0);
        INSERT INTO evidence_full_results
            (id, owner_kind, owner_id, run_id, blob_id, availability, preview,
             preview_bytes, full_bytes, sha256, media_type, redaction_count,
             created_at)
        VALUES
            ('result-1', 'run', 'run-1', 'run-1', 'blob-result', 'available',
             '0123', 4, 12,
             'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
             'text/plain', 0, '2026-07-29T10:00:02Z');
        INSERT INTO actors
            (id, parent_run_id, session_id, idempotency_key, role, goal, mode,
             status, depth, created_at, updated_at)
        VALUES
            ('actor-1', 'run-1', 'surface-1', 'actor-key-1', 'worker', 'inspect',
             'joined', 'completed', 1, '2026-07-29T10:00:00Z',
             '2026-07-29T10:01:00Z');
        "#,
    )
    .unwrap();
    path
}

fn query_plan(path: &Path, sql: &str, params: &[&dyn rusqlite::ToSql]) -> String {
    let conn = rusqlite::Connection::open(path).unwrap();
    let mut statement = conn.prepare(&format!("EXPLAIN QUERY PLAN {sql}")).unwrap();
    statement
        .query_map(params, |row| row.get::<_, String>(3))
        .unwrap()
        .collect::<rusqlite::Result<Vec<_>>>()
        .unwrap()
        .join(" ")
}

#[test]
fn evidence_db_cursor_pages_are_stable_bounded_and_indexed() {
    let dir = tempfile::tempdir().unwrap();
    let path = seeded_evidence_db(&dir);

    let (events, next) = db::list_audit_events(
        &path,
        &AuditEventFilters {
            session_id: Some("surface-1".into()),
            tool_name: Some("write_file".into()),
            ..Default::default()
        },
        None,
        1,
    )
    .unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].id, "event-1");
    let (second, _) =
        db::list_audit_events(&path, &AuditEventFilters::default(), next.as_deref(), 5000).unwrap();
    assert_eq!(
        second
            .iter()
            .map(|event| event.id.as_str())
            .collect::<Vec<_>>(),
        ["event-2"]
    );

    let (sets, set_cursor) =
        db::list_change_sets(&path, &ChangeSetScope::Run("run-1".into()), None, 5000).unwrap();
    assert_eq!(sets.len(), 1);
    assert_eq!(sets[0].id, "change-1");
    assert!(EvidenceCursor::decode(set_cursor.as_deref().unwrap()).is_ok());

    let (files, _) = db::list_file_changes(&path, "change-1", None, 5000).unwrap();
    assert_eq!(files.len(), 2);
    assert!(files[0].get("patch").is_none());
    let (hunks, _) = db::list_hunks(&path, "file-1", None, 5000).unwrap();
    assert_eq!(hunks.len(), 1);
    assert!(hunks[0].get("patch").is_none());

    let assertions = [
        (
            "idx_evidence_change_sets_run_cursor",
            "SELECT id FROM evidence_change_sets WHERE run_id=?1 \
             ORDER BY created_at,id LIMIT ?2",
            vec![
                &"run-1" as &dyn rusqlite::ToSql,
                &10_i64 as &dyn rusqlite::ToSql,
            ],
        ),
        (
            "idx_evidence_file_changes_set_cursor",
            "SELECT id FROM evidence_file_changes WHERE change_set_id=?1 \
             ORDER BY id LIMIT ?2",
            vec![
                &"change-1" as &dyn rusqlite::ToSql,
                &10_i64 as &dyn rusqlite::ToSql,
            ],
        ),
        (
            "idx_evidence_hunks_file_cursor",
            "SELECT id FROM evidence_hunks WHERE file_change_id=?1 \
             ORDER BY hunk_index LIMIT ?2",
            vec![
                &"file-1" as &dyn rusqlite::ToSql,
                &10_i64 as &dyn rusqlite::ToSql,
            ],
        ),
    ];
    for (index, sql, params) in assertions {
        let plan = query_plan(&path, sql, &params);
        assert!(plan.contains(index), "{index} missing from {plan}");
    }
}

#[test]
fn evidence_db_content_ranges_and_owner_scopes_are_explicit() {
    let dir = tempfile::tempdir().unwrap();
    let path = seeded_evidence_db(&dir);

    let patch = db::get_file_patch(
        &path,
        "surface-1",
        "file-1",
        ContentRange::new(3, 5).unwrap(),
    )
    .unwrap()
    .unwrap();
    assert_eq!(patch.bytes, b"-old\n");
    assert_eq!(patch.total_bytes, 12);
    assert_eq!(patch.availability, "available");

    let result = db::get_result_range(
        &path,
        "surface-1",
        "result-1",
        ContentRange::new(4, 4).unwrap(),
    )
    .unwrap()
    .unwrap();
    assert_eq!(result.bytes, b"4567");
    assert_eq!(
        result.sha256.as_deref(),
        Some("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    );

    assert!(db::get_result_range(
        &path,
        "other-surface",
        "result-1",
        ContentRange::new(0, 4).unwrap(),
    )
    .unwrap()
    .is_none());
    assert!(ContentRange::new(0, 65 * 1024).is_err());

    let actors = db::list_actor_history(&path, "surface-1", None, 5000).unwrap();
    assert_eq!(actors.0.len(), 1);
    assert_eq!(actors.0[0]["id"], "actor-1");
}
