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
// 0006 adds runs.agent_runtime (TEXT NOT NULL DEFAULT 'native'), which RUN_COLS
// now selects — the seed DB must apply it so the runs read surface stays valid.
const MIGRATION_0006: &str = include_str!("../../../../../infra/migrations/0006_agent_runtime.sql");
// 0007 adds the optional-modules table (seeds the cashflow module inactive).
const MIGRATION_0007: &str = include_str!("../../../../../infra/migrations/0007_modules.sql");

fn seeded_db(dir: &tempfile::TempDir) -> PathBuf {
    let path = dir.path().join("atlas.db");
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0001).unwrap();
    conn.execute_batch(MIGRATION_0006).unwrap();
    conn.execute_batch(
        "INSERT INTO missions VALUES
            ('m1', 'First mission', 'ship it', 'completed', 'atlas',
             '2026-06-01T10:00:00Z', '2026-06-01T11:00:00Z'),
            ('m2', 'Second mission', '', 'pending', 'atlas',
             '2026-06-02T10:00:00Z', '2026-06-02T10:00:00Z');
         INSERT INTO runs VALUES
            ('r1', 'm1', 'sess-1', 'succeeded',
             '2026-06-01T10:00:00Z', '2026-06-01T10:30:00Z', 'done', 'native');
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
        repo_root: PathBuf::from("."),
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
        repo_root: PathBuf::from("."),
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
async fn config_view_returns_masked_json_from_cli() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    // Stub `atlas config json` output: masked config (env: ref, no secret value).
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"provider": {"name": "openrouter", "api_key": "env:OPENROUTER_API_KEY"}}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/config").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["provider"]["name"], "openrouter");
    assert_eq!(body["provider"]["api_key"], "env:OPENROUTER_API_KEY");
}

#[tokio::test]
async fn channels_list_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"channels": [{"name": "discord", "enabled": true, "credential_present": true}]}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/channels").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["channels"][0]["name"], "discord");
    assert_eq!(body["channels"][0]["enabled"], true);
}

#[tokio::test]
async fn channel_toggle_dispatches_and_echoes_state() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(seeded_db(&dir), "enabled discord", &stub_dir);
    let (status, body) =
        post_json(&router, "/v1/channels/discord/toggle", json!({ "enabled": true })).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["name"], "discord");
    assert_eq!(body["enabled"], true);
}

#[tokio::test]
async fn messaging_gateway_status_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(seeded_db(&dir), r#"{"running": false, "pid": null}"#, &stub_dir);
    let (status, body) = get_json(&router, "/v1/gateway/messaging/status").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["running"], false);
    assert!(body["pid"].is_null());
}

#[tokio::test]
async fn messaging_gateway_start_returns_pid() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"ok": true, "message": "messaging gateway starting (pid 8200)", "running": true, "pid": 8200}"#,
        &stub_dir,
    );
    let (status, body) = post_json(&router, "/v1/gateway/messaging/start", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["ok"], true);
    assert_eq!(body["pid"], 8200);
}

#[tokio::test]
async fn messaging_gateway_stop_is_idempotent() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"ok": true, "message": "messaging gateway not running"}"#,
        &stub_dir,
    );
    let (status, body) = post_json(&router, "/v1/gateway/messaging/stop", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["ok"], true);
}

#[tokio::test]
async fn discord_status_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"running": true, "pid": 1234, "ready": true, "guild_count": 3}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/discord/status").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["running"], true);
    assert_eq!(body["guild_count"], 3);
}

#[tokio::test]
async fn discord_guilds_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"guilds": [{"id": "111", "name": "L2 HQ"}]}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/discord/guilds").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["guilds"][0]["id"], "111");
    assert_eq!(body["guilds"][0]["name"], "L2 HQ");
}

#[tokio::test]
async fn discord_structure_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"guild": {"id": "111", "name": "L2 HQ", "member_count": 9}, "categories": [], "uncategorized": [], "roles": []}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/discord/guilds/111/structure").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["guild"]["name"], "L2 HQ");
}

#[tokio::test]
async fn discord_propose_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"id": "ap1", "status": "pending", "action": "create_channel", "summary": "create text channel #ops"}"#,
        &stub_dir,
    );
    let (status, body) = post_json(
        &router,
        "/v1/discord/writes",
        json!({"action": "create_channel", "guild": "g1", "params": {"name": "ops"}}),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["id"], "ap1");
    assert_eq!(body["status"], "pending");
}

#[tokio::test]
async fn discord_approvals_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"approvals": [{"id": "ap1", "status": "pending", "action": "create_channel"}]}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/discord/approvals").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["approvals"][0]["id"], "ap1");
}

#[tokio::test]
async fn discord_approve_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"id": "ap1", "status": "executed", "result": "ok"}"#,
        &stub_dir,
    );
    let (status, body) = post_json(&router, "/v1/discord/approvals/ap1/approve", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["status"], "executed");
}

