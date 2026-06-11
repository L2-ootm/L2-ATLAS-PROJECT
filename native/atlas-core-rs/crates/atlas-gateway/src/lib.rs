//! atlas-gateway — L2 ATLAS API gateway (Phase 7, D-022).
//!
//! Read-only REST surface over the shared ATLAS SQLite store plus an SSE
//! audit stream. Writes are out of scope here — they dispatch through the
//! `atlas` CLI contract. Loopback-only bind, no auth (v1.0 single operator).

pub mod db;

use axum::extract::{Path as AxPath, Query, State};
use axum::http::StatusCode;
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::{routing::{get, post}, Json, Router};
use futures_util::stream::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::time::Duration;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// SSE poll interval (PHASE_7_8_READINESS: rowid-cursor poll ≤500 ms).
const STREAM_POLL: Duration = Duration::from_millis(500);

#[derive(Clone)]
pub struct AppState {
    pub db_path: PathBuf,
    /// Atlas CLI invocation prefix: first element is the program, rest are
    /// pre-arguments (e.g. ["atlas"] in production, ["python", "stub.py"] in
    /// tests). Write handlers append subcommand + flags after these.
    pub atlas_cmd: Vec<String>,
}

/// Default atlas CLI path: ATLAS_CLI env var or "atlas" on PATH.
pub fn default_atlas_cli() -> Vec<String> {
    vec![std::env::var("ATLAS_CLI").unwrap_or_else(|_| "atlas".to_string())]
}

/// Resolve the ATLAS SQLite database path: $ATLAS_DB or ~/.atlas/atlas.db
/// (same default as the Python `atlas` CLI — one shared store).
pub fn default_db_path() -> PathBuf {
    if let Some(p) = std::env::var_os("ATLAS_DB") {
        return PathBuf::from(p);
    }
    let home = std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_default();
    home.join(".atlas").join("atlas.db")
}

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

enum ApiError {
    DbAbsent,
    Db(String),
    NotFound(&'static str),
    BadRequest(&'static str),
    Internal(String),
}

impl From<db::DbError> for ApiError {
    fn from(e: db::DbError) -> Self {
        match e {
            db::DbError::Absent => ApiError::DbAbsent,
            db::DbError::Failed(msg) => ApiError::Db(msg),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            ApiError::DbAbsent => (
                StatusCode::SERVICE_UNAVAILABLE,
                "db_unavailable",
                "ATLAS database not found (no missions recorded yet?)".to_string(),
            ),
            ApiError::Db(msg) => (StatusCode::SERVICE_UNAVAILABLE, "db_error", msg),
            ApiError::NotFound(what) => (
                StatusCode::NOT_FOUND,
                "not_found",
                format!("{what} not found"),
            ),
            ApiError::BadRequest(msg) => (StatusCode::BAD_REQUEST, "bad_request", msg.to_string()),
            ApiError::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, "internal", msg),
        };
        let body = Json(json!({ "error": { "code": code, "message": message } }));
        (status, body).into_response()
    }
}

type ApiResult = Result<Json<Value>, ApiError>;

/// Run a blocking rusqlite call off the async runtime.
async fn blocking<T, F>(f: F) -> Result<T, ApiError>
where
    T: Send + 'static,
    F: FnOnce() -> Result<T, db::DbError> + Send + 'static,
{
    tokio::task::spawn_blocking(f)
        .await
        .map_err(|e| ApiError::Internal(e.to_string()))?
        .map_err(ApiError::from)
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

async fn health(State(state): State<AppState>) -> Json<Value> {
    let path = state.db_path.clone();
    let db = tokio::task::spawn_blocking(move || db::status(&path))
        .await
        .unwrap_or("error");
    Json(json!({
        "status": "ok",
        "service": "atlas-gateway",
        "version": VERSION,
        "db": db,
    }))
}

#[derive(Deserialize)]
struct ListParams {
    limit: Option<i64>,
}

fn clamp_limit(limit: Option<i64>, default: i64, max: i64) -> i64 {
    limit.unwrap_or(default).clamp(1, max)
}

async fn missions_list(
    State(state): State<AppState>,
    Query(params): Query<ListParams>,
) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 100, 500);
    let missions = blocking(move || db::list_missions(&path, limit)).await?;
    let count = missions.len();
    Ok(Json(json!({ "missions": missions, "count": count })))
}

