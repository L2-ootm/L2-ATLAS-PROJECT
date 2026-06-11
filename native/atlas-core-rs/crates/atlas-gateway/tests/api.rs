//! Integration tests for the atlas-gateway read surface + SSE skeleton.
//! Each test runs against a throwaway SQLite database seeded with the real
//! 0001_core.sql migration, so field names stay locked to the schema.

use atlas_gateway::{app, AppState};
use axum::body::Body;
use axum::http::{Request, StatusCode};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use std::path::PathBuf;
use tower::util::ServiceExt;

const MIGRATION_0001: &str = include_str!("../../../../../infra/migrations/0001_core.sql");

fn seeded_db(dir: &tempfile::TempDir) -> PathBuf {
    let path = dir.path().join("atlas.db");
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0001).unwrap();
    conn.execute_batch(
        "INSERT INTO missions VALUES
            ('m1', 'First mission', 'ship it', 'completed', 'atlas',
             '2026-06-01T10:00:00Z', '2026-06-01T11:00:00Z'),
            ('m2', 'Second mission', '', 'pending', 'atlas',
             '2026-06-02T10:00:00Z', '2026-06-02T10:00:00Z');
         INSERT INTO runs VALUES
            ('r1', 'm1', 'sess-1', 'succeeded',
             '2026-06-01T10:00:00Z', '2026-06-01T10:30:00Z', 'done');
         INSERT INTO audit_events
            (id, run_id, event_type, tool_name, timestamp, duration_ms, data)
         VALUES
            ('e1', 'r1', 'tool_call', 'bash', '2026-06-01T10:01:00Z', 120,
             '{\"cmd\": \"echo hi\"}'),
            ('e2', 'r1', 'run_finished', NULL, '2026-06-01T10:30:00Z', NULL, '{}');
         INSERT INTO wiki_pages (id, slug, title, body, created_at, updated_at)
         VALUES
            ('w1', 'atlas-gateway', 'ATLAS Gateway',
             'The rust gateway serves read endpoints over sqlite.',
             '2026-06-01T10:00:00Z', '2026-06-01T10:00:00Z');",
    )
    .unwrap();
    path
}

fn test_app(db_path: PathBuf) -> axum::Router {
    app(AppState {
        db_path,
        atlas_cmd: vec!["atlas".to_string()],
    })
}

/// Build a test app that routes atlas CLI calls to a Python one-liner stub.
/// The stub script just prints `stub_output` to stdout and exits 0.
fn test_app_with_stub(db_path: PathBuf, stub_output: &str, dir: &tempfile::TempDir) -> axum::Router {
    let stub = dir.path().join("mock_atlas.py");
    std::fs::write(
        &stub,
        format!("import sys\nprint('{}')\n", stub_output.replace('\'', "\\'")),
    )
    .unwrap();
    let python = if cfg!(windows) { "python" } else { "python3" };
    app(AppState {
        db_path,
        atlas_cmd: vec![python.to_string(), stub.to_string_lossy().to_string()],
    })
}

async fn post_json(router: &axum::Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let bytes = serde_json::to_vec(&body).unwrap();
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri(uri)
                .header("content-type", "application/json")
                .body(Body::from(bytes))
                .unwrap(),
        )
        .await
        .unwrap();
    let status = resp.status();
    let body_bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let body: Value = serde_json::from_slice(&body_bytes).unwrap_or(Value::Null);
    (status, body)
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

#[tokio::test]
async fn health_reports_db_ok() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/health").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["status"], "ok");
    assert_eq!(body["db"], "ok");
    assert_eq!(body["service"], "atlas-gateway");
}

#[tokio::test]
async fn health_reports_db_absent() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(dir.path().join("missing.db"));
    let (status, body) = get_json(&router, "/health").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["db"], "absent");
}

#[tokio::test]
async fn missions_list_returns_rows_newest_first() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/missions").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 2);
    assert_eq!(body["missions"][0]["id"], "m2");
    assert_eq!(body["missions"][1]["id"], "m1");
    assert_eq!(body["missions"][1]["title"], "First mission");
}

#[tokio::test]
async fn missions_list_respects_limit() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/missions?limit=1").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1);
}

#[tokio::test]
async fn missions_list_absent_db_is_structured_503() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(dir.path().join("missing.db"));
    let (status, body) = get_json(&router, "/v1/missions").await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(body["error"]["code"], "db_unavailable");
}

#[tokio::test]
async fn mission_detail_includes_runs() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/missions/m1").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["mission"]["id"], "m1");
    assert_eq!(body["runs"][0]["id"], "r1");
    assert_eq!(body["runs"][0]["status"], "succeeded");
}

#[tokio::test]
async fn mission_detail_unknown_is_404() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/missions/nope").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["error"]["code"], "not_found");
}

#[tokio::test]
async fn run_detail_roundtrips() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/r1").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["run"]["mission_id"], "m1");
    assert_eq!(body["run"]["finished_at"], "2026-06-01T10:30:00Z");

    let (status, _) = get_json(&router, "/v1/runs/nope").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn run_events_pages_by_rowid_cursor() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/r1/events").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["events"].as_array().unwrap().len(), 2);
    assert_eq!(body["events"][0]["event_type"], "tool_call");
    assert_eq!(body["events"][0]["data"]["cmd"], "echo hi");
    let cursor = body["next_cursor"].as_i64().unwrap();
    assert!(cursor > 0);

    let (status, body) = get_json(&router, &format!("/v1/runs/r1/events?after={cursor}")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["events"].as_array().unwrap().len(), 0);
    assert_eq!(body["next_cursor"].as_i64().unwrap(), cursor);
}

