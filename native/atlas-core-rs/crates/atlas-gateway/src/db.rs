//! Read-only SQLite access for the gateway (D-022: reads direct, writes via
//! the `atlas` CLI contract — no business logic here, only row → JSON).

use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};
use std::path::Path;

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

fn open_ro(path: &Path) -> Result<Connection, DbError> {
    if !path.exists() {
        return Err(DbError::Absent);
    }
    Connection::open_with_flags(path, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .map_err(|e| DbError::Failed(e.to_string()))
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
    }))
}

const MISSION_COLS: &str = "id, title, intent, status, project, created_at, updated_at";
const RUN_COLS: &str = "id, mission_id, session_id, status, started_at, finished_at, summary";

pub fn list_missions(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {MISSION_COLS} FROM missions ORDER BY created_at DESC LIMIT ?1");
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt
        .query_map([limit], mission_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
}

/// Mission detail plus its runs. `None` when the mission id is unknown.
pub fn get_mission(path: &Path, id: &str) -> Result<Option<(Value, Vec<Value>)>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!("SELECT {MISSION_COLS} FROM missions WHERE id = ?1");
    let mission = match conn.query_row(&sql, [id], mission_row) {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(e) => return Err(e.into()),
    };
    let sql = format!("SELECT {RUN_COLS} FROM runs WHERE mission_id = ?1 ORDER BY started_at DESC");
    let mut stmt = conn.prepare(&sql)?;
    let runs = stmt
        .query_map([id], run_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(Some((mission, runs)))
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

/// Audit events for a run after a rowid cursor, ascending. Returns the events
/// and the cursor of the last event (unchanged when no new events).
pub fn list_events(
    path: &Path,
    run_id: &str,
    after: i64,
    limit: i64,
) -> Result<(Vec<Value>, i64), DbError> {
    let conn = open_ro(path)?;
    let mut stmt = conn.prepare(
        "SELECT rowid, id, event_type, tool_name, timestamp, duration_ms, data, \
                policy_result, task_id, session_id, tool_call_id \
         FROM audit_events WHERE run_id = ?1 AND rowid > ?2 ORDER BY rowid LIMIT ?3",
    )?;
    let mut cursor = after;
    let rows = stmt
        .query_map(rusqlite::params![run_id, after, limit], |row| {
            let rowid: i64 = row.get(0)?;
            let raw_data: String = row.get(6)?;
            let data: Value = serde_json::from_str(&raw_data).unwrap_or(Value::String(raw_data));
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

/// Quote every token so FTS5 operators/hyphens are treated literally
/// (same hyphen-query pitfall already fixed in the Python wiki CLI).
fn fts_quote(query: &str) -> String {
    query
        .split_whitespace()
        .map(|t| format!("\"{}\"", t.replace('"', "")))
        .collect::<Vec<_>>()
        .join(" ")
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
