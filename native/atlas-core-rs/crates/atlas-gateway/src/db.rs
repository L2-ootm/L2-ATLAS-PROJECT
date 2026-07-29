//! Read-only SQLite access for the gateway (D-022: reads direct, writes via
//! the `atlas` CLI contract — no business logic here, only row → JSON).

use rusqlite::{Connection, OpenFlags, OptionalExtension};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Owner-scoped full-result bytes. The evidence module performs the indexed
/// metadata lookup and ordered chunk assembly; callers never receive a result
/// belonging to a different run/team/tool owner.
pub fn get_full_result(
    path: &Path,
    owner_kind: &str,
    owner_id: &str,
    evidence_id: &str,
) -> Result<Vec<u8>, DbError> {
    crate::evidence::read_full_result(path, owner_kind, owner_id, evidence_id)
        .map_err(DbError::Failed)
}

#[derive(Debug)]
pub enum DbError {
    /// Database file does not exist yet (fresh machine, no runs).
    Absent,
    /// Open/query failure (missing table, corrupt file, locked, …).
    Failed(String),
}

impl From<rusqlite::Error> for DbError {
    fn from(e: rusqlite::Error) -> Self {
        DbError::Failed(e.to_string())
    }
}

const MAX_EVIDENCE_PAGE: i64 = 1_000;
const MAX_CONTENT_RANGE: u64 = 64 * 1024;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EvidenceCursor {
    pub sort_key: String,
    pub id: String,
}

impl EvidenceCursor {
    pub fn new(sort_key: impl Into<String>, id: impl Into<String>) -> Self {
        Self {
            sort_key: sort_key.into(),
            id: id.into(),
        }
    }

    pub fn encode(&self) -> String {
        format!(
            "v1:{}:{}",
            hex_encode(self.sort_key.as_bytes()),
            hex_encode(self.id.as_bytes())
        )
    }

    pub fn decode(value: &str) -> Result<Self, DbError> {
        let mut parts = value.split(':');
        if parts.next() != Some("v1") {
            return Err(invalid_input("cursor must use the v1 evidence format"));
        }
        let sort_key = parts
            .next()
            .ok_or_else(|| invalid_input("cursor is missing its sort key"))?;
        let id = parts
            .next()
            .ok_or_else(|| invalid_input("cursor is missing its identity"))?;
        if parts.next().is_some() {
            return Err(invalid_input("cursor contains unexpected fields"));
        }
        Ok(Self {
            sort_key: hex_decode(sort_key)?,
            id: hex_decode(id)?,
        })
    }
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

fn hex_decode(value: &str) -> Result<String, DbError> {
    if !value.len().is_multiple_of(2) {
        return Err(invalid_input("cursor has invalid hex"));
    }
    let mut bytes = Vec::with_capacity(value.len() / 2);
    for pair in value.as_bytes().chunks_exact(2) {
        let high = hex_nibble(pair[0])?;
        let low = hex_nibble(pair[1])?;
        bytes.push((high << 4) | low);
    }
    String::from_utf8(bytes).map_err(|_| invalid_input("cursor contains invalid UTF-8"))
}

fn hex_nibble(value: u8) -> Result<u8, DbError> {
    match value {
        b'0'..=b'9' => Ok(value - b'0'),
        b'a'..=b'f' => Ok(value - b'a' + 10),
        b'A'..=b'F' => Ok(value - b'A' + 10),
        _ => Err(invalid_input("cursor has invalid hex")),
    }
}

fn evidence_limit(limit: i64) -> i64 {
    limit.clamp(1, MAX_EVIDENCE_PAGE)
}

fn invalid_input(message: impl Into<String>) -> DbError {
    DbError::Failed(format!("invalid input: {}", message.into()))
}

#[derive(Debug, Clone, Default)]
pub struct AuditEventFilters {
    pub run_id: Option<String>,
    pub session_id: Option<String>,
    pub actor_id: Option<String>,
    pub event_type: Option<String>,
    pub tool_name: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AuditEventRecord {
    pub cursor: String,
    pub id: String,
    pub run_id: String,
    pub session_id: Option<String>,
    pub event_type: String,
    pub tool_name: Option<String>,
    pub timestamp: String,
    pub duration_ms: Option<i64>,
    pub data: Value,
    pub policy_result: Option<String>,
    pub task_id: Option<String>,
    pub tool_call_id: Option<String>,
}

#[derive(Debug, Clone)]
pub enum ChangeSetScope {
    Run(String),
    Session(String),
    TeamRun(String),
}

#[derive(Debug, Clone, Serialize)]
pub struct EvidenceProvenanceRecord {
    pub run_id: String,
    pub session_id: Option<String>,
    pub team_run_id: Option<String>,
    pub turn_id: Option<String>,
    pub actor_id: Option<String>,
    pub parent_actor_id: Option<String>,
    pub tool_call_id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChangeSetRecord {
    pub id: String,
    pub provenance: EvidenceProvenanceRecord,
    pub coverage: String,
    pub status: String,
    pub redaction_count: i64,
    pub created_at: String,
    pub file_count: i64,
    pub additions: i64,
    pub deletions: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContentRange {
    pub start: u64,
    pub length: u64,
}

impl ContentRange {
    pub fn new(start: u64, length: u64) -> Result<Self, DbError> {
        if length == 0 || length > MAX_CONTENT_RANGE {
            return Err(invalid_input(format!(
                "range length must be between 1 and {MAX_CONTENT_RANGE} bytes"
            )));
        }
        start
            .checked_add(length)
            .ok_or_else(|| invalid_input("range overflows u64"))?;
        Ok(Self { start, length })
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ContentPage {
    #[serde(skip)]
    pub bytes: Vec<u8>,
    pub total_bytes: u64,
    pub start: u64,
    pub end: u64,
    pub availability: String,
    pub sha256: Option<String>,
    pub media_type: String,
}

fn open_ro(path: &Path) -> Result<Connection, DbError> {
    if !path.exists() {
        return Err(DbError::Absent);
    }
    Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| DbError::Failed(e.to_string()))
}

/// Validate a surface owner token without returning or logging it.
pub fn surface_owner_matches(
    path: &Path,
    session_id: &str,
    owner_token: &str,
) -> Result<bool, DbError> {
    if owner_token.is_empty() {
        return Ok(false);
    }
    let conn = open_ro(path)?;
    match conn.query_row(
        "SELECT owner_token FROM surface_sessions WHERE id=?1",
        [session_id],
        |row| row.get::<_, String>(0),
    ) {
        Ok(stored) => Ok(stored == owner_token),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(false),
        Err(error) => Err(error.into()),
    }
}

fn mission_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "title": row.get::<_, String>(1)?,
        "intent": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "project": row.get::<_, String>(4)?,
        "created_at": row.get::<_, String>(5)?,
        "updated_at": row.get::<_, String>(6)?,
        // Legacy fallback (pre-0024 DB): origin is unknowable, serve "".
        "origin": "",
    }))
}

fn mission_row_with_archive(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "title": row.get::<_, String>(1)?,
        "intent": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "project": row.get::<_, String>(4)?,
        "created_at": row.get::<_, String>(5)?,
        "updated_at": row.get::<_, String>(6)?,
        "archived_at": row.get::<_, Option<String>>(7)?,
        "delete_after": row.get::<_, Option<String>>(8)?,
        // origin (0024) is absent on older DBs — the fallback SQL omits the
        // column, so the out-of-range get degrades to "" (legacy/unknown).
        "origin": row.get::<_, String>(9).unwrap_or_default(),
    }))
}

fn run_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "mission_id": row.get::<_, String>(1)?,
        "session_id": row.get::<_, Option<String>>(2)?,
        "status": row.get::<_, String>(3)?,
        "started_at": row.get::<_, String>(4)?,
        "finished_at": row.get::<_, Option<String>>(5)?,
        "summary": row.get::<_, String>(6)?,
        "agent_runtime": row.get::<_, String>(7)?,
    }))
}

fn project_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "name": row.get::<_, String>(1)?,
        "root_path": row.get::<_, String>(2)?,
        "created_at": row.get::<_, String>(3)?,
        "updated_at": row.get::<_, String>(4)?,
    }))
}

fn module_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    // manifest_json (0023) is parsed to a JSON object so the WebUI receives
    // structured capabilities (commands/pages); malformed/empty becomes null.
    let manifest_raw: String = row.get::<_, Option<String>>(7)?.unwrap_or_default();
    let manifest: Value = serde_json::from_str(&manifest_raw).unwrap_or(Value::Null);
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "name": row.get::<_, String>(1)?,
        "description": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "activated_at": row.get::<_, Option<String>>(4)?,
        "version": row.get::<_, Option<String>>(5)?.unwrap_or_default(),
        "source_path": row.get::<_, Option<String>>(6)?.unwrap_or_default(),
        "manifest": manifest,
        "missing": row.get::<_, Option<i64>>(8)?.unwrap_or(0) != 0,
    }))
}