#[tokio::test]
async fn discord_reject_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"id": "ap1", "status": "rejected", "reason": "not now"}"#,
        &stub_dir,
    );
    let (status, body) =
        post_json(&router, "/v1/discord/approvals/ap1/reject", json!({"reason": "not now"})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["status"], "rejected");
}

#[tokio::test]
async fn discord_start_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"ok": true, "message": "discord bot starting (pid 4321)", "running": true, "pid": 4321, "ready": false, "guild_count": 0}"#,
        &stub_dir,
    );
    let (status, body) = post_json(&router, "/v1/discord/start", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["ok"], true);
    assert_eq!(body["pid"], 4321);
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
        repo_root: PathBuf::from("."),
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

/// Build a test app whose atlas stub records its argv (one arg per line) to
/// `argv_path` before echoing `stub_output`. Lets a test assert exactly which
/// flags the gateway forwarded to the CLI.
fn test_app_with_arg_capture(
    db_path: PathBuf,
    stub_output: &str,
    argv_path: &std::path::Path,
    dir: &tempfile::TempDir,
) -> axum::Router {
    let stub = dir.path().join("mock_atlas_argv.py");
    let argv = argv_path.to_string_lossy().replace('\\', "\\\\");
    std::fs::write(
        &stub,
        format!(
            "import sys\nopen(r'{argv}', 'w').write('\\n'.join(sys.argv[1:]))\nprint('{out}')\n",
            argv = argv,
            out = stub_output.replace('\'', "\\'"),
        ),
    )
    .unwrap();
    let python = if cfg!(windows) { "python" } else { "python3" };
    app(AppState {
        db_path,
        atlas_cmd: vec![python.to_string(), stub.to_string_lossy().to_string()],
        repo_root: PathBuf::from("."),
    })
}

#[tokio::test]
async fn start_run_forwards_agent_claude_code() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(db_path, "r1", &argv_path, &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/missions/m1/run",
        json!({ "agent": "claude_code" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["run"]["id"], "r1");
    // The gateway must forward `--agent claude_code` to the CLI.
    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    let idx = args
        .iter()
        .position(|a| *a == "--agent")
        .expect("--agent flag missing from dispatched args");
    assert_eq!(args.get(idx + 1).copied(), Some("claude_code"));
}

#[tokio::test]
async fn start_run_defaults_agent_to_native() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(db_path, "r1", &argv_path, &stub_dir);
    // Empty body — no agent field. Defaults to "native".
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
    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    let idx = args
        .iter()
        .position(|a| *a == "--agent")
        .expect("--agent flag missing from dispatched args");
    assert_eq!(args.get(idx + 1).copied(), Some("native"));
}

