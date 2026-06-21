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
use serde_json::Value;
use std::path::PathBuf;
use tower::util::ServiceExt;

const MIGRATION_0001: &str = include_str!("../../../../../infra/migrations/0001_core.sql");
// 0006 adds runs.agent_runtime, now part of RUN_COLS — seed DB must apply it.
const MIGRATION_0006: &str = include_str!("../../../../../infra/migrations/0006_agent_runtime.sql");

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
    assert!(!required.is_empty(), "Mission schema has no required fields — suspicious");

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
    assert!(!required.is_empty(), "Run schema has no required fields — suspicious");

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
    assert!(!required.is_empty(), "AuditEvent schema has no required fields — suspicious");

    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/r1/events").await;
    assert_eq!(status, StatusCode::OK);
    let event = &body["events"][0];
    assert_fields_present(event, &required, "GET /v1/runs/{id}/events → events[0]");
}
