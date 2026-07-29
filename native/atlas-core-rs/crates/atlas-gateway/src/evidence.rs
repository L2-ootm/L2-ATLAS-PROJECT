//! Authoritative Evidence Plane storage and content identity.
//!
//! The module intentionally uses only workspace dependencies. Content is
//! redacted before hashing and all linked blob/result rows share one
//! `BEGIN IMMEDIATE` transaction.

use rusqlite::{params, Connection, TransactionBehavior};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeSet, VecDeque};
use std::path::{Component, Path};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::diff::{diff_file, DiffInput};

pub const PROTOCOL_VERSION: &str = "atlas-evidence/v1";
pub const CHUNK_SIZE: usize = 64 * 1024;
pub const FILE_RETAINED_CAP: usize = 32 * 1024 * 1024;
pub const RUN_RETAINED_CAP: i64 = 256 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Availability {
    Available,
    Redacted,
    Unavailable,
    TooLarge,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullResultRequest {
    pub protocol: String,
    pub db_path: String,
    pub owner_kind: String,
    pub owner_id: String,
    #[serde(default)]
    pub run_id: Option<String>,
    #[serde(default)]
    pub team_run_id: Option<String>,
    #[serde(default)]
    pub tool_call_id: Option<String>,
    pub content: String,
    #[serde(default = "default_media_type")]
    pub media_type: String,
    #[serde(default = "default_preview_limit")]
    pub preview_limit: usize,
}

fn default_media_type() -> String {
    "text/plain".to_string()
}

fn default_preview_limit() -> usize {
    2000
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FullResultReceipt {
    pub evidence_id: String,
    pub owner_kind: String,
    pub owner_id: String,
    pub availability: Availability,
    pub preview: String,
    pub preview_bytes: usize,
    pub full_bytes: usize,
    pub sha256: Option<String>,
    pub media_type: String,
    pub redaction_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolResponse {
    pub protocol: String,
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reference: Option<FullResultReceipt>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub change_set: Option<ChangeSetReceipt>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub aggregation: Option<AggregationReceipt>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ProtocolError>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProtocolError {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceProvenance {
    pub run_id: String,
    #[serde(default)]
    pub session_id: Option<String>,
    #[serde(default)]
    pub team_run_id: Option<String>,
    #[serde(default)]
    pub turn_id: Option<String>,
    #[serde(default)]
    pub actor_id: Option<String>,
    #[serde(default)]
    pub parent_actor_id: Option<String>,
    #[serde(default)]
    pub tool_call_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaptureFileRequest {
    pub path: String,
    #[serde(default)]
    pub old_path: Option<String>,
    pub operation: String,
    pub before: String,
    pub after: String,
    #[serde(default)]
    pub generated: bool,
    #[serde(default)]
    pub mode_before: Option<String>,
    #[serde(default)]
    pub mode_after: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeSetRequest {
    pub protocol: String,
    pub db_path: String,
    pub kind: String,
    pub provenance: EvidenceProvenance,
    pub coverage: String,
    pub status: String,
    pub files: Vec<CaptureFileRequest>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeSetReceipt {
    pub change_set_id: String,
    pub coverage: String,
    pub status: String,
    pub file_count: usize,
    pub additions: usize,
    pub deletions: usize,
    pub redaction_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregateChangeSetsRequest {
    pub protocol: String,
    pub db_path: String,
    pub kind: String,
    pub provenance: EvidenceProvenance,
    pub child_change_set_ids: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregationReceipt {
    pub change_set_id: String,
    pub coverage: String,
    pub status: String,
    pub child_count: usize,
    pub file_count: usize,
    pub additions: usize,
    pub deletions: usize,
    pub redaction_count: usize,
}

pub fn persist_change_set_aggregation(
    request: &AggregateChangeSetsRequest,
) -> Result<AggregationReceipt, String> {
    if request.protocol != PROTOCOL_VERSION {
        return Err(format!("unsupported protocol {:?}", request.protocol));
    }
    if request.kind != "aggregate_change_sets" {
        return Err("kind must be aggregate_change_sets".to_string());
    }
    if request.provenance.run_id.trim().is_empty() {
        return Err("run_id must be non-empty".to_string());
    }
    if request.child_change_set_ids.is_empty() {
        return Err("aggregation requires at least one child change set".to_string());
    }

    let mut conn = Connection::open(Path::new(&request.db_path)).map_err(|e| e.to_string())?;
    conn.pragma_update(None, "foreign_keys", "ON")
        .map_err(|e| e.to_string())?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;

    let mut queue: VecDeque<String> = request
        .child_change_set_ids
        .iter()
        .filter(|value| !value.trim().is_empty())
        .cloned()
        .collect();
    let mut visited = BTreeSet::new();
    let mut leaves = BTreeSet::new();
    while let Some(change_set_id) = queue.pop_front() {
        if !visited.insert(change_set_id.clone()) {
            continue;
        }
        let exists: i64 = tx
            .query_row(
                "SELECT COUNT(*) FROM evidence_change_sets WHERE id=?1",
                [&change_set_id],
                |row| row.get(0),
            )
            .map_err(|e| e.to_string())?;
        if exists != 1 {
            return Err(format!("unknown child change set {change_set_id:?}"));
        }
        let mut statement = tx
            .prepare(
                "SELECT child_change_set_id FROM evidence_child_refs
                 WHERE parent_change_set_id=?1 ORDER BY child_change_set_id",
            )
            .map_err(|e| e.to_string())?;
        let children = statement
            .query_map([&change_set_id], |row| row.get::<_, String>(0))
            .map_err(|e| e.to_string())?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| e.to_string())?;
        drop(statement);
        if children.is_empty() {
            leaves.insert(change_set_id);
        } else {
            queue.extend(children);
        }
    }
    if leaves.is_empty() {
        return Err("aggregation resolved to no leaf change sets".to_string());
    }

    let identity = format!(
        "{}|{}|{}|{}",
        request.provenance.run_id,
        request.provenance.actor_id.as_deref().unwrap_or(""),
        request.provenance.team_run_id.as_deref().unwrap_or(""),
        leaves.iter().cloned().collect::<Vec<_>>().join("|"),
    );
    let fingerprint = sha256_hex(identity.as_bytes());
    let change_set_id = format!("aggregate-{}", &fingerprint[..24]);
    if leaves.contains(&change_set_id) {
        return Err("aggregation cycle detected".to_string());
    }

    let mut coverage = "complete".to_string();
    let mut status = "captured".to_string();
    let mut file_count = 0usize;
    let mut additions = 0usize;
    let mut deletions = 0usize;
    let mut redaction_count = 0usize;
    let mut leaf_actors: Vec<(String, Option<String>)> = Vec::new();
    for leaf in &leaves {
        let (leaf_coverage, leaf_status, leaf_redactions, actor_id): (
            String,
            String,
            i64,
            Option<String>,
        ) = tx
            .query_row(
                "SELECT coverage,status,redaction_count,actor_id
                 FROM evidence_change_sets WHERE id=?1",
                [leaf],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .map_err(|e| e.to_string())?;
        coverage = worse_coverage(&coverage, &leaf_coverage).to_string();
        status = worse_status(&status, &leaf_status).to_string();
        redaction_count = redaction_count.saturating_add(leaf_redactions.max(0) as usize);
        let (files, adds, deletes): (i64, i64, i64) = tx
            .query_row(
                "SELECT COUNT(*),COALESCE(SUM(additions),0),COALESCE(SUM(deletions),0)
                 FROM evidence_file_changes WHERE change_set_id=?1",
                [leaf],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .map_err(|e| e.to_string())?;
        file_count = file_count.saturating_add(files.max(0) as usize);
        additions = additions.saturating_add(adds.max(0) as usize);
        deletions = deletions.saturating_add(deletes.max(0) as usize);
        leaf_actors.push((leaf.clone(), actor_id));
    }

    let now = unix_nanos().to_string();
    tx.execute(
        "INSERT OR IGNORE INTO evidence_change_sets
         (id,run_id,session_id,team_run_id,turn_id,actor_id,parent_actor_id,
          tool_call_id,coverage,status,redaction_count,created_at)
         VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12)",
        params![
            change_set_id,
            request.provenance.run_id,
            request.provenance.session_id,
            request.provenance.team_run_id,
            request.provenance.turn_id,
            request.provenance.actor_id,
            request.provenance.parent_actor_id,
            request.provenance.tool_call_id,
            coverage,
            status,
            redaction_count as i64,
            now,
        ],
    )
    .map_err(|e| e.to_string())?;
    for (leaf, actor_id) in &leaf_actors {
        tx.execute(
            "INSERT OR IGNORE INTO evidence_child_refs
             (parent_change_set_id,child_change_set_id,actor_id)
             VALUES (?1,?2,?3)",
            params![change_set_id, leaf, actor_id],
        )
        .map_err(|e| e.to_string())?;
    }
    tx.commit().map_err(|e| e.to_string())?;

    Ok(AggregationReceipt {
        change_set_id,
        coverage,
        status,
        child_count: leaves.len(),
        file_count,
        additions,
        deletions,
        redaction_count,
    })
}

fn worse_coverage<'a>(left: &'a str, right: &'a str) -> &'a str {
    let rank = |value: &str| match value {
        "complete" => 0,
        "tool_only" => 1,
        "partial" => 2,
        "unavailable" => 3,
        _ => 3,
    };
    if rank(right) > rank(left) {
        right
    } else {
        left
    }
}

fn worse_status<'a>(left: &'a str, right: &'a str) -> &'a str {
    let rank = |value: &str| match value {
        "captured" => 0,
        "partial" => 1,
        "unavailable" => 2,
        "too_large" => 3,
        _ => 2,
    };
    if rank(right) > rank(left) {
        right
    } else {
        left
    }
}

pub fn persist_change_set(request: &ChangeSetRequest) -> Result<ChangeSetReceipt, String> {
    validate_change_set_request(request)?;

    let mut conn = Connection::open(Path::new(&request.db_path)).map_err(|e| e.to_string())?;
    conn.pragma_update(None, "foreign_keys", "ON")
        .map_err(|e| e.to_string())?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;

    let now = unix_nanos();
    let fingerprint = sha256_hex(
        format!(
            "{}:{}:{}:{}",
            request.provenance.run_id,
            request.provenance.tool_call_id.as_deref().unwrap_or(""),
            request.files.len(),
            now
        )
        .as_bytes(),
    );
    let change_set_id = format!("change-{}-{now}", &fingerprint[..16]);
    let mut additions = 0usize;
    let mut deletions = 0usize;
    let mut redaction_count = 0usize;
    let mut any_too_large = false;

    tx.execute(
        "INSERT INTO evidence_change_sets
         (id,run_id,session_id,team_run_id,turn_id,actor_id,parent_actor_id,
          tool_call_id,coverage,status,redaction_count,created_at)
         VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,0,?11)",
        params![
            change_set_id,
            request.provenance.run_id,
            request.provenance.session_id,
            request.provenance.team_run_id,
            request.provenance.turn_id,
            request.provenance.actor_id,
            request.provenance.parent_actor_id,
            request.provenance.tool_call_id,
            request.coverage,
            request.status,
            now.to_string(),
        ],
    )
    .map_err(|e| e.to_string())?;

    for (index, file) in request.files.iter().enumerate() {
        let (before, before_redactions) = redact_text(&file.before);
        let (after, after_redactions) = redact_text(&file.after);
        let file_redactions = before_redactions + after_redactions;
        redaction_count += file_redactions;
        let before_sha = sha256_hex(before.as_bytes());
        let after_sha = sha256_hex(after.as_bytes());
        let too_large = before.len() > FILE_RETAINED_CAP || after.len() > FILE_RETAINED_CAP;
        any_too_large |= too_large;

        let result = diff_file(&DiffInput {
            path: file.path.clone(),
            old_path: file.old_path.clone(),
            operation: file.operation.clone(),
            before: before.clone(),
            after: after.clone(),
            generated: file.generated,
        });
        if !too_large {
            additions += result.additions;
            deletions += result.deletions;
        }
        let file_id = format!("file-{}-{now}-{index}", &after_sha[..16]);
        let availability = if too_large {
            "too_large"
        } else if file_redactions > 0 {
            "redacted"
        } else {
            "available"
        };
        let before_blob_id = if too_large {
            None
        } else {
            Some(persist_blob(
                &tx,
                before.as_bytes(),
                "text/plain",
                before_redactions,
                now,
            )?)
        };
        let after_blob_id = if too_large {
            None
        } else {
            Some(persist_blob(
                &tx,
                after.as_bytes(),
                "text/plain",
                after_redactions,
                now,
            )?)
        };
        let patch_blob_id = if too_large {
            None
        } else {
            Some(persist_blob(
                &tx,
                result.patch.as_bytes(),
                "text/x-diff",
                file_redactions,
                now,
            )?)
        };
        tx.execute(
            "INSERT INTO evidence_file_changes
             (id,change_set_id,path,old_path,operation,availability,before_sha256,
              after_sha256,before_bytes,after_bytes,additions,deletions,binary,
              generated,mode_before,mode_after,redaction_count,before_blob_id,
              after_blob_id,patch_blob_id)
             VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,
                     ?16,?17,?18,?19,?20)",
            params![
                file_id,
                change_set_id,
                file.path,
                file.old_path,
                file.operation,
                availability,
                before_sha,
                after_sha,
                before.len() as i64,
                after.len() as i64,
                if too_large {
                    0
                } else {
                    result.additions as i64
                },
                if too_large {
                    0
                } else {
                    result.deletions as i64
                },
                result.binary as i64,
                file.generated as i64,
                file.mode_before,
                file.mode_after,
                file_redactions as i64,
                before_blob_id,
                after_blob_id,
                patch_blob_id,
            ],
        )
        .map_err(|e| e.to_string())?;

        if !too_large {
            for hunk in &result.hunks {
                let hunk_id = format!("hunk-{now}-{index}-{}", hunk.index);
                tx.execute(
                    "INSERT INTO evidence_hunks
                     (id,file_change_id,hunk_index,old_start,old_lines,new_start,
                      new_lines,patch_start_byte,patch_bytes,redacted)
                     VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
                    params![
                        hunk_id,
                        file_id,
                        hunk.index as i64,
                        hunk.old_start as i64,
                        hunk.old_lines as i64,
                        hunk.new_start as i64,
                        hunk.new_lines as i64,
                        hunk.patch_start_byte as i64,
                        hunk.patch_bytes as i64,
                        (file_redactions > 0) as i64,
                    ],
                )
                .map_err(|e| e.to_string())?;
            }
        }
    }

    let final_status = if any_too_large {
        "too_large"
    } else {
        request.status.as_str()
    };
    tx.execute(
        "UPDATE evidence_change_sets SET status=?1, redaction_count=?2 WHERE id=?3",
        params![final_status, redaction_count as i64, change_set_id],
    )
    .map_err(|e| e.to_string())?;
    tx.commit().map_err(|e| e.to_string())?;

    Ok(ChangeSetReceipt {
        change_set_id,
        coverage: request.coverage.clone(),
        status: final_status.to_string(),
        file_count: request.files.len(),
        additions,
        deletions,
        redaction_count,
    })
}

fn validate_change_set_request(request: &ChangeSetRequest) -> Result<(), String> {
    if request.protocol != PROTOCOL_VERSION {
        return Err(format!("unsupported protocol {:?}", request.protocol));
    }
    if request.kind != "change_set" {
        return Err("kind must be change_set".to_string());
    }
    if request.provenance.run_id.trim().is_empty() {
        return Err("run_id must be non-empty".to_string());
    }
    if !matches!(
        request.coverage.as_str(),
        "complete" | "tool_only" | "partial" | "unavailable"
    ) {
        return Err("invalid coverage".to_string());
    }
    if !matches!(
        request.status.as_str(),
        "captured" | "partial" | "unavailable" | "too_large"
    ) {
        return Err("invalid status".to_string());
    }
    if request.files.is_empty() {
        return Err("capture must contain at least one file".to_string());
    }
    for file in &request.files {
        validate_relative_path(&file.path)?;
        if let Some(old_path) = file.old_path.as_deref() {
            validate_relative_path(old_path)?;
        }
        if !matches!(
            file.operation.as_str(),
            "create" | "edit" | "delete" | "rename" | "mode" | "binary"
        ) {
            return Err(format!("invalid operation {:?}", file.operation));
        }
    }
    Ok(())
}

fn validate_relative_path(value: &str) -> Result<(), String> {
    if value.trim().is_empty() || value.contains('\\') || value.contains(':') {
        return Err("path must be canonical workspace-relative POSIX form".to_string());
    }
    let path = Path::new(value);
    if path.is_absolute()
        || path
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err("path must be canonical workspace-relative POSIX form".to_string());
    }
    Ok(())
}

fn persist_blob(
    tx: &rusqlite::Transaction<'_>,
    bytes: &[u8],
    media_type: &str,
    redaction_count: usize,
    now: u128,
) -> Result<String, String> {
    let sha = sha256_hex(bytes);
    let blob_id = format!("blob-{sha}");
    let availability = if redaction_count > 0 {
        "redacted"
    } else {
        "available"
    };
    let chunk_count = bytes.len().div_ceil(CHUNK_SIZE);
    tx.execute(
        "INSERT OR IGNORE INTO evidence_blobs
         (id,sha256,media_type,size_bytes,chunk_size,chunk_count,availability,
          redaction_count,created_at) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9)",
        params![
            blob_id,
            sha,
            media_type,
            bytes.len() as i64,
            CHUNK_SIZE as i64,
            chunk_count as i64,
            availability,
            redaction_count as i64,
            now.to_string(),
        ],
    )
    .map_err(|e| e.to_string())?;
    for (index, chunk) in bytes.chunks(CHUNK_SIZE).enumerate() {
        tx.execute(
            "INSERT OR IGNORE INTO evidence_blob_chunks(blob_id,chunk_index,content)
             VALUES (?1,?2,?3)",
            params![blob_id, index as i64, chunk],
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(blob_id)
}

pub fn persist_full_result(request: &FullResultRequest) -> Result<FullResultReceipt, String> {
    if request.protocol != PROTOCOL_VERSION {
        return Err(format!("unsupported protocol {:?}", request.protocol));
    }
    if !matches!(
        request.owner_kind.as_str(),
        "run" | "team_run" | "tool_call"
    ) {
        return Err("owner_kind must be run, team_run, or tool_call".to_string());
    }
    if request.owner_id.trim().is_empty() {
        return Err("owner_id must be non-empty".to_string());
    }

    let (redacted, redaction_count) = redact_text(&request.content);
    let bytes = redacted.as_bytes();
    let full_bytes = bytes.len();
    let preview = utf8_prefix(&redacted, request.preview_limit);
    let preview_bytes = preview.len();
    let sha = sha256_hex(bytes);
    let now = unix_nanos();
    let evidence_id = format!("result-{}-{now}", &sha[..16]);
    let blob_id = format!("blob-{sha}");

    let mut conn = Connection::open(Path::new(&request.db_path)).map_err(|e| e.to_string())?;
    conn.pragma_update(None, "foreign_keys", "ON")
        .map_err(|e| e.to_string())?;
    let tx = conn
        .transaction_with_behavior(TransactionBehavior::Immediate)
        .map_err(|e| e.to_string())?;

    let retained: i64 = match request.run_id.as_deref() {
        Some(run_id) => tx
            .query_row(
                "SELECT COALESCE(SUM(full_bytes),0) FROM evidence_full_results
                 WHERE run_id=?1 AND availability IN ('available','redacted')",
                [run_id],
                |row| row.get(0),
            )
            .map_err(|e| e.to_string())?,
        None => 0,
    };
    let too_large = full_bytes > FILE_RETAINED_CAP
        || retained.saturating_add(full_bytes as i64) > RUN_RETAINED_CAP;
    let availability = if too_large {
        Availability::TooLarge
    } else if redaction_count > 0 {
        Availability::Redacted
    } else {
        Availability::Available
    };
    let availability_db = availability_name(&availability);

    if !too_large {
        let chunk_count = bytes.len().div_ceil(CHUNK_SIZE);
        tx.execute(
            "INSERT OR IGNORE INTO evidence_blobs
             (id,sha256,media_type,size_bytes,chunk_size,chunk_count,availability,
              redaction_count,created_at) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9)",
            params![
                blob_id,
                sha,
                request.media_type,
                full_bytes as i64,
                CHUNK_SIZE as i64,
                chunk_count as i64,
                availability_db,
                redaction_count as i64,
                now.to_string()
            ],
        )
        .map_err(|e| e.to_string())?;
        for (index, chunk) in bytes.chunks(CHUNK_SIZE).enumerate() {
            tx.execute(
                "INSERT OR IGNORE INTO evidence_blob_chunks(blob_id,chunk_index,content)
                 VALUES (?1,?2,?3)",
                params![blob_id, index as i64, chunk],
            )
            .map_err(|e| e.to_string())?;
        }
    }

    tx.execute(
        "INSERT INTO evidence_full_results
         (id,owner_kind,owner_id,run_id,team_run_id,tool_call_id,blob_id,
          availability,preview,preview_bytes,full_bytes,sha256,media_type,
          redaction_count,created_at)
         VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15)",
        params![
            evidence_id,
            request.owner_kind,
            request.owner_id,
            request.run_id,
            request.team_run_id,
            request.tool_call_id,
            if too_large {
                None::<String>
            } else {
                Some(blob_id)
            },
            availability_db,
            preview,
            preview_bytes as i64,
            full_bytes as i64,
            if too_large {
                None::<String>
            } else {
                Some(sha.clone())
            },
            request.media_type,
            redaction_count as i64,
            now.to_string()
        ],
    )
    .map_err(|e| e.to_string())?;
    tx.commit().map_err(|e| e.to_string())?;

    Ok(FullResultReceipt {
        evidence_id,
        owner_kind: request.owner_kind.clone(),
        owner_id: request.owner_id.clone(),
        availability,
        preview,
        preview_bytes,
        full_bytes,
        sha256: (!too_large).then_some(sha),
        media_type: request.media_type.clone(),
        redaction_count,
    })
}

pub fn read_full_result(
    db_path: &Path,
    owner_kind: &str,
    owner_id: &str,
    evidence_id: &str,
) -> Result<Vec<u8>, String> {
    let conn = Connection::open(db_path).map_err(|e| e.to_string())?;
    let blob_id: String = conn
        .query_row(
            "SELECT blob_id FROM evidence_full_results
             WHERE id=?1 AND owner_kind=?2 AND owner_id=?3
               AND availability IN ('available','redacted')",
            params![evidence_id, owner_kind, owner_id],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT content FROM evidence_blob_chunks
             WHERE blob_id=?1 ORDER BY chunk_index",
        )
        .map_err(|e| e.to_string())?;
    let chunks = stmt
        .query_map([blob_id], |row| row.get::<_, Vec<u8>>(0))
        .map_err(|e| e.to_string())?;
    let mut result = Vec::new();
    for chunk in chunks {
        result.extend(chunk.map_err(|e| e.to_string())?);
    }
    Ok(result)
}

fn availability_name(value: &Availability) -> &'static str {
    match value {
        Availability::Available => "available",
        Availability::Redacted => "redacted",
        Availability::Unavailable => "unavailable",
        Availability::TooLarge => "too_large",
    }
}

fn utf8_prefix(value: &str, max_bytes: usize) -> String {
    if value.len() <= max_bytes {
        return value.to_string();
    }
    let mut end = max_bytes;
    while end > 0 && !value.is_char_boundary(end) {
        end -= 1;
    }
    value[..end].to_string()
}

/// Fail-closed redaction for common assignment, JSON, and bearer forms.
pub fn redact_text(content: &str) -> (String, usize) {
    let mut output = content.to_string();
    let mut count = 0;
    for key in ["token", "api_key", "api-key", "secret", "password"] {
        let lower = output.to_ascii_lowercase();
        let mut search_from = 0;
        while let Some(relative) = lower[search_from..].find(key) {
            let key_start = search_from + relative;
            let after_key = key_start + key.len();
            let tail = &output[after_key..];
            let Some(separator_offset) = tail.find(['=', ':']) else {
                break;
            };
            if separator_offset > 3 {
                search_from = after_key;
                continue;
            }
            let value_start = after_key + separator_offset + 1;
            let bytes = output.as_bytes();
            let mut start = value_start;
            while start < bytes.len() && matches!(bytes[start], b' ' | b'\"' | b'\'') {
                start += 1;
            }
            let mut end = start;
            while end < bytes.len()
                && !matches!(
                    bytes[end],
                    b' ' | b'&' | b',' | b'}' | b'\"' | b'\'' | b'\r' | b'\n'
                )
            {
                end += 1;
            }
            if end > start {
                output.replace_range(start..end, "[REDACTED]");
                count += 1;
                search_from = start + "[REDACTED]".len();
            } else {
                search_from = after_key;
            }
        }
    }
    let lower = output.to_ascii_lowercase();
    if let Some(start) = lower.find("bearer ") {
        let token_start = start + 7;
        let token_end = output[token_start..]
            .find(char::is_whitespace)
            .map_or(output.len(), |offset| token_start + offset);
        if token_end > token_start {
            output.replace_range(token_start..token_end, "[REDACTED]");
            count += 1;
        }
    }
    (output, count)
}

fn unix_nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos()
}

/// Small dependency-free SHA-256 implementation (FIPS 180-4).
pub fn sha256_hex(input: &[u8]) -> String {
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];
    let mut h = [
        0x6a09e667u32,
        0xbb67ae85,
        0x3c6ef372,
        0xa54ff53a,
        0x510e527f,
        0x9b05688c,
        0x1f83d9ab,
        0x5be0cd19,
    ];
    let bit_len = (input.len() as u64).wrapping_mul(8);
    let mut data = input.to_vec();
    data.push(0x80);
    while data.len() % 64 != 56 {
        data.push(0);
    }
    data.extend_from_slice(&bit_len.to_be_bytes());
    for block in data.chunks_exact(64) {
        let mut w = [0u32; 64];
        for (index, bytes) in block.chunks_exact(4).enumerate() {
            w[index] = u32::from_be_bytes(bytes.try_into().expect("four bytes"));
        }
        for index in 16..64 {
            let s0 = w[index - 15].rotate_right(7)
                ^ w[index - 15].rotate_right(18)
                ^ (w[index - 15] >> 3);
            let s1 = w[index - 2].rotate_right(17)
                ^ w[index - 2].rotate_right(19)
                ^ (w[index - 2] >> 10);
            w[index] = w[index - 16]
                .wrapping_add(s0)
                .wrapping_add(w[index - 7])
                .wrapping_add(s1);
        }
        let mut v = h;
        for index in 0..64 {
            let s1 = v[4].rotate_right(6) ^ v[4].rotate_right(11) ^ v[4].rotate_right(25);
            let ch = (v[4] & v[5]) ^ ((!v[4]) & v[6]);
            let temp1 = v[7]
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[index])
                .wrapping_add(w[index]);
            let s0 = v[0].rotate_right(2) ^ v[0].rotate_right(13) ^ v[0].rotate_right(22);
            let maj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);
            let temp2 = s0.wrapping_add(maj);
            v = [
                temp1.wrapping_add(temp2),
                v[0],
                v[1],
                v[2],
                v[3].wrapping_add(temp1),
                v[4],
                v[5],
                v[6],
            ];
        }
        for index in 0..8 {
            h[index] = h[index].wrapping_add(v[index]);
        }
    }
    h.iter().map(|word| format!("{word:08x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn evidence_db() -> (tempfile::TempDir, String) {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("atlas.db");
        let conn = Connection::open(&path).expect("open");
        conn.execute_batch(include_str!(
            "../../../../../infra/migrations/0001_core.sql"
        ))
        .expect("core migration");
        conn.execute_batch(include_str!(
            "../../../../../infra/migrations/0033_evidence_plane.sql"
        ))
        .expect("evidence migration");
        conn.execute(
            "INSERT INTO missions(id,title,intent,status,project,created_at,updated_at)
             VALUES ('mission-1','test','','running','','now','now')",
            [],
        )
        .expect("mission");
        conn.execute(
            "INSERT INTO runs(id,mission_id,status,started_at,summary)
             VALUES ('run-1','mission-1','running','now','')",
            [],
        )
        .expect("run");
        (dir, path.to_string_lossy().into_owned())
    }

    #[test]
    fn evidence_storage_sha256_matches_standard_vector() {
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn evidence_storage_redacts_before_identity() {
        let (redacted, count) = redact_text("token=super-secret value");
        assert_eq!(redacted, "token=[REDACTED] value");
        assert_eq!(count, 1);
        assert!(!sha256_hex(redacted.as_bytes()).contains("super-secret"));
    }

    #[test]
    fn evidence_storage_round_trips_chunks_with_owner_scope() {
        let (_dir, db_path) = evidence_db();
        let secret = "password=hunter2 ";
        let content = format!("{secret}{}", "evidence".repeat(20_000));
        let receipt = persist_full_result(&FullResultRequest {
            protocol: PROTOCOL_VERSION.to_string(),
            db_path: db_path.clone(),
            owner_kind: "run".to_string(),
            owner_id: "run-1".to_string(),
            run_id: Some("run-1".to_string()),
            team_run_id: None,
            tool_call_id: None,
            content,
            media_type: "text/plain".to_string(),
            preview_limit: 2000,
        })
        .expect("persist");
        assert_eq!(receipt.availability, Availability::Redacted);
        assert!(receipt.preview.len() <= 2000);
        let bytes = read_full_result(Path::new(&db_path), "run", "run-1", &receipt.evidence_id)
            .expect("read");
        let text = String::from_utf8(bytes).expect("utf8");
        assert!(text.starts_with("password=[REDACTED] "));
        assert!(!text.contains("hunter2"));
        assert!(read_full_result(
            Path::new(&db_path),
            "run",
            "another-owner",
            &receipt.evidence_id
        )
        .is_err());
        let conn = Connection::open(db_path).expect("open");
        let chunks: i64 = conn
            .query_row("SELECT COUNT(*) FROM evidence_blob_chunks", [], |row| {
                row.get(0)
            })
            .expect("chunks");
        assert!(chunks > 1);
    }

    #[test]
    fn evidence_storage_rolls_back_all_linked_rows_on_failure() {
        let (_dir, db_path) = evidence_db();
        let conn = Connection::open(&db_path).expect("open");
        conn.execute_batch(
            "CREATE TRIGGER evidence_test_abort BEFORE INSERT ON evidence_blob_chunks
             BEGIN SELECT RAISE(ABORT, 'forced chunk failure'); END;",
        )
        .expect("trigger");
        drop(conn);
        let result = persist_full_result(&FullResultRequest {
            protocol: PROTOCOL_VERSION.to_string(),
            db_path: db_path.clone(),
            owner_kind: "run".to_string(),
            owner_id: "run-1".to_string(),
            run_id: Some("run-1".to_string()),
            team_run_id: None,
            tool_call_id: None,
            content: "will roll back".to_string(),
            media_type: "text/plain".to_string(),
            preview_limit: 2000,
        });
        assert!(result.is_err());
        let conn = Connection::open(db_path).expect("open");
        for table in [
            "evidence_blobs",
            "evidence_blob_chunks",
            "evidence_full_results",
        ] {
            let count: i64 = conn
                .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
                    row.get(0)
                })
                .expect("count");
            assert_eq!(count, 0, "{table} leaked a partial row");
        }
    }
}
