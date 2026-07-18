"""ATLAS retention service — data lifecycle management.

Implements automated data cleanup: compression, auto-archiving,
preview, and storage usage reporting.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional


def compress_mission_data(
    conn: sqlite3.Connection,
    lock: threading.Lock,
    *,
    after_archive_days: int = 14,
) -> int:
    """Compress old archived missions: summarize tool calls/events, delete artifact files.

    Returns count of missions compressed.
    """
    threshold = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=after_archive_days)
    ).isoformat()

    with lock:
        with conn:
            # Find archived missions older than threshold, not yet compressed
            rows = conn.execute(
                "SELECT m.id FROM missions m "
                "JOIN mission_archive ma ON ma.mission_id = m.id "
                "WHERE m.status = 'archived' "
                "AND ma.archived_at <= ? "
                "AND m.id NOT IN (SELECT mission_id FROM mission_compressions)",
                (threshold,),
            ).fetchall()

            for row in rows:
                mission_id = row[0]
                run_ids = [
                    r[0]
                    for r in conn.execute(
                        "SELECT id FROM runs WHERE mission_id=?", (mission_id,)
                    ).fetchall()
                ]

                tool_call_count = 0
                audit_event_count = 0
                artifact_count = 0
                summary_parts = []

                for run_id in run_ids:
                    # Summarize tool calls
                    tc_rows = conn.execute(
                        "SELECT tool_name, COUNT(*) FROM tool_calls "
                        "WHERE run_id=? GROUP BY tool_name",
                        (run_id,),
                    ).fetchall()
                    for tool_name, count in tc_rows:
                        tool_call_count += count
                        summary_parts.append(f"{tool_name}: {count} calls")

                    # Count audit events
                    ae_count = conn.execute(
                        "SELECT COUNT(*) FROM audit_events WHERE run_id=?",
                        (run_id,),
                    ).fetchone()[0]
                    audit_event_count += ae_count

                    # Count artifacts
                    art_count = conn.execute(
                        "SELECT COUNT(*) FROM artifacts WHERE run_id=?",
                        (run_id,),
                    ).fetchone()[0]
                    artifact_count += art_count

                # Store compression summary
                summary = {
                    "runs": len(run_ids),
                    "tool_calls": tool_call_count,
                    "audit_events": audit_event_count,
                    "artifacts": artifact_count,
                    "details": summary_parts[:20],  # Cap detail list
                }

                conn.execute(
                    "INSERT OR REPLACE INTO mission_compressions "
                    "(mission_id, compressed_at, tool_call_count, audit_event_count, "
                    "artifact_count, summary_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        mission_id,
                        datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        tool_call_count,
                        audit_event_count,
                        artifact_count,
                        json.dumps(summary),
                    ),
                )

                # Delete raw data for compressed runs
                for run_id in run_ids:
                    conn.execute("DELETE FROM tool_calls WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM audit_events WHERE run_id=?", (run_id,))
                    conn.execute("DELETE FROM artifacts WHERE run_id=?", (run_id,))

    return len(rows)


def get_storage_usage(conn: sqlite3.Connection) -> dict:
    """Get storage usage statistics."""
    mission_counts = {}
    for status in ["pending", "running", "succeeded", "failed", "cancelled", "archived"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM missions WHERE status=?", (status,)
        ).fetchone()[0]
        mission_counts[status] = count

    total_missions = sum(mission_counts.values())
    compressed = conn.execute(
        "SELECT COUNT(*) FROM mission_compressions"
    ).fetchone()[0]

    return {
        "missions": mission_counts,
        "missions_total": total_missions,
        "compressed": compressed,
    }


def get_purge_preview(
    conn: sqlite3.Connection,
    *,
    now: Optional[str] = None,
) -> list[dict]:
    """Preview missions that would be purged by auto-purge."""
    now_iso = now or datetime.datetime.now(datetime.timezone.utc).isoformat()

    rows = conn.execute(
        "SELECT m.id, m.title, ma.delete_after, ma.archived_at "
        "FROM missions m "
        "JOIN mission_archive ma ON ma.mission_id = m.id "
        "WHERE m.status = 'archived' AND ma.delete_after <= ? "
        "ORDER BY ma.delete_after ASC",
        (now_iso,),
    ).fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "delete_after": row[2],
            "archived_at": row[3],
        }
        for row in rows
    ]