#[tokio::test]
async fn run_events_unknown_run_is_404() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, _) = get_json(&router, "/v1/runs/nope/events").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn wiki_search_matches_fts() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/search?q=gateway").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["results"][0]["slug"], "atlas-gateway");
    assert!(body["results"][0]["snippet"]
        .as_str()
        .unwrap()
        .contains("gateway"));
}

#[tokio::test]
async fn wiki_search_hyphenated_query_does_not_error() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    // Raw hyphens are FTS5 operators; the gateway must quote them.
    let (status, _) = get_json(&router, "/v1/wiki/search?q=atlas-gateway").await;
    assert_eq!(status, StatusCode::OK);
}

#[tokio::test]
async fn wiki_search_requires_q() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/search").await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

#[tokio::test]
async fn sse_stream_replays_events_and_ends_for_finished_run() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .uri("/v1/runs/r1/stream")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
    assert_eq!(
        resp.headers()["content-type"].to_str().unwrap(),
        "text/event-stream"
    );
    // r1 is terminal, so the stream replays history, emits `end`, and closes
    // — the body is finite and can be fully collected.
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let text = String::from_utf8(bytes.to_vec()).unwrap();
    assert!(
        text.contains("event: audit"),
        "missing audit events: {text}"
    );
    assert!(text.contains("tool_call"), "missing event payload: {text}");
    assert!(text.contains("event: end"), "missing end event: {text}");
}

#[tokio::test]
async fn sse_stream_unknown_run_is_404() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/runs/nope/stream").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["error"]["code"], "not_found");
}

// ---------------------------------------------------------------------------
// GET /v1/wiki/pages
// ---------------------------------------------------------------------------

#[tokio::test]
async fn wiki_pages_returns_list() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/pages").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1);
    assert_eq!(body["pages"][0]["slug"], "atlas-gateway");
    assert_eq!(body["pages"][0]["title"], "ATLAS Gateway");
    // list endpoint must NOT expose body content (bandwidth)
    assert!(body["pages"][0].get("body").is_none());
}

#[tokio::test]
async fn wiki_pages_respects_limit() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/pages?limit=0").await;
    // limit is clamped to [1, 500], so 0 → 1
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1);
}

#[tokio::test]
async fn wiki_pages_absent_db_is_503() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(dir.path().join("missing.db"));
    let (status, body) = get_json(&router, "/v1/wiki/pages").await;
    assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
    assert_eq!(body["error"]["code"], "db_unavailable");
}

// ---------------------------------------------------------------------------
// POST /v1/missions — write dispatch via atlas CLI stub
// ---------------------------------------------------------------------------

#[tokio::test]
async fn post_mission_missing_body_is_422() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    // No JSON body — axum rejects before reaching the handler
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/v1/missions")
                .header("content-type", "application/json")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    // axum 0.8 returns 400 Bad Request for an empty JSON body (cannot parse)
    assert!(
        resp.status() == StatusCode::BAD_REQUEST
            || resp.status() == StatusCode::UNPROCESSABLE_ENTITY,
        "expected 400 or 422, got {}",
        resp.status()
    );
}

#[tokio::test]
async fn post_mission_dispatches_to_atlas_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    // The stub echoes "m2" (already in seeded DB)
    let router = test_app_with_stub(db_path, "m2", &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/missions",
        json!({ "title": "Test mission", "intent": "Test intent" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["mission"]["id"], "m2");
    assert!(body["runs"].is_array());
}

#[tokio::test]
async fn post_mission_atlas_not_found_is_500() {
    let dir = tempfile::tempdir().unwrap();
    let router = app(AppState {
        db_path: seeded_db(&dir),
        // Point to a binary that definitely does not exist
        atlas_cmd: vec!["__nonexistent_atlas_binary__".to_string()],
    });
    let (status, body) = post_json(
        &router,
        "/v1/missions",
        json!({ "title": "Fail", "intent": "" }),
    )
    .await;
    assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
    assert_eq!(body["error"]["code"], "internal");
}

// ---------------------------------------------------------------------------
// POST /v1/missions/{id}/run — write dispatch via atlas CLI stub
// ---------------------------------------------------------------------------

#[tokio::test]
async fn start_run_dispatches_to_atlas_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    // Stub echoes "r1" (already in seeded DB)
    let router = test_app_with_stub(db_path, "r1", &stub_dir);
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/v1/missions/m1/run")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), StatusCode::CREATED);
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["run"]["id"], "r1");
    assert_eq!(body["run"]["mission_id"], "m1");
}

#[tokio::test]
async fn start_run_atlas_not_found_is_500() {
    let dir = tempfile::tempdir().unwrap();
    let router = app(AppState {
        db_path: seeded_db(&dir),
        atlas_cmd: vec!["__nonexistent_atlas_binary__".to_string()],
    });
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/v1/missions/m1/run")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), StatusCode::INTERNAL_SERVER_ERROR);
}