#[tokio::test]
async fn start_run_invalid_agent_is_400() {
    let dir = tempfile::tempdir().unwrap();
    // Rejected before any dispatch — no stub needed.
    let router = test_app(seeded_db(&dir));
    let (status, body) = post_json(
        &router,
        "/v1/missions/m1/run",
        json!({ "agent": "rogue_runtime" }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

#[tokio::test]
async fn retry_mission_dispatches_mission_retry_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    // Stub echoes "r1" (already in seeded DB) as the new run id.
    let router = test_app_with_arg_capture(db_path, "r1", &argv_path, &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/missions/m1/retry",
        json!({ "agent": "claude_code" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["run"]["id"], "r1");
    assert_eq!(body["run"]["mission_id"], "m1");
    // The gateway must dispatch `mission retry --agent claude_code -- m1`.
    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("mission"));
    assert_eq!(args.get(1).copied(), Some("retry"));
    let idx = args
        .iter()
        .position(|a| *a == "--agent")
        .expect("--agent flag missing from dispatched args");
    assert_eq!(args.get(idx + 1).copied(), Some("claude_code"));
    assert!(args.contains(&"m1"));
}

#[tokio::test]
async fn console_chat_forwards_agent_prompt_and_cwd() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(
        db_path,
        r#"{"status":"succeeded","agent":"claude_code","text":"ok","events":[]}"#,
        &argv_path,
        &stub_dir,
    );
    let (status, body) = post_json(
        &router,
        "/v1/console/chat",
        json!({
            "agent": "claude_code",
            "cwd": "C:\\Work\\Atlas",
            "prompt": "inspect project"
        }),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["agent"], "claude_code");
    assert_eq!(body["text"], "ok");

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("console"));
    assert!(args.windows(2).any(|w| w == ["--agent", "claude_code"]));
    assert!(args.windows(2).any(|w| w == ["--cwd", "C:\\Work\\Atlas"]));
    assert!(args.windows(2).any(|w| w == ["--prompt", "inspect project"]));
}

#[tokio::test]
async fn start_run_atlas_not_found_is_500() {
    let dir = tempfile::tempdir().unwrap();
    let router = app(AppState {
        db_path: seeded_db(&dir),
        atlas_cmd: vec!["__nonexistent_atlas_binary__".to_string()],
        repo_root: PathBuf::from("."),
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

// ===========================================================================
// Phase 08.5 — coverage for the four Phase 8 gateway surfaces that shipped
// untested (wiki create/update/detail, models, cancel) + a fresh multi-
// migration DB read smoke. Closes Phase 8 judge-report item 5 + item 7.
// ===========================================================================

const MIGRATION_0002: &str =
    include_str!("../../../../../infra/migrations/0002_wiki_provenance.sql");
const MIGRATION_0003: &str =
    include_str!("../../../../../infra/migrations/0003_model_registry.sql");

/// seeded_db + 0002 (provenance) + 0003 (model_registry) and one model row.
fn seeded_db_all(dir: &tempfile::TempDir) -> PathBuf {
    let path = seeded_db(dir);
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0002).unwrap();
    conn.execute_batch(MIGRATION_0003).unwrap();
    conn.execute_batch(
        "INSERT INTO model_registry
            (model_id, provider, source, first_seen, last_seen, active)
         VALUES
            ('gpt-test', 'openai', 'manual',
             '2026-06-01T00:00:00Z', '2026-06-10T00:00:00Z', 1);",
    )
    .unwrap();
    path
}

async fn put_json(router: &axum::Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let bytes = serde_json::to_vec(&body).unwrap();
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("PUT")
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

async fn patch_json(router: &axum::Router, uri: &str, body: Value) -> (StatusCode, Value) {
    let bytes = serde_json::to_vec(&body).unwrap();
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("PATCH")
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

// --- GET /v1/wiki/pages/{slug} ---------------------------------------------

#[tokio::test]
async fn wiki_page_detail_returns_page() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/pages/atlas-gateway").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["page"]["slug"], "atlas-gateway");
    assert_eq!(body["page"]["title"], "ATLAS Gateway");
}

#[tokio::test]
async fn wiki_page_detail_unknown_is_404() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/wiki/pages/nope").await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["error"]["code"], "not_found");
}

// --- POST /v1/wiki/pages (create via atlas CLI dispatch) -------------------

#[tokio::test]
async fn wiki_create_dispatches_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    // The CLI echoes the canonical slug; point the stub at the existing page so
    // the handler's read-back (by canonical slug) succeeds.
    let router = test_app_with_stub(db_path, "atlas-gateway", &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/wiki/pages",
        json!({ "slug": "Atlas Gateway", "title": "ATLAS Gateway", "body": "hello" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["page"]["slug"], "atlas-gateway");
}

#[tokio::test]
async fn wiki_create_empty_slug_is_400() {
    let dir = tempfile::tempdir().unwrap();
    // Rejected by require_arg before any dispatch — no stub needed.
    let router = test_app(seeded_db(&dir));
    let (status, body) = post_json(
        &router,
        "/v1/wiki/pages",
        json!({ "slug": "", "title": "t", "body": "b" }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

// --- PUT /v1/wiki/pages/{slug} (update via atlas CLI dispatch) -------------

#[tokio::test]
async fn wiki_update_dispatches_and_returns_200() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let router = test_app_with_stub(db_path, "atlas-gateway", &stub_dir);
    let (status, body) = put_json(
        &router,
        "/v1/wiki/pages/atlas-gateway",
        json!({ "title": "New Title" }),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["page"]["slug"], "atlas-gateway");
}

#[tokio::test]
async fn wiki_update_unknown_slug_is_404() {
    let dir = tempfile::tempdir().unwrap();
    // Unknown slug 404s on the read-current step, before any dispatch.
    let router = test_app(seeded_db(&dir));
    let (status, body) = put_json(
        &router,
        "/v1/wiki/pages/nope",
        json!({ "title": "x" }),
    )
    .await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    assert_eq!(body["error"]["code"], "not_found");
}

// --- GET /v1/models ---------------------------------------------------------

#[tokio::test]
async fn models_list_absent_table_returns_empty() {
    let dir = tempfile::tempdir().unwrap();
    // seeded_db applies 0001 only — model_registry table does not exist.
    // The gateway must degrade to an empty list, never 503, on a fresh deploy.
    let router = test_app(seeded_db(&dir));
    let (status, body) = get_json(&router, "/v1/models").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 0);
    assert_eq!(body["models"].as_array().unwrap().len(), 0);
}

#[tokio::test]
async fn models_list_returns_rows() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_all(&dir));
    let (status, body) = get_json(&router, "/v1/models").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1);
    assert_eq!(body["models"][0]["model_id"], "gpt-test");
    assert_eq!(body["models"][0]["active"], true);
}

// --- POST /v1/missions/{id}/cancel (dispatch via atlas CLI) ----------------

#[tokio::test]
async fn cancel_run_dispatches_and_returns_200() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let router = test_app_with_stub(db_path, "r1", &stub_dir);
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/v1/missions/m1/cancel")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
    let bytes = resp.into_body().collect().await.unwrap().to_bytes();
    let body: Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["mission"]["id"], "m1");
    assert_eq!(body["message"], "run cancelled");
}

