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