fn focus_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    // priorities/drivers are JSON-array strings in SQLite (0009_focus.sql) — parse
    // back to JSON arrays for the API; tolerate malformed values as empty arrays.
    let priorities: String = row.get(3)?;
    let drivers: String = row.get(4)?;
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "title": row.get::<_, String>(1)?,
        "framework": row.get::<_, String>(2)?,
        "priorities": serde_json::from_str::<Value>(&priorities).unwrap_or_else(|_| json!([])),
        "drivers": serde_json::from_str::<Value>(&drivers).unwrap_or_else(|_| json!([])),
        "project_id": row.get::<_, Option<String>>(5)?,
        "status": row.get::<_, String>(6)?,
        "created_at": row.get::<_, String>(7)?,
        "updated_at": row.get::<_, String>(8)?,
    }))
}

const MISSION_COLS: &str = "id, title, intent, status, project, created_at, updated_at";
const MISSION_COLS_ORIGIN: &str =
    "id, title, intent, status, project, created_at, updated_at, NULL, NULL, origin";
const MISSION_ARCHIVE_COLS: &str =
    "m.id, m.title, m.intent, m.status, m.project, m.created_at, m.updated_at, \
     a.archived_at, a.delete_after";
const MISSION_ARCHIVE_COLS_ORIGIN: &str =
    "m.id, m.title, m.intent, m.status, m.project, m.created_at, m.updated_at, \
     a.archived_at, a.delete_after, m.origin";
const RUN_COLS: &str =
    "id, mission_id, session_id, status, started_at, finished_at, summary, agent_runtime";
const RUN_COLS_QUALIFIED: &str = "r.id, r.mission_id, r.session_id, r.status, r.started_at, \
     r.finished_at, r.summary, r.agent_runtime";
const PROJECT_COLS: &str = "id, name, root_path, created_at, updated_at";
const MODULE_COLS: &str =
    "id, name, description, status, activated_at, version, source_path, manifest_json, missing";
const FOCUS_COLS: &str =
    "id, title, framework, priorities, drivers, project_id, status, created_at, updated_at";

/// True for prepare errors caused by schema drift (older DB without a table or
/// the 0024 origin column) — the callers then try the next fallback SQL.
fn is_schema_drift(err: &rusqlite::Error) -> bool {
    match err {
        // Statement-prepare failures surface as SqlInputError on current
        // rusqlite; SqliteFailure covers older paths and execute-time errors.
        rusqlite::Error::SqlInputError { msg, .. } => {
            msg.contains("no such table") || msg.contains("no such column")
        }
        rusqlite::Error::SqliteFailure(_, Some(msg)) => {
            msg.contains("no such table") || msg.contains("no such column")
        }
        _ => false,
    }
}

type RowMapper = fn(&rusqlite::Row<'_>) -> rusqlite::Result<Value>;

pub fn list_missions(path: &Path, limit: i64, origin: Option<&str>) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    // Filter semantics: "operator" means everything not machine- or
    // prompt-created (pre-0024 "" rows count as operator); "chat"/"system"
    // match exactly. Pre-0024 DBs fall back to unfiltered SQL below.
    let where_origin = match origin {
        Some("operator") => " WHERE m.origin NOT IN ('chat','system')",
        Some("chat") => " WHERE m.origin = 'chat'",
        Some("system") => " WHERE m.origin = 'system'",
        _ => "",
    };
    let candidates: [(String, RowMapper); 4] = [
        (
            format!(
                "SELECT {MISSION_ARCHIVE_COLS_ORIGIN} FROM missions m \
                 LEFT JOIN mission_archive a ON a.mission_id = m.id{where_origin} \
                 ORDER BY m.created_at DESC LIMIT ?1"
            ),
            mission_row_with_archive,
        ),
        (
            format!(
                "SELECT {MISSION_COLS_ORIGIN} FROM missions m{where_origin} \
                 ORDER BY m.created_at DESC LIMIT ?1"
            ),
            mission_row_with_archive,
        ),
        (
            format!(
                "SELECT {MISSION_ARCHIVE_COLS} FROM missions m \
                 LEFT JOIN mission_archive a ON a.mission_id = m.id \
                 ORDER BY m.created_at DESC LIMIT ?1"
            ),
            mission_row_with_archive,
        ),
        (
            format!("SELECT {MISSION_COLS} FROM missions ORDER BY created_at DESC LIMIT ?1"),
            mission_row,
        ),
    ];
    let mut last_err: Option<rusqlite::Error> = None;
    for (sql, mapper) in candidates {
        match conn.prepare(&sql) {
            Ok(mut stmt) => {
                let rows = stmt
                    .query_map([limit], mapper)?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                return Ok(rows);
            }
            Err(e) if is_schema_drift(&e) => last_err = Some(e),
            Err(e) => return Err(e.into()),
        }
    }
    Err(last_err.expect("candidates is non-empty").into())
}

/// Mission detail plus its runs. `None` when the mission id is unknown.
pub fn get_mission(path: &Path, id: &str) -> Result<Option<(Value, Vec<Value>)>, DbError> {
    let conn = open_ro(path)?;
    let candidates: [(String, RowMapper); 4] = [
        (
            format!(
                "SELECT {MISSION_ARCHIVE_COLS_ORIGIN} FROM missions m \
                 LEFT JOIN mission_archive a ON a.mission_id = m.id WHERE m.id = ?1"
            ),
            mission_row_with_archive,
        ),
        (
            format!("SELECT {MISSION_COLS_ORIGIN} FROM missions m WHERE m.id = ?1"),
            mission_row_with_archive,
        ),
        (
            format!(
                "SELECT {MISSION_ARCHIVE_COLS} FROM missions m \
                 LEFT JOIN mission_archive a ON a.mission_id = m.id WHERE m.id = ?1"
            ),
            mission_row_with_archive,
        ),
        (
            format!("SELECT {MISSION_COLS} FROM missions WHERE id = ?1"),
            mission_row,
        ),
    ];
    let mut mission: Option<Value> = None;
    let mut last_err: Option<rusqlite::Error> = None;
    for (sql, mapper) in candidates {
        match conn.query_row(&sql, [id], mapper) {
            Ok(v) => {
                mission = Some(v);
                last_err = None;
                break;
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
            Err(e) if is_schema_drift(&e) => last_err = Some(e),
            Err(e) => return Err(e.into()),
        }
    }
    let mission = match (mission, last_err) {
        (Some(v), _) => v,
        (None, Some(e)) => return Err(e.into()),
        (None, None) => return Ok(None),
    };
    let sql = format!("SELECT {RUN_COLS} FROM runs WHERE mission_id = ?1 ORDER BY started_at DESC");
    let mut stmt = conn.prepare(&sql)?;
    let runs = stmt
        .query_map([id], run_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(Some((mission, runs)))
}

/// Projects ordered by created_at DESC. Returns `Ok(vec![])` when the `projects`
/// table does not exist yet (pre-0005 DB) so the gateway never 503s.
pub fn list_projects(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {PROJECT_COLS} FROM projects ORDER BY created_at DESC LIMIT ?1");
    let mut stmt = match conn.prepare(&sql) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(vec![]);
        }
        Err(e) => return Err(e.into()),
    };
    let rows = stmt
        .query_map([limit], project_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// Project detail plus the missions linked to it. `None` when the project id is
/// unknown or the `projects` table does not exist yet.
pub fn get_project(path: &Path, id: &str) -> Result<Option<(Value, Vec<Value>)>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {PROJECT_COLS} FROM projects WHERE id = ?1");
    let project = match conn.query_row(&sql, [id], project_row) {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(None);
        }
        Err(e) => return Err(e.into()),
    };
    // A projects row exists ⇒ 0005 was applied ⇒ missions.project_id exists.
    let sql = format!(
        "SELECT {MISSION_ARCHIVE_COLS} FROM missions m \
         LEFT JOIN mission_archive a ON a.mission_id = m.id \
         WHERE m.project_id = ?1 ORDER BY m.created_at DESC"
    );
    let missions = match conn.prepare(&sql) {
        Ok(mut stmt) => stmt
            .query_map([id], mission_row_with_archive)?
            .collect::<rusqlite::Result<Vec<_>>>()?,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            let sql = format!(
                "SELECT {MISSION_COLS} FROM missions WHERE project_id = ?1 ORDER BY created_at DESC"
            );
            let mut stmt = conn.prepare(&sql)?;
            let rows = stmt
                .query_map([id], mission_row)?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            rows
        }
        Err(e) => return Err(e.into()),
    };
    Ok(Some((project, missions)))
}

