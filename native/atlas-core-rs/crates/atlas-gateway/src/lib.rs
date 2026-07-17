//! atlas-gateway — L2 ATLAS API gateway (Phase 7, D-022).
//!
//! Read-only REST surface over the shared ATLAS SQLite store plus an SSE
//! audit stream. Writes are out of scope here — they dispatch through the
//! `atlas` CLI contract. Loopback-only bind, no auth (v1.0 single operator).

pub mod db;

use axum::extract::{Path as AxPath, Query, Request, State};
use axum::http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use axum::middleware::{self, Next};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{Html, IntoResponse, Response};
use axum::{
    routing::{get, post},
    Json, Router,
};
use futures_util::stream::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::OnceLock;
use std::time::Duration;
use tokio::io::AsyncWriteExt;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// SSE poll interval (PHASE_7_8_READINESS: rowid-cursor poll ≤500 ms).
///
/// Lowered from 500ms once the Python runtime started emitting coalesced
/// `llm_delta` audit rows (~150ms cadence, `native.py::_DeltaBuffer`) — at
/// 500ms the deltas would still arrive in visible bursts rather than a
/// steady stream. 200ms keeps relay latency under the delta cadence without
/// meaningfully increasing DB poll load (single-operator, few concurrent runs).
const STREAM_POLL: Duration = Duration::from_millis(200);

#[derive(Clone)]
pub struct AppState {
    pub db_path: PathBuf,
    /// Atlas CLI invocation prefix: first element is the program, rest are
    /// pre-arguments (e.g. ["atlas"] in production, ["python", "stub.py"] in
    /// tests). Write handlers append subcommand + flags after these.
    pub atlas_cmd: Vec<String>,
    /// Project root passed to CLI commands that scan the tree (e.g.
    /// `atlas graph build --root <repo_root>`). The gateway's CWD is its own
    /// crate dir, so a bare "." would scan the wrong tree and return nothing.
    pub repo_root: PathBuf,
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

/// Resolve the project root for tree-scanning CLI commands.
///
/// Priority: `$ATLAS_REPO_ROOT` (set by the Python gateway launcher,
/// `gateway_control._child_env`) → derived from the running executable
/// (`native/atlas-core-rs/target/<profile>/atlas-gateway` → 5 ancestors up) →
/// `"."` as a last resort (preserves the legacy behaviour).
pub fn default_repo_root() -> PathBuf {
    if let Some(p) = std::env::var_os("ATLAS_REPO_ROOT") {
        let p = PathBuf::from(p);
        if !p.as_os_str().is_empty() {
            return p;
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(root) = exe.ancestors().nth(5) {
            return root.to_path_buf();
        }
    }
    PathBuf::from(".")
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
    /// A structured error body parsed verbatim from a CLI's stderr JSON
    /// (e.g. `atlas config patch`'s `{"error": {...}, "current_revision": N}`).
    /// The gateway maps the CLI's machine-readable `code` to an HTTP status
    /// (409 conflict / 400 validation) but never inspects config fields —
    /// the JSON body itself is forwarded unchanged (D-022).
    Structured(StatusCode, Value),
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
        if let ApiError::Structured(status, body) = self {
            return (status, Json(body)).into_response();
        }
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
            ApiError::Structured(..) => unreachable!("handled above"),
        };
        let body = Json(json!({ "error": { "code": code, "message": message } }));
        (status, body).into_response()
    }
}

type ApiResult = Result<Json<Value>, ApiError>;
const SURFACE_OWNER_HEADER: &str = "x-atlas-surface-owner";

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

async fn require_surface_owner(
    state: &AppState,
    headers: &HeaderMap,
    session_id: &str,
) -> Result<(), ApiError> {
    let token = headers
        .get(SURFACE_OWNER_HEADER)
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default()
        .to_owned();
    let path = state.db_path.clone();
    let id = session_id.to_owned();
    if blocking(move || db::surface_owner_matches(&path, &id, &token)).await? {
        return Ok(());
    }
    Err(ApiError::Structured(
        StatusCode::FORBIDDEN,
        json!({
            "error": {
                "code": "surface_owner_mismatch",
                "message": "surface owner token is missing or stale",
                "remediation": "use the token returned by create/resume or create a new session"
            }
        }),
    ))
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

#[derive(Deserialize)]
struct ArchiveMissionBody {
    delete_after_days: Option<i64>,
}

async fn archive_mission(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    body: Option<Json<ArchiveMissionBody>>,
) -> ApiResult {
    require_arg(&id, "mission id must be non-empty")?;
    let days = body
        .and_then(|Json(b)| b.delete_after_days)
        .unwrap_or(30)
        .clamp(1, 3650);
    let days_arg = days.to_string();
    dispatch_atlas(
        &state.atlas_cmd,
        &[
            "mission",
            "archive",
            "--delete-after-days",
            &days_arg,
            "--",
            &id,
        ],
    )
    .await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_mission(&path, &id_clone)).await?;
    match found {
        Some((mission, runs)) => Ok(Json(json!({ "mission": mission, "runs": runs }))),
        None => Err(ApiError::Internal(format!(
            "mission '{id}' archive dispatched but not found in db"
        ))),
    }
}

async fn purge_archived_missions(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["mission", "purge-archived"]).await?;
    let deleted = out.trim().parse::<i64>().unwrap_or(0);
    Ok(Json(json!({ "deleted": deleted })))
}