async fn mission_detail(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let path = state.db_path.clone();
    let found = blocking(move || db::get_mission(&path, &id)).await?;
    match found {
        Some((mission, runs)) => Ok(Json(json!({ "mission": mission, "runs": runs }))),
        None => Err(ApiError::NotFound("mission")),
    }
}

async fn run_detail(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let path = state.db_path.clone();
    let found = blocking(move || db::get_run(&path, &id)).await?;
    match found {
        Some(run) => Ok(Json(json!({ "run": run }))),
        None => Err(ApiError::NotFound("run")),
    }
}

#[derive(Deserialize)]
struct EventParams {
    after: Option<i64>,
    limit: Option<i64>,
}

async fn run_events(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    Query(params): Query<EventParams>,
) -> ApiResult {
    let path = state.db_path.clone();
    let run_id = id.clone();
    let exists = blocking(move || db::run_status(&path, &run_id)).await?;
    if exists.is_none() {
        return Err(ApiError::NotFound("run"));
    }
    let path = state.db_path.clone();
    let after = params.after.unwrap_or(0).max(0);
    let limit = clamp_limit(params.limit, 200, 1000);
    let run_id = id.clone();
    let (events, cursor) = blocking(move || db::list_events(&path, &run_id, after, limit)).await?;
    Ok(Json(json!({
        "run_id": id,
        "events": events,
        "next_cursor": cursor,
    })))
}

#[derive(Deserialize)]
struct SearchParams {
    q: Option<String>,
    limit: Option<i64>,
}

async fn wiki_search(
    State(state): State<AppState>,
    Query(params): Query<SearchParams>,
) -> ApiResult {
    let q = match params.q.as_deref().map(str::trim) {
        Some(q) if !q.is_empty() => q.to_string(),
        _ => return Err(ApiError::BadRequest("missing query parameter: q")),
    };
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 20, 100);
    let query = q.clone();
    let results = blocking(move || db::wiki_search(&path, &query, limit)).await?;
    Ok(Json(json!({ "query": q, "results": results })))
}

// ---------------------------------------------------------------------------
// SSE audit stream
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct StreamParams {
    after: Option<i64>,
}

/// Poll-based audit event stream for a run. Emits `audit` events as they
/// land in SQLite (rowid cursor, 500 ms poll) and a final `end` event once
/// the run leaves `running` with no events pending. The stream stops on
/// client disconnect (the body future is dropped).
async fn run_stream(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    Query(params): Query<StreamParams>,
) -> Result<Sse<impl Stream<Item = Result<Event, std::convert::Infallible>>>, ApiError> {
    let path = state.db_path.clone();
    let run_id = id.clone();
    let status = blocking(move || db::run_status(&path, &run_id)).await?;
    if status.is_none() {
        return Err(ApiError::NotFound("run"));
    }

    struct StreamState {
        db_path: PathBuf,
        run_id: String,
        cursor: i64,
        pending: VecDeque<Event>,
        first_poll: bool,
        done: bool,
    }

    let initial = StreamState {
        db_path: state.db_path.clone(),
        run_id: id,
        cursor: params.after.unwrap_or(0).max(0),
        pending: VecDeque::new(),
        first_poll: true,
        done: false,
    };

    let stream = futures_util::stream::unfold(initial, |mut s| async move {
        loop {
            if let Some(event) = s.pending.pop_front() {
                return Some((Ok(event), s));
            }
            if s.done {
                return None;
            }
            if !s.first_poll {
                tokio::time::sleep(STREAM_POLL).await;
            }
            s.first_poll = false;

            let (db_path, run_id, cursor) = (s.db_path.clone(), s.run_id.clone(), s.cursor);
            let polled = tokio::task::spawn_blocking(move || {
                let events = db::list_events(&db_path, &run_id, cursor, 500)?;
                let status = db::run_status(&db_path, &run_id)?;
                Ok::<_, db::DbError>((events, status))
            })
            .await;

            match polled {
                Ok(Ok(((events, next_cursor), status))) => {
                    s.cursor = next_cursor;
                    let had_events = !events.is_empty();
                    for ev in events {
                        s.pending
                            .push_back(Event::default().event("audit").data(ev.to_string()));
                    }
                    let terminal = !matches!(status.as_deref(), Some("running") | Some("pending"));
                    if terminal && !had_events {
                        s.pending.push_back(
                            Event::default()
                                .event("end")
                                .data(json!({"status": status}).to_string()),
                        );
                        s.done = true;
                    }
                }
                // DB went away mid-stream (or task panic): report and close.
                Ok(Err(e)) => {
                    let msg = match e {
                        db::DbError::Absent => "db_unavailable".to_string(),
                        db::DbError::Failed(m) => m,
                    };
                    s.pending.push_back(
                        Event::default()
                            .event("error")
                            .data(json!({"error": msg}).to_string()),
                    );
                    s.done = true;
                }
                Err(e) => {
                    s.pending.push_back(
                        Event::default()
                            .event("error")
                            .data(json!({"error": e.to_string()}).to_string()),
                    );
                    s.done = true;
                }
            }
        }
    });

    Ok(Sse::new(stream).keep_alive(KeepAlive::new().interval(Duration::from_secs(15))))
}