/// Custom Graphify scopes (0025) ordered by creation. Returns `Ok(vec![])`
/// when the `graph_scopes` table does not exist yet so the tabs render
/// built-ins only, never 503.
pub fn list_graph_scopes(path: &Path) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let mut stmt = match conn.prepare(
        "SELECT id, label, root_path, kind, created_at, updated_at \
         FROM graph_scopes ORDER BY created_at ASC",
    ) {
        Ok(s) => s,
        Err(e) if is_schema_drift(&e) => return Ok(vec![]),
        Err(e) => return Err(e.into()),
    };
    let rows = stmt
        .query_map([], |row| {
            Ok(json!({
                "id": row.get::<_, String>(0)?,
                "label": row.get::<_, String>(1)?,
                "root_path": row.get::<_, String>(2)?,
                "kind": row.get::<_, String>(3)?,
                "created_at": row.get::<_, String>(4)?,
                "updated_at": row.get::<_, String>(5)?,
            }))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// Focus rows ordered by created_at DESC — active only unless `include_archived`
/// (the Command Center focus switcher lists archived goal sets so they can be
/// reactivated). Returns `Ok(vec![])` when the `focus` table does not exist yet
/// (pre-0009 DB) so the gateway never 503s.
pub fn list_focus(path: &Path, limit: i64, include_archived: bool) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let where_status = if include_archived {
        ""
    } else {
        " WHERE status = 'active'"
    };
    let sql =
        format!("SELECT {FOCUS_COLS} FROM focus{where_status} ORDER BY created_at DESC LIMIT ?1");
    let mut stmt = match conn.prepare(&sql) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(vec![]);
        }
        Err(e) => return Err(e.into()),
    };
    let rows = stmt
        .query_map([limit], focus_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// The single newest active focus (the Current Focus). `Ok(None)` when there is
/// no active focus or the `focus` table does not exist yet.
pub fn current_focus(path: &Path) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!(
        "SELECT {FOCUS_COLS} FROM focus WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
    );
    match conn.query_row(&sql, [], focus_row) {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            Ok(None)
        }
        Err(e) => Err(e.into()),
    }
}

/// Focus detail by id (used for read-back after create). `Ok(None)` when the id
/// is unknown or the `focus` table does not exist yet.
pub fn get_focus(path: &Path, id: &str) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {FOCUS_COLS} FROM focus WHERE id = ?1");
    match conn.query_row(&sql, [id], focus_row) {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            Ok(None)
        }
        Err(e) => Err(e.into()),
    }
}

fn goal_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "focus_id": row.get::<_, Option<String>>(1)?,
        "parent_goal_id": row.get::<_, Option<String>>(2)?,
        "title": row.get::<_, String>(3)?,
        "description": row.get::<_, String>(4)?,
        "status": row.get::<_, String>(5)?,
        "position": row.get::<_, i64>(6)?,
        "created_at": row.get::<_, String>(7)?,
        "updated_at": row.get::<_, String>(8)?,
    }))
}

fn task_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "goal_id": row.get::<_, String>(1)?,
        "title": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "position": row.get::<_, i64>(4)?,
        "created_at": row.get::<_, String>(5)?,
        "updated_at": row.get::<_, String>(6)?,
    }))
}

fn observation_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "goal_id": row.get::<_, Option<String>>(1)?,
        "run_id": row.get::<_, Option<String>>(2)?,
        "body": row.get::<_, String>(3)?,
        "source": row.get::<_, String>(4)?,
        "created_at": row.get::<_, String>(5)?,
    }))
}

const GOAL_COLS: &str =
    "id, focus_id, parent_goal_id, title, description, status, position, created_at, updated_at";
const TASK_COLS: &str = "id, goal_id, title, status, position, created_at, updated_at";
const OBSERVATION_COLS: &str = "id, goal_id, run_id, body, source, created_at";

/// Goal detail by id (read-back after create). `Ok(None)` if unknown / table absent.
pub fn get_goal(path: &Path, id: &str) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {GOAL_COLS} FROM goals WHERE id = ?1");
    match conn.query_row(&sql, [id], goal_row) {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            Ok(None)
        }
        Err(e) => Err(e.into()),
    }
}

/// The non-archived goal forest for a focus: top-level goals each with nested
/// `children`, their `tasks`, and recent `observations`. Mirrors
/// goal_service.build_goal_tree. Returns `Ok(vec![])` when the `goals` table does
/// not exist yet (pre-0010 DB) so the gateway never 503s.
pub fn goal_tree(path: &Path, focus_id: &str) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!(
        "SELECT {GOAL_COLS} FROM goals WHERE focus_id = ?1 AND status != 'archived' \
         ORDER BY position ASC, created_at ASC"
    );
    let mut stmt = match conn.prepare(&sql) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(vec![]);
        }
        Err(e) => return Err(e.into()),
    };
    // (id, parent_goal_id, base goal JSON)
    let goals: Vec<(String, Option<String>, Value)> = stmt
        .query_map([focus_id], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, Option<String>>(2)?,
                goal_row(row)?,
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    if goals.is_empty() {
        return Ok(vec![]);
    }

    // Group tasks / observations by goal_id, filtered to this focus's goals in
    // SQL (tables co-created in 0010; tolerate absence). The IN-subquery keeps
    // the scan bounded — loading whole tables grew with global dataset size.
    let tasks_by_goal = group_by_goal(
        &conn,
        &format!(
            "SELECT {TASK_COLS} FROM tasks \
             WHERE goal_id IN (SELECT id FROM goals WHERE focus_id = ?1) \
             ORDER BY position ASC, created_at ASC"
        ),
        focus_id,
        task_row,
    )?;
    let obs_by_goal = group_by_goal(
        &conn,
        &format!(
            "SELECT {OBSERVATION_COLS} FROM observations \
             WHERE goal_id IN (SELECT id FROM goals WHERE focus_id = ?1) \
             ORDER BY created_at DESC"
        ),
        focus_id,
        observation_row,
    )?;

    Ok(build_goal_nodes(None, &goals, &tasks_by_goal, &obs_by_goal))
}