#[tokio::test]
async fn cancel_run_atlas_not_found_is_500() {
    let dir = tempfile::tempdir().unwrap();
    let router = app(AppState {
        db_path: seeded_db(&dir),
        atlas_cmd: vec!["__nonexistent_atlas_binary__".to_string()],
        repo_root: PathBuf::from("."),
    });
    let resp = router
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/v1/missions/m1/cancel")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();
    assert_eq!(resp.status(), StatusCode::INTERNAL_SERVER_ERROR);
}

// --- Fresh multi-migration DB read smoke (judge item 7) --------------------

#[tokio::test]
async fn fresh_multi_migration_db_serves_all_read_surfaces() {
    // A freshly migrated DB (0001+0002+0003) must serve every read surface
    // without 503/500 — the fresh-DB blind spot called out in the Phase 8
    // judge report. One GET per gateway read surface, all expected 200.
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_all(&dir));
    for uri in [
        "/health",
        "/v1/missions",
        "/v1/missions/m1",
        "/v1/runs/r1",
        "/v1/runs/r1/events",
        "/v1/wiki/pages",
        "/v1/wiki/pages/atlas-gateway",
        "/v1/wiki/search?q=gateway",
        "/v1/models",
    ] {
        let (status, _) = get_json(&router, uri).await;
        assert_eq!(status, StatusCode::OK, "read surface {uri} did not return 200");
    }
}

// --- Modules read surface (Decision 3b — optional activatable modules) -------

#[tokio::test]
async fn modules_list_returns_seeded_cashflow() {
    let dir = tempfile::tempdir().unwrap();
    let path = seeded_db(&dir);
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0007).unwrap();
    drop(conn);
    let router = test_app(path);
    let (status, body) = get_json(&router, "/v1/modules").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1);
    assert_eq!(body["modules"][0]["id"], "cashflow");
    assert_eq!(body["modules"][0]["status"], "inactive");
}

#[tokio::test]
async fn modules_list_empty_when_table_absent() {
    // Pre-0007 DB: the endpoint must return an empty list, never 500.
    let dir = tempfile::tempdir().unwrap();
    let path = seeded_db(&dir); // 0007 not applied
    let router = test_app(path);
    let (status, body) = get_json(&router, "/v1/modules").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 0);
}

// --- Focus read + write surface (WP-2 — Command Center Current Focus) --------

const MIGRATION_0009: &str = include_str!("../../../../../infra/migrations/0009_focus.sql");

/// seeded_db + 0009 (focus) and two focus rows: an active Current Focus (newest)
/// plus an archived one (must be excluded from the active list/current).
fn seeded_db_focus(dir: &tempfile::TempDir) -> PathBuf {
    let path = seeded_db(dir);
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0009).unwrap();
    conn.execute_batch(
        "INSERT INTO focus
            (id, title, framework, priorities, drivers, project_id, status, created_at, updated_at)
         VALUES
            ('f-old', 'Old focus', 'OKR', '[\"a\"]', '[]', NULL, 'archived',
             '2026-06-01T10:00:00Z', '2026-06-01T10:00:00Z'),
            ('f-cur', 'Ship the loop', 'GSD', '[\"latency\",\"trust\"]', '[\"operator\"]',
             'atlas', 'active', '2026-06-10T10:00:00Z', '2026-06-10T10:00:00Z');",
    )
    .unwrap();
    path
}

#[tokio::test]
async fn focus_list_returns_active_with_parsed_arrays() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_focus(&dir));
    let (status, body) = get_json(&router, "/v1/focus").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 1); // archived 'f-old' excluded
    assert_eq!(body["focus"][0]["id"], "f-cur");
    // priorities/drivers stored as JSON-array strings must come back as arrays.
    assert_eq!(body["focus"][0]["priorities"][0], "latency");
    assert_eq!(body["focus"][0]["priorities"][1], "trust");
    assert_eq!(body["focus"][0]["drivers"][0], "operator");
}

#[tokio::test]
async fn focus_current_returns_newest_active() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_focus(&dir));
    let (status, body) = get_json(&router, "/v1/focus/current").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["focus"]["id"], "f-cur");
    assert_eq!(body["focus"]["framework"], "GSD");
}

#[tokio::test]
async fn focus_current_null_when_table_absent() {
    // Pre-0009 DB: the endpoint must return focus: null, never 500.
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir)); // 0009 not applied
    let (status, body) = get_json(&router, "/v1/focus/current").await;
    assert_eq!(status, StatusCode::OK);
    assert!(body["focus"].is_null());
}

#[tokio::test]
async fn focus_list_empty_when_table_absent() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir)); // 0009 not applied
    let (status, body) = get_json(&router, "/v1/focus").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["count"], 0);
}

