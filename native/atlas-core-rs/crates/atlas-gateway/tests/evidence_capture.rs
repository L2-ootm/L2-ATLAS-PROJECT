use atlas_gateway::evidence::{
    persist_change_set, CaptureFileRequest, ChangeSetRequest, EvidenceProvenance, PROTOCOL_VERSION,
};
use rusqlite::Connection;

fn evidence_db() -> (tempfile::TempDir, String) {
    let dir = tempfile::tempdir().expect("tempdir");
    let path = dir.path().join("atlas.db");
    let conn = Connection::open(&path).expect("open");
    conn.execute_batch(include_str!(
        "../../../../../infra/migrations/0001_core.sql"
    ))
    .expect("core migration");
    conn.execute_batch(include_str!(
        "../../../../../infra/migrations/0033_evidence_plane.sql"
    ))
    .expect("evidence migration");
    conn.execute(
        "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at)
         VALUES ('mission-1','test','','running','','now','now')",
        [],
    )
    .expect("mission");
    conn.execute(
        "INSERT INTO runs(id,mission_id,status,started_at,summary)
         VALUES ('run-1','mission-1','running','now','')",
        [],
    )
    .expect("run");
    (dir, path.to_string_lossy().into_owned())
}

fn request(db_path: String) -> ChangeSetRequest {
    ChangeSetRequest {
        protocol: PROTOCOL_VERSION.to_string(),
        db_path,
        kind: "change_set".to_string(),
        provenance: EvidenceProvenance {
            run_id: "run-1".to_string(),
            session_id: Some("session-1".to_string()),
            team_run_id: None,
            turn_id: None,
            actor_id: Some("actor-1".to_string()),
            parent_actor_id: None,
            tool_call_id: Some("call-1".to_string()),
        },
        coverage: "complete".to_string(),
        status: "captured".to_string(),
        files: vec![CaptureFileRequest {
            path: "src/example.txt".to_string(),
            old_path: None,
            operation: "edit".to_string(),
            before: "token=before-secret\nold\n".to_string(),
            after: "token=after-secret\nnew\n".to_string(),
            generated: false,
            mode_before: None,
            mode_after: None,
        }],
    }
}

#[test]
fn capture_persists_redacted_hashes_diff_hunks_and_one_receipt() {
    let (_dir, db_path) = evidence_db();
    let receipt = persist_change_set(&request(db_path.clone())).expect("persist");
    assert_eq!(receipt.file_count, 1);
    assert_eq!(receipt.additions, 1);
    assert_eq!(receipt.deletions, 1);
    assert_eq!(receipt.redaction_count, 2);

    let conn = Connection::open(db_path).expect("open");
    assert_eq!(
        conn.query_row("SELECT COUNT(*) FROM evidence_change_sets", [], |row| row
            .get::<_, i64>(
            0
        ))
        .unwrap(),
        1
    );
    assert_eq!(
        conn.query_row("SELECT COUNT(*) FROM evidence_file_changes", [], |row| row
            .get::<_, i64>(
            0
        ))
        .unwrap(),
        1
    );
    assert_eq!(
        conn.query_row("SELECT COUNT(*) FROM evidence_hunks", [], |row| row
            .get::<_, i64>(0))
            .unwrap(),
        1
    );
    let stored: Vec<u8> = conn
        .query_row(
            "SELECT content FROM evidence_blob_chunks ORDER BY blob_id, chunk_index LIMIT 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert!(!String::from_utf8(stored).unwrap().contains("before-secret"));
}

#[test]
fn capture_failure_rolls_back_every_linked_row() {
    let (_dir, db_path) = evidence_db();
    let conn = Connection::open(&db_path).expect("open");
    conn.execute_batch(
        "CREATE TRIGGER evidence_capture_abort BEFORE INSERT ON evidence_hunks
         BEGIN SELECT RAISE(ABORT, 'forced hunk failure'); END;",
    )
    .expect("trigger");
    drop(conn);

    assert!(persist_change_set(&request(db_path.clone())).is_err());
    let conn = Connection::open(db_path).expect("open");
    for table in [
        "evidence_change_sets",
        "evidence_file_changes",
        "evidence_hunks",
        "evidence_blobs",
        "evidence_blob_chunks",
    ] {
        let count: i64 = conn
            .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
                row.get(0)
            })
            .expect("count");
        assert_eq!(count, 0, "{table} leaked a partial row");
    }
}
