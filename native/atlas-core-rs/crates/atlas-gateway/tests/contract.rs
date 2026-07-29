//! D-012 contract tests: Rust gateway response shapes match Pydantic JSON Schema.
//!
//! These tests export JSON schemas from the live atlas_core Python models and
//! validate that every `required` field in the Pydantic schema is present in
//! the corresponding gateway endpoint response. Any drift between the Python
//! schema source of truth and the Rust row-builders is a test failure.
//!
//! Requires: Python with atlas_core installed (the agent-runtime venv).
//! Skip gracefully if Python / atlas_core is not available.

use atlas_gateway::{app, AppState};
use axum::body::Body;
use axum::http::{Request, StatusCode};
use http_body_util::BodyExt;
use serde::Deserialize;
use serde_json::Value;
use std::path::PathBuf;
use tower::util::ServiceExt;

const MIGRATION_0001: &str = include_str!("../../../../../infra/migrations/0001_core.sql");
// 0006 adds runs.agent_runtime, now part of RUN_COLS — seed DB must apply it.
const MIGRATION_0006: &str = include_str!("../../../../../infra/migrations/0006_agent_runtime.sql");
const MIGRATION_0016: &str =
    include_str!("../../../../../infra/migrations/0016_surface_sessions.sql");
const MIGRATION_0033: &str =
    include_str!("../../../../../infra/migrations/0033_evidence_plane.sql");

fn seeded_db(dir: &tempfile::TempDir) -> PathBuf {
    let path = dir.path().join("atlas.db");
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0001).unwrap();
    conn.execute_batch(MIGRATION_0006).unwrap();
    conn.execute_batch(
        "INSERT INTO missions VALUES
            ('m1', 'Contract test', 'verify schema', 'completed', 'atlas',
             '2026-06-01T10:00:00Z', '2026-06-01T11:00:00Z');
         INSERT INTO runs VALUES
            ('r1', 'm1', 'sess-1', 'succeeded',
             '2026-06-01T10:00:00Z', '2026-06-01T10:30:00Z', 'done', 'native');
         INSERT INTO audit_events
            (id, run_id, event_type, tool_name, timestamp, duration_ms, data)
         VALUES
            ('e1', 'r1', 'tool_call', 'bash', '2026-06-01T10:01:00Z', 120, '{}');
         INSERT INTO wiki_pages (id, slug, title, body, created_at, updated_at)
         VALUES
            ('w1', 'test-page', 'Test Page', 'body text',
             '2026-06-01T10:00:00Z', '2026-06-01T10:00:00Z');",
    )
    .unwrap();
    path
}

fn test_app(db_path: PathBuf) -> axum::Router {
    app(AppState {
        db_path,
        atlas_cmd: vec!["atlas".to_string()],
        repo_root: PathBuf::from("."),
    })
}

fn seeded_evidence_contract_db(dir: &tempfile::TempDir) -> PathBuf {
    let path = seeded_db(dir);
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0016).unwrap();
    conn.execute_batch(MIGRATION_0033).unwrap();
    conn.execute_batch(
        r#"
        INSERT INTO surface_sessions
            (id, surface_kind, surface_session_id, workspace_kind, workspace_root,
             agent, model_provider, model_id, permission_mode, prompt_version,
             tool_catalog_version, context_policy_version, state, owner_token,
             heartbeat_at, created_at, updated_at)
        VALUES
            ('sess-1', 'webui', 'browser-1', 'project', 'C:/atlas', 'native',
             'mock', 'mock', 'ask', '1', '1', '1', 'active', 'owner-1',
             '2026-07-29T10:00:00Z', '2026-07-29T10:00:00Z',
             '2026-07-29T10:00:00Z');
        INSERT INTO evidence_change_sets
            (id, run_id, session_id, actor_id, coverage, status, redaction_count,
             created_at)
        VALUES
            ('change-1', 'r1', 'sess-1', 'actor-1', 'complete', 'captured', 0,
             '2026-07-29T10:01:00Z');
        INSERT INTO evidence_file_changes
            (id, change_set_id, path, old_path, operation, availability,
             additions, deletions)
        VALUES
            ('file-1', 'change-1', 'src/new.rs', NULL, 'create', 'available', 2, 0);
        "#,
    )
    .unwrap();
    path
}