#[tokio::test]
async fn focus_create_forwards_args_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_focus(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    // The CLI prints the new id; point the stub at the seeded active row so the
    // handler's read-back succeeds.
    let router = test_app_with_arg_capture(db_path, "f-cur", &argv_path, &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/focus",
        json!({
            "title": "Ship the loop",
            "framework": "GSD",
            "priorities": ["latency", "trust"],
            "drivers": ["operator"],
            "project": "atlas"
        }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["focus"]["id"], "f-cur");

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("focus"));
    assert!(args.windows(2).any(|w| w == ["--title", "Ship the loop"]));
    assert!(args.windows(2).any(|w| w == ["--framework", "GSD"]));
    // Vec<String> priorities/drivers joined with commas for the CLI's _split_csv.
    assert!(args.windows(2).any(|w| w == ["--priorities", "latency,trust"]));
    assert!(args.windows(2).any(|w| w == ["--drivers", "operator"]));
    assert!(args.windows(2).any(|w| w == ["--project", "atlas"]));
}

#[tokio::test]
async fn focus_create_empty_title_is_400() {
    let dir = tempfile::tempdir().unwrap();
    // Rejected by require_arg before any dispatch — no stub needed.
    let router = test_app(seeded_db_focus(&dir));
    let (status, body) = post_json(&router, "/v1/focus", json!({ "title": "" })).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

#[tokio::test]
async fn focus_archive_dispatches_and_returns_200() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_focus(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(db_path, "archived", &argv_path, &stub_dir);
    let (status, body) = post_json(&router, "/v1/focus/f-cur/archive", json!({})).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["archived"], true);
    assert_eq!(body["id"], "f-cur");

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("focus"));
    assert!(args.contains(&"archive"));
    // id passed after the `--` argument-injection guard.
    assert_eq!(args.last().copied(), Some("f-cur"));
}

// --- Goal hierarchy read + write surface (loop-engineering slice) ------------

const MIGRATION_0010: &str = include_str!("../../../../../infra/migrations/0010_goal_model.sql");

/// seeded_db_focus + 0010 (goal model) with a root goal, a sub-goal, a task on
/// the root, and an observation on the root — enough to exercise tree nesting.
fn seeded_db_goals(dir: &tempfile::TempDir) -> PathBuf {
    let path = seeded_db_focus(dir);
    let conn = rusqlite::Connection::open(&path).unwrap();
    conn.execute_batch(MIGRATION_0010).unwrap();
    conn.execute_batch(
        "INSERT INTO goals
            (id, focus_id, parent_goal_id, title, description, status, position, created_at, updated_at)
         VALUES
            ('g-root', 'f-cur', NULL, 'Ship the loop', 'full slice', 'active', 0,
             '2026-06-10T10:00:00Z', '2026-06-10T10:00:00Z'),
            ('g-sub', 'f-cur', 'g-root', 'Wire execution', '', 'open', 0,
             '2026-06-10T10:05:00Z', '2026-06-10T10:05:00Z'),
            ('g-archived', 'f-cur', NULL, 'old goal', '', 'archived', 1,
             '2026-06-09T10:00:00Z', '2026-06-09T10:00:00Z');
         INSERT INTO tasks(id, goal_id, title, status, position, created_at, updated_at)
         VALUES
            ('t1', 'g-root', 'write migration', 'done', 0,
             '2026-06-10T10:01:00Z', '2026-06-10T10:01:00Z');
         INSERT INTO observations(id, goal_id, run_id, body, source, created_at)
         VALUES
            ('o1', 'g-root', 'r1', 'tests green', 'run:r1', '2026-06-10T10:02:00Z'),
            -- run-level observation (compounding loop) with NULL goal_id: the tree
            -- build must skip it, never error on the NULL grouping key.
            ('o2', NULL, 'r1', 'run failed: no creds', 'compounding-loop', '2026-06-10T10:03:00Z');",
    )
    .unwrap();
    path
}

#[tokio::test]
async fn focus_tree_nests_children_tasks_observations() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_goals(&dir));
    let (status, body) = get_json(&router, "/v1/focus/f-cur/tree").await;
    assert_eq!(status, StatusCode::OK);
    let tree = body["tree"].as_array().unwrap();
    assert_eq!(tree.len(), 1); // archived root excluded; sub nested under root
    let root = &tree[0];
    assert_eq!(root["id"], "g-root");
    assert_eq!(root["tasks"][0]["title"], "write migration");
    assert_eq!(root["observations"][0]["body"], "tests green");
    assert_eq!(root["children"][0]["id"], "g-sub");
}

#[tokio::test]
async fn focus_tree_empty_when_table_absent() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db_focus(&dir)); // 0010 not applied
    let (status, body) = get_json(&router, "/v1/focus/f-cur/tree").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["tree"].as_array().unwrap().len(), 0);
}

