"""
Approval Queue Manager for Zeno Autonomous Safety.
Captures and queues high-impact or risky operations for human confirmation.
Enforces that risky actions never execute automatically without explicit human consent.
"""

from __future__ import annotations

from datetime import datetime
import json
import uuid
from typing import Any, Optional

from zeno.safety.database import get_db_connection


def create_approval_request(
    action_type: str,
    description: str = "",
    payload: Optional[dict[str, Any]] = None,
    job_id: Optional[str] = None,
    guard_verdict: str = "REQUIRES_APPROVAL",
    **kwargs: Any,
) -> str:
    """Create a pending approval record and return the approval ID."""
    if not description and "summary" in kwargs:
        description = str(kwargs["summary"])
    if payload is None:
        payload = kwargs.get("payload_json") or {}

    approval_id = f"appr-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    payload_json = json.dumps(payload)

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO approvals (
                id, job_id, action_type, description, guard_verdict, payload_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (approval_id, job_id, action_type, description, guard_verdict, payload_json, now),
        )
        conn.commit()
        return approval_id
    finally:
        conn.close()


def list_pending_approvals() -> list[dict[str, Any]]:
    """List all approvals currently awaiting human confirmation."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, job_id, action_type, description, guard_verdict, payload_json, status, created_at
            FROM approvals
            WHERE status = 'pending'
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["approval_id"] = item["id"]
            try:
                item["payload"] = json.loads(item.get("payload_json", "{}"))
            except Exception:
                item["payload"] = {}
            result.append(item)
        return result
    finally:
        conn.close()


def decide_approval(approval_id: str, approved: bool) -> bool:
    """Approve or reject a pending approval request."""
    now = datetime.now().isoformat()
    new_status = "approved" if approved else "rejected"
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE approvals
            SET status = ?, decided_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (new_status, now, approval_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_approval_status(approval_id: str) -> Optional[dict[str, Any]]:
    """Query current status of an approval request."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, action_type, status, decided_at FROM approvals WHERE id = ?",
            (approval_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
