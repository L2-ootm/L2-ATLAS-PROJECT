//! Read-only SQLite access for the gateway (D-022: reads direct, writes via
//! the `atlas` CLI contract — no business logic here, only row → JSON).

use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

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
    Ok(json!({
        "id": row.get::<_, String>(0)?,
        "name": row.get::<_, String>(1)?,
        "description": row.get::<_, String>(2)?,
        "status": row.get::<_, String>(3)?,
        "activated_at": row.get::<_, Option<String>>(4)?,
    }))
}

const MISSION_COLS: &str = "id, title, intent, status, project, created_at, updated_at";
const MISSION_ARCHIVE_COLS: &str =
    "m.id, m.title, m.intent, m.status, m.project, m.created_at, m.updated_at, \
     a.archived_at, a.delete_after";
const RUN_COLS: &str =
    "id, mission_id, session_id, status, started_at, finished_at, summary, agent_runtime";
const PROJECT_COLS: &str = "id, name, root_path, created_at, updated_at";
const MODULE_COLS: &str = "id, name, description, status, activated_at";

pub fn list_missions(path: &Path, limit: i64) -> Result<Vec<Value>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!(
        "SELECT {MISSION_ARCHIVE_COLS} FROM missions m \
         LEFT JOIN mission_archive a ON a.mission_id = m.id \
         ORDER BY m.created_at DESC LIMIT ?1"
    );
    let rows = match conn.prepare(&sql) {
        Ok(mut stmt) => {
            stmt
                .query_map([limit], mission_row_with_archive)?
                .collect::<rusqlite::Result<Vec<_>>>()?
        }
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            let sql = format!("SELECT {MISSION_COLS} FROM missions ORDER BY created_at DESC LIMIT ?1");
            let mut stmt = conn.prepare(&sql)?;
            let rows = stmt
                .query_map([limit], mission_row)?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            rows
        }
        Err(e) => return Err(e.into()),
    };
    Ok(rows)
}

/// Mission detail plus its runs. `None` when the mission id is unknown.
pub fn get_mission(path: &Path, id: &str) -> Result<Option<(Value, Vec<Value>)>, DbError> {
    let conn = open_ro(path)?;
    let sql = format!(
        "SELECT {MISSION_ARCHIVE_COLS} FROM missions m \
         LEFT JOIN mission_archive a ON a.mission_id = m.id \
         WHERE m.id = ?1"
    );
    let mission = match conn.query_row(&sql, [id], mission_row_with_archive) {
        Ok(v) => v,
        Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
        Err(rusqlite::Error::SqliteFailure(_, Some(ref msg))) if msg.contains("no such table") => {
            let sql = format!("SELECT {MISSION_COLS} FROM missions WHERE id = ?1");
            match conn.query_row(&sql, [id], mission_row) {
                Ok(v) => v,
                Err(rusqlite::Error::QueryReturnedNoRows) => return Ok(None),
                Err(e) => return Err(e.into()),
            }
        }
        Err(e) => return Err(e.into()),
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
        Err(e) => return Err(e.into()),
    };
    let rows = stmt
        .query_map([], module_row)?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    Ok(rows)
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
        Err(e) => return Err(e.into()),
    }
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
        return PathBuf::from(root).join("services").join("cashflow").join("dev.db");
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
        let rows = stmt.query_map([], |row| {
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
        let rows = stmt.query_map([], |row| {
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
        let rows = stmt.query_map([], |row| {
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