/// Run a query whose row's column index 1 is `goal_id`, grouping mapped rows by it.
/// `goal_id` may be NULL (run-level observations from the compounding loop carry
/// no goal) — those never match the focus IN-subquery, they belong to no goal in
/// the tree. A missing table yields an empty map (graceful pre-0010 degradation).
fn group_by_goal(
    conn: &Connection,
    sql: &str,
    focus_id: &str,
    mapper: fn(&rusqlite::Row<'_>) -> rusqlite::Result<Value>,
) -> Result<HashMap<String, Vec<Value>>, DbError> {
    let mut stmt = match conn.prepare(sql) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(HashMap::new());
        }
        Err(e) => return Err(e.into()),
    };
    let rows: Vec<(Option<String>, Value)> = stmt
        .query_map([focus_id], |row| {
            Ok((row.get::<_, Option<String>>(1)?, mapper(row)?))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let mut map: HashMap<String, Vec<Value>> = HashMap::new();
    for (gid, v) in rows {
        if let Some(gid) = gid {
            map.entry(gid).or_default().push(v);
        }
    }
    Ok(map)
}

/// Recursively assemble goal nodes whose parent matches `parent` (None = roots).
fn build_goal_nodes(
    parent: Option<&str>,
    goals: &[(String, Option<String>, Value)],
    tasks_by_goal: &HashMap<String, Vec<Value>>,
    obs_by_goal: &HashMap<String, Vec<Value>>,
) -> Vec<Value> {
    let mut out = Vec::new();
    for (id, p, base) in goals.iter() {
        if p.as_deref() != parent {
            continue;
        }
        let mut node = base.clone();
        if let Some(obj) = node.as_object_mut() {
            obj.insert(
                "tasks".into(),
                json!(tasks_by_goal.get(id).cloned().unwrap_or_default()),
            );
            let obs: Vec<Value> = obs_by_goal
                .get(id)
                .cloned()
                .unwrap_or_default()
                .into_iter()
                .take(10)
                .collect();
            obj.insert("observations".into(), json!(obs));
            obj.insert(
                "children".into(),
                json!(build_goal_nodes(
                    Some(id),
                    goals,
                    tasks_by_goal,
                    obs_by_goal
                )),
            );
        }
        out.push(node);
    }
    out
}

/// Optional modules ordered by id ASC. Returns `Ok(vec![])` when the `modules`
/// table does not exist yet (pre-0007 DB) so the gateway never 503s.
pub fn list_modules(path: &Path) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {MODULE_COLS} FROM modules ORDER BY id ASC");
    let mut stmt = match conn.prepare(&sql) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(vec![]);
        }
        Err(original) => {
            // Pre-0023 database (missing manifest columns): serve the legacy
            // shape until migrations run. Any other failure propagates.
            let legacy = "SELECT id, name, description, status, activated_at \
                          FROM modules ORDER BY id ASC";
            match conn.prepare(legacy) {
                Ok(mut stmt) => {
                    let rows = stmt
                        .query_map([], module_row_legacy)?
                        .collect::<rusqlite::Result<Vec<_>>>()?;
                    return Ok(rows);
                }
                Err(_) => return Err(original.into()),
            }
        }
    };
    let rows = stmt
        .query_map([], module_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// Slash commands contributed by active, present manifest modules.
/// Built-in command names are never shadowed; first module wins a collision.
pub fn list_module_commands(path: &Path) -> Result<Vec<Value>, DbError> {
    const RESERVED: [&str; 7] = [
        "init",
        "review",
        "dream",
        "distill",
        "goal",
        "mission",
        "deep-research",
    ];
    let conn = open_ro(path)?;
    let sql = "SELECT id, manifest_json FROM modules \
               WHERE status='active' AND missing=0 AND manifest_json != '' \
               ORDER BY id ASC";
    // Pre-0007 (no table) or pre-0023 (no manifest columns) databases have no
    // module commands by definition — degrade to an empty catalog, never 500.
    let Ok(mut stmt) = conn.prepare(sql) else {
        return Ok(vec![]);
    };
    let rows: Vec<(String, String)> = stmt
        .query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let mut taken: std::collections::HashSet<String> =
        RESERVED.iter().map(|s| s.to_string()).collect();
    let mut commands = Vec::new();
    for (module_id, manifest_json) in rows {
        let Ok(manifest) = serde_json::from_str::<Value>(&manifest_json) else {
            continue;
        };
        let Some(entries) = manifest
            .pointer("/capabilities/commands")
            .and_then(Value::as_array)
        else {
            continue;
        };
        for entry in entries {
            let name = entry.get("name").and_then(Value::as_str).unwrap_or("");
            if name.is_empty() || taken.contains(name) {
                continue;
            }
            taken.insert(name.to_string());
            commands.push(json!({
                "name": name,
                "description": entry.get("description").and_then(Value::as_str).unwrap_or(""),
                "template": entry.get("template").and_then(Value::as_str).unwrap_or(""),
                "module": module_id,
            }));
        }
    }
    Ok(commands)
}

fn module_row_legacy(row: &rusqlite::Row<'_>) -> rusqlite::Result<Value> {
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "name": row.get::<_, String>(1)?,
        "description": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "activated_at": row.get::<_, Option<String>>(4)?,
        "version": "",
        "source_path": "",
        "manifest": Value::Null,
        "missing": false,
    }))
}

/// Single module by id. `None` when unknown or the `modules` table is absent.
pub fn get_module(path: &Path, id: &str) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {MODULE_COLS} FROM modules WHERE id = ?1");
    match conn.query_row(&sql, [id], module_row) {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            Ok(None)
        }
        Err(original) => {
            // Pre-0023 database: fall back to the legacy column set.
            let legacy =
                "SELECT id, name, description, status, activated_at FROM modules WHERE id = ?1";
            match conn.query_row(legacy, [id], module_row_legacy) {
                Ok(v) => Ok(Some(v)),
                Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
                Err(_) => Err(original.into()),
            }
        }
    }
}

/// Cross-mission run feed: runs joined to their mission title, newest first.
/// One query — replaces the cockpit's listMissions -> getMission N+1 fan-out.
/// `mission_origin` (0024) lets callers regroup chat-origin runs by session
/// client-side; pre-0024 DBs fall back to the un-joined origin column and the
/// row mapper degrades it to "" (legacy/unknown), same convention as
/// `mission_row_with_archive`.
pub fn list_runs(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let candidates = [
        format!(
            "SELECT {RUN_COLS_QUALIFIED}, m.title, m.origin \
             FROM runs r JOIN missions m ON m.id = r.mission_id \
             ORDER BY r.started_at DESC LIMIT ?1"
        ),
        format!(
            "SELECT {RUN_COLS_QUALIFIED}, m.title \
             FROM runs r JOIN missions m ON m.id = r.mission_id \
             ORDER BY r.started_at DESC LIMIT ?1"
        ),
    ];
    let mut last_err: Option<rusqlite::Error> = None;
    for sql in candidates {
        match conn.prepare(&sql) {
            Ok(mut stmt) => {
                let rows = stmt
                    .query_map([limit], |row| {
                        let mut run = run_row(row)?;
                        run["mission_title"] = Value::String(row.get::<_, String>(8)?);
                        run["mission_origin"] =
                            Value::String(row.get::<_, String>(9).unwrap_or_default());
                        Ok(run)
                    })?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                return Ok(rows);
            }
            Err(e) if is_schema_drift(&e) => last_err = Some(e),
            Err(e) => return Err(e.into()),
        }
    }
    Err(last_err.expect("candidates is non-empty").into())
}

