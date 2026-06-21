//! atlas-gateway binary — loopback-only HTTP server (Phase 7, D-022).

use atlas_gateway::{app, default_atlas_cli, default_db_path, default_repo_root, AppState, VERSION};
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("ATLAS_GATEWAY_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(8484);
    // Loopback only — never bind a routable interface (NATIVE_COCKPIT_STRATEGY).
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let state = AppState {
        db_path: default_db_path(),
        atlas_cmd: default_atlas_cli(),
        repo_root: default_repo_root(),
    };
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("failed to bind 127.0.0.1");
    println!("atlas-gateway v{VERSION} listening on http://{addr}");
    axum::serve(listener, app(state))
        .await
        .expect("server error");
}
