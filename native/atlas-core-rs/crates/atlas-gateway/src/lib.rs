//! atlas-gateway — L2 ATLAS API gateway (Phase 7, D-022).
//!
//! Read-only REST surface over the shared ATLAS SQLite store plus an SSE
//! audit stream. Writes are out of scope here — they dispatch through the
//! `atlas` CLI contract. Loopback-only bind, no auth (v1.0 single operator).

pub mod db;

use axum::extract::{Path as AxPath, Query, Request, State};
use axum::http::{header, HeaderValue, Method, StatusCode};
use axum::middleware::{self, Next};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::{routing::{get, post}, Json, Router};
use futures_util::stream::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::OnceLock;
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

/// Default atlas CLI invocation from ATLAS_CLI, else "atlas" on PATH.
///
/// ATLAS_CLI may be a single program (the installed `atlas` console script on
/// PATH — the production default) or a multi-token command for dev, e.g.
/// "<python> -m atlas_runtime.cli.main". Tokens split on whitespace; a path
/// containing spaces must use the installed single-exe form.
pub fn default_atlas_cli() -> Vec<String> {
    match std::env::var("ATLAS_CLI") {
        Ok(v) if !v.trim().is_empty() => v.split_whitespace().map(str::to_string).collect(),
        _ => vec!["atlas".to_string()],
    }
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
                        // Final drain: events committed between the events-read
                        // and the status-read above would otherwise be dropped
                        // from the live stream.
                        let (db_path, run_id, cursor) =
                            (s.db_path.clone(), s.run_id.clone(), s.cursor);
                        if let Ok(Ok((late, late_cursor))) = tokio::task::spawn_blocking(
                            move || db::list_events(&db_path, &run_id, cursor, 500),
                        )
                        .await
                        {
                            s.cursor = late_cursor;
                            for ev in late {
                                s.pending.push_back(
                                    Event::default().event("audit").data(ev.to_string()),
                                );
                            }
                        }
                        s.pending.push_back(
                            Event::default()
                                .event("end")
                                .data(json!({"status": status}).to_string()),
                        );
                        s.done = true;
                    }
                }
                // DB went away mid-stream (or task panic): report and close.
                // Named "stream_error" — a plain "error" event name collides
                // with the EventSource transport-error event on the client.
                Ok(Err(e)) => {
                    let msg = match e {
                        db::DbError::Absent => "db_unavailable".to_string(),
                        db::DbError::Failed(m) => m,
                    };
                    s.pending.push_back(
                        Event::default()
                            .event("stream_error")
                            .data(json!({"error": msg}).to_string()),
                    );
                    s.done = true;
                }
                Err(e) => {
                    s.pending.push_back(
                        Event::default()
                            .event("stream_error")
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

/// Upper bound on a single CLI dispatch — a hung `atlas` process (DB lock
/// contention, stdin prompt) must not hang the HTTP request forever.
const DISPATCH_TIMEOUT: Duration = Duration::from_secs(30);

/// Reject empty/whitespace user input destined for CLI positional arguments.
/// Values starting with `-` are also rejected: even behind a `--` separator
/// they read as options to a human and signal a malformed request.
fn require_arg(value: &str, what: &'static str) -> Result<(), ApiError> {
    if value.trim().is_empty() {
        return Err(ApiError::BadRequest(what));
    }
    Ok(())
}

/// Dispatch a write to the `atlas` CLI. Returns trimmed stdout on success or
/// ApiError on non-zero exit / spawn failure / timeout.
///
/// Callers pass user-controlled values AFTER a `--` separator so click/typer
/// never parses request data as options (argument-injection guard).
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
    // Dropping the output() future on timeout kills the child.
    cmd.kill_on_drop(true);
    let output = tokio::time::timeout(DISPATCH_TIMEOUT, cmd.output())
        .await
        .map_err(|_| ApiError::Internal("atlas command timed out".into()))?
        .map_err(|e| ApiError::Internal(format!("failed to spawn atlas: {e}")))?;
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
    /// Optional project id — mission runs in that project's working directory.
    project: Option<String>,
}

async fn create_mission(
    State(state): State<AppState>,
    Json(body): Json<CreateMissionBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let title = body.title.clone();
    let intent = body.intent.clone().unwrap_or_default();
    require_arg(&title, "title must be non-empty")?;
    let project = body
        .project
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let mut args: Vec<&str> = vec!["mission", "create", "--title", &title, "--intent", &intent];
    if let Some(pid) = project {
        args.push("--project");
        args.push(pid);
    }
    let id = dispatch_atlas(&state.atlas_cmd, &args).await?;
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

#[derive(Deserialize, Default)]
struct StartRunBody {
    /// Agent runtime selector: "native" (default) or "claude_code". Mirrors the
    /// `atlas mission run --agent` flag (P4 — modular agents). The gateway stays
    /// record-only: it dispatches the run row write, never `--execute`.
    agent: Option<String>,
}

async fn start_run(
    State(state): State<AppState>,
    AxPath(mission_id): AxPath<String>,
    // Optional JSON body — an empty body (no agent selection) defaults to "native".
    body: Option<Json<StartRunBody>>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&mission_id, "mission id must be non-empty")?;
    let agent = body
        .and_then(|Json(b)| b.agent)
        .map(|a| a.trim().to_string())
        .filter(|a| !a.is_empty())
        .unwrap_or_else(|| "native".to_string());
    if agent != "native" && agent != "claude_code" {
        return Err(ApiError::BadRequest(
            "agent must be 'native' or 'claude_code'",
        ));
    }
    let run_id = dispatch_atlas(
        &state.atlas_cmd,
        &["mission", "run", "--agent", &agent, "--", &mission_id],
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
// Wiki write + detail handlers (Phase 8 — D-022 dispatch pattern)
// ---------------------------------------------------------------------------

async fn wiki_page_detail(
    State(state): State<AppState>,
    AxPath(slug): AxPath<String>,
) -> ApiResult {
    let path = state.db_path.clone();
    let found = blocking(move || db::get_wiki_page(&path, &slug)).await?;
    match found {
        Some(page) => Ok(Json(json!({ "page": page }))),
        None => Err(ApiError::NotFound("wiki page")),
    }
}

#[derive(Deserialize)]
struct CreateWikiPageBody {
    slug: String,
    title: String,
    body: String,
}

async fn wiki_create(
    State(state): State<AppState>,
    Json(body): Json<CreateWikiPageBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    let slug = body.slug;
    let title = body.title;
    let content = body.body;
    require_arg(&slug, "slug must be non-empty")?;
    // The CLI normalizes the slug (lowercase, spaces→dashes) and echoes the
    // canonical form to stdout — read back with THAT, not the request slug.
    let canonical = dispatch_atlas(
        &state.atlas_cmd,
        &["wiki", "update", "--title", &title, "--body", &content, "--", &slug],
    )
    .await?;
    let path = state.db_path.clone();
    let slug_clone = if canonical.is_empty() { slug.clone() } else { canonical };
    let found = blocking(move || db::get_wiki_page(&path, &slug_clone)).await?;
    match found {
        Some(page) => Ok((StatusCode::CREATED, Json(json!({ "page": page })))),
        None => Err(ApiError::Internal(format!(
            "wiki page '{slug}' created but not found in db"
        ))),
    }
}

#[derive(Deserialize)]
struct UpdateWikiPageBody {
    title: Option<String>,
    body: Option<String>,
}

async fn wiki_update(
    State(state): State<AppState>,
    AxPath(slug): AxPath<String>,
    Json(body): Json<UpdateWikiPageBody>,
) -> ApiResult {
    // Read current page to merge optional fields.
    let path = state.db_path.clone();
    let slug_clone = slug.clone();
    let current = blocking(move || db::get_wiki_page(&path, &slug_clone)).await?;
    let current = match current {
        Some(p) => p,
        None => return Err(ApiError::NotFound("wiki page")),
    };
    let merged_title = body
        .title
        .unwrap_or_else(|| current["title"].as_str().unwrap_or("").to_string());
    let merged_body = body
        .body
        .unwrap_or_else(|| current["body"].as_str().unwrap_or("").to_string());
    dispatch_atlas(
        &state.atlas_cmd,
        &["wiki", "update", "--title", &merged_title, "--body", &merged_body, "--", &slug],
    )
    .await?;
    let path = state.db_path.clone();
    let slug_clone = slug.clone();
    let found = blocking(move || db::get_wiki_page(&path, &slug_clone)).await?;
    match found {
        Some(page) => Ok(Json(json!({ "page": page }))),
        None => Err(ApiError::Internal(format!(
            "wiki page '{slug}' updated but not found in db"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Model registry handler (Phase 8 — D-017 read-only model panel)
// ---------------------------------------------------------------------------

async fn models_list(
    State(state): State<AppState>,
    Query(params): Query<ListParams>,
) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 100, 500);
    let models = blocking(move || db::list_models(&path, limit)).await?;
    let count = models.len();
    Ok(Json(json!({ "models": models, "count": count })))
}

// ---------------------------------------------------------------------------
// Projects handlers (P3 — folder-backed working directories)
// ---------------------------------------------------------------------------

async fn projects_list(
    State(state): State<AppState>,
    Query(params): Query<ListParams>,
) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 100, 500);
    let projects = blocking(move || db::list_projects(&path, limit)).await?;
    let count = projects.len();
    Ok(Json(json!({ "projects": projects, "count": count })))
}

async fn project_detail(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let path = state.db_path.clone();
    let found = blocking(move || db::get_project(&path, &id)).await?;
    match found {
        Some((project, missions)) => Ok(Json(json!({ "project": project, "missions": missions }))),
        None => Err(ApiError::NotFound("project")),
    }
}

#[derive(Deserialize)]
struct CreateProjectBody {
    name: String,
    path: String,
}

/// Shared create/register dispatch — `sub` is "create" (mkdir new folder) or
/// "register" (adopt existing folder). Both go through the `atlas` CLI contract.
async fn dispatch_project(
    state: &AppState,
    sub: &str,
    name: &str,
    dir: &str,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(name, "name must be non-empty")?;
    require_arg(dir, "path must be non-empty")?;
    let id = dispatch_atlas(
        &state.atlas_cmd,
        &["project", sub, "--name", name, "--path", dir],
    )
    .await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_project(&path, &id_clone)).await?;
    match found {
        Some((project, missions)) => Ok((
            StatusCode::CREATED,
            Json(json!({ "project": project, "missions": missions })),
        )),
        None => Err(ApiError::Internal(format!(
            "project '{id}' created but not found in db"
        ))),
    }
}

async fn projects_create(
    State(state): State<AppState>,
    Json(body): Json<CreateProjectBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    dispatch_project(&state, "create", &body.name, &body.path).await
}

async fn projects_register(
    State(state): State<AppState>,
    Json(body): Json<CreateProjectBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    dispatch_project(&state, "register", &body.name, &body.path).await
}

// ---------------------------------------------------------------------------
// Modules handlers (Decision 3b — optional activatable modules)
// ---------------------------------------------------------------------------

async fn modules_list(State(state): State<AppState>) -> ApiResult {
    let path = state.db_path.clone();
    let modules = blocking(move || db::list_modules(&path)).await?;
    let count = modules.len();
    Ok(Json(json!({ "modules": modules, "count": count })))
}

/// Toggle a module via the `atlas` CLI (writes go through the CLI contract), then
/// read the updated row back. `sub` is "activate" or "deactivate".
async fn module_set_active(state: &AppState, id: &str, sub: &str) -> ApiResult {
    require_arg(id, "module id must be non-empty")?;
    dispatch_atlas(&state.atlas_cmd, &["module", sub, "--", id]).await?;
    let path = state.db_path.clone();
    let id_clone = id.to_string();
    let found = blocking(move || db::get_module(&path, &id_clone)).await?;
    match found {
        Some(module) => Ok(Json(json!({ "module": module }))),
        None => Err(ApiError::NotFound("module")),
    }
}

async fn module_activate(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    module_set_active(&state, &id, "activate").await
}

async fn module_deactivate(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    module_set_active(&state, &id, "deactivate").await
}

// ---------------------------------------------------------------------------
// Run cancel handler (Phase 8 — Surface 2 run monitoring)
// ---------------------------------------------------------------------------

async fn cancel_run(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
) -> ApiResult {
    require_arg(&id, "mission id must be non-empty")?;
    dispatch_atlas(&state.atlas_cmd, &["mission", "cancel", "--", &id]).await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_mission(&path, &id_clone)).await?;
    match found {
        Some((mission, runs)) => Ok(Json(json!({
            "mission": mission,
            "runs": runs,
            "message": "run cancelled",
        }))),
        None => Err(ApiError::Internal(format!(
            "mission '{id}' cancel dispatched but not found in db"
        ))),
    }
}

// ---------------------------------------------------------------------------
// CORS (cockpit dev/preview + Phase 10 Tauri shell are cross-origin)
// ---------------------------------------------------------------------------

/// Allowed browser origins. The gateway binds loopback-only, but browsers on
/// the same machine enforce the same-origin policy, so the cockpit served
/// from the Vite dev/preview server (or the Tauri WebView in Phase 10) needs
/// explicit CORS grants. An allowlist — never a wildcard — keeps arbitrary
/// websites from scripting the local API (DNS-rebinding / drive-by-localhost).
/// Extend via ATLAS_CORS_ORIGINS (comma-separated).
fn allowed_origins() -> &'static Vec<String> {
    static ORIGINS: OnceLock<Vec<String>> = OnceLock::new();
    ORIGINS.get_or_init(|| {
        let mut origins: Vec<String> = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "tauri://localhost",
        ]
        .iter()
        .map(|s| s.to_string())
        .collect();
        if let Ok(extra) = std::env::var("ATLAS_CORS_ORIGINS") {
            origins.extend(
                extra
                    .split(',')
                    .map(str::trim)
                    .filter(|s| !s.is_empty())
                    .map(String::from),
            );
        }
        origins
    })
}