pub fn get_run(path: &Path, id: &str) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {RUN_COLS} FROM runs WHERE id = ?1");
    match conn.query_row(&sql, [id], run_row) {
        Ok(v) => Ok(Some(v)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

/// Run status string, `None` when the run id is unknown.
pub fn run_status(path: &Path, id: &str) -> Result<Option<String>, DbError> {
    let conn = open_ro(path)?;
    match conn.query_row("SELECT status FROM runs WHERE id = ?1", [id], |r| {
        r.get::<_, String>(0)
    }) {
        Ok(s) => Ok(Some(s)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e.into()),
    }
}

#[derive(Debug)]
pub struct MissionLoopStreamSnapshot {
    pub state: String,
    pub last_run_id: Option<String>,
    pub newer_running_run_id: Option<String>,
}

/// Goal-loop state relevant to a terminal run stream. `None` means the schema
/// or mission loop is absent, preserving ordinary per-run SSE behavior.
pub fn mission_loop_stream_snapshot(
    path: &Path,
    current_run_id: &str,
) -> Result<Option<MissionLoopStreamSnapshot>, DbError> {
    let conn = open_ro(path)?;
    let has_table = conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='mission_loops')",
        [],
        |row| row.get::<_, i64>(0),
    )? != 0;
    if !has_table {
        return Ok(None);
    }

    match conn.query_row(
        "SELECT ml.state, ml.last_run_id, \
                (SELECT newer.id FROM runs newer \
                 WHERE newer.mission_id = current.mission_id \
                   AND newer.status = 'running' \
                   AND newer.rowid > current.rowid \
                 ORDER BY newer.rowid ASC LIMIT 1) \
         FROM runs current \
         JOIN mission_loops ml ON ml.mission_id = current.mission_id \
         WHERE current.id = ?1",
        [current_run_id],
        |row| {
            Ok(MissionLoopStreamSnapshot {
                state: row.get(0)?,
                last_run_id: row.get(1)?,
                newer_running_run_id: row.get(2)?,
            })
        },
    ) {
        Ok(snapshot) => Ok(Some(snapshot)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(error) => Err(error.into()),
    }
}

/// Audit events for a run after a rowid cursor, ascending. Returns the events
/// and the cursor of the last event (unchanged when no new events).
pub fn list_events(
    path: &Path,
    run_id: &str,
    after: i64,
    limit: i64,
) -> Result<(Vec<Value>, i64), DbError> {
    let conn = open_ro(path)?;
    let sql = if table_exists(&conn, "evidence_change_sets")? {
        "SELECT ae.rowid,ae.id,ae.event_type,ae.tool_name,ae.timestamp,
                ae.duration_ms,ae.data,ae.policy_result,ae.task_id,ae.session_id,
                ae.tool_call_id,cs.actor_id,cs.parent_actor_id,cs.team_run_id
         FROM audit_events ae
         LEFT JOIN evidence_change_sets cs
           ON cs.id=COALESCE(
                json_extract(ae.data,'$.evidence.change_set_id'),
                json_extract(ae.data,'$.change_set_id'))
         WHERE ae.run_id=?1 AND ae.rowid>?2
         ORDER BY ae.rowid LIMIT ?3"
    } else {
        "SELECT rowid,id,event_type,tool_name,timestamp,duration_ms,data,
                policy_result,task_id,session_id,tool_call_id,NULL,NULL,NULL
         FROM audit_events
         WHERE run_id=?1 AND rowid>?2
         ORDER BY rowid LIMIT ?3"
    };
    let mut stmt = conn.prepare(sql)?;
    let mut cursor = after;
    let rows = stmt
        .query_map(rusqlite::params![run_id, after, limit], |row| {
            let rowid: i64 = row.get(0)?;
            let raw_data: String = row.get(6)?;
            let data =
                metadata_only_evidence_data(&raw_data, row.get(11)?, row.get(12)?, row.get(13)?);
            Ok((
                rowid,
                json!({
                    "cursor": rowid,
                    "id": row.get::<_, String>(1)?,
                    "run_id": run_id,
                    "event_type": row.get::<_, String>(2)?,
                    "tool_name": row.get::<_, Option<String>>(3)?,
                    "timestamp": row.get::<_, String>(4)?,
                    "duration_ms": row.get::<_, Option<i64>>(5)?,
                    "data": data,
                    "policy_result": row.get::<_, Option<String>>(7)?,
                    "task_id": row.get::<_, Option<String>>(8)?,
                    "session_id": row.get::<_, Option<String>>(9)?,
                    "tool_call_id": row.get::<_, Option<String>>(10)?,
                }),
            ))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let events = rows
        .into_iter()
        .map(|(rowid, v)| {
            cursor = cursor.max(rowid);
            v
        })
        .collect();
    Ok((events, cursor))
}

fn metadata_only_evidence_data(
    raw_data: &str,
    actor_id: Option<String>,
    parent_actor_id: Option<String>,
    team_run_id: Option<String>,
) -> Value {
    let parsed = serde_json::from_str::<Value>(raw_data)
        .unwrap_or_else(|_| Value::String(raw_data.to_string()));
    let Some(evidence) = parsed.get("evidence").and_then(Value::as_object) else {
        return parsed;
    };
    const SAFE_KEYS: &[&str] = &[
        "change_set_id",
        "capture_status",
        "status",
        "coverage",
        "file_count",
        "additions",
        "deletions",
        "redaction_count",
        "error_code",
        "duration_ms",
    ];
    let mut metadata = serde_json::Map::new();
    for key in SAFE_KEYS {
        if let Some(value) = evidence.get(*key) {
            metadata.insert((*key).to_string(), value.clone());
        }
    }
    if let Some(actor_id) = actor_id {
        metadata.insert("actor_id".into(), Value::String(actor_id));
    }
    if let Some(parent_actor_id) = parent_actor_id {
        metadata.insert("parent_actor_id".into(), Value::String(parent_actor_id));
    }
    if let Some(team_run_id) = team_run_id {
        metadata.insert("team_run_id".into(), Value::String(team_run_id));
    }
    json!({"evidence": metadata})
}

/// Cross-run audit feed ordered by the database-global rowid. The opaque
/// cursor never compares rowids from different databases or per-run feeds.
pub fn list_audit_events(
    path: &Path,
    filters: &AuditEventFilters,
    after: Option<&str>,
    limit: i64,
) -> Result<(Vec<AuditEventRecord>, Option<String>), DbError> {
    let conn = open_ro(path)?;
    let after_rowid = match after {
        Some(cursor) => EvidenceCursor::decode(cursor)?
            .sort_key
            .parse::<i64>()
            .map_err(|_| invalid_input("audit cursor is not numeric"))?,
        None => 0,
    };
    let sql = if table_exists(&conn, "evidence_change_sets")? {
        "SELECT ae.rowid,ae.id,ae.run_id,ae.session_id,ae.event_type,ae.tool_name,
                ae.timestamp,ae.duration_ms,ae.data,ae.policy_result,ae.task_id,
                ae.tool_call_id,cs.actor_id,cs.parent_actor_id,cs.team_run_id
         FROM audit_events ae
         LEFT JOIN evidence_change_sets cs
           ON cs.id=COALESCE(
                json_extract(ae.data,'$.evidence.change_set_id'),
                json_extract(ae.data,'$.change_set_id'))
         WHERE ae.rowid > ?1
           AND (?2 IS NULL OR ae.run_id = ?2)
           AND (?3 IS NULL OR ae.session_id = ?3)
           AND (?4 IS NULL OR cs.actor_id = ?4)
           AND (?5 IS NULL OR ae.event_type = ?5)
           AND (?6 IS NULL OR ae.tool_name = ?6)
         ORDER BY ae.rowid
         LIMIT ?7"
    } else {
        "SELECT rowid,id,run_id,session_id,event_type,tool_name,timestamp,
                duration_ms,data,policy_result,task_id,tool_call_id,NULL,NULL,NULL
         FROM audit_events
         WHERE rowid > ?1
           AND (?2 IS NULL OR run_id = ?2)
           AND (?3 IS NULL OR session_id = ?3)
           AND ?4 IS NULL
           AND (?5 IS NULL OR event_type = ?5)
           AND (?6 IS NULL OR tool_name = ?6)
         ORDER BY rowid
         LIMIT ?7"
    };
    let mut statement = conn.prepare(sql)?;
    let rows = statement
        .query_map(
            rusqlite::params![
                after_rowid,
                filters.run_id,
                filters.session_id,
                filters.actor_id,
                filters.event_type,
                filters.tool_name,
                evidence_limit(limit),
            ],
            |row| {
                let rowid = row.get::<_, i64>(0)?;
                let id = row.get::<_, String>(1)?;
                let raw_data = row.get::<_, String>(8)?;
                Ok((
                    rowid,
                    AuditEventRecord {
                        cursor: EvidenceCursor::new(rowid.to_string(), &id).encode(),
                        id,
                        run_id: row.get(2)?,
                        session_id: row.get(3)?,
                        event_type: row.get(4)?,
                        tool_name: row.get(5)?,
                        timestamp: row.get(6)?,
                        duration_ms: row.get(7)?,
                        data: metadata_only_evidence_data(
                            &raw_data,
                            row.get(12)?,
                            row.get(13)?,
                            row.get(14)?,
                        ),
                        policy_result: row.get(9)?,
                        task_id: row.get(10)?,
                        tool_call_id: row.get(11)?,
                    },
                ))
            },
        )?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let next = rows
        .last()
        .map(|(rowid, event)| EvidenceCursor::new(rowid.to_string(), &event.id).encode());
    Ok((rows.into_iter().map(|(_, event)| event).collect(), next))
}

pub fn list_change_sets(
    path: &Path,
    scope: &ChangeSetScope,
    after: Option<&str>,
    limit: i64,
) -> Result<(Vec<ChangeSetRecord>, Option<String>), DbError> {
    let conn = open_ro(path)?;
    let cursor = after
        .map(EvidenceCursor::decode)
        .transpose()?
        .unwrap_or_else(|| EvidenceCursor::new("", ""));
    let (column, scope_id) = match scope {
        ChangeSetScope::Run(id) => ("run_id", id),
        ChangeSetScope::Session(id) => ("session_id", id),
        ChangeSetScope::TeamRun(id) => ("team_run_id", id),
    };
    // column is selected from a closed enum above, never user input.
    let sql = format!(
        "SELECT cs.id,cs.run_id,cs.session_id,cs.team_run_id,cs.turn_id,
                cs.actor_id,cs.parent_actor_id,cs.tool_call_id,cs.coverage,
                cs.status,cs.redaction_count,cs.created_at,
                COUNT(fc.id),COALESCE(SUM(fc.additions),0),
                COALESCE(SUM(fc.deletions),0)
         FROM evidence_change_sets cs
         LEFT JOIN evidence_file_changes fc ON fc.change_set_id=cs.id
         WHERE cs.{column}=?1 AND (cs.created_at,cs.id) > (?2,?3)
         GROUP BY cs.id
         ORDER BY cs.created_at,cs.id
         LIMIT ?4"
    );
    let mut statement = conn.prepare(&sql)?;
    let rows = statement
        .query_map(
            rusqlite::params![scope_id, cursor.sort_key, cursor.id, evidence_limit(limit)],
            change_set_row,
        )?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let next = rows
        .last()
        .map(|item| EvidenceCursor::new(&item.created_at, &item.id).encode());
    Ok((rows, next))
}

fn change_set_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<ChangeSetRecord> {
    Ok(ChangeSetRecord {
        id: row.get(0)?,
        provenance: EvidenceProvenanceRecord {
            run_id: row.get(1)?,
            session_id: row.get(2)?,
            team_run_id: row.get(3)?,
            turn_id: row.get(4)?,
            actor_id: row.get(5)?,
            parent_actor_id: row.get(6)?,
            tool_call_id: row.get(7)?,
        },
        coverage: row.get(8)?,
        status: row.get(9)?,
        redaction_count: row.get(10)?,
        created_at: row.get(11)?,
        file_count: row.get(12)?,
        additions: row.get(13)?,
        deletions: row.get(14)?,
    })
}

pub fn get_change_set(
    path: &Path,
    session_id: &str,
    change_set_id: &str,
) -> Result<Option<ChangeSetRecord>, DbError> {
    let conn = open_ro(path)?;
    conn.query_row(
        "SELECT cs.id,cs.run_id,cs.session_id,cs.team_run_id,cs.turn_id,
                cs.actor_id,cs.parent_actor_id,cs.tool_call_id,cs.coverage,
                cs.status,cs.redaction_count,cs.created_at,
                COUNT(fc.id),COALESCE(SUM(fc.additions),0),
                COALESCE(SUM(fc.deletions),0)
         FROM evidence_change_sets cs
         LEFT JOIN evidence_file_changes fc ON fc.change_set_id=cs.id
         WHERE cs.id=?1 AND cs.session_id=?2
         GROUP BY cs.id",
        rusqlite::params![change_set_id, session_id],
        change_set_row,
    )
    .optional()
    .map_err(Into::into)
}

pub fn run_owner_session(path: &Path, run_id: &str) -> Result<Option<Option<String>>, DbError> {
    let conn = open_ro(path)?;
    conn.query_row("SELECT session_id FROM runs WHERE id=?1", [run_id], |row| {
        row.get::<_, Option<String>>(0)
    })
    .optional()
    .map_err(Into::into)
}

pub fn change_set_owner_session(
    path: &Path,
    change_set_id: &str,
) -> Result<Option<String>, DbError> {
    let conn = open_ro(path)?;
    conn.query_row(
        "SELECT session_id FROM evidence_change_sets WHERE id=?1",
        [change_set_id],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .map_err(Into::into)
}

pub fn file_change_owner_session(
    path: &Path,
    file_change_id: &str,
) -> Result<Option<String>, DbError> {
    let conn = open_ro(path)?;
    conn.query_row(
        "SELECT cs.session_id
         FROM evidence_file_changes fc
         JOIN evidence_change_sets cs ON cs.id=fc.change_set_id
         WHERE fc.id=?1",
        [file_change_id],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .map_err(Into::into)
}

pub fn result_owner_session(path: &Path, evidence_id: &str) -> Result<Option<String>, DbError> {
    let conn = open_ro(path)?;
    conn.query_row(
        "SELECT r.session_id
         FROM evidence_full_results fr
         JOIN runs r ON r.id=fr.run_id
         WHERE fr.id=?1",
        [evidence_id],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .map_err(Into::into)
}

pub fn list_file_changes(
    path: &Path,
    change_set_id: &str,
    after: Option<&str>,
    limit: i64,
) -> Result<(Vec<Value>, Option<String>), DbError> {
    let conn = open_ro(path)?;
    let cursor = after
        .map(EvidenceCursor::decode)
        .transpose()?
        .unwrap_or_else(|| EvidenceCursor::new("", ""));
    let mut statement = conn.prepare(
        "SELECT id,path,old_path,operation,availability,before_sha256,after_sha256,
                before_bytes,after_bytes,additions,deletions,binary,generated,
                mode_before,mode_after,redaction_count
         FROM evidence_file_changes
         WHERE change_set_id=?1 AND id>?2
         ORDER BY id
         LIMIT ?3",
    )?;
    let rows = statement
        .query_map(
            rusqlite::params![change_set_id, cursor.id, evidence_limit(limit)],
            |row| {
                let id = row.get::<_, String>(0)?;
                Ok((
                    id.clone(),
                    json!({
                        "id": id,
                        "change_set_id": change_set_id,
                        "path": row.get::<_, String>(1)?,
                        "old_path": row.get::<_, Option<String>>(2)?,
                        "operation": row.get::<_, String>(3)?,
                        "availability": row.get::<_, String>(4)?,
                        "before_sha256": row.get::<_, Option<String>>(5)?,
                        "after_sha256": row.get::<_, Option<String>>(6)?,
                        "before_bytes": row.get::<_, i64>(7)?,
                        "after_bytes": row.get::<_, i64>(8)?,
                        "additions": row.get::<_, i64>(9)?,
                        "deletions": row.get::<_, i64>(10)?,
                        "binary": row.get::<_, i64>(11)? != 0,
                        "generated": row.get::<_, i64>(12)? != 0,
                        "mode_before": row.get::<_, Option<String>>(13)?,
                        "mode_after": row.get::<_, Option<String>>(14)?,
                        "redaction_count": row.get::<_, i64>(15)?,
                    }),
                ))
            },
        )?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let next = rows
        .last()
        .map(|(id, _)| EvidenceCursor::new("", id).encode());
    Ok((rows.into_iter().map(|(_, value)| value).collect(), next))
}

pub fn list_hunks(
    path: &Path,
    file_change_id: &str,
    after: Option<&str>,
    limit: i64,
) -> Result<(Vec<Value>, Option<String>), DbError> {
    let conn = open_ro(path)?;
    let after_index = after
        .map(EvidenceCursor::decode)
        .transpose()?
        .map(|cursor| {
            cursor
                .sort_key
                .parse::<i64>()
                .map_err(|_| invalid_input("hunk cursor is not numeric"))
        })
        .transpose()?
        .unwrap_or(-1);
    let mut statement = conn.prepare(
        "SELECT id,hunk_index,old_start,old_lines,new_start,new_lines,
                patch_start_byte,patch_bytes,redacted
         FROM evidence_hunks
         WHERE file_change_id=?1 AND hunk_index>?2
         ORDER BY hunk_index
         LIMIT ?3",
    )?;
    let rows = statement
        .query_map(
            rusqlite::params![file_change_id, after_index, evidence_limit(limit)],
            |row| {
                let id = row.get::<_, String>(0)?;
                let index = row.get::<_, i64>(1)?;
                Ok((
                    index,
                    id.clone(),
                    json!({
                        "id": id,
                        "file_change_id": file_change_id,
                        "hunk_index": index,
                        "old_start": row.get::<_, i64>(2)?,
                        "old_lines": row.get::<_, i64>(3)?,
                        "new_start": row.get::<_, i64>(4)?,
                        "new_lines": row.get::<_, i64>(5)?,
                        "patch_start_byte": row.get::<_, i64>(6)?,
                        "patch_bytes": row.get::<_, i64>(7)?,
                        "redacted": row.get::<_, i64>(8)? != 0,
                    }),
                ))
            },
        )?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let next = rows
        .last()
        .map(|(index, id, _)| EvidenceCursor::new(index.to_string(), id).encode());
    Ok((rows.into_iter().map(|(_, _, value)| value).collect(), next))
}

pub fn get_file_patch(
    path: &Path,
    session_id: &str,
    file_change_id: &str,
    range: ContentRange,
) -> Result<Option<ContentPage>, DbError> {
    let conn = open_ro(path)?;
    let metadata = conn
        .query_row(
            "SELECT fc.availability,fc.binary,fc.patch_blob_id,b.size_bytes,b.sha256,
                    b.media_type,b.chunk_size
             FROM evidence_file_changes fc
             JOIN evidence_change_sets cs ON cs.id=fc.change_set_id
             LEFT JOIN evidence_blobs b ON b.id=fc.patch_blob_id
             WHERE fc.id=?1 AND cs.session_id=?2",
            rusqlite::params![file_change_id, session_id],
            |row| {
                Ok(BlobMetadata {
                    availability: if row.get::<_, i64>(1)? != 0 {
                        "binary".into()
                    } else {
                        row.get(0)?
                    },
                    blob_id: row.get(2)?,
                    total_bytes: row.get::<_, Option<i64>>(3)?.unwrap_or_default() as u64,
                    sha256: row.get(4)?,
                    media_type: row
                        .get::<_, Option<String>>(5)?
                        .unwrap_or_else(|| "text/x-diff".into()),
                    chunk_size: row.get::<_, Option<i64>>(6)?.unwrap_or(65_536) as u64,
                })
            },
        )
        .optional()?;
    metadata
        .map(|metadata| read_blob_range(&conn, metadata, range))
        .transpose()
}

pub fn get_result_range(
    path: &Path,
    session_id: &str,
    evidence_id: &str,
    range: ContentRange,
) -> Result<Option<ContentPage>, DbError> {
    let conn = open_ro(path)?;
    let metadata = conn
        .query_row(
            "SELECT fr.availability,fr.blob_id,fr.full_bytes,fr.sha256,fr.media_type,
                    b.chunk_size
             FROM evidence_full_results fr
             JOIN runs r ON r.id=fr.run_id
             LEFT JOIN evidence_blobs b ON b.id=fr.blob_id
             WHERE fr.id=?1 AND r.session_id=?2",
            rusqlite::params![evidence_id, session_id],
            |row| {
                Ok(BlobMetadata {
                    availability: row.get(0)?,
                    blob_id: row.get(1)?,
                    total_bytes: row.get::<_, i64>(2)? as u64,
                    sha256: row.get(3)?,
                    media_type: row.get(4)?,
                    chunk_size: row.get::<_, Option<i64>>(5)?.unwrap_or(65_536) as u64,
                })
            },
        )
        .optional()?;
    metadata
        .map(|metadata| read_blob_range(&conn, metadata, range))
        .transpose()
}

struct BlobMetadata {
    availability: String,
    blob_id: Option<String>,
    total_bytes: u64,
    sha256: Option<String>,
    media_type: String,
    chunk_size: u64,
}

fn read_blob_range(
    conn: &Connection,
    metadata: BlobMetadata,
    range: ContentRange,
) -> Result<ContentPage, DbError> {
    let start = range.start.min(metadata.total_bytes);
    let end = range
        .start
        .saturating_add(range.length)
        .min(metadata.total_bytes);
    let mut bytes = Vec::with_capacity((end - start) as usize);
    if let Some(blob_id) = metadata.blob_id.as_deref() {
        if start < end {
            let first_chunk = start / metadata.chunk_size;
            let last_chunk = (end - 1) / metadata.chunk_size;
            let mut statement = conn.prepare(
                "SELECT chunk_index,content FROM evidence_blob_chunks
                 WHERE blob_id=?1 AND chunk_index BETWEEN ?2 AND ?3
                 ORDER BY chunk_index",
            )?;
            let chunks = statement.query_map(
                rusqlite::params![blob_id, first_chunk as i64, last_chunk as i64],
                |row| Ok((row.get::<_, u64>(0)?, row.get::<_, Vec<u8>>(1)?)),
            )?;
            for chunk in chunks {
                let (index, content) = chunk?;
                let chunk_start = index * metadata.chunk_size;
                let local_start = start.saturating_sub(chunk_start) as usize;
                let local_end = (end.saturating_sub(chunk_start) as usize).min(content.len());
                if local_start < local_end {
                    bytes.extend_from_slice(&content[local_start..local_end]);
                }
            }
        }
    }
    let expected = (end - start) as usize;
    let availability = if metadata.blob_id.is_some() && bytes.len() != expected {
        bytes.clear();
        "corrupt".to_string()
    } else if metadata.blob_id.is_none() && metadata.availability == "available" {
        "corrupt".to_string()
    } else {
        metadata.availability
    };
    Ok(ContentPage {
        bytes,
        total_bytes: metadata.total_bytes,
        start,
        end,
        availability,
        sha256: metadata.sha256,
        media_type: metadata.media_type,
    })
}

pub fn list_actor_history(
    path: &Path,
    session_id: &str,
    after: Option<&str>,
    limit: i64,
) -> Result<(Vec<Value>, Option<String>), DbError> {
    let conn = open_ro(path)?;
    let cursor = after
        .map(EvidenceCursor::decode)
        .transpose()?
        .unwrap_or_else(|| EvidenceCursor::new("", ""));
    let mut statement = conn.prepare(
        "SELECT id,parent_run_id,parent_actor_id,session_id,role,goal,model,mode,
                status,workspace_root,depth,child_run_id,result_preview,error,
                created_at,started_at,finished_at,updated_at
         FROM actors
         WHERE session_id=?1 AND (created_at,id)>(?2,?3)
         ORDER BY created_at,id
         LIMIT ?4",
    )?;
    let rows = statement
        .query_map(
            rusqlite::params![
                session_id,
                cursor.sort_key,
                cursor.id,
                evidence_limit(limit)
            ],
            |row| {
                let id = row.get::<_, String>(0)?;
                let created_at = row.get::<_, String>(14)?;
                Ok((
                    created_at.clone(),
                    id.clone(),
                    json!({
                        "id": id,
                        "parent_run_id": row.get::<_, String>(1)?,
                        "parent_actor_id": row.get::<_, Option<String>>(2)?,
                        "session_id": row.get::<_, Option<String>>(3)?,
                        "role": row.get::<_, String>(4)?,
                        "goal": row.get::<_, String>(5)?,
                        "model": row.get::<_, Option<String>>(6)?,
                        "mode": row.get::<_, String>(7)?,
                        "status": row.get::<_, String>(8)?,
                        "workspace_root": row.get::<_, Option<String>>(9)?,
                        "depth": row.get::<_, i64>(10)?,
                        "child_run_id": row.get::<_, Option<String>>(11)?,
                        "result_preview": row.get::<_, Option<String>>(12)?,
                        "error": row.get::<_, Option<String>>(13)?,
                        "created_at": created_at,
                        "started_at": row.get::<_, Option<String>>(15)?,
                        "finished_at": row.get::<_, Option<String>>(16)?,
                        "updated_at": row.get::<_, String>(17)?,
                    }),
                ))
            },
        )?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    let next = rows
        .last()
        .map(|(created_at, id, _)| EvidenceCursor::new(created_at, id).encode());
    Ok((rows.into_iter().map(|(_, _, value)| value).collect(), next))
}

/// Quote the whole input as a single FTS5 phrase with `""` doubling — the
/// exact escaping the Python wiki CLI uses (wiki_service.py), so the same
/// query returns the same results through both surfaces. A doubled-quote
/// phrase is always syntactically valid, so user input can never produce an
/// FTS syntax error here.
fn fts_quote(query: &str) -> String {
    format!("\"{}\"", query.replace('"', "\"\""))
}

pub fn wiki_search(path: &Path, query: &str, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let mut stmt = conn.prepare(
        "SELECT p.slug, p.title, snippet(wiki_fts, 1, '[', ']', '…', 16), \
                bm25(wiki_fts), p.updated_at \
         FROM wiki_fts JOIN wiki_pages p ON p.rowid = wiki_fts.rowid \
         WHERE wiki_fts MATCH ?1 ORDER BY bm25(wiki_fts) LIMIT ?2",
    )?;
    let rows = stmt
        .query_map(rusqlite::params![fts_quote(query), limit], |row| {
            Ok(json!({
                "slug": row.get::<_, String>(0)?,
                "title": row.get::<_, String>(1)?,
                "snippet": row.get::<_, String>(2)?,
                "score": row.get::<_, f64>(3)?,
                "updated_at": row.get::<_, String>(4)?,
            }))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

pub fn list_wiki_pages(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let mut stmt = conn.prepare(
        "SELECT id, slug, title, created_at, updated_at FROM wiki_pages ORDER BY updated_at DESC LIMIT ?1",
    )?;
    let rows = stmt
        .query_map([limit], |row| {
            Ok(json!({
                "id": row.get::<_, String>(0)?,
                "slug": row.get::<_, String>(1)?,
                "title": row.get::<_, String>(2)?,
                "created_at": row.get::<_, String>(3)?,
                "updated_at": row.get::<_, String>(4)?,
            }))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// Wiki page detail by slug. Returns `None` when slug is unknown (not DbError).
/// Provenance is sourced from `memory_provenance` via `item_id = slug`; if the
/// table is absent or no rows exist the field is `null` (never a DbError).
pub fn get_wiki_page(path: &Path, slug: &str) -> Result<Option<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = "SELECT slug, title, body, created_at, updated_at FROM wiki_pages WHERE slug = ?1";
    let page = match conn.query_row(sql, [slug], |row| {
        Ok(json!({
            "slug": row.get::<_, String>(0)?,
            "title": row.get::<_, String>(1)?,
            "body": row.get::<_, String>(2)?,
            "created_at": row.get::<_, String>(3)?,
            "updated_at": row.get::<_, String>(4)?,
        }))
    }) {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(e) => return Err(e.into()),
    };

    // Attempt to fetch the most recent provenance record. The table may not
    // exist yet (fresh databases), so any error is silently treated as absent.
    let provenance: Option<Value> = conn
        .query_row(
            "SELECT run_id, source_id, operator_id, sensitivity, written_at \
             FROM memory_provenance \
             WHERE item_id = ?1 \
             ORDER BY written_at DESC \
             LIMIT 1",
            [slug],
            |row| {
                Ok(json!({
                    "run_id": row.get::<_, Option<String>>(0)?,
                    "source_id": row.get::<_, Option<String>>(1)?,
                    "operator_id": row.get::<_, Option<String>>(2)?,
                    "sensitivity": row.get::<_, String>(3)?,
                    "written_at": row.get::<_, String>(4)?,
                }))
            },
        )
        .ok();

    let mut obj = page;
    obj["provenance"] = serde_json::to_value(provenance).unwrap_or(Value::Null);
    Ok(Some(obj))
}

/// Model registry list ordered by model_id. Returns `Ok(vec![])` when the
/// `model_registry` table does not exist (no models registered yet) so the
/// gateway never 503s on a fresh deployment.
pub fn list_models(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let mut stmt = match conn.prepare(
        "SELECT model_id, provider, source, first_seen, last_seen, active \
         FROM model_registry \
         ORDER BY model_id \
         LIMIT ?1",
    ) {
        Ok(s) => s,
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            return Ok(vec![]);
        }
        Err(e) => return Err(e.into()),
    };
    let rows = stmt
        .query_map([limit], |row| {
            Ok(json!({
                "model_id": row.get::<_, String>(0)?,
                "provider": row.get::<_, String>(1)?,
                "source": row.get::<_, String>(2)?,
                "first_seen": row.get::<_, String>(3)?,
                "last_seen": row.get::<_, String>(4)?,
                "active": row.get::<_, i64>(5)? != 0,
            }))
        })?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

fn cashflow_db_path() -> PathBuf {
    if let Some(p) = std::env::var_os("ATLAS_CASHFLOW_DB_PATH") {
        return PathBuf::from(p);
    }
    if let Some(root) = std::env::var_os("ATLAS_REPO_ROOT") {
        return PathBuf::from(root)
            .join("services")
            .join("cashflow")
            .join("dev.db");
    }
    std::env::current_dir()
        .unwrap_or_default()
        .join("services")
        .join("cashflow")
        .join("dev.db")
}

fn table_exists(conn: &Connection, name: &str) -> Result<bool, rusqlite::Error> {
    let count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
        [name],
        |r| r.get(0),
    )?;
    Ok(count > 0)
}

fn scalar_f64(conn: &Connection, sql: &str) -> Result<f64, rusqlite::Error> {
    conn.query_row(sql, [], |r| r.get::<_, f64>(0))
}

fn scalar_i64(conn: &Connection, sql: &str) -> Result<i64, rusqlite::Error> {
    conn.query_row(sql, [], |r| r.get::<_, i64>(0))
}

/// Native, read-only cashflow cockpit summary. This reads the vendored module's
/// local SQLite store directly; it does not require the Next.js cashflow server.
pub fn cashflow_summary() -> Result<Value, DbError> {
    let path = cashflow_db_path();
    if !path.exists() {
        return Ok(json!({
            "available": false,
            "db_path": path.to_string_lossy(),
            "metrics": {
                "active_clients": 0,
                "monthly_revenue": 0.0,
                "monthly_expenses": 0.0,
                "profit": 0.0,
                "outstanding": 0.0,
                "overdue_invoices": 0,
                "due_soon_invoices": 0
            },
            "clients": [],
            "invoices": [],
            "expenses": []
        }));
    }

    let conn = open_ro(&path)?;
    let has_clients = table_exists(&conn, "Client")?;
    let has_expenses = table_exists(&conn, "Expense")?;
    let has_invoices = table_exists(&conn, "Invoice")?;
    if !has_clients && !has_expenses && !has_invoices {
        return Ok(json!({
            "available": false,
            "db_path": path.to_string_lossy(),
            "metrics": {
                "active_clients": 0,
                "monthly_revenue": 0.0,
                "monthly_expenses": 0.0,
                "profit": 0.0,
                "outstanding": 0.0,
                "overdue_invoices": 0,
                "due_soon_invoices": 0
            },
            "clients": [],
            "invoices": [],
            "expenses": []
        }));
    }

    let active_clients = if has_clients {
        scalar_i64(&conn, "SELECT COUNT(*) FROM Client WHERE active = 1")?
    } else {
        0
    };
    let monthly_revenue = if has_clients {
        scalar_f64(
            &conn,
            "SELECT COALESCE(SUM(monthlyPayment), 0) FROM Client WHERE active = 1",
        )?
    } else {
        0.0
    };
    let monthly_expenses = if has_expenses {
        scalar_f64(
            &conn,
            "SELECT COALESCE(SUM(amount), 0) FROM Expense WHERE substr(date, 1, 7) = strftime('%Y-%m', 'now')",
        )?
    } else {
        0.0
    };
    let outstanding = if has_invoices {
        scalar_f64(
            &conn,
            "SELECT COALESCE(SUM(amount), 0) FROM Invoice WHERE status = 'pendente'",
        )?
    } else {
        0.0
    };
    let overdue_invoices = if has_invoices {
        scalar_i64(
            &conn,
            "SELECT COUNT(*) FROM Invoice WHERE status = 'pendente' AND dueDate < date('now')",
        )?
    } else {
        0
    };
    let due_soon_invoices = if has_invoices {
        scalar_i64(
            &conn,
            "SELECT COUNT(*) FROM Invoice WHERE status = 'pendente' \
             AND dueDate >= date('now') AND dueDate <= date('now', '+7 days')",
        )?
    } else {
        0
    };

    let clients = if has_clients {
        let mut stmt = conn.prepare(
            "SELECT id, name, service, monthlyPayment, startDate, contractMonths, active, phone, notes \
             FROM Client ORDER BY createdAt DESC LIMIT 8",
        )?;
        let rows = stmt
            .query_map([], |row| {
                Ok(json!({
                    "id": row.get::<_, String>(0)?,
                    "name": row.get::<_, String>(1)?,
                    "service": row.get::<_, String>(2)?,
                    "monthlyPayment": row.get::<_, f64>(3)?,
                    "startDate": row.get::<_, String>(4)?,
                    "contractMonths": row.get::<_, Option<i64>>(5)?.unwrap_or(0),
                    "active": row.get::<_, i64>(6)? != 0,
                    "phone": row.get::<_, Option<String>>(7)?,
                    "notes": row.get::<_, Option<String>>(8)?.unwrap_or_default(),
                }))
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        rows
    } else {
        vec![]
    };

    let invoices = if has_invoices {
        let mut stmt = conn.prepare(
            "SELECT id, clientName, description, amount, issueDate, dueDate, paidDate, status \
             FROM Invoice ORDER BY dueDate ASC LIMIT 10",
        )?;
        let rows = stmt
            .query_map([], |row| {
                Ok(json!({
                    "id": row.get::<_, String>(0)?,
                    "clientName": row.get::<_, String>(1)?,
                    "description": row.get::<_, String>(2)?,
                    "amount": row.get::<_, f64>(3)?,
                    "issueDate": row.get::<_, String>(4)?,
                    "dueDate": row.get::<_, String>(5)?,
                    "paidDate": row.get::<_, Option<String>>(6)?,
                    "status": row.get::<_, String>(7)?,
                }))
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        rows
    } else {
        vec![]
    };

    let expenses = if has_expenses {
        let mut stmt = conn.prepare(
            "SELECT id, clientId, category, description, amount, date, recurring \
             FROM Expense ORDER BY date DESC LIMIT 10",
        )?;
        let rows = stmt
            .query_map([], |row| {
                Ok(json!({
                    "id": row.get::<_, String>(0)?,
                    "clientId": row.get::<_, Option<String>>(1)?,
                    "category": row.get::<_, String>(2)?,
                    "description": row.get::<_, String>(3)?,
                    "amount": row.get::<_, f64>(4)?,
                    "date": row.get::<_, String>(5)?,
                    "recurring": row.get::<_, i64>(6)? != 0,
                }))
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?;
        rows
    } else {
        vec![]
    };

    Ok(json!({
        "available": true,
        "db_path": path.to_string_lossy(),
        "metrics": {
            "active_clients": active_clients,
            "monthly_revenue": monthly_revenue,
            "monthly_expenses": monthly_expenses,
            "profit": monthly_revenue - monthly_expenses,
            "outstanding": outstanding,
            "overdue_invoices": overdue_invoices,
            "due_soon_invoices": due_soon_invoices
        },
        "clients": clients,
        "invoices": invoices,
        "expenses": expenses
    }))
}

/// Read-only DB probe for /health: "ok" | "absent" | "error".
pub fn status(path: &Path) -> &'static str {
    match open_ro(path) {
        Err(DbError::Absent) => "absent",
        Err(DbError::Failed(_)) => "error",
        Ok(conn) => {
            let probe: Result<i64, _> =
                conn.query_row("SELECT count(*) FROM sqlite_master", [], |r| r.get(0));
            if probe.is_ok() {
                "ok"
            } else {
                "error"
            }
        }
    }
}
