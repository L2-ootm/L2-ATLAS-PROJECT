use atlas_gateway::diff::{diff_file, DiffInput};
use serde::Deserialize;
use std::process::Command;
use std::time::{Duration, Instant};

#[derive(Debug, Deserialize)]
struct Fixture {
    name: String,
    path: String,
    #[serde(default)]
    old_path: Option<String>,
    operation: String,
    before: String,
    after: String,
    additions: usize,
    deletions: usize,
    binary: bool,
    #[serde(default)]
    generated: bool,
}

fn fixtures() -> Vec<Fixture> {
    serde_json::from_str(include_str!(
        "../../../../../services/agent-runtime/tests/fixtures/evidence_diff_cases.json"
    ))
    .expect("valid frozen evidence fixtures")
}

fn resident_bytes() -> Option<u64> {
    #[cfg(target_os = "windows")]
    {
        let output = Command::new("tasklist")
            .args([
                "/FI",
                &format!("PID eq {}", std::process::id()),
                "/FO",
                "CSV",
                "/NH",
            ])
            .output()
            .ok()?;
        let text = String::from_utf8(output.stdout).ok()?;
        let memory = text.trim().rsplit("\",\"").next()?.trim_matches('"');
        let kib = memory
            .chars()
            .filter(char::is_ascii_digit)
            .collect::<String>()
            .parse::<u64>()
            .ok()?;
        Some(kib * 1024)
    }
    #[cfg(target_os = "linux")]
    {
        let status = std::fs::read_to_string("/proc/self/status").ok()?;
        let line = status.lines().find(|line| line.starts_with("VmRSS:"))?;
        let kib = line.split_whitespace().nth(1)?.parse::<u64>().ok()?;
        Some(kib * 1024)
    }
    #[cfg(target_os = "macos")]
    {
        let output = Command::new("ps")
            .args(["-o", "rss=", "-p", &std::process::id().to_string()])
            .output()
            .ok()?;
        let kib = String::from_utf8(output.stdout)
            .ok()?
            .trim()
            .parse::<u64>()
            .ok()?;
        Some(kib * 1024)
    }
}

#[test]
fn evidence_engine_matches_frozen_fixture_oracle() {
    for fixture in fixtures() {
        let result = diff_file(&DiffInput {
            path: fixture.path.clone(),
            old_path: fixture.old_path.clone(),
            operation: fixture.operation.clone(),
            before: fixture.before.clone(),
            after: fixture.after.clone(),
            generated: fixture.generated,
        });
        assert_eq!(
            result.additions, fixture.additions,
            "{} additions",
            fixture.name
        );
        assert_eq!(
            result.deletions, fixture.deletions,
            "{} deletions",
            fixture.name
        );
        assert_eq!(result.binary, fixture.binary, "{} binary", fixture.name);
        assert_eq!(
            result,
            diff_file(&DiffInput {
                path: fixture.path,
                old_path: fixture.old_path,
                operation: fixture.operation,
                before: fixture.before,
                after: fixture.after,
                generated: fixture.generated,
            }),
            "{} is deterministic",
            fixture.name
        );
    }
}

#[test]
fn evidence_engine_initial_page_is_bounded() {
    let before = (0..1000).map(|i| format!("old-{i}\n")).collect::<String>();
    let after = (0..1000).map(|i| format!("new-{i}\n")).collect::<String>();
    let result = diff_file(&DiffInput {
        path: "large.txt".into(),
        old_path: None,
        operation: "edit".into(),
        before,
        after,
        generated: false,
    });
    let page = result.initial_page(16 * 1024, 250);
    assert!(serde_json::to_vec(&page).unwrap().len() <= 16 * 1024);
    assert!(page.rows.len() <= 250);
}

#[test]
fn evidence_engine_scale_budgets() {
    for (lines, budget) in [
        (1_000usize, Duration::from_millis(100)),
        (10_000, Duration::from_millis(500)),
        (100_000, Duration::from_millis(2_000)),
    ] {
        let before = (0..lines)
            .map(|i| format!("line-{i}\n"))
            .collect::<String>();
        let mut after = before.clone();
        after.push_str("tail-change\n");
        let input = DiffInput {
            path: format!("{lines}.txt"),
            old_path: None,
            operation: "edit".into(),
            before,
            after,
            generated: false,
        };
        let _warmup = diff_file(&input);
        let rss_before = resident_bytes();
        let mut samples = Vec::new();
        for _ in 0..10 {
            let started = Instant::now();
            let result = diff_file(&input);
            assert!(!result.hunks.is_empty());
            samples.push(started.elapsed());
        }
        samples.sort();
        let p95 = samples[9];
        eprintln!(
            "evidence_engine lines={lines} p95_ms={} target_ms={} target={}",
            p95.as_millis(),
            budget.as_millis(),
            std::env::consts::OS
        );
        assert!(p95 <= budget, "{lines} lines p95 {p95:?} > {budget:?}");
        if lines == 100_000 {
            if let (Some(before_rss), Some(after_rss)) = (rss_before, resident_bytes()) {
                let rss_delta = after_rss.saturating_sub(before_rss);
                eprintln!("evidence_engine lines=100000 peak_rss_delta={rss_delta}");
                assert!(
                    rss_delta <= 256 * 1024 * 1024,
                    "100k peak RSS delta exceeded 256 MiB"
                );
            }
            let working_bytes =
                input.before.len() + input.after.len() + diff_file(&input).patch.len();
            assert!(
                working_bytes <= 256 * 1024 * 1024,
                "100k deterministic working set exceeded 256 MiB"
            );
        }
    }
}