#[tokio::test]
async fn goal_create_forwards_args_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_goals(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    // Stub prints the seeded root id so the handler's read-back succeeds.
    let router = test_app_with_arg_capture(db_path, "g-root", &argv_path, &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/goals",
        json!({ "title": "Ship the loop", "description": "full slice", "focus": "f-cur", "parent": "g-root" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["goal"]["id"], "g-root");

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("goal"));
    assert!(args.windows(2).any(|w| w == ["--title", "Ship the loop"]));
    assert!(args.windows(2).any(|w| w == ["--focus", "f-cur"]));
    assert!(args.windows(2).any(|w| w == ["--parent", "g-root"]));
}

#[tokio::test]
async fn task_create_and_status_forward_args() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_goals(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(db_path, "t-new", &argv_path, &stub_dir);

    let (status, body) = post_json(
        &router,
        "/v1/tasks",
        json!({ "goal": "g-root", "title": "write service" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["id"], "t-new");
    let args = std::fs::read_to_string(&argv_path).unwrap();
    assert!(args.contains("--goal"));
    assert!(args.contains("write service"));

    let (status, body) = post_json(&router, "/v1/tasks/t1/status", json!({ "status": "done" })).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["updated"], true);
    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert!(args.windows(2).any(|w| w == ["--status", "done"]));
    assert_eq!(args.last().copied(), Some("t1")); // id after `--`
}

#[tokio::test]
async fn observation_create_forwards_args_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_goals(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let router = test_app_with_arg_capture(db_path, "o-new", &argv_path, &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/observations",
        json!({ "body": "found a bug", "goal": "g-root", "source": "operator" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["id"], "o-new");
    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("observe"));
    assert!(args.windows(2).any(|w| w == ["--body", "found a bug"]));
    assert!(args.windows(2).any(|w| w == ["--goal", "g-root"]));
}

// --- Operations (WP-6 — premade autonomous operations) -----------------------

#[tokio::test]
async fn operations_list_parses_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db_goals(&dir);
    // The CLI prints a JSON array; the gateway parses it into `operations`.
    let stub = r#"[{"id":"elaborate","label":"Elaborate Goal","risk":"internal"}]"#;
    let router = test_app_with_stub(db_path, stub, &stub_dir);
    let (status, body) = get_json(&router, "/v1/operations").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["operations"][0]["id"], "elaborate");
}

#[tokio::test]
async fn operation_run_prepares_and_returns_201() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir); // has run r1
    // Stub prints the seeded run id so the prepare read-back succeeds. (argv is not
    // asserted here: operation_run dispatches twice — prepare + a detached
    // `run exec` — which would race on a shared argv file. The response body
    // proves prepare ran: r1 only resolves if `operation prepare` was invoked.)
    let router = test_app_with_stub(db_path, "r1", &stub_dir);
    let (status, body) = post_json(
        &router,
        "/v1/operations/elaborate/run",
        json!({ "goal_id": "g-root" }),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED);
    assert_eq!(body["executing"], true);
    assert_eq!(body["operation"], "elaborate");
    assert_eq!(body["run"]["id"], "r1");
}

#[tokio::test]
async fn operation_run_rejects_bad_agent() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = post_json(
        &router,
        "/v1/operations/elaborate/run",
        json!({ "goal_id": "g-root", "agent": "rogue" }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

// --- Phase 10.0.4: developer tool integrations (dispatch-only) ---

#[tokio::test]
async fn tool_call_empty_tool_is_rejected() {
    // require_arg must reject an empty tool name with 400 before any dispatch.
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, _body) = post_json(&router, "/v1/tools/calls", json!({ "tool": "" })).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn tool_manifests_returns_cli_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"manifests": [{"name": "workspace", "risk_level": "read"}]}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/tools/manifests").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["manifests"][0]["name"], "workspace");
}

// ---------------------------------------------------------------------------
// Phase 10.4-05 — PATCH /v1/config dispatch adapter + structured error mapping
// (D-022: the gateway shells to `atlas config patch`; no config schema/auth
// parsing/secret resolution/model-selection logic lives in Rust).
// ---------------------------------------------------------------------------

#[tokio::test]
async fn config_patch_dispatches_expected_revision_and_changes_json() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let stub_output = r#"{"schema_version":1,"revision":1,"provider":{"name":"openrouter","api_key":"env:OPENROUTER_API_KEY"}}"#;
    let router = test_app_with_arg_capture(db_path, stub_output, &argv_path, &stub_dir);

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({
            "expected_revision": 0,
            "changes": {"provider.model": "patched/model"}
        }),
    )
    .await;

    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["revision"], 1);

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    assert_eq!(args.first().copied(), Some("config"));
    assert_eq!(args.get(1).copied(), Some("patch"));
    let rev_idx = args
        .iter()
        .position(|a| *a == "--expected-revision")
        .expect("--expected-revision missing");
    assert_eq!(args.get(rev_idx + 1).copied(), Some("0"));
    let changes_idx = args
        .iter()
        .position(|a| *a == "--changes-json")
        .expect("--changes-json missing");
    // Changes must be ONE argv element — serde_json-serialized, never shell-interpolated
    // into multiple tokens.
    let changes_arg = args.get(changes_idx + 1).copied().unwrap();
    let parsed: Value = serde_json::from_str(changes_arg).unwrap();
    assert_eq!(parsed["provider.model"], "patched/model");
    assert_eq!(args.len(), changes_idx + 2, "changes-json leaked extra argv tokens");
}

