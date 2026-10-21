"""
SQLite persistence engine for Zeno Autonomous Safety, Action Logs, Job Store,
Approvals Queue, and Observer Safety Dialogues.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Optional

from zeno.settings import BASE_DIR

DB_PATH = BASE_DIR / "safety.db"
_db_lock = threading.Lock()


def get_db_connection() -> sqlite3.Connection:
    """Return an initialized SQLite connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_safety_database() -> None:
    """Initialize SQLite tables for safety audit, jobs, approvals, and schedules."""
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 1. Action Log Table (Append-only)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    job_id TEXT,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    working_directory TEXT NOT NULL,
                    exit_code INTEGER,
                    duration_ms INTEGER,
                    output_preview TEXT
                )
            """)

            # 2. Jobs Store Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    pid INTEGER
                )
            """)

            # 3. Approvals Queue Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    job_id TEXT,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    guard_verdict TEXT,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
            """)

            # 4. Recurring Schedules Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    cron_expression TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    status TEXT NOT NULL
                )
            """)

            # 5. Observer & Builder Inter-Agent Safety Dialogue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observer_dialogue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    job_id TEXT,
                    speaker TEXT NOT NULL,
                    message TEXT NOT NULL,
                    action_proposed TEXT,
                    guard_verdict TEXT
                )
            """)

            conn.commit()
        finally:
            conn.close()


def redact_secrets(content: str) -> str:
    """Mask API keys, auth tokens, and secret parameters in argument strings."""
    if not content:
        return ""
    # Redact common key patterns
    patterns = [
        (r"(AIzaSy[a-zA-Z0-9_\-]{20,})", r"AIzaSy...[REDACTED]"),
        (r"(sk-[a-zA-Z0-9_\-]{15,})", r"sk-...[REDACTED]"),
        (r"(bearer\s+)([a-zA-Z0-9_\-\.]{16,})", r"\1[REDACTED_TOKEN]"),
        (r'("(?:api_?key|secret|token|password)"\s*:\s*")[^"]+(")', r"\1[REDACTED]\2"),
        (r"((?:key|token|secret|password)=)[^\s&]+", r"\1[REDACTED]"),
    ]
    redacted = content
    for pattern, repl in patterns:
        try:
            redacted = re.sub(pattern, repl, redacted, flags=re.IGNORECASE)
        except Exception:
            continue
    return redacted


def record_action_log(
    tool_name: str,
    arguments: Any,
    working_directory: str,
    duration_ms: int,
    exit_code: Optional[int] = 0,
    output_preview: str = "",
    job_id: Optional[str] = None,
) -> None:
    """Record an executed tool action to the append-only SQLite log table."""
    now = datetime.now().isoformat()
    try:
        args_str = json.dumps(arguments) if not isinstance(arguments, str) else arguments
    except Exception:
        args_str = str(arguments)

    safe_args = redact_secrets(args_str)
    truncated_output = output_preview[:2000] if output_preview else ""

    with _db_lock:
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO action_log (
                    timestamp, job_id, tool_name, arguments_json,
                    working_directory, exit_code, duration_ms, output_preview
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    job_id,
                    tool_name,
                    safe_args,
                    str(working_directory),
                    exit_code,
                    duration_ms,
                    truncated_output,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def recover_interrupted_jobs() -> int:
    """
    On application startup, recover any jobs left in status 'running'
    and mark them as failed with reason 'interrupted by restart'.
    Returns count of recovered jobs.
    """
    now = datetime.now().isoformat()
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    finished_at = ?,
                    error = 'interrupted by restart'
                WHERE status = 'running'
                """,
                (now,),
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()


def record_observer_dialogue(
    speaker: str,
    message: str,
    job_id: Optional[str] = None,
    action_proposed: Optional[str] = None,
    guard_verdict: Optional[str] = None,
) -> None:
    """Record safety exchange between Zeno Builder and Zeno Observer."""
    now = datetime.now().isoformat()
    with _db_lock:
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO observer_dialogue (
                    timestamp, job_id, speaker, message, action_proposed, guard_verdict
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, job_id, speaker, message, action_proposed, guard_verdict),
            )
            conn.commit()
        finally:
            conn.close()


def get_recent_observer_dialogues(limit: int = 15) -> list[dict[str, Any]]:
    """Retrieve recent safety checks and dialogues for the UI stream."""
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, job_id, speaker, message, action_proposed, guard_verdict
                FROM observer_dialogue
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()


def get_recent_action_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent action logs from the action_log table."""
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, job_id, tool_name, arguments_json, working_directory, exit_code, duration_ms, output_preview
                FROM action_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def clear_action_logs(log_ids: Optional[list[int | str]] = None) -> bool:
    """Clear all or selected action logs from SQLite table."""
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if log_ids and len(log_ids) > 0:
                placeholders = ",".join("?" for _ in log_ids)
                cursor.execute(f"DELETE FROM action_log WHERE id IN ({placeholders})", log_ids)
            else:
                cursor.execute("DELETE FROM action_log")
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

