use std::time::Duration;
use tokio::time;

use crate::AppState;

/// Spawn a background retention worker that periodically dispatches
/// cleanup commands via the existing `dispatch_atlas()` mechanism.
pub fn spawn_retention_worker(state: AppState, interval_hours: u64) {
    let interval = Duration::from_secs(interval_hours * 3600);
    tokio::spawn(async move {
        let mut ticker = time::interval(interval);
        ticker.tick().await; // skip first immediate tick
        loop {
            ticker.tick().await;
            run_sweep(&state).await;
        }
    });
}

async fn run_sweep(state: &AppState) {
    println!("retention: running periodic sweep");

    // Purge expired archives
    match crate::dispatch_atlas(&state.atlas_cmd, &["mission", "purge-archived"]).await {
        Ok(out) => {
            let count = out.trim().parse::<i64>().unwrap_or(0);
            if count > 0 {
                println!("retention: purged {count} expired archives");
            }
        }
        Err(_) => {
            eprintln!("retention: purge failed");
        }
    }

    // Compress old mission data
    match crate::dispatch_atlas(&state.atlas_cmd, &["retention", "compress"]).await {
        Ok(out) => {
            let count = out.trim().parse::<i64>().unwrap_or(0);
            if count > 0 {
                println!("retention: compressed {count} missions");
            }
        }
        Err(_) => {
            eprintln!("retention: compress failed");
        }
    }

    println!("retention: sweep complete");
}