#[tokio::test]
async fn config_patch_empty_changes_object_is_400_before_dispatch() {
    let dir = tempfile::tempdir().unwrap();
    // No stub configured — a dispatch here would fail to spawn and prove the
    // handler skipped the empty/non-object short-circuit.
    let router = test_app(seeded_db(&dir));
    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {} }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

#[tokio::test]
async fn config_patch_non_object_changes_is_400_before_dispatch() {
    let dir = tempfile::tempdir().unwrap();
    let router = test_app(seeded_db(&dir));
    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": "not-an-object" }),
    )
    .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "bad_request");
}

#[tokio::test]
async fn config_patch_value_with_spaces_stays_one_argv_element() {
    // Regression guard for shell-interpolation: a changes value containing
    // spaces/special chars must not split into multiple argv tokens.
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let db_path = seeded_db(&dir);
    let argv_path = stub_dir.path().join("argv.txt");
    let stub_output = r#"{"schema_version":1,"revision":1}"#;
    let router = test_app_with_arg_capture(db_path, stub_output, &argv_path, &stub_dir);

    let (status, _body) = patch_json(
        &router,
        "/v1/config",
        json!({
            "expected_revision": 0,
            "changes": {"cockpit.branding": "atlas; rm -rf /"}
        }),
    )
    .await;
    assert_eq!(status, StatusCode::OK);

    let argv = std::fs::read_to_string(&argv_path).unwrap();
    let args: Vec<&str> = argv.lines().collect();
    let changes_idx = args.iter().position(|a| *a == "--changes-json").unwrap();
    let changes_arg = args.get(changes_idx + 1).copied().unwrap();
    let parsed: Value = serde_json::from_str(changes_arg).unwrap();
    assert_eq!(parsed["cockpit.branding"], "atlas; rm -rf /");
    // Exactly one token holds the whole dangerous string — no extra argv entries.
    assert_eq!(args.len(), changes_idx + 2);
}

// ---------------------------------------------------------------------------
// Task 2 — structured 409/400 error mapping + secret guard
// ---------------------------------------------------------------------------

/// Build a test app whose atlas CLI stub fails (`config patch` style): writes
/// a structured `{"error": {...}}` JSON to stderr and exits with `exit_code`.
fn test_app_with_failing_stub(
    db_path: PathBuf,
    stderr_json: &str,
    exit_code: i32,
    dir: &tempfile::TempDir,
) -> axum::Router {
    let stub = dir.path().join("mock_atlas_fail.py");
    std::fs::write(
        &stub,
        format!(
            "import sys\nsys.stderr.write('{}')\nsys.exit({})\n",
            stderr_json.replace('\'', "\\'"),
            exit_code,
        ),
    )
    .unwrap();
    let python = if cfg!(windows) { "python" } else { "python3" };
    app(AppState {
        db_path,
        atlas_cmd: vec![python.to_string(), stub.to_string_lossy().to_string()],
        repo_root: PathBuf::from("."),
    })
}

#[tokio::test]
async fn config_patch_revision_conflict_maps_to_409() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let stderr_json = serde_json::json!({
        "error": {
            "code": "config_revision_conflict",
            "message": "config revision 0 is stale (current revision 3)",
            "remediation": "re-fetch GET /v1/config and retry with the current revision",
        },
        "current_revision": 3,
    })
    .to_string();
    let router = test_app_with_failing_stub(seeded_db(&dir), &stderr_json, 2, &stub_dir);

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.model": "x"} }),
    )
    .await;

    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(body["error"]["code"], "config_revision_conflict");
    assert_eq!(body["current_revision"], 3);
    assert!(body["error"]["remediation"].as_str().unwrap().len() > 0);
}

#[tokio::test]
async fn config_patch_validation_error_maps_to_400() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let stderr_json = serde_json::json!({
        "error": {
            "code": "config_invalid",
            "message": "runtime.iteration_budget must be >= 1",
            "remediation": "provide a positive integer",
            "field": "runtime.iteration_budget",
        },
    })
    .to_string();
    let router = test_app_with_failing_stub(seeded_db(&dir), &stderr_json, 1, &stub_dir);

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"runtime.iteration_budget": 0} }),
    )
    .await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "config_invalid");
    assert_eq!(body["error"]["field"], "runtime.iteration_budget");
}

#[tokio::test]
async fn config_patch_unknown_key_maps_to_400() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let stderr_json = serde_json::json!({
        "error": {
            "code": "config_schema_unsupported",
            "message": "unknown config key: provider.nope",
            "remediation": "use a recognized dotted config path",
        },
    })
    .to_string();
    let router = test_app_with_failing_stub(seeded_db(&dir), &stderr_json, 1, &stub_dir);

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.nope": "x"} }),
    )
    .await;

    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(body["error"]["code"], "config_schema_unsupported");
}

