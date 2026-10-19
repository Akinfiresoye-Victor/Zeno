"""
Background Worker Pool and Job Execution Controller for Zeno Autonomous Agents.
Manages a SQLite-backed job queue, enforces max 2 concurrent jobs, per-job timeouts,
and cleans up process trees on cancellation or termination via psutil.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Callable, Optional
import uuid

import psutil

from zeno.safety.database import get_db_connection, record_action_log

MAX_CONCURRENT_JOBS = 2
DEFAULT_JOB_TIMEOUT = 60

_shutdown_event = threading.Event()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)
_active_processes: dict[str, int] = {}  # job_id -> pid
_lock = threading.Lock()


def submit_background_job(
    job_type: str,
    payload: dict[str, Any],
    executor_fn: Optional[Callable[..., Any]] = None,
) -> str:
    """Create a new job record in SQLite and schedule it in the background worker pool."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    payload_json = json.dumps(payload)

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs (id, type, status, created_at, payload_json)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (job_id, job_type, now, payload_json),
        )
        conn.commit()
    finally:
        conn.close()

    # Schedule asynchronously in thread pool
    _executor.submit(_job_worker_wrapper, job_id, job_type, payload, executor_fn)
    return job_id


def get_job_info(job_id: str) -> Optional[dict[str, Any]]:
    """Retrieve job details from SQLite."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        info = dict(row)
        try:
            info["payload"] = json.loads(info.get("payload_json", "{}"))
        except Exception:
            info["payload"] = {}
        try:
            info["result"] = json.loads(info.get("result_json", "{}")) if info.get("result_json") else None
        except Exception:
            info["result"] = info.get("result_json")
        return info
    finally:
        conn.close()


def list_background_jobs(limit: int = 20) -> list[dict[str, Any]]:
    """List recent background jobs ordered by creation timestamp."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, type, status, created_at, started_at, finished_at, error, pid
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def cancel_background_job(job_id: str) -> bool:
    """Cancel a running or queued job and kill its process tree via psutil."""
    with _lock:
        pid = _active_processes.get(job_id)

    if pid:
        _kill_process_tree(pid)

    now = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE jobs
            SET status = 'cancelled', finished_at = ?, error = 'Job cancelled by user'
            WHERE id = ? AND status IN ('queued', 'running')
            """,
            (now, job_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _kill_process_tree(pid: int) -> None:
    """Terminate parent process and all its child subprocesses cleanly."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs(children, timeout=2)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass
        parent.terminate()
        parent.wait(timeout=2)
    except Exception:
        pass


def _job_worker_wrapper(
    job_id: str,
    job_type: str,
    payload: dict[str, Any],
    executor_fn: Optional[Callable[..., Any]] = None,
) -> None:
    """Worker loop executing a single background task with lifecycle tracking."""
    if _shutdown_event.is_set():
        return

    started_at = datetime.now().isoformat()
    timeout_sec = payload.get("timeout", DEFAULT_JOB_TIMEOUT)

    # Transition to running
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
            (started_at, job_id),
        )
        conn.commit()
    finally:
        conn.close()

    result_data = None
    error_msg = None
    status = "succeeded"

    start_time = time.time()
    try:
        if executor_fn:
            result_data = executor_fn(payload, job_id=job_id)
        else:
            # Default shell execution if command provided
            cmd = payload.get("command")
            cwd = payload.get("cwd", str(Path.cwd()))
            if cmd:
                from zeno.safety.command_guard import parse_and_validate_command

                valid, cmd_args, err = parse_and_validate_command(cmd)
                if not valid:
                    raise RuntimeError(f"Command rejected by guard: {err}")

                proc = subprocess.Popen(
                    cmd_args,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                )
                with _lock:
                    _active_processes[job_id] = proc.pid

                conn = get_db_connection()
                try:
                    conn.execute("UPDATE jobs SET pid = ? WHERE id = ?", (proc.pid, job_id))
                    conn.commit()
                finally:
                    conn.close()

                try:
                    stdout, stderr = proc.communicate(timeout=timeout_sec)
                    result_data = {
                        "exit_code": proc.returncode,
                        "stdout": stdout[:8000],
                        "stderr": stderr[:4000],
                    }
                    if proc.returncode != 0:
                        status = "failed"
                        error_msg = f"Process exited with non-zero code {proc.returncode}"
                except subprocess.TimeoutExpired:
                    _kill_process_tree(proc.pid)
                    status = "failed"
                    error_msg = f"Job exceeded timeout of {timeout_sec}s."
    except Exception as exc:
        status = "failed"
        error_msg = str(exc)
    finally:
        with _lock:
            _active_processes.pop(job_id, None)

    duration_ms = int((time.time() - start_time) * 1000)
    finished_at = datetime.now().isoformat()
    result_json = json.dumps(result_data) if result_data is not None else None

    # Update job in DB
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, finished_at = ?, result_json = ?, error = ?
            WHERE id = ?
            """,
            (status, finished_at, result_json, error_msg, job_id),
        )
        conn.commit()
    finally:
        conn.close()

    # Write to action log
    record_action_log(
        tool_name=f"job_{job_type}",
        arguments=payload,
        working_directory=payload.get("cwd", ""),
        duration_ms=duration_ms,
        exit_code=0 if status == "succeeded" else 1,
        output_preview=error_msg or str(result_data)[:500],
        job_id=job_id,
    )


def shutdown_worker_pool() -> None:
    """Trigger clean shutdown of background worker pool."""
    _shutdown_event.set()
    _executor.shutdown(wait=False)


class WorkerPoolManager:
    def list_active_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, type, status, created_at, started_at, error, pid, payload_json
                FROM jobs
                WHERE status IN ('queued', 'running')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            jobs = []
            for r in rows:
                item = dict(r)
                item["job_id"] = item["id"]
                item["command_type"] = item.get("type", "job")
                try:
                    payload = json.loads(item.get("payload_json", "{}"))
                    cmd = payload.get("command", "")
                    item["command_args"] = [cmd] if isinstance(cmd, str) else cmd
                except Exception:
                    item["command_args"] = []
                jobs.append(item)
            return jobs
        finally:
            conn.close()

    def cancel_job(self, job_id: str) -> bool:
        return cancel_background_job(job_id)


_pool_manager = WorkerPoolManager()


def get_worker_pool() -> WorkerPoolManager:
    return _pool_manager