async fn get_json(router: &axum::Router, uri: &str) -> (StatusCode, Value) {
    let resp = router
        .clone()
        .oneshot(Request::builder().uri(uri).body(Body::empty()).unwrap())
        .await
        .unwrap();
    let status = resp.status();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let body: Value = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
    (status, body)
}

async fn get_json_with_owner(router: &axum::Router, uri: &str) -> (StatusCode, Value) {
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .uri(uri)
                .header("x-atlas-surface-owner", "owner-1")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    let status = resp.status();
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let body: Value = serde_json::from_slice(&bytes).unwrap_or(Value::Null);
    (status, body)
}

/// Run a Python one-liner. Returns None if Python is unavailable or
/// atlas_core is not installed (test will skip gracefully).
fn python_schema(model: &str) -> Option<Value> {
    let snippet = format!(
        "from atlas_core.schemas.core import {m}; \
         import json, sys; \
         print(json.dumps({m}.model_json_schema()))",
        m = model
    );
    // Try `python` first (Windows default), then `python3` (Unix default).
    for exe in &["python", "python3"] {
        let out = std::process::Command::new(exe)
            .args(["-c", &snippet])
            .output();
        match out {
            Ok(o) if o.status.success() => {
                return serde_json::from_slice(&o.stdout).ok();
            }
            _ => continue,
        }
    }
    None
}

fn required_fields(schema: &Value) -> Vec<String> {
    schema["required"]
        .as_array()
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default()
}

fn assert_fields_present(obj: &Value, required: &[String], context: &str) {
    for field in required {
        assert!(
            obj.get(field).is_some(),
            "D-012 contract failure: {context} response missing required field '{field}' \
             (from Pydantic schema source of truth)"
        );
    }
}

#[derive(Deserialize)]
struct SurfaceEventFixture {
    session_id: String,
    terminal_outcome: String,
    events: Vec<SurfaceEventDto>,
}

#[derive(Deserialize)]
struct SurfaceEventDto {
    session_id: String,
    seq: i64,
    kind: String,
    payload_json: String,
}

#[test]
fn normalized_surface_event_fixture_is_contiguous_and_terminal() {
    let fixture: SurfaceEventFixture = serde_json::from_str(include_str!(
        "../../../../../services/agent-runtime/tests/fixtures/surface_event_parity.json"
    ))
    .expect("Rust must accept the frozen normalized-event fixture");

    assert_eq!(fixture.events.len(), 10);
    for (index, event) in fixture.events.iter().enumerate() {
        assert_eq!(event.session_id, fixture.session_id);
        assert_eq!(event.seq, index as i64);
    }
    let terminal = fixture.events.last().unwrap();
    assert_eq!(terminal.kind, "completion");
    let payload: Value = serde_json::from_str(&terminal.payload_json).unwrap();
    assert_eq!(payload["status"], fixture.terminal_outcome);
}

#[test]
fn permission_receipt_fixture_remains_gateway_transparent() {
    let fixture: Value = serde_json::from_str(include_str!(
        "../../../../../services/agent-runtime/tests/fixtures/permission_policy_matrix.json"
    ))
    .expect("Rust must accept the frozen permission fixture");
    let cases = fixture["cases"].as_array().expect("fixture cases");
    assert_eq!(cases.len(), 9);
    for case in cases {
        let expected = case["expected"]
            .as_object()
            .expect("expected receipt projection");
        assert!(matches!(
            expected["decision"].as_str(),
            Some("allow" | "ask" | "deny")
        ));
        assert!(matches!(
            expected["source_layer"].as_str(),
            Some("hardline" | "master" | "profile" | "scoped_allow" | "default")
        ));
    }
    let hardline = cases
        .iter()
        .find(|case| case["id"] == "hardline-block-device")
        .expect("hardline fixture");
    assert_eq!(hardline["expected"]["decision"], "deny");
    assert_eq!(hardline["expected"]["source_layer"], "hardline");
}

// ---------------------------------------------------------------------------
// Contract test: Mission fields
// ---------------------------------------------------------------------------