#[tokio::test]
async fn config_patch_unexpected_cli_failure_is_500() {
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    // Non-JSON stderr (e.g. a Python traceback) — an unstructured failure must
    // never be reported as a 400/409; it stays a generic 500.
    let router = test_app_with_failing_stub(
        seeded_db(&dir),
        "Traceback (most recent call last): boom",
        1,
        &stub_dir,
    );

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.model": "x"} }),
    )
    .await;

    assert_eq!(status, StatusCode::INTERNAL_SERVER_ERROR);
    assert_eq!(body["error"]["code"], "internal");
}

#[tokio::test]
async fn config_get_and_patch_never_contain_secret_sentinel() {
    let get_dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    // Sentinel that MUST NOT appear in either response body — the CLI itself
    // always masks secrets, but this proves the gateway forwards verbatim
    // (Rust performs no secret resolution) and does not introduce a leak path.
    const SECRET_SENTINEL: &str = "sk-should-never-leak-9f3c";
    let masked_snapshot = r#"{"schema_version":1,"revision":1,"provider":{"name":"openrouter","api_key":"env:OPENROUTER_API_KEY"}}"#;

    let get_router = test_app_with_stub(seeded_db(&get_dir), masked_snapshot, &stub_dir);
    let (status, body) = get_json(&get_router, "/v1/config").await;
    assert_eq!(status, StatusCode::OK);
    assert!(!body.to_string().contains(SECRET_SENTINEL));

    let patch_dir = tempfile::tempdir().unwrap();
    let patch_stub_dir = tempfile::tempdir().unwrap();
    let patch_router = test_app_with_stub(seeded_db(&patch_dir), masked_snapshot, &patch_stub_dir);
    let (status, body) = patch_json(
        &patch_router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.model": "x"} }),
    )
    .await;
    assert_eq!(status, StatusCode::OK);
    assert!(!body.to_string().contains(SECRET_SENTINEL));
}

#[tokio::test]
async fn config_view_top_level_compatibility_unaffected_by_patch_route() {
    // Existing GET /v1/config compatibility (provider/runtime top-level fields)
    // must remain green after PATCH wiring lands alongside it.
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let router = test_app_with_stub(
        seeded_db(&dir),
        r#"{"provider": {"name": "openrouter", "api_key": "env:OPENROUTER_API_KEY"}, "runtime": {"default_agent": "native"}}"#,
        &stub_dir,
    );
    let (status, body) = get_json(&router, "/v1/config").await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(body["provider"]["name"], "openrouter");
    assert_eq!(body["runtime"]["default_agent"], "native");
}

// ---------------------------------------------------------------------------
// Task 3 — cross-surface conformance smoke (fixture-level transport contract)
// ---------------------------------------------------------------------------

#[tokio::test]
async fn config_patch_then_get_reflects_same_revision_without_restart() {
    // Proves the gateway's PATCH/GET pair consumes one shared contract shape:
    // a patch's returned revision is visible to a subsequent GET against the
    // same stub fixture (no gateway-side caching of the snapshot).
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let snapshot_after_patch = r#"{"schema_version":1,"revision":1,"provider":{"name":"openrouter","model":"patched/model","api_key":"env:OPENROUTER_API_KEY"}}"#;
    let router = test_app_with_stub(seeded_db(&dir), snapshot_after_patch, &stub_dir);

    let (patch_status, patch_body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.model": "patched/model"} }),
    )
    .await;
    assert_eq!(patch_status, StatusCode::OK);
    assert_eq!(patch_body["revision"], 1);

    let (get_status, get_body) = get_json(&router, "/v1/config").await;
    assert_eq!(get_status, StatusCode::OK);
    assert_eq!(get_body["revision"], 1);
    assert_eq!(get_body["provider"]["model"], "patched/model");
}

#[tokio::test]
async fn config_patch_stale_second_writer_rejected_not_silently_applied() {
    // A second writer using an already-superseded revision must be rejected
    // (409), never silently accepted and overwrite the first writer's change.
    let dir = tempfile::tempdir().unwrap();
    let stub_dir = tempfile::tempdir().unwrap();
    let stderr_json = serde_json::json!({
        "error": {
            "code": "config_revision_conflict",
            "message": "config revision 0 is stale (current revision 1)",
            "remediation": "re-fetch GET /v1/config and retry with the current revision",
        },
        "current_revision": 1,
    })
    .to_string();
    let router = test_app_with_failing_stub(seeded_db(&dir), &stderr_json, 2, &stub_dir);

    let (status, body) = patch_json(
        &router,
        "/v1/config",
        json!({ "expected_revision": 0, "changes": {"provider.model": "stale-writer"} }),
    )
    .await;

    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(body["error"]["code"], "config_revision_conflict");
    assert_eq!(body["current_revision"], 1);
}