/// GET /v1/runs — cross-mission run feed, one JOIN query (no N+1 fan-out).
async fn runs_list(State(state): State<AppState>, Query(params): Query<ListParams>) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 100, 500);
    let runs = blocking(move || db::list_runs(&path, limit)).await?;
    let count = runs.len();
    Ok(Json(json!({ "runs": runs, "count": count })))
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
                let terminal = !matches!(status.as_deref(), Some("running") | Some("pending"));
                let loop_snapshot = if terminal {
                    db::mission_loop_stream_snapshot(&db_path, &run_id)?
                } else {
                    None
                };
                Ok::<_, db::DbError>((events, status, loop_snapshot))
            })
            .await;

            match polled {
                Ok(Ok(((events, next_cursor), status, loop_snapshot))) => {
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
                        if let Ok(Ok((late, late_cursor))) =
                            tokio::task::spawn_blocking(move || {
                                db::list_events(&db_path, &run_id, cursor, 500)
                            })
                            .await
                        {
                            s.cursor = late_cursor;
                            for ev in late {
                                s.pending.push_back(
                                    Event::default().event("audit").data(ev.to_string()),
                                );
                            }
                        }
                        let mut should_close = loop_snapshot.is_none();
                        if let Some(snapshot) = loop_snapshot {
                            match snapshot.state.as_str() {
                                "active" => {
                                    should_close = false;
                                    if snapshot.last_run_id.as_deref() == Some(s.run_id.as_str()) {
                                        if let Some(new_run_id) = snapshot.newer_running_run_id {
                                            let prior_run_id =
                                                std::mem::replace(&mut s.run_id, new_run_id);
                                            s.cursor = 0;
                                            s.pending.push_back(
                                                Event::default().event("continuation").data(
                                                    json!({
                                                        "prior_run_id": prior_run_id,
                                                        "run_id": s.run_id.as_str(),
                                                    })
                                                    .to_string(),
                                                ),
                                            );
                                        }
                                    }
                                }
                                "done" | "paused" | "exhausted" | "failed" => {
                                    should_close = true;
                                }
                                _ => {
                                    // Unknown loop states are not terminal. Keep the
                                    // stream open rather than truncating a live loop.
                                    should_close = false;
                                }
                            }
                        }
                        if should_close {
                            s.pending.push_back(
                                Event::default()
                                    .event("end")
                                    .data(json!({"status": status}).to_string()),
                            );
                            s.done = true;
                        }
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

async fn wiki_pages(State(state): State<AppState>, Query(params): Query<ListParams>) -> ApiResult {
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
const CONSOLE_DISPATCH_TIMEOUT: Duration = Duration::from_secs(180);

/// The atlas CLI is a console-subsystem program (python.exe). When the gateway
/// runs detached (no console of its own — `atlas gateway start`), each child
/// spawn makes Windows allocate a NEW console window, so every dispatched route
/// flashes a terminal that also steals focus from the cockpit. CREATE_NO_WINDOW
/// suppresses that console without affecting stdout capture or GUI children
/// (e.g. the folder-picker dialog still shows). No-op on non-Windows.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[cfg(windows)]
fn hide_console_tokio(cmd: &mut tokio::process::Command) {
    cmd.creation_flags(CREATE_NO_WINDOW);
}
#[cfg(not(windows))]
fn hide_console_tokio(_cmd: &mut tokio::process::Command) {}

#[cfg(windows)]
fn hide_console_std(cmd: &mut std::process::Command) {
    use std::os::windows::process::CommandExt;
    cmd.creation_flags(CREATE_NO_WINDOW);
}
#[cfg(not(windows))]
fn hide_console_std(_cmd: &mut std::process::Command) {}

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
async fn dispatch_atlas(atlas_cmd: &[String], args: &[&str]) -> Result<String, ApiError> {
    dispatch_atlas_with_timeout(atlas_cmd, args, DISPATCH_TIMEOUT).await
}

/// Dispatch a write and return the raw child `Output` (exit status, stdout,
/// stderr) instead of collapsing a non-zero exit to a generic `ApiError`.
/// For callers (e.g. `config_patch`) that need to parse a CLI's structured
/// JSON error from stderr to map specific failure codes (409/400) rather
/// than always reporting 500.
async fn dispatch_atlas_raw(
    atlas_cmd: &[String],
    args: &[&str],
    timeout: Duration,
) -> Result<std::process::Output, ApiError> {
    if atlas_cmd.is_empty() {
        return Err(ApiError::Internal("atlas_cmd is empty".into()));
    }
    let mut cmd = tokio::process::Command::new(&atlas_cmd[0]);
    hide_console_tokio(&mut cmd);
    for pre in &atlas_cmd[1..] {
        cmd.arg(pre);
    }
    for arg in args {
        cmd.arg(arg);
    }
    cmd.kill_on_drop(true);
    tokio::time::timeout(timeout, cmd.output())
        .await
        .map_err(|_| ApiError::Internal("atlas command timed out".into()))?
        .map_err(|e| ApiError::Internal(format!("failed to spawn atlas: {e}")))
}

fn structured_cli_status(body: &Value) -> StatusCode {
    let code = body
        .get("error")
        .and_then(|error| error.get("code"))
        .and_then(Value::as_str)
        .unwrap_or("");
    match code {
        "surface_not_found" | "approval_not_found" => StatusCode::NOT_FOUND,
        "surface_owner_mismatch" | "approval_wrong_session" | "approval_session_inactive" => {
            StatusCode::FORBIDDEN
        }
        "surface_transition_conflict"
        | "surface_resume_conflict"
        | "approval_already_decided"
        | "config_revision_conflict"
        | "permission_profile_widening" => StatusCode::CONFLICT,
        "approval_stale" => StatusCode::GONE,
        _ => StatusCode::BAD_REQUEST,
    }
}

async fn dispatch_json_cli(
    atlas_cmd: &[String],
    args: &[&str],
    label: &str,
) -> Result<Value, ApiError> {
    let output = dispatch_atlas_raw(atlas_cmd, args, DISPATCH_TIMEOUT).await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    if output.status.success() {
        return serde_json::from_str(stdout.trim())
            .map_err(|error| ApiError::Internal(format!("{label} parse failed: {error}")));
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let raw = if stdout.trim().is_empty() {
        stderr.trim()
    } else {
        stdout.trim()
    };
    if let Ok(body) = serde_json::from_str::<Value>(raw) {
        return Err(ApiError::Structured(structured_cli_status(&body), body));
    }
    Err(ApiError::Internal(format!(
        "{label} failed without structured output"
    )))
}

/// Dispatch an atlas CLI command while supplying sensitive input through the
/// child's stdin. Secret bytes never enter argv, process listings, error
/// messages, or audit metadata.
async fn dispatch_atlas_raw_with_stdin(
    atlas_cmd: &[String],
    args: &[&str],
    stdin_bytes: &[u8],
    timeout: Duration,
) -> Result<std::process::Output, ApiError> {
    if atlas_cmd.is_empty() {
        return Err(ApiError::Internal("atlas_cmd is empty".into()));
    }
    let mut cmd = tokio::process::Command::new(&atlas_cmd[0]);
    hide_console_tokio(&mut cmd);
    for pre in &atlas_cmd[1..] {
        cmd.arg(pre);
    }
    for arg in args {
        cmd.arg(arg);
    }
    cmd.stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .kill_on_drop(true);
    let mut child = cmd
        .spawn()
        .map_err(|e| ApiError::Internal(format!("failed to spawn atlas: {e}")))?;
    let mut stdin = child
        .stdin
        .take()
        .ok_or_else(|| ApiError::Internal("atlas stdin unavailable".into()))?;
    stdin
        .write_all(stdin_bytes)
        .await
        .map_err(|e| ApiError::Internal(format!("failed to write atlas stdin: {e}")))?;
    stdin
        .write_all(b"\n")
        .await
        .map_err(|e| ApiError::Internal(format!("failed to finish atlas stdin: {e}")))?;
    drop(stdin);
    tokio::time::timeout(timeout, child.wait_with_output())
        .await
        .map_err(|_| ApiError::Internal("atlas command timed out".into()))?
        .map_err(|e| ApiError::Internal(format!("failed to wait for atlas: {e}")))
}

async fn dispatch_atlas_with_timeout(
    atlas_cmd: &[String],
    args: &[&str],
    timeout: Duration,
) -> Result<String, ApiError> {
    if atlas_cmd.is_empty() {
        return Err(ApiError::Internal("atlas_cmd is empty".into()));
    }
    let mut cmd = tokio::process::Command::new(&atlas_cmd[0]);
    hide_console_tokio(&mut cmd);
    for pre in &atlas_cmd[1..] {
        cmd.arg(pre);
    }
    for arg in args {
        cmd.arg(arg);
    }
    // Dropping the output() future on timeout kills the child.
    cmd.kill_on_drop(true);
    let output = tokio::time::timeout(timeout, cmd.output())
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

/// Fire-and-forget: spawn the atlas CLI as a detached background process and
/// return immediately. The child keeps running after the returned handle is
/// dropped (std::process does NOT kill on drop), so a long-running `run exec`
/// outlives this request — that's how the gateway drives autonomous runs in the
/// background. User-controlled values are passed after a `--` separator by the
/// caller (argument-injection guard), same as dispatch_atlas.
fn spawn_detached_atlas(atlas_cmd: &[String], args: &[&str]) -> Result<(), ApiError> {
    if atlas_cmd.is_empty() {
        return Err(ApiError::Internal("atlas_cmd is empty".into()));
    }
    let mut cmd = std::process::Command::new(&atlas_cmd[0]);
    hide_console_std(&mut cmd);
    for pre in &atlas_cmd[1..] {
        cmd.arg(pre);
    }
    for arg in args {
        cmd.arg(arg);
    }
    cmd.stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    cmd.spawn()
        .map(|_child| ()) // drop the handle; the process keeps running
        .map_err(|e| ApiError::Internal(format!("failed to spawn detached atlas: {e}")))
}

/// GET /v1/config — the masked ATLAS config (~/.atlas/config.yaml).
///
/// Config parsing lives in Python (single source of truth, D-022); the gateway
/// dispatches `atlas config json` and returns the already-masked JSON. Secrets
/// are env: refs only, so nothing sensitive crosses this surface.
async fn config_view(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["config", "json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("config json parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/auth — masked auth status (owned + env + external). Dispatch-only:
/// the CLI owns the auth store; nothing secret crosses this surface.
async fn auth_list(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["auth", "json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("auth json parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/auth/codex — secret-free status of the operator's Codex/ChatGPT login.
async fn auth_codex_status(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["auth", "codex-status"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("codex status parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/auth/codex/import — import the Codex login into the foundation store.
/// `import-codex` exits non-zero when there is nothing valid to import but still
/// emits a structured JSON result on stdout ({imported:false,reason}); surface
/// that as 200 rather than collapsing the legitimate outcome to a 500.
async fn auth_codex_import(State(state): State<AppState>) -> ApiResult {
    let output = dispatch_atlas_raw(
        &state.atlas_cmd,
        &["auth", "import-codex"],
        DISPATCH_TIMEOUT,
    )
    .await?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let value: Value = serde_json::from_str(stdout.trim())
        .map_err(|e| ApiError::Internal(format!("import-codex parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct AuthProviderBody {
    provider: String,
    api_key: String,
    base_url: Option<String>,
}

/// POST /v1/auth/providers — store an API key through the Python auth service.
///
/// The gateway remains dispatch-only (D-022). The secret crosses the local HTTP
/// request boundary, then is piped to `atlas auth add --stdin`; it is never an
/// argv element and the response is the CLI's masked AuthStatus.
async fn auth_provider_write(
    State(state): State<AppState>,
    Json(body): Json<AuthProviderBody>,
) -> ApiResult {
    require_arg(&body.provider, "provider is required")?;
    if body.provider.starts_with('-') {
        return Err(ApiError::BadRequest("provider must not start with '-'"));
    }
    if body.api_key.is_empty() {
        return Err(ApiError::BadRequest("api_key is required"));
    }
    if body.api_key.len() > 16 * 1024 {
        return Err(ApiError::BadRequest("api_key exceeds 16384 bytes"));
    }
    let mut owned_args = vec![
        "auth".to_string(),
        "add".to_string(),
        "--stdin".to_string(),
        "--source".to_string(),
        "gateway".to_string(),
    ];
    if let Some(base_url) = body.base_url.as_deref().filter(|v| !v.trim().is_empty()) {
        owned_args.push("--base-url".to_string());
        owned_args.push(base_url.to_string());
    }
    owned_args.push("--".to_string());
    owned_args.push(body.provider.clone());
    let args = owned_args.iter().map(String::as_str).collect::<Vec<_>>();
    let output = dispatch_atlas_raw_with_stdin(
        &state.atlas_cmd,
        &args,
        body.api_key.as_bytes(),
        DISPATCH_TIMEOUT,
    )
    .await?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        if let Ok(error_body) = serde_json::from_str::<Value>(stderr.trim()) {
            return Err(ApiError::Structured(StatusCode::BAD_REQUEST, error_body));
        }
        return Err(ApiError::Internal(
            "atlas auth add failed without a structured error".into(),
        ));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let value: Value = serde_json::from_str(stdout.trim())
        .map_err(|e| ApiError::Internal(format!("auth status parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/provider/status — active provider resolution + mock-vs-live verdict.
async fn provider_status(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["provider", "status", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("provider status parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/provider/modes — the four-way "which ways can I wire?" board.
async fn provider_modes(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["provider", "modes", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("provider modes parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct ConfigPatchBody {
    expected_revision: i64,
    changes: Value,
}

/// PATCH /v1/config — one optimistic config mutation dispatched to the
/// canonical `atlas config patch` CLI contract. The Rust gateway contains no
/// config schema, validation, or secret-resolution logic (D-022): it only
/// (1) rejects an empty/non-object `changes` payload before any dispatch,
/// (2) serializes `changes` as ONE argv element via serde_json (never
/// shell-interpolated), and (3) parses the CLI's structured stderr JSON
/// error to map `config_revision_conflict` -> 409 and other known
/// validation codes -> 400; any unstructured/unexpected failure stays 500.
async fn config_patch(
    State(state): State<AppState>,
    Json(body): Json<ConfigPatchBody>,
) -> ApiResult {
    let changes_obj = match &body.changes {
        Value::Object(map) if !map.is_empty() => &body.changes,
        Value::Object(_) => return Err(ApiError::BadRequest("changes must be a non-empty object")),
        _ => return Err(ApiError::BadRequest("changes must be a JSON object")),
    };
    let revision_arg = body.expected_revision.to_string();
    // serde_json::Value::to_string() serializes the whole object into one
    // String -> one argv element; there is no shell involved, so no value
    // inside `changes` (spaces, semicolons, etc.) can split into extra args.
    let changes_arg = changes_obj.to_string();
    let args = [
        "config",
        "patch",
        "--expected-revision",
        &revision_arg,
        "--changes-json",
        &changes_arg,
    ];
    let output = dispatch_atlas_raw(&state.atlas_cmd, &args, DISPATCH_TIMEOUT).await?;
    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        let value: Value = serde_json::from_str(stdout.trim())
            .map_err(|e| ApiError::Internal(format!("config patch parse failed: {e}")))?;
        return Ok(Json(value));
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    if let Ok(error_body) = serde_json::from_str::<Value>(stderr.trim()) {
        let code = error_body
            .get("error")
            .and_then(|e| e.get("code"))
            .and_then(Value::as_str)
            .unwrap_or("");
        let status = match code {
            "config_revision_conflict" => StatusCode::CONFLICT,
            "config_invalid" | "config_schema_unsupported" => StatusCode::BAD_REQUEST,
            _ => {
                return Err(ApiError::Internal(format!(
                    "atlas config patch failed: {stderr}"
                )))
            }
        };
        return Err(ApiError::Structured(status, error_body));
    }
    Err(ApiError::Internal(format!(
        "atlas config patch failed: {stderr}"
    )))
}

/// GET /v1/channels — configured messaging channels (foundation gateway config).
/// Dispatches `atlas channels json`; values are never returned, only presence.
async fn channels_list(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["channels", "json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("channels json parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct ToggleChannelBody {
    enabled: bool,
}

/// POST /v1/channels/{name}/toggle — enable/disable a channel via the CLI.
/// The user-controlled `name` is passed after `--` (argument-injection guard).
async fn channel_toggle(
    State(state): State<AppState>,
    AxPath(name): AxPath<String>,
    Json(body): Json<ToggleChannelBody>,
) -> ApiResult {
    let sub = if body.enabled { "enable" } else { "disable" };
    dispatch_atlas(&state.atlas_cmd, &["channels", sub, "--", &name]).await?;
    Ok(Json(json!({ "name": name, "enabled": body.enabled })))
}

/// GET /v1/gateway/messaging/status — is the foundation messaging gateway running?
/// Dispatches `atlas channels gateway status --json` -> {running, pid}. This is the
/// Python *messaging* daemon's lifecycle, NOT the Rust REST gateway serving here.
async fn messaging_gateway_status(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(
        &state.atlas_cmd,
        &["channels", "gateway", "status", "--json"],
    )
    .await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("messaging gateway status parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/gateway/messaging/start — spawn the foundation messaging gateway.
/// Returns the CLI's `{ok, message, running, pid}`. A missing foundation CLI is a
/// genuine misconfiguration and surfaces as an error.
async fn messaging_gateway_start(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(
        &state.atlas_cmd,
        &["channels", "gateway", "start", "--json"],
    )
    .await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("messaging gateway start parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/gateway/messaging/stop — stop the foundation messaging gateway.
/// Idempotent: stopping an already-stopped gateway succeeds.
async fn messaging_gateway_stop(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["channels", "gateway", "stop", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("messaging gateway stop parse failed: {e}")))?;
    Ok(Json(value))
}

// ---------------------------------------------------------------------------
// Discord surface — the vendored L2-BOT sidecar (services/discord-bot). The
// gateway only dispatches `atlas discord ...` (D-022); the CLI calls the bot's
// loopback API. Read-only browse; writes are a gated follow-up.
// ---------------------------------------------------------------------------

/// GET /v1/discord/status — sidecar lifecycle {running, pid, ready, guild_count}.
async fn discord_status(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["discord", "status", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord status parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/discord/start — start the Discord sidecar (detached).
async fn discord_start(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["discord", "start", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord start parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/discord/stop — stop the Discord sidecar (idempotent).
async fn discord_stop(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["discord", "stop", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord stop parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/discord/guilds — guilds the bot is in: {guilds: [{id, name}]}.
async fn discord_guilds(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["discord", "guilds", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord guilds parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/discord/guilds/{id}/structure — a guild's categories/channels/roles.
/// The user-controlled `id` is passed after `--` (injection guard); `--json`
/// stays BEFORE `--` so it is parsed as the flag, not a positional arg.
async fn discord_structure(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let out = dispatch_atlas(
        &state.atlas_cmd,
        &["discord", "structure", "--json", "--", &id],
    )
    .await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord structure parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct DiscordWriteBody {
    action: String,
    guild: String,
    target: Option<String>,
    params: Option<Value>,
    reason: Option<String>,
}

/// POST /v1/discord/writes — propose a gated Discord write (does NOT execute).
/// Approval state lives in Python/SQLite (D-022); this only dispatches the CLI.
/// The user-controlled `action` is passed after `--`; option VALUES (guild,
/// target, reason, params-json) are separate argv entries, never shell-parsed.
async fn discord_propose(
    State(state): State<AppState>,
    Json(body): Json<DiscordWriteBody>,
) -> ApiResult {
    require_arg(&body.action, "action must be non-empty")?;
    require_arg(&body.guild, "guild must be non-empty")?;
    let params_json = body.params.as_ref().map(|p| p.to_string());

    let mut args: Vec<String> = vec![
        "discord".into(),
        "propose".into(),
        "--json".into(),
        "--guild".into(),
        body.guild.clone(),
    ];
    if let Some(t) = &body.target {
        args.push("--target".into());
        args.push(t.clone());
    }
    if let Some(r) = &body.reason {
        args.push("--reason".into());
        args.push(r.clone());
    }
    if let Some(p) = &params_json {
        args.push("--params".into());
        args.push(p.clone());
    }
    args.push("--".into());
    args.push(body.action.clone());

    let arg_refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let out = dispatch_atlas(&state.atlas_cmd, &arg_refs).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord propose parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/discord/approvals — pending gated writes awaiting operator decision.
async fn discord_approvals(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["discord", "approvals", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord approvals parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/discord/approvals/{id}/approve — execute a pending write via the
/// sidecar. A failed Discord write returns 200 with status="failed" (the CLI
/// exits 0 on a processed outcome); only an unknown/non-pending id errors.
async fn discord_approve(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let out = dispatch_atlas(
        &state.atlas_cmd,
        &["discord", "approve", "--json", "--", &id],
    )
    .await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord approve parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct DiscordRejectBody {
    reason: Option<String>,
}

/// POST /v1/discord/approvals/{id}/reject — reject a pending write (never runs).
async fn discord_reject(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    body: Option<Json<DiscordRejectBody>>,
) -> ApiResult {
    let mut args: Vec<String> = vec!["discord".into(), "reject".into(), "--json".into()];
    if let Some(Json(b)) = &body {
        if let Some(r) = &b.reason {
            args.push("--reason".into());
            args.push(r.clone());
        }
    }
    args.push("--".into());
    args.push(id.clone());
    let arg_refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let out = dispatch_atlas(&state.atlas_cmd, &arg_refs).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("discord reject parse failed: {e}")))?;
    Ok(Json(value))
}

// ---------------------------------------------------------------------------
// Developer tool integrations (Phase 10.0.4) — dispatch-only (D-022).
// Every handler validates + shells to the `atlas tools` CLI + parses JSON.
// No DB reads/writes, no policy, no approval state in Rust — that all lives in
// Python/SQLite. User-controlled values are passed AFTER `--` (injection guard).
// ---------------------------------------------------------------------------

/// GET /v1/tools/manifests — the tool manifest list (name/risk_level/permissions/…).
async fn tool_manifests(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["tools", "manifests", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("tools manifests parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct ToolCallBody {
    tool: String,
    args: Option<Value>,
    mode: Option<String>,
    reason: Option<String>,
    surface_session_id: Option<String>,
    surface_kind: Option<String>,
    workspace_root: Option<String>,
}

/// POST /v1/tools/calls — invoke a tool through the Python policy chokepoint.
/// Read-class runs now; write/shell returns a pending approval. The tool name is
/// passed AFTER `--`; option VALUES are separate argv entries, never shell-parsed.
async fn tool_call(State(state): State<AppState>, Json(body): Json<ToolCallBody>) -> ApiResult {
    require_arg(&body.tool, "tool must be non-empty")?;
    let args_json = body.args.as_ref().map(|a| a.to_string());

    let mut args: Vec<String> = vec!["tools".into(), "call".into(), "--json".into()];
    if let Some(m) = &body.mode {
        args.push("--mode".into());
        args.push(m.clone());
    }
    if let Some(a) = &args_json {
        args.push("--args".into());
        args.push(a.clone());
    }
    if let Some(r) = &body.reason {
        args.push("--reason".into());
        args.push(r.clone());
    }
    if let Some(session_id) = &body.surface_session_id {
        args.push("--surface-session-id".into());
        args.push(session_id.clone());
    }
    if let Some(surface_kind) = &body.surface_kind {
        args.push("--surface-kind".into());
        args.push(surface_kind.clone());
    }
    if let Some(workspace_root) = &body.workspace_root {
        args.push("--workspace-root".into());
        args.push(workspace_root.clone());
    }
    args.push("--".into());
    args.push(body.tool.clone());

    let arg_refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let out = dispatch_atlas(&state.atlas_cmd, &arg_refs).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("tools call parse failed: {e}")))?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct ToolApprovalsQuery {
    status: Option<String>,
}

/// GET /v1/tools/approvals — read-only compatibility/audit projection.
///
/// Actionable queues live below a surface-session path; this route never accepts
/// surface authority and therefore cannot be used to claim a decision.
async fn tool_approval_outcomes(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(
        &state.atlas_cmd,
        &["tools", "approvals", "--json", "--status", "all"],
    )
    .await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("tools approvals parse failed: {e}")))?;
    Ok(Json(value))
}

/// GET /v1/surface-sessions/{session_id}/approvals — one owned actionable queue.
async fn surface_tool_approvals(
    State(state): State<AppState>,
    AxPath(session_id): AxPath<String>,
    Query(q): Query<ToolApprovalsQuery>,
    headers: HeaderMap,
) -> ApiResult {
    require_arg(&session_id, "surface session id must be non-empty")?;
    require_surface_owner(&state, &headers, &session_id).await?;
    let mut args: Vec<String> = vec!["tools".into(), "approvals".into(), "--json".into()];
    if let Some(s) = &q.status {
        args.push("--status".into());
        args.push(s.clone());
    }
    args.push("--surface-session-id".into());
    args.push(session_id);
    let arg_refs: Vec<&str> = args.iter().map(String::as_str).collect();
    let out = dispatch_atlas(&state.atlas_cmd, &arg_refs).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("tools approvals parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/surface-sessions/{session_id}/approvals/{id}/approve.
/// A failed-but-processed run returns 200 with status="failed" (CLI exits 0);
/// only an unknown/non-pending id errors.
#[derive(Deserialize)]
struct ToolDecisionBody {
    nonce: String,
    scope: Option<String>,
    reason: Option<String>,
}

async fn tool_approve(
    State(state): State<AppState>,
    AxPath((session_id, id)): AxPath<(String, String)>,
    headers: HeaderMap,
    Json(body): Json<ToolDecisionBody>,
) -> ApiResult {
    require_arg(&id, "approval id must be non-empty")?;
    require_arg(&session_id, "surface session id must be non-empty")?;
    require_surface_owner(&state, &headers, &session_id).await?;
    require_arg(&body.nonce, "nonce must be non-empty")?;
    let scope = body.scope.as_deref().unwrap_or("once");
    let mut args = vec![
        "tools",
        "approve",
        "--json",
        "--surface-session-id",
        session_id.as_str(),
        "--nonce",
        body.nonce.as_str(),
        "--scope",
        scope,
    ];
    if let Some(value) = body.reason.as_deref() {
        args.extend(["--reason", value]);
    }
    args.extend(["--", id.as_str()]);
    let value = dispatch_json_cli(&state.atlas_cmd, &args, "tools approve").await?;
    Ok(Json(value))
}

/// POST /v1/surface-sessions/{session_id}/approvals/{id}/reject.
async fn tool_reject(
    State(state): State<AppState>,
    AxPath((session_id, id)): AxPath<(String, String)>,
    headers: HeaderMap,
    Json(body): Json<ToolDecisionBody>,
) -> ApiResult {
    require_arg(&id, "approval id must be non-empty")?;
    require_arg(&session_id, "surface session id must be non-empty")?;
    require_surface_owner(&state, &headers, &session_id).await?;
    require_arg(&body.nonce, "nonce must be non-empty")?;
    let mut args = vec![
        "tools",
        "reject",
        "--json",
        "--surface-session-id",
        session_id.as_str(),
        "--nonce",
        body.nonce.as_str(),
    ];
    if let Some(value) = body.reason.as_deref() {
        args.extend(["--reason", value]);
    }
    args.extend(["--", id.as_str()]);
    let value = dispatch_json_cli(&state.atlas_cmd, &args, "tools reject").await?;
    Ok(Json(value))
}

// ---------------------------------------------------------------------------
// Shared surface sessions (Phase 10.7) — dispatch-only, owner-token bound.
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct SurfaceCreateBody {
    surface_kind: String,
    surface_id: Option<String>,
    workspace_kind: String,
    project_id: Option<String>,
    agent: Option<String>,
    provider: Option<String>,
    model: Option<String>,
    permission_mode: Option<String>,
    approval_channel: Option<bool>,
}

async fn surface_create(
    State(state): State<AppState>,
    Json(body): Json<SurfaceCreateBody>,
) -> ApiResult {
    require_arg(&body.surface_kind, "surface_kind must be non-empty")?;
    let mut args: Vec<String> = vec![
        "surface".into(),
        "create".into(),
        "--json".into(),
        "--surface-kind".into(),
        body.surface_kind,
    ];
    if let Some(value) = body.surface_id {
        args.extend(["--surface-id".into(), value]);
    }
    match body.workspace_kind.as_str() {
        "global" => args.push("--global".into()),
        "project" => {
            let project = body
                .project_id
                .ok_or(ApiError::BadRequest("project_id is required"))?;
            args.extend(["--project".into(), project]);
        }
        _ => {
            return Err(ApiError::BadRequest(
                "workspace_kind must be global or project",
            ))
        }
    }
    for (flag, value) in [
        ("--agent", body.agent),
        ("--provider", body.provider),
        ("--model", body.model),
        ("--permission-mode", body.permission_mode),
    ] {
        if let Some(value) = value {
            args.extend([flag.into(), value]);
        }
    }
    if body.approval_channel == Some(false) {
        args.push("--no-approval-channel".into());
    }
    let refs = args.iter().map(String::as_str).collect::<Vec<_>>();
    let value = dispatch_json_cli(&state.atlas_cmd, &refs, "surface create").await?;
    Ok(Json(value))
}

async fn surface_list(State(state): State<AppState>) -> ApiResult {
    let mut value = dispatch_json_cli(
        &state.atlas_cmd,
        &["surface", "list", "--json"],
        "surface list",
    )
    .await?;
    redact_owner_tokens(&mut value);
    Ok(Json(value))
}

fn redact_owner_tokens(value: &mut Value) {
    match value {
        Value::Object(object) => {
            object.remove("owner_token");
            for child in object.values_mut() {
                redact_owner_tokens(child);
            }
        }
        Value::Array(items) => {
            for item in items {
                redact_owner_tokens(item);
            }
        }
        _ => {}
    }
}

async fn surface_get(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    headers: HeaderMap,
) -> ApiResult {
    require_arg(&id, "surface session id must be non-empty")?;
    require_surface_owner(&state, &headers, &id).await?;
    let value = dispatch_json_cli(
        &state.atlas_cmd,
        &["surface", "get", "--json", "--", &id],
        "surface get",
    )
    .await?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct SurfaceEventsQuery {
    after_seq: Option<i64>,
}

async fn surface_events(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    Query(query): Query<SurfaceEventsQuery>,
    headers: HeaderMap,
) -> ApiResult {
    require_arg(&id, "surface session id must be non-empty")?;
    require_surface_owner(&state, &headers, &id).await?;
    let after_seq = query.after_seq.unwrap_or(-1).to_string();
    let value = dispatch_json_cli(
        &state.atlas_cmd,
        &[
            "surface",
            "events",
            "--json",
            "--after-seq",
            &after_seq,
            "--",
            &id,
        ],
        "surface events",
    )
    .await?;
    Ok(Json(value))
}

#[derive(Deserialize)]
struct SurfaceOwnerBody {
    owner_token: String,
}

async fn surface_action(
    state: AppState,
    id: String,
    action: &'static str,
    owner_token: String,
) -> ApiResult {
    require_arg(&id, "surface session id must be non-empty")?;
    require_arg(&owner_token, "owner_token must be non-empty")?;
    let value = dispatch_json_cli(
        &state.atlas_cmd,
        &[
            "surface",
            action,
            "--json",
            "--owner-token",
            &owner_token,
            "--",
            &id,
        ],
        action,
    )
    .await?;
    Ok(Json(value))
}

macro_rules! surface_action_handler {
    ($name:ident, $action:literal) => {
        async fn $name(
            State(state): State<AppState>,
            AxPath(id): AxPath<String>,
            Json(body): Json<SurfaceOwnerBody>,
        ) -> ApiResult {
            surface_action(state, id, $action, body.owner_token).await
        }
    };
}

surface_action_handler!(surface_heartbeat, "heartbeat");
surface_action_handler!(surface_suspend, "suspend");
surface_action_handler!(surface_resume, "resume");
surface_action_handler!(surface_cancel, "cancel");
surface_action_handler!(surface_close, "close");

#[derive(Deserialize)]
struct SelectFolderBody {
    title: Option<String>,
}

#[cfg(windows)]
async fn select_folder(body: Option<Json<SelectFolderBody>>) -> ApiResult {
    let title = body
        .and_then(|Json(b)| b.title)
        .map(|t| t.trim().to_string())
        .filter(|t| !t.is_empty())
        .unwrap_or_else(|| "Choose folder".to_string());
    // The dialog is spawned from a hidden background process; without an owner
    // window Windows' foreground lock leaves it behind the browser. An invisible
    // TopMost owner keeps the dialog on top of every window without stealing focus
    // permissions the process does not have.
    let script = r#"
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.FormBorderStyle = 'None'
$owner.StartPosition = 'CenterScreen'
$owner.Opacity = 0
$owner.Show()
$owner.Activate()
try {
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $env:ATLAS_FOLDER_DIALOG_TITLE
    $dialog.ShowNewFolderButton = $true
    $result = $dialog.ShowDialog($owner)
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        [Console]::Out.Write($dialog.SelectedPath)
    }
} finally {
    $owner.Close()
    $owner.Dispose()
}
"#;
    let mut cmd = tokio::process::Command::new("powershell.exe");
    hide_console_tokio(&mut cmd);
    cmd.arg("-NoProfile")
        .arg("-STA")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-Command")
        .arg(script)
        .env("ATLAS_FOLDER_DIALOG_TITLE", title)
        .kill_on_drop(true);
    let output = tokio::time::timeout(Duration::from_secs(300), cmd.output())
        .await
        .map_err(|_| ApiError::Internal("folder picker timed out".into()))?
        .map_err(|e| ApiError::Internal(format!("failed to open folder picker: {e}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(ApiError::Internal(format!(
            "folder picker failed: {stderr}"
        )));
    }
    let picked = String::from_utf8_lossy(&output.stdout).trim().to_string();
    Ok(Json(
        json!({ "path": if picked.is_empty() { Value::Null } else { Value::String(picked) } }),
    ))
}

#[cfg(not(windows))]
async fn select_folder(_body: Option<Json<SelectFolderBody>>) -> ApiResult {
    Err(ApiError::BadRequest(
        "folder picker is only available on Windows in browser mode",
    ))
}

#[derive(Deserialize)]
struct VcsParams {
    /// Directory to inspect; defaults to the gateway's repo root.
    path: Option<String>,
}

/// Git context for cockpit surfaces: current branch (or detached short sha),
/// read dependency-free from `.git/HEAD` — worktree pointer files and detached
/// HEAD aware. No git binary, no libgit2; mirrors the reader vendored in
/// services/atlas-terminal so every surface reports the same identity.
async fn vcs_context(State(state): State<AppState>, Query(params): Query<VcsParams>) -> ApiResult {
    let dir = params
        .path
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| state.repo_root.clone());
    Ok(Json(read_vcs_context(&dir)))
}

fn read_vcs_context(dir: &std::path::Path) -> Value {
    let not_a_repo = json!({ "repo": false, "branch": Value::Null });
    let git_path = dir.join(".git");
    let git_dir = if git_path.is_file() {
        // Linked worktree / submodule: `.git` is a pointer file "gitdir: <path>".
        let Ok(text) = std::fs::read_to_string(&git_path) else {
            return not_a_repo;
        };
        let Some(pointer) = text.trim().strip_prefix("gitdir:") else {
            return not_a_repo;
        };
        let pointer = PathBuf::from(pointer.trim());
        if pointer.is_absolute() {
            pointer
        } else {
            dir.join(pointer)
        }
    } else if git_path.is_dir() {
        git_path
    } else {
        return not_a_repo;
    };
    let Ok(head) = std::fs::read_to_string(git_dir.join("HEAD")) else {
        return not_a_repo;
    };
    let head = head.trim();
    if let Some(reference) = head.strip_prefix("ref:") {
        let reference = reference.trim();
        let branch = reference.strip_prefix("refs/heads/").unwrap_or(reference);
        json!({ "repo": true, "branch": branch, "detached": false })
    } else {
        let short: String = head.chars().take(7).collect();
        json!({ "repo": true, "branch": Value::Null, "detached": true, "commit": short })
    }
}

#[derive(Deserialize)]
struct GraphParams {
    /// atlas | global | projects | obsidian (defaults to atlas).
    scope: Option<String>,
}

/// Knowledge graph for the cockpit Graphify view. `scope` selects the corpus:
/// `atlas` (the gateway's `.planning/`), `global` (repo-wide markdown),
/// `projects` (sibling L2 projects), or `obsidian` (the configured vault).
async fn graph_view(State(state): State<AppState>, Query(params): Query<GraphParams>) -> ApiResult {
    let scope = match params
        .scope
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        Some(s) if matches!(s, "atlas" | "global" | "projects" | "obsidian") => s,
        _ => "atlas",
    };
    let root = state.repo_root.to_string_lossy();
    let args = ["graph", "build", "--root", root.as_ref(), "--scope", scope];
    let out =
        dispatch_atlas_with_timeout(&state.atlas_cmd, &args, CONSOLE_DISPATCH_TIMEOUT).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("atlas graph build returned invalid JSON: {e}")))?;
    Ok(Json(value))
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

/// Agent runtime keys the gateway accepts; mirrors atlas_runtime.agents.base.VALID_AGENTS.
const VALID_AGENTS: [&str; 3] = ["native", "claude_code", "codex"];

#[derive(Deserialize, Default)]
struct StartRunBody {
    /// Agent runtime selector: "native" (default), "claude_code" or "codex".
    /// Mirrors the `atlas mission run --agent` flag (P4 — modular agents).
    agent: Option<String>,
    /// When true, the gateway spawns a *detached* `atlas run exec` after creating
    /// the run, so it executes in the background (autonomous loop) while this
    /// endpoint returns the run_id immediately. Default false = record-only.
    execute: Option<bool>,
    /// Attach the run to the shared surface that initiated it so normalized
    /// events and approvals remain owned by that surface.
    surface_session_id: Option<String>,
    /// Enable the long-horizon goal loop for this mission run.
    #[serde(default)]
    goal_mode: bool,
    /// Optional provider/model override used by the goal-loop judge.
    judge_model: Option<String>,
    /// Optional cap on goal-loop attempts.
    max_runs: Option<i64>,
}

async fn start_run(
    State(state): State<AppState>,
    AxPath(mission_id): AxPath<String>,
    // Optional JSON body — an empty body (no agent selection) defaults to "native".
    body: Option<Json<StartRunBody>>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&mission_id, "mission id must be non-empty")?;
    let (agent_opt, execute, surface_session_id, goal_mode, judge_model, max_runs) = match body {
        Some(Json(b)) => (
            b.agent,
            b.execute.unwrap_or(false),
            b.surface_session_id,
            b.goal_mode,
            b.judge_model,
            b.max_runs,
        ),
        None => (None, false, None, false, None, None),
    };
    let agent = agent_opt
        .map(|a| a.trim().to_string())
        .filter(|a| !a.is_empty())
        .unwrap_or_else(|| "native".to_string());
    if !VALID_AGENTS.contains(&agent.as_str()) {
        return Err(ApiError::BadRequest(
            "agent must be 'native', 'claude_code' or 'codex'",
        ));
    }
    let judge_model = judge_model.map(|model| model.trim().to_string());
    if let Some(model) = judge_model.as_deref() {
        require_arg(model, "judge_model must be non-empty")?;
    }
    if let Some(max_runs) = max_runs {
        if !(1..=100).contains(&max_runs) {
            return Err(ApiError::BadRequest("max_runs must be between 1 and 100"));
        }
    }
    let max_runs_arg = max_runs.map(|value| value.to_string());
    let mut args = vec!["mission", "run", "--agent", agent.as_str()];
    if let Some(session_id) = surface_session_id.as_deref() {
        require_arg(session_id, "surface_session_id must be non-empty")?;
        args.extend(["--session-id", session_id]);
    }
    if goal_mode {
        args.push("--goal");
        if let Some(model) = judge_model.as_deref() {
            args.extend(["--judge-model", model]);
        }
        if let Some(max_runs) = max_runs_arg.as_deref() {
            args.extend(["--max-runs", max_runs]);
        }
    }
    args.extend(["--", mission_id.as_str()]);
    let run_id = dispatch_atlas(&state.atlas_cmd, &args).await?;
    let path = state.db_path.clone();
    let run_id_clone = run_id.clone();
    let found = blocking(move || db::get_run(&path, &run_id_clone)).await?;
    match found {
        Some(run) => {
            // (a) Background execution: spawn a detached `atlas run exec` that
            // drives the just-started run to completion (assembles context, runs
            // the agent, emits audit/SSE) without blocking this response.
            if execute {
                spawn_detached_atlas(&state.atlas_cmd, &["run", "exec", "--", &run_id])?;
            }
            Ok((
                StatusCode::CREATED,
                Json(json!({ "run": run, "executing": execute })),
            ))
        }
        None => Err(ApiError::Internal(format!(
            "run '{run_id}' started but not found in db"
        ))),
    }
}

/// Retry a failed/cancelled mission: reopen it in place and start a fresh run.
/// Mirrors `start_run` — the CLI `mission retry` reopens (`failed|cancelled ->
/// pending`) and starts the run, returning the new run_id; with `execute` we
/// spawn a detached `run exec` to drive it in the background. Prior runs stay
/// attached as attempt history.
async fn retry_mission(
    State(state): State<AppState>,
    AxPath(mission_id): AxPath<String>,
    body: Option<Json<StartRunBody>>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&mission_id, "mission id must be non-empty")?;
    let (agent_opt, execute, surface_session_id) = match body {
        Some(Json(b)) => (b.agent, b.execute.unwrap_or(false), b.surface_session_id),
        None => (None, false, None),
    };
    let agent = agent_opt
        .map(|a| a.trim().to_string())
        .filter(|a| !a.is_empty())
        .unwrap_or_else(|| "native".to_string());
    if !VALID_AGENTS.contains(&agent.as_str()) {
        return Err(ApiError::BadRequest(
            "agent must be 'native', 'claude_code' or 'codex'",
        ));
    }
    let mut args = vec!["mission", "retry", "--agent", agent.as_str()];
    if let Some(session_id) = surface_session_id.as_deref() {
        require_arg(session_id, "surface_session_id must be non-empty")?;
        args.extend(["--session-id", session_id]);
    }
    args.extend(["--", mission_id.as_str()]);
    let run_id = dispatch_atlas(&state.atlas_cmd, &args).await?;
    let path = state.db_path.clone();
    let run_id_clone = run_id.clone();
    let found = blocking(move || db::get_run(&path, &run_id_clone)).await?;
    match found {
        Some(run) => {
            if execute {
                spawn_detached_atlas(&state.atlas_cmd, &["run", "exec", "--", &run_id])?;
            }
            Ok((
                StatusCode::CREATED,
                Json(json!({ "run": run, "executing": execute })),
            ))
        }
        None => Err(ApiError::Internal(format!(
            "retry run '{run_id}' started but not found in db"
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
        &[
            "wiki", "update", "--title", &title, "--body", &content, "--", &slug,
        ],
    )
    .await?;
    let path = state.db_path.clone();
    let slug_clone = if canonical.is_empty() {
        slug.clone()
    } else {
        canonical
    };
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
        &[
            "wiki",
            "update",
            "--title",
            &merged_title,
            "--body",
            &merged_body,
            "--",
            &slug,
        ],
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

async fn models_list(State(state): State<AppState>, Query(params): Query<ListParams>) -> ApiResult {
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
// Focus handlers (WP-2 — Command Center Current Focus, D-022 dispatch pattern)
// ---------------------------------------------------------------------------

async fn focus_list(State(state): State<AppState>, Query(params): Query<ListParams>) -> ApiResult {
    let path = state.db_path.clone();
    let limit = clamp_limit(params.limit, 50, 200);
    let focus = blocking(move || db::list_focus(&path, limit)).await?;
    let count = focus.len();
    Ok(Json(json!({ "focus": focus, "count": count })))
}

async fn focus_current(State(state): State<AppState>) -> ApiResult {
    let path = state.db_path.clone();
    let focus = blocking(move || db::current_focus(&path)).await?;
    Ok(Json(json!({ "focus": focus })))
}

#[derive(Deserialize)]
struct CreateFocusBody {
    title: String,
    framework: Option<String>,
    /// Priorities / drivers arrive as string lists and are joined with commas for
    /// the CLI (`_split_csv`). Commas inside a single value are a known limitation.
    priorities: Option<Vec<String>>,
    drivers: Option<Vec<String>>,
    project: Option<String>,
}

async fn focus_create(
    State(state): State<AppState>,
    Json(body): Json<CreateFocusBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&body.title, "title must be non-empty")?;
    let framework = body.framework.unwrap_or_default();
    let priorities = body.priorities.unwrap_or_default().join(",");
    let drivers = body.drivers.unwrap_or_default().join(",");
    let project = body.project.unwrap_or_default();
    let mut args: Vec<&str> = vec!["focus", "create", "--title", &body.title];
    if !framework.is_empty() {
        args.extend_from_slice(&["--framework", &framework]);
    }
    if !priorities.is_empty() {
        args.extend_from_slice(&["--priorities", &priorities]);
    }
    if !drivers.is_empty() {
        args.extend_from_slice(&["--drivers", &drivers]);
    }
    if !project.is_empty() {
        args.extend_from_slice(&["--project", &project]);
    }
    let id = dispatch_atlas(&state.atlas_cmd, &args).await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_focus(&path, &id_clone)).await?;
    match found {
        Some(focus) => Ok((StatusCode::CREATED, Json(json!({ "focus": focus })))),
        None => Err(ApiError::Internal(format!(
            "focus '{id}' created but not found in db"
        ))),
    }
}

async fn focus_archive(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    require_arg(&id, "focus id must be non-empty")?;
    dispatch_atlas(&state.atlas_cmd, &["focus", "archive", "--", &id]).await?;
    Ok(Json(json!({ "archived": true, "id": id })))
}

// ---------------------------------------------------------------------------
// Goal hierarchy handlers (loop-engineering slice — D-022 dispatch pattern)
// ---------------------------------------------------------------------------

/// The nested goal forest for a focus (goals → children → tasks → observations).
async fn focus_tree(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    let path = state.db_path.clone();
    let tree = blocking(move || db::goal_tree(&path, &id)).await?;
    Ok(Json(json!({ "tree": tree })))
}

#[derive(Deserialize)]
struct CreateGoalBody {
    title: String,
    description: Option<String>,
    focus: Option<String>,
    parent: Option<String>,
    status: Option<String>,
}

async fn goal_create(
    State(state): State<AppState>,
    Json(body): Json<CreateGoalBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&body.title, "title must be non-empty")?;
    let description = body.description.unwrap_or_default();
    let focus = body.focus.unwrap_or_default();
    let parent = body.parent.unwrap_or_default();
    let status = body.status.unwrap_or_default();
    let mut args: Vec<&str> = vec!["goal", "create", "--title", &body.title];
    if !description.is_empty() {
        args.extend_from_slice(&["--description", &description]);
    }
    if !focus.is_empty() {
        args.extend_from_slice(&["--focus", &focus]);
    }
    if !parent.is_empty() {
        args.extend_from_slice(&["--parent", &parent]);
    }
    if !status.is_empty() {
        args.extend_from_slice(&["--status", &status]);
    }
    let id = dispatch_atlas(&state.atlas_cmd, &args).await?;
    let path = state.db_path.clone();
    let id_clone = id.clone();
    let found = blocking(move || db::get_goal(&path, &id_clone)).await?;
    match found {
        Some(goal) => Ok((StatusCode::CREATED, Json(json!({ "goal": goal })))),
        None => Err(ApiError::Internal(format!(
            "goal '{id}' created but not found in db"
        ))),
    }
}

async fn goal_archive(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    require_arg(&id, "goal id must be non-empty")?;
    dispatch_atlas(&state.atlas_cmd, &["goal", "archive", "--", &id]).await?;
    Ok(Json(json!({ "archived": true, "id": id })))
}

#[derive(Deserialize)]
struct CreateTaskBody {
    goal: String,
    title: String,
}

async fn task_create(
    State(state): State<AppState>,
    Json(body): Json<CreateTaskBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&body.goal, "goal id must be non-empty")?;
    require_arg(&body.title, "title must be non-empty")?;
    let id = dispatch_atlas(
        &state.atlas_cmd,
        &["task", "add", "--goal", &body.goal, "--title", &body.title],
    )
    .await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({ "created": true, "id": id })),
    ))
}

#[derive(Deserialize)]
struct TaskStatusBody {
    status: String,
}

async fn task_set_status(
    State(state): State<AppState>,
    AxPath(id): AxPath<String>,
    Json(body): Json<TaskStatusBody>,
) -> ApiResult {
    require_arg(&id, "task id must be non-empty")?;
    require_arg(&body.status, "status must be non-empty")?;
    // Options before the `--` guard so the positional id can't be parsed as a flag.
    dispatch_atlas(
        &state.atlas_cmd,
        &["task", "status", "--status", &body.status, "--", &id],
    )
    .await?;
    Ok(Json(
        json!({ "updated": true, "id": id, "status": body.status }),
    ))
}

#[derive(Deserialize)]
struct CreateObservationBody {
    body: String,
    goal: Option<String>,
    run: Option<String>,
    source: Option<String>,
}

async fn observation_create(
    State(state): State<AppState>,
    Json(payload): Json<CreateObservationBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&payload.body, "body must be non-empty")?;
    let goal = payload.goal.unwrap_or_default();
    let run = payload.run.unwrap_or_default();
    let source = payload.source.unwrap_or_default();
    let mut args: Vec<&str> = vec!["observe", "add", "--body", &payload.body];
    if !goal.is_empty() {
        args.extend_from_slice(&["--goal", &goal]);
    }
    if !run.is_empty() {
        args.extend_from_slice(&["--run", &run]);
    }
    if !source.is_empty() {
        args.extend_from_slice(&["--source", &source]);
    }
    let id = dispatch_atlas(&state.atlas_cmd, &args).await?;
    Ok((
        StatusCode::CREATED,
        Json(json!({ "created": true, "id": id })),
    ))
}

// ---------------------------------------------------------------------------
// Operations handlers (WP-6 — premade autonomous operations on goals)
// ---------------------------------------------------------------------------

/// The built-in operation registry. Read via the CLI (operations are not a DB
/// table — the Python registry is the single source of truth).
async fn operations_list(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["operation", "list"]).await?;
    let operations: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("operation list parse: {e}")))?;
    Ok(Json(json!({ "operations": operations })))
}

#[derive(Deserialize)]
struct OperationRunBody {
    goal_id: String,
    agent: Option<String>,
}

/// Trigger an operation on a goal: prepare a mission+run (mission intent = the
/// rendered operation instruction), then spawn a detached `run exec` so it
/// executes in the background (mirrors start_run's execute path).
async fn operation_run(
    State(state): State<AppState>,
    AxPath(op_id): AxPath<String>,
    Json(body): Json<OperationRunBody>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    require_arg(&op_id, "operation id must be non-empty")?;
    require_arg(&body.goal_id, "goal_id must be non-empty")?;
    let agent = body
        .agent
        .map(|a| a.trim().to_string())
        .filter(|a| !a.is_empty())
        .unwrap_or_else(|| "native".to_string());
    if !VALID_AGENTS.contains(&agent.as_str()) {
        return Err(ApiError::BadRequest(
            "agent must be 'native', 'claude_code' or 'codex'",
        ));
    }
    let run_id = dispatch_atlas(
        &state.atlas_cmd,
        &[
            "operation",
            "prepare",
            "--op",
            &op_id,
            "--goal",
            &body.goal_id,
            "--agent",
            &agent,
        ],
    )
    .await?;
    let path = state.db_path.clone();
    let run_id_clone = run_id.clone();
    let found = blocking(move || db::get_run(&path, &run_id_clone)).await?;
    match found {
        Some(run) => {
            spawn_detached_atlas(
                &state.atlas_cmd,
                &["run", "exec", "--agent", &agent, "--", &run_id],
            )?;
            Ok((
                StatusCode::CREATED,
                Json(json!({ "run": run, "executing": true, "operation": op_id })),
            ))
        }
        None => Err(ApiError::Internal(format!(
            "operation run '{run_id}' prepared but not found in db"
        ))),
    }
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

/// Slash commands contributed by active manifest modules — merged by every
/// surface (WebUI palette/slash, terminal) with its built-in catalog.
async fn commands_list(State(state): State<AppState>) -> ApiResult {
    let path = state.db_path.clone();
    let commands = blocking(move || db::list_module_commands(&path)).await?;
    let count = commands.len();
    Ok(Json(json!({ "commands": commands, "count": count })))
}

async fn module_activate(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    module_set_active(&state, &id, "activate").await
}

async fn module_deactivate(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
    module_set_active(&state, &id, "deactivate").await
}

// ---------------------------------------------------------------------------
// Cashflow module process control (start/stop the vendored Next.js app)
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct CashflowStartBody {
    /// "local" | "supabase" — DB backend the cashflow app runs against.
    backend: Option<String>,
}

async fn cashflow_status(State(state): State<AppState>) -> ApiResult {
    // CLI prints "running <backend>" | "stopped <backend>".
    let out = dispatch_atlas(&state.atlas_cmd, &["cashflow", "status"]).await?;
    let mut parts = out.split_whitespace();
    let running = parts.next() == Some("running");
    let backend = parts.next().unwrap_or("local").to_string();
    Ok(Json(json!({ "running": running, "backend": backend })))
}

async fn cashflow_start(
    State(state): State<AppState>,
    body: Option<Json<CashflowStartBody>>,
) -> ApiResult {
    let backend = body
        .and_then(|b| b.0.backend)
        .unwrap_or_else(|| "local".to_string());
    if backend != "local" && backend != "supabase" {
        return Err(ApiError::BadRequest(
            "backend must be 'local' or 'supabase'",
        ));
    }
    let msg = dispatch_atlas(
        &state.atlas_cmd,
        &["cashflow", "start", "--backend", &backend],
    )
    .await?;
    Ok(Json(json!({ "message": msg })))
}

async fn cashflow_stop(State(state): State<AppState>) -> ApiResult {
    let msg = dispatch_atlas(&state.atlas_cmd, &["cashflow", "stop"]).await?;
    Ok(Json(json!({ "message": msg })))
}

/// POST /v1/models/refresh — sync the registry against the live sidecar
/// /models list. Dispatch-only; the CLI owns discovery/seed semantics.
async fn models_refresh(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["models", "refresh"]).await?;
    Ok(Json(json!({ "message": out })))
}

/// GET /v1/freellmapi/status — sidecar liveness + install/remediation state.
async fn freellmapi_status(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["freellmapi", "status", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("freellmapi status parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/freellmapi/start — bring the external OpenAI-compatible sidecar up.
async fn freellmapi_start(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["freellmapi", "start", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("freellmapi start parse failed: {e}")))?;
    Ok(Json(value))
}

/// POST /v1/freellmapi/stop — stop the CLI-managed sidecar process.
async fn freellmapi_stop(State(state): State<AppState>) -> ApiResult {
    let out = dispatch_atlas(&state.atlas_cmd, &["freellmapi", "stop", "--json"]).await?;
    let value: Value = serde_json::from_str(&out)
        .map_err(|e| ApiError::Internal(format!("freellmapi stop parse failed: {e}")))?;
    Ok(Json(value))
}

async fn cashflow_summary() -> ApiResult {
    let summary = tokio::task::spawn_blocking(db::cashflow_summary)
        .await
        .map_err(|e| ApiError::Internal(e.to_string()))?
        .map_err(ApiError::from)?;
    Ok(Json(summary))
}

/// Browser-facing handoff to the complete cashflow surface (the vendored
/// Next.js app). Serves an ATLAS-styled launcher page that checks module
/// status via /v1/cashflow/status, auto-starts a stopped module, waits for
/// the app to accept connections, then redirects. The app URL is resolved at
/// request time from ATLAS_CASHFLOW_URL (same knob the CLI honors).
async fn cashflow_full() -> Html<String> {
    let app_url = std::env::var("ATLAS_CASHFLOW_URL")
        .unwrap_or_else(|_| "http://localhost:3000".to_string());
    Html(CASHFLOW_FULL_PAGE.replace("__CASHFLOW_URL__", app_url.trim_end_matches('/')))
}

const CASHFLOW_FULL_PAGE: &str = r#"<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ATLAS // CASHFLOW LINK</title>
<style>
  :root {
    --void: #0B0D12; --ink: #151820; --ivory: #EDEAE0; --fg2: #9BA0AD; --fg3: #565C6B;
    --celestial: #4F8BFF; --cyan: #46F0E0; --bronze: #B08A57; --error: #FF0055;
    --hairline: rgba(237,234,224,0.08); --ease: cubic-bezier(0.22, 1, 0.36, 1);
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    background:
      radial-gradient(circle at 24% 30%, rgba(79,139,255,0.07) 0%, transparent 46%),
      radial-gradient(circle at 76% 66%, rgba(70,240,224,0.04) 0%, transparent 40%),
      linear-gradient(180deg, #07080C 0%, #0B0D12 50%, #0A0C11 100%);
    color: var(--ivory);
    font-family: 'JetBrains Mono', ui-monospace, 'Courier New', monospace;
    display: grid; place-items: center; position: relative; overflow: hidden;
  }
  body::after {
    content: ''; position: absolute; inset: 0; pointer-events: none; opacity: .5;
    background-image:
      repeating-radial-gradient(circle at 22% 38%, transparent 0, transparent 28px,
        rgba(180,200,235,0.05) 28px, rgba(180,200,235,0.05) 29px),
      repeating-radial-gradient(circle at 72% 62%, transparent 0, transparent 34px,
        rgba(180,200,235,0.04) 34px, rgba(180,200,235,0.04) 35px);
    mix-blend-mode: screen;
  }
  .panel {
    position: relative; z-index: 1; width: min(560px, calc(100vw - 48px));
    background: linear-gradient(180deg, rgba(21,24,32,0.72), rgba(11,13,18,0.82));
    backdrop-filter: blur(22px) saturate(140%); -webkit-backdrop-filter: blur(22px) saturate(140%);
    border: 1px solid var(--hairline); border-radius: 2px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 1px 0 rgba(0,0,0,0.4), 0 24px 64px rgba(0,0,0,0.5);
    padding: 30px 34px;
  }
  .eyebrow { font-size: 10px; letter-spacing: 0.22em; color: var(--bronze); margin-bottom: 12px; }
  h1 { font-size: 20px; font-weight: 700; letter-spacing: 0.12em; margin-bottom: 22px; }
  .row { display: flex; align-items: center; gap: 10px; padding: 11px 0; border-top: 1px solid var(--hairline); }
  .row:last-of-type { border-bottom: 1px solid var(--hairline); }
  .k { font-size: 10px; letter-spacing: 0.18em; color: var(--fg3); width: 120px; flex-shrink: 0; }
  .v { font-size: 12px; letter-spacing: 0.08em; color: var(--fg2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--fg3); flex-shrink: 0; }
  .dot.live { background: var(--cyan); box-shadow: 0 0 10px rgba(70,240,224,0.45); animation: pulse 2.4s ease-in-out infinite; }
  .dot.bad { background: var(--error); box-shadow: 0 0 10px rgba(255,0,85,0.45); }
  .dot.wait { background: var(--celestial); box-shadow: 0 0 10px rgba(79,139,255,0.45); animation: pulse 1.4s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: .55; } 50% { opacity: 1; } }
  #state { color: var(--fg2); }
  #state.live { color: var(--cyan); }
  #state.bad { color: var(--error); }
  #detail { font-size: 10.5px; letter-spacing: 0.06em; color: var(--fg3); margin-top: 16px; min-height: 15px; word-break: break-all; }
  .actions { margin-top: 22px; display: flex; gap: 10px; }
  a.btn, button.btn {
    display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; cursor: pointer;
    border-radius: 2px; font-family: inherit; font-size: 10.5px; letter-spacing: 0.16em;
    text-transform: uppercase; text-decoration: none; transition: all .25s var(--ease);
    background: rgba(79,139,255,0.10); border: 1px solid rgba(79,139,255,0.36); color: #9CC0FF;
  }
  a.btn:hover, button.btn:hover { background: rgba(79,139,255,0.20); box-shadow: 0 0 18px rgba(79,139,255,0.18); }
  .btn.ghost { background: transparent; border-color: var(--hairline); color: var(--fg3); }
  .btn.ghost:hover { color: var(--fg2); box-shadow: none; background: rgba(255,255,255,0.03); }
  .bar { height: 1px; background: linear-gradient(90deg, transparent, rgba(176,138,87,0.32), transparent); margin: 20px 0 0; }
</style>
</head>
<body>
  <main class="panel" role="status" aria-live="polite">
    <div class="eyebrow">ATLAS // MODULE LINK</div>
    <h1>COMPLETE CASHFLOW</h1>
    <div class="row"><span id="dot" class="dot wait"></span><span class="k">MODULE STATE</span><span class="v" id="state">CHECKING…</span></div>
    <div class="row"><span class="dot"></span><span class="k">SURFACE</span><span class="v" id="surface">__CASHFLOW_URL__</span></div>
    <div id="detail"></div>
    <div class="bar"></div>
    <div class="actions">
      <button class="btn" id="retry" style="display:none" onclick="boot()">RETRY LINK</button>
      <a class="btn ghost" href="javascript:history.back()">RETURN TO COCKPIT</a>
    </div>
  </main>
<script>
  var APP = "__CASHFLOW_URL__";
  var TARGET = APP + "/dashboard";
  function el(id) { return document.getElementById(id); }
  function setState(cls, msg, detail) {
    el("dot").className = "dot " + cls;
    el("state").className = cls;
    el("state").textContent = msg;
    el("detail").textContent = detail || "";
    el("retry").style.display = cls === "bad" ? "inline-flex" : "none";
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function probeApp() {
    // no-cors fetch resolves once the Next server accepts connections.
    return fetch(TARGET, { mode: "no-cors", cache: "no-store" }).then(function () { return true; }, function () { return false; });
  }
  async function status() {
    var r = await fetch("/v1/cashflow/status", { cache: "no-store" });
    if (!r.ok) { throw new Error("status " + r.status + ": " + (await r.text()).slice(0, 300)); }
    return r.json();
  }
  async function waitReady(tries) {
    for (var i = 0; i < tries; i++) {
      if (await probeApp()) { return true; }
      await sleep(1500);
    }
    return false;
  }
  async function boot() {
    try {
      setState("wait", "CHECKING…");
      if (await probeApp()) { setState("live", "ONLINE — LINKING"); location.replace(TARGET); return; }
      var s = await status();
      if (!s.running) {
        setState("wait", "OFFLINE — STARTING MODULE");
        var r = await fetch("/v1/cashflow/start", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ backend: s.backend || "local" })
        });
        if (!r.ok) { throw new Error("start " + r.status + ": " + (await r.text()).slice(0, 300)); }
      }
      setState("wait", "WAITING FOR SURFACE…");
      if (await waitReady(40)) { setState("live", "ONLINE — LINKING"); location.replace(TARGET); return; }
      setState("bad", "SURFACE UNREACHABLE", "Module process started but " + TARGET + " did not accept connections.");
    } catch (e) {
      setState("bad", "LINK FAILED", String(e && e.message || e));
    }
  }
  boot();
</script>
</body>
</html>
"#;

// ---------------------------------------------------------------------------
// Run cancel handler (Phase 8 — Surface 2 run monitoring)
// ---------------------------------------------------------------------------

async fn cancel_run(State(state): State<AppState>, AxPath(id): AxPath<String>) -> ApiResult {
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
            // React cockpit (web-ui-react) Vite dev port — see its vite.config.ts.
            "http://localhost:5174",
            "http://127.0.0.1:5174",
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
            HeaderValue::from_static("GET, POST, PUT, PATCH, OPTIONS"),
        );
        headers.insert(
            header::ACCESS_CONTROL_ALLOW_HEADERS,
            HeaderValue::from_static("content-type, x-atlas-surface-owner"),
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
        .route("/v1/missions/purge-archived", post(purge_archived_missions))
        .route("/v1/missions/{id}", get(mission_detail))
        .route("/v1/missions/{id}/archive", post(archive_mission))
        .route("/v1/missions/{id}/run", post(start_run))
        .route("/v1/missions/{id}/retry", post(retry_mission))
        .route("/v1/missions/{id}/cancel", post(cancel_run))
        .route("/v1/runs", get(runs_list))
        .route("/v1/runs/{id}", get(run_detail))
        .route("/v1/runs/{id}/events", get(run_events))
        .route("/v1/runs/{id}/stream", get(run_stream))
        .route("/v1/wiki/pages", get(wiki_pages).post(wiki_create))
        .route(
            "/v1/wiki/pages/{slug}",
            get(wiki_page_detail).put(wiki_update),
        )
        .route("/v1/wiki/search", get(wiki_search))
        .route("/v1/models", get(models_list))
        .route("/v1/config", get(config_view).patch(config_patch))
        .route("/v1/auth", get(auth_list))
        .route("/v1/auth/providers", post(auth_provider_write))
        .route("/v1/auth/codex", get(auth_codex_status))
        .route("/v1/auth/codex/import", post(auth_codex_import))
        .route("/v1/provider/status", get(provider_status))
        .route("/v1/provider/modes", get(provider_modes))
        .route("/v1/channels", get(channels_list))
        .route("/v1/channels/{name}/toggle", post(channel_toggle))
        .route(
            "/v1/gateway/messaging/status",
            get(messaging_gateway_status),
        )
        .route("/v1/gateway/messaging/start", post(messaging_gateway_start))
        .route("/v1/gateway/messaging/stop", post(messaging_gateway_stop))
        .route("/v1/discord/status", get(discord_status))
        .route("/v1/discord/start", post(discord_start))
        .route("/v1/discord/stop", post(discord_stop))
        .route("/v1/discord/guilds", get(discord_guilds))
        .route("/v1/discord/guilds/{id}/structure", get(discord_structure))
        .route("/v1/discord/writes", post(discord_propose))
        .route("/v1/discord/approvals", get(discord_approvals))
        .route("/v1/discord/approvals/{id}/approve", post(discord_approve))
        .route("/v1/discord/approvals/{id}/reject", post(discord_reject))
        .route("/v1/tools/manifests", get(tool_manifests))
        .route("/v1/tools/calls", post(tool_call))
        .route("/v1/tools/approvals", get(tool_approval_outcomes))
        .route(
            "/v1/surface-sessions",
            get(surface_list).post(surface_create),
        )
        .route("/v1/surface-sessions/{id}", get(surface_get))
        .route("/v1/surface-sessions/{id}/events", get(surface_events))
        .route(
            "/v1/surface-sessions/{session_id}/approvals",
            get(surface_tool_approvals),
        )
        .route(
            "/v1/surface-sessions/{session_id}/approvals/{id}/approve",
            post(tool_approve),
        )
        .route(
            "/v1/surface-sessions/{session_id}/approvals/{id}/reject",
            post(tool_reject),
        )
        .route(
            "/v1/surface-sessions/{id}/heartbeat",
            post(surface_heartbeat),
        )
        .route("/v1/surface-sessions/{id}/suspend", post(surface_suspend))
        .route("/v1/surface-sessions/{id}/resume", post(surface_resume))
        .route("/v1/surface-sessions/{id}/cancel", post(surface_cancel))
        .route("/v1/surface-sessions/{id}/close", post(surface_close))
        .route("/v1/graph", get(graph_view))
        .route("/v1/host/select-folder", post(select_folder))
        .route("/v1/vcs", get(vcs_context))
        .route("/v1/projects", get(projects_list).post(projects_create))
        .route("/v1/projects/register", post(projects_register))
        .route("/v1/focus", get(focus_list).post(focus_create))
        .route("/v1/focus/current", get(focus_current))
        .route("/v1/focus/{id}/archive", post(focus_archive))
        .route("/v1/focus/{id}/tree", get(focus_tree))
        .route("/v1/goals", post(goal_create))
        .route("/v1/goals/{id}/archive", post(goal_archive))
        .route("/v1/tasks", post(task_create))
        .route("/v1/tasks/{id}/status", post(task_set_status))
        .route("/v1/observations", post(observation_create))
        .route("/v1/operations", get(operations_list))
        .route("/v1/operations/{id}/run", post(operation_run))
        .route("/v1/modules", get(modules_list))
        .route("/v1/commands", get(commands_list))
        .route("/v1/modules/{id}/activate", post(module_activate))
        .route("/v1/modules/{id}/deactivate", post(module_deactivate))
        .route("/cashflow/full", get(cashflow_full))
        .route("/v1/cashflow/status", get(cashflow_status))
        .route("/v1/cashflow/summary", get(cashflow_summary))
        .route("/v1/cashflow/start", post(cashflow_start))
        .route("/v1/cashflow/stop", post(cashflow_stop))
        .route("/v1/models/refresh", post(models_refresh))
        .route("/v1/freellmapi/status", get(freellmapi_status))
        .route("/v1/freellmapi/start", post(freellmapi_start))
        .route("/v1/freellmapi/stop", post(freellmapi_stop))
        .route("/v1/projects/{id}", get(project_detail))
        .layer(middleware::from_fn(cors))
        .with_state(state)
}