#[tokio::test]
async fn mission_response_matches_pydantic_schema() {
    let schema = match python_schema("Mission") {
        Some(s) => s,
        None => {
            eprintln!("SKIP: atlas_core not importable — skipping Mission D-012 contract test");
            return;
        }
    };
    let required = required_fields(&schema);
    assert!(
        !required.is_empty(),
        "Mission schema has no required fields — suspicious"
    );

    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/missions/m1").await;
    assert_eq!(status, StatusCode::OK);
    let mission = &body["mission"];
    assert_fields_present(mission, &required, "GET /v1/missions/{id} → mission");
}

// ---------------------------------------------------------------------------
// Contract test: Run fields
// ---------------------------------------------------------------------------

#[tokio::test]
async fn run_response_matches_pydantic_schema() {
    let schema = match python_schema("Run") {
        Some(s) => s,
        None => {
            eprintln!("SKIP: atlas_core not importable — skipping Run D-012 contract test");
            return;
        }
    };
    let required = required_fields(&schema);
    assert!(
        !required.is_empty(),
        "Run schema has no required fields — suspicious"
    );

    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/r1").await;
    assert_eq!(status, StatusCode::OK);
    let run = &body["run"];
    assert_fields_present(run, &required, "GET /v1/runs/{id} → run");
}

// ---------------------------------------------------------------------------
// Contract test: AuditEvent fields
// ---------------------------------------------------------------------------

#[tokio::test]
async fn audit_event_response_matches_pydantic_schema() {
    let schema = match python_schema("AuditEvent") {
        Some(s) => s,
        None => {
            eprintln!("SKIP: atlas_core not importable — skipping AuditEvent D-012 contract test");
            return;
        }
    };
    let required = required_fields(&schema);
    assert!(
        !required.is_empty(),
        "AuditEvent schema has no required fields — suspicious"
    );

    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/r1/events").await;
    assert_eq!(status, StatusCode::OK);
    let event = &body["events"][0];
    assert_fields_present(event, &required, "GET /v1/runs/{id}/events → events[0]");
}

fn schema_enum(schema: &Value, field: &str) -> Vec<String> {
    schema["properties"][field]["enum"]
        .as_array()
        .unwrap_or_else(|| panic!("{field} must declare a direct enum"))
        .iter()
        .map(|value| value.as_str().unwrap().to_string())
        .collect()
}

#[tokio::test]
async fn evidence_responses_match_pydantic_types_enums_and_optionality() {
    let change_schema = match python_schema("ChangeSet") {
        Some(schema) => schema,
        None => {
            eprintln!("SKIP: atlas_core not importable — skipping Evidence D-012 contract test");
            return;
        }
    };
    let file_schema = python_schema("FileChange").expect("FileChange schema");
    assert_eq!(
        schema_enum(&change_schema, "coverage"),
        ["complete", "tool_only", "partial", "unavailable"]
    );
    assert_eq!(
        schema_enum(&file_schema, "operation"),
        ["create", "edit", "delete", "rename", "mode", "binary"]
    );
    assert_eq!(
        schema_enum(&file_schema, "availability"),
        [
            "available",
            "redacted",
            "partial",
            "unavailable",
            "too_large"
        ]
    );

    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_evidence_contract_db(&dir));
    let (status, detail) = get_json_with_owner(&router, "/v1/change-sets/change-1").await;
    assert_eq!(status, StatusCode::OK);
    let change_set = &detail["change_set"];
    assert!(change_set["id"].is_string());
    assert!(change_set["provenance"].is_object());
    assert!(change_set["provenance"]["run_id"].is_string());
    assert!(change_set["provenance"]["actor_id"].is_string());
    assert!(change_set["coverage"].is_string());
    assert!(change_set["status"].is_string());
    assert!(change_set["redaction_count"].is_i64());
    assert!(change_set["created_at"].is_string());

    let (status, files) = get_json_with_owner(&router, "/v1/change-sets/change-1/files").await;
    assert_eq!(status, StatusCode::OK);
    let file = &files["files"][0];
    assert!(file["id"].is_string());
    assert!(file["change_set_id"].is_string());
    assert!(file["path"].is_string());
    assert!(file["old_path"].is_null());
    assert!(file["operation"].is_string());
    assert!(file["availability"].is_string());
    assert!(file["binary"].is_boolean());
    assert!(file["generated"].is_boolean());
    assert!(file["redaction_count"].is_i64());
}