async fn wiki_pages(
    State(state): State<AppState>,
    Query(params): Query<ListParams>,
) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 100, 500);
    let pages = blocking(move || db::list_wiki_pages(&path, limit)).await?;
    let count = pages.len();
    Ok(Json(json!({ "pages": pages, "count": count })))
}

// ---------------------------------------------------------------------------
// Write dispatch (POST routes — delegate to `atlas` CLI, no Rust business logic)
// ---------------------------------------------------------------------------

/// Dispatch a write to the `atlas` CLI. Returns trimmed stdout on success or
/// ApiError on non-zero exit / spawn failure.
async fn dispatch_atlas(
    atlas_cmd: &[String],
    args: &[&str],
) -> Result<String, ApiError> {
    if atlas_cmd.is_empty() {
        return Err(ApiError::Internal("atlas_cmd is empty".into()));
    }
    let mut cmd = tokio::process::Command::new(&atlas_cmd[0]);
    for pre in &atlas_cmd[1..] {
        cmd.arg(pre);
    }
    for arg in args {
        cmd.arg(arg);
    }
    let output = cmd.output().await.map_err(|e| {
        ApiError::Internal(format!("failed to spawn atlas: {e}"))
    })?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(ApiError::Internal(format!(
            "atlas command failed: {stderr}"
        )));
    }
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

#[derive(Deserialize)]
struct CreateMissionBody {
    title: String,
    intent: Option<String>,
}

async fn create_mission(
    State(state): State<AppState>,
    Json(body): Json<CreateMissionBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let title = body.title;
    let intent = body.intent.unwrap_or_default();
    let id = dispatch_atlas(
        &state.atlas_cmd,
        &["mission", "create", "--title", &title, "--intent", &intent],
    )
    .await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_mission(&path, &id_clone)).await?;
    match found {
        Some((mission, runs)) => Ok((
            StatusCode::CREATED,
            Json(json!({ "mission": mission, "runs": runs })),
        )),
        None => Err(ApiError::Internal(format!(
            "mission '{id}' created but not found in db"
        ))),
    }
}

async fn start_run(
    State(state): State<AppState>,
    AxPath(mission_id): AxPath<String>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let run_id = dispatch_atlas(
        &state.atlas_cmd,
        &["mission", "run", &mission_id],
    )
    .await?;
    let path = state.db_path.clone();
    let run_id_clone = run_id.clone();
    let found = blocking(move || db::get_run(&path, &run_id_clone)).await?;
    match found {
        Some(run) => Ok((StatusCode::CREATED, Json(json!({ "run": run })))),
        None => Err(ApiError::Internal(format!(
            "run '{run_id}' started but not found in db"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

pub fn app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/v1/missions", get(missions_list).post(create_mission))
        .route("/v1/missions/{id}", get(mission_detail))
        .route("/v1/missions/{id}/run", post(start_run))
        .route("/v1/runs/{id}", get(run_detail))
        .route("/v1/runs/{id}/events", get(run_events))
        .route("/v1/runs/{id}/stream", get(run_stream))
        .route("/v1/wiki/pages", get(wiki_pages))
        .route("/v1/wiki/search", get(wiki_search))
        .with_state(state)
}
