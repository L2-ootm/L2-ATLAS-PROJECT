//! Deterministic, dependency-free file diff and hunk index authority.
//!
//! The engine is deliberately linear: it identifies the common prefix and
//! suffix and emits one canonical unified hunk for the changed middle. This
//! keeps the first-hunk path bounded for 100k-line evidence while preserving
//! exact changed bytes and stable paging offsets.

use serde::{Deserialize, Serialize};

const CONTEXT_LINES: usize = 3;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiffInput {
    pub path: String,
    #[serde(default)]
    pub old_path: Option<String>,
    pub operation: String,
    pub before: String,
    pub after: String,
    #[serde(default)]
    pub generated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Hunk {
    pub index: usize,
    pub old_start: usize,
    pub old_lines: usize,
    pub new_start: usize,
    pub new_lines: usize,
    pub patch_start_byte: usize,
    pub patch_bytes: usize,
    pub patch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiffResult {
    pub path: String,
    pub old_path: Option<String>,
    pub operation: String,
    pub binary: bool,
    pub generated: bool,
    pub additions: usize,
    pub deletions: usize,
    pub hunks: Vec<Hunk>,
    pub patch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiffPage {
    pub path: String,
    pub operation: String,
    pub additions: usize,
    pub deletions: usize,
    pub binary: bool,
    pub generated: bool,
    pub rows: Vec<String>,
    pub next_row: Option<usize>,
}

impl DiffResult {
    /// Bounded initial inspector projection. A long row is byte-trimmed at a
    /// UTF-8 boundary and the cursor remains explicit.
    pub fn initial_page(&self, max_bytes: usize, max_rows: usize) -> DiffPage {
        let all_rows: Vec<&str> = self.patch.lines().collect();
        let metadata_reserve = 512usize.min(max_bytes);
        let row_budget = max_bytes.saturating_sub(metadata_reserve);
        let mut used = 0;
        let mut rows = Vec::new();
        for row in all_rows.iter().take(max_rows) {
            if used >= row_budget {
                break;
            }
            let remaining = row_budget - used;
            let mut take = row.len().min(remaining.saturating_sub(1));
            while take > 0 && !row.is_char_boundary(take) {
                take -= 1;
            }
            if take == 0 && !row.is_empty() {
                break;
            }
            rows.push(row[..take].to_string());
            used += take + 1;
            if take < row.len() {
                break;
            }
        }
        let next_row = (rows.len() < all_rows.len()).then_some(rows.len());
        DiffPage {
            path: self.path.clone(),
            operation: self.operation.clone(),
            additions: self.additions,
            deletions: self.deletions,
            binary: self.binary,
            generated: self.generated,
            rows,
            next_row,
        }
    }
}

pub fn diff_file(input: &DiffInput) -> DiffResult {
    let before = normalize_lines(&input.before);
    let after = normalize_lines(&input.after);
    let binary = input.operation == "binary"
        || before.as_bytes().contains(&0)
        || after.as_bytes().contains(&0);
    if binary {
        return DiffResult {
            path: input.path.clone(),
            old_path: input.old_path.clone(),
            operation: input.operation.clone(),
            binary: true,
            generated: input.generated,
            additions: 0,
            deletions: 0,
            hunks: Vec::new(),
            patch: format!("Binary files differ: {}\n", input.path),
        };
    }

    let old_lines: Vec<&str> = before.split_terminator('\n').collect();
    let new_lines: Vec<&str> = after.split_terminator('\n').collect();
    let prefix = old_lines
        .iter()
        .zip(&new_lines)
        .take_while(|(old, new)| old == new)
        .count();
    let suffix = old_lines[prefix..]
        .iter()
        .rev()
        .zip(new_lines[prefix..].iter().rev())
        .take_while(|(old, new)| old == new)
        .count();
    let old_changed_end = old_lines.len().saturating_sub(suffix);
    let new_changed_end = new_lines.len().saturating_sub(suffix);
    let deletions = old_changed_end.saturating_sub(prefix);
    let additions = new_changed_end.saturating_sub(prefix);

    let old_label = input.old_path.as_deref().unwrap_or(&input.path);
    let mut patch = format!("--- a/{old_label}\n+++ b/{}\n", input.path);
    let mut hunks = Vec::new();
    if additions > 0 || deletions > 0 {
        let context_start = prefix.saturating_sub(CONTEXT_LINES);
        let old_context_end = (old_changed_end + CONTEXT_LINES).min(old_lines.len());
        let new_context_end = (new_changed_end + CONTEXT_LINES).min(new_lines.len());
        let old_count = old_context_end - context_start;
        let new_count = new_context_end - context_start;
        let old_start = if old_count == 0 { 0 } else { context_start + 1 };
        let new_start = if new_count == 0 { 0 } else { context_start + 1 };
        let patch_start_byte = patch.len();
        let mut hunk_patch = format!("@@ -{old_start},{old_count} +{new_start},{new_count} @@\n");
        for line in &old_lines[context_start..prefix] {
            hunk_patch.push(' ');
            hunk_patch.push_str(line);
            hunk_patch.push('\n');
        }
        for line in &old_lines[prefix..old_changed_end] {
            hunk_patch.push('-');
            hunk_patch.push_str(line);
            hunk_patch.push('\n');
        }
        for line in &new_lines[prefix..new_changed_end] {
            hunk_patch.push('+');
            hunk_patch.push_str(line);
            hunk_patch.push('\n');
        }
        for line in &new_lines[new_changed_end..new_context_end] {
            hunk_patch.push(' ');
            hunk_patch.push_str(line);
            hunk_patch.push('\n');
        }
        let patch_bytes = hunk_patch.len();
        patch.push_str(&hunk_patch);
        hunks.push(Hunk {
            index: 0,
            old_start,
            old_lines: old_count,
            new_start,
            new_lines: new_count,
            patch_start_byte,
            patch_bytes,
            patch: hunk_patch,
        });
    }

    DiffResult {
        path: input.path.clone(),
        old_path: input.old_path.clone(),
        operation: input.operation.clone(),
        binary: false,
        generated: input.generated,
        additions,
        deletions,
        hunks,
        patch,
    }
}

fn normalize_lines(value: &str) -> String {
    value.replace("\r\n", "\n").replace('\r', "\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evidence_engine_byte_ranges_address_exact_hunk() {
        let result = diff_file(&DiffInput {
            path: "x.txt".into(),
            old_path: None,
            operation: "edit".into(),
            before: "a\nold\nz\n".into(),
            after: "a\nnew\nz\n".into(),
            generated: false,
        });
        let hunk = &result.hunks[0];
        assert_eq!(
            &result.patch[hunk.patch_start_byte..hunk.patch_start_byte + hunk.patch_bytes],
            hunk.patch
        );
    }
}
