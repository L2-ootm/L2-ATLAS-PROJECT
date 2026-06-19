use std::process::Command;

// ATLAS desktop shell — wraps the React cockpit and exposes gateway lifecycle to
// the in-app UI via Tauri commands. Commands shell out to the canonical `atlas`
// CLI primitive (one start path for terminal / shell / login auto-start), so the
// shell stays thin. `atlas` must be on PATH (scripts/install-atlas-cli.ps1).

/// Run the `atlas` CLI with args; return trimmed stdout, or stderr as an error.
fn run_atlas(args: &[&str]) -> Result<String, String> {
    let output = Command::new("atlas")
        .args(args)
        .output()
        .map_err(|e| {
            format!(
                "could not run the `atlas` CLI (is it on PATH? run scripts/install-atlas-cli.ps1): {e}"
            )
        })?;
    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
    }
}

#[tauri::command]
fn start_gateway() -> Result<String, String> {
    run_atlas(&["gateway", "start"])
}

#[tauri::command]
fn gateway_status() -> Result<String, String> {
    run_atlas(&["gateway", "status"])
}

#[tauri::command]
fn stop_gateway() -> Result<String, String> {
    run_atlas(&["gateway", "stop"])
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      start_gateway,
      gateway_status,
      stop_gateway
    ])
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
