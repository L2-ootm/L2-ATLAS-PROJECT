//! atlas-gateway binary — loopback-only HTTP server (Phase 7, D-022).

use atlas_gateway::{
    app, default_atlas_cli, default_db_path, default_repo_root, version_info, AppState,
    RELEASE_VERSION,
};
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args == ["--version", "--json"] || args == ["--json", "--version"] {
        println!(
            "{}",
            serde_json::to_string(&version_info()).expect("version identity must serialize")
        );
        return;
    }
    if args == ["--version"] {
        println!("atlas-gateway {RELEASE_VERSION}");
        return;
    }
    if !args.is_empty() {
        eprintln!("usage: atlas-gateway [--version [--json]]");
        std::process::exit(2);
    }

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
    println!("atlas-gateway v{RELEASE_VERSION} listening on http://{addr}");
    atlas_gateway::retention::spawn_retention_worker(state.clone(), 24);
    axum::serve(listener, app(state))
        .await
        .expect("server error");
}
