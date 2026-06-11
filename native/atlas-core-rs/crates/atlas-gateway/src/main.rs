//! atlas-gateway — L2 ATLAS API gateway (D-022 L0 skeleton).
//!
//! Phase 7 fills in the full endpoint surface (missions, runs, audit events,
//! wiki, SSE stream). This skeleton establishes the crate, the loopback-only
//! bind, and the SQLite read path so the toolchain and native deps are
//! validated before Phase 7 planning.

use axum::{routing::get, Json, Router};
use serde_json::{json, Value};
use std::net::SocketAddr;
use std::path::PathBuf;

const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Resolve the ATLAS SQLite database path: $ATLAS_DB or ~/.atlas/atlas.db
/// (same default as the Python `atlas` CLI — one shared store).
fn db_path() -> PathBuf {
    if let Some(p) = std::env::var_os("ATLAS_DB") {
        return PathBuf::from(p);
    }
    let home = std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_default();
    home.join(".atlas").join("atlas.db")
}

/// Read-only DB probe: "ok" | "absent" | "error".
fn db_status() -> &'static str {
    let path = db_path();
    if !path.exists() {
        return "absent";
    }
    match rusqlite::Connection::open_with_flags(
        &path,
        rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY,
    ) {
        Ok(conn) => {
            let probe: Result<i64, _> =
                conn.query_row("SELECT count(*) FROM sqlite_master", [], |r| r.get(0));
            if probe.is_ok() {
                "ok"
            } else {
                "error"
            }
        }
        Err(_) => "error",
    }
}

async fn health() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "atlas-gateway",
        "version": VERSION,
        "db": db_status(),
    }))
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ATLAS_GATEWAY_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8484);
    // Loopback only — never bind a routable interface (NATIVE_COCKPIT_STRATEGY).
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let app = Router::new().route("/health", get(health));
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind 127.0.0.1");
    println!("atlas-gateway v{VERSION} listening on http://{addr}");
    axum::serve(listener, app).await.expect("server error");
}