async fn cors(req: Request, next: Next) -> Response {
    let origin = req.headers().get(header::ORIGIN).cloned();
    let allowed = origin
        .as_ref()
        .and_then(|o| o.to_str().ok())
        .map(|o| allowed_origins().iter().any(|a| a == o))
        .unwrap_or(false);

    // Only short-circuit genuine CORS preflights; a plain OPTIONS request
    // (no Access-Control-Request-Method) still reaches the router.
    let is_preflight = req.method() == Method::OPTIONS
        && req
            .headers()
            .contains_key(header::ACCESS_CONTROL_REQUEST_METHOD);
    let mut res = if is_preflight {
        StatusCode::NO_CONTENT.into_response()
    } else {
        next.run(req).await
    };

    // Vary on Origin unconditionally (append, not insert) — responses to
    // disallowed/absent origins must not be cacheable across origins either.
    res.headers_mut()
        .append(header::VARY, HeaderValue::from_static("Origin"));

    if allowed {
        let headers = res.headers_mut();
        // Unwrap is safe: origin was already validated as a present header value.
        headers.insert(header::ACCESS_CONTROL_ALLOW_ORIGIN, origin.unwrap());
        headers.insert(
            header::ACCESS_CONTROL_ALLOW_METHODS,
            HeaderValue::from_static("GET, POST, PUT, OPTIONS"),
        );
        headers.insert(
            header::ACCESS_CONTROL_ALLOW_HEADERS,
            HeaderValue::from_static("content-type"),
        );
        headers.insert(
            header::ACCESS_CONTROL_MAX_AGE,
            HeaderValue::from_static("3600"),
        );
    }
    res
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
        .route("/v1/missions/{id}/cancel", post(cancel_run))
        .route("/v1/runs/{id}", get(run_detail))
        .route("/v1/runs/{id}/events", get(run_events))
        .route("/v1/runs/{id}/stream", get(run_stream))
        .route("/v1/wiki/pages", get(wiki_pages).post(wiki_create))
        .route("/v1/wiki/pages/{slug}", get(wiki_page_detail).put(wiki_update))
        .route("/v1/wiki/search", get(wiki_search))
        .route("/v1/models", get(models_list))
        .route("/v1/projects", get(projects_list).post(projects_create))
        .route("/v1/projects/register", post(projects_register))
        .route("/v1/modules", get(modules_list))
        .route("/v1/modules/{id}/activate", post(module_activate))
        .route("/v1/modules/{id}/deactivate", post(module_deactivate))
        .route("/v1/projects/{id}", get(project_detail))
        .layer(middleware::from_fn(cors))
        .with_state(state)
}
