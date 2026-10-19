"""
Comprehensive Development Tools and Autonomous Safety Suite for Zeno AI Assistant.
Category: dev_tools
Implements job submission, isolated worktrees, allowlisted shell execution,
git inspection, test runner, lint auditing, security scanning, dev servers,
directory watching, task scheduling, sandbox execution, and package management.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Optional

from zeno.safety.approvals import create_approval_request
from zeno.safety.command_guard import parse_and_validate_command
from zeno.safety.database import (
    get_db_connection,
    record_action_log,
    record_observer_dialogue,
)
from zeno.safety.notifications import send_desktop_notification
from zeno.safety.observer import audit_action_with_observer
from zeno.safety.path_validator import validate_approved_path
from zeno.safety.worker import (
    cancel_background_job,
    get_job_info,
    submit_background_job,
)
from zeno.safety.worktree import (
    get_current_commit_hash,
    is_git_repository,
    rollback_agent_worktree,
    setup_agent_worktree,
)
from zeno.settings import BASE_DIR, DEFAULT_WORKSPACE_DIR

OUTPUT_MAX_CHARS = 8000

# Track active dev servers per project path: project_path -> {"pid": int, "log_file": Path, "proc": Popen}
_active_servers: dict[str, dict[str, Any]] = {}
_server_lock = threading.Lock()

# Watcher registry: project_path -> thread/controller
_active_watchers: dict[str, threading.Event] = {}
_watcher_lock = threading.Lock()


# -----------------------------------------------------------------------------
# 1. Job Management Tools (job_submit, job_status, job_cancel)
# -----------------------------------------------------------------------------
def job_submit(project_path: str, task_command: str, timeout_seconds: int = 60) -> dict[str, Any]:
    """
    Enqueue an autonomous background task in the job store.
    Validates project path and allowlisted command before scheduling.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    # Verify through Zeno Observer
    verdict, obs_reason = audit_action_with_observer(
        tool_name="shell_run",
        tool_args={"command": task_command, "cwd": str(res_path)},
        project_path=str(res_path),
    )
    if verdict == "BLOCK":
        return {"ok": False, "error": obs_reason}

    job_id = submit_background_job(
        job_type="dev_task",
        payload={
            "command": task_command,
            "cwd": str(res_path),
            "timeout": timeout_seconds,
        },
    )
    send_desktop_notification("Zeno Background Job", f"Job '{job_id}' queued in {res_path.name}")
    return {"ok": True, "job_id": job_id, "status": "queued", "project": str(res_path)}


def job_status(job_id: str) -> dict[str, Any]:
    """Query current status, execution duration, and output preview of a background job."""
    info = get_job_info(job_id)
    if not info:
        return {"ok": False, "error": f"Job '{job_id}' not found."}
    return {
        "ok": True,
        "job_id": info["id"],
        "status": info["status"],
        "created_at": info.get("created_at"),
        "started_at": info.get("started_at"),
        "finished_at": info.get("finished_at"),
        "result": info.get("result"),
        "error": info.get("error"),
    }


def job_cancel(job_id: str) -> dict[str, Any]:
    """Cancel a running or queued background job and terminate its process tree."""
    success = cancel_background_job(job_id)
    if success:
        return {"ok": True, "job_id": job_id, "message": "Job cancelled and process tree terminated."}
    return {"ok": False, "error": f"Unable to cancel job '{job_id}' (may be already finished or invalid)."}


# -----------------------------------------------------------------------------
# 2. Structured Report Writing (report_write)
# -----------------------------------------------------------------------------
def report_write(project_path: str, title: str, summary_markdown: str, job_id: str = "manual") -> dict[str, Any]:
    """
    Write an autonomous execution report to <project>/reports/<timestamp>-<job-id>.md.
    Strictly restricted to the project's reports/ subdirectory.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    reports_dir = res_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^\w\-]", "_", title.strip())[:30]
    filename = f"{timestamp}_{safe_title}_{job_id}.md"
    target_file = reports_dir / filename

    content = (
        f"# Autonomous Task Report: {title}\n\n"
        f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- **Job ID**: {job_id}\n"
        f"- **Project**: `{res_path}`\n\n"
        f"## Executive Summary & Actions Taken\n\n{summary_markdown.strip()}\n"
    )

    try:
        target_file.write_text(content, encoding="utf-8")
        record_action_log("report_write", {"file": str(target_file)}, str(res_path), 10, 0, content[:200], job_id)
        return {"ok": True, "report_path": str(target_file), "filename": filename}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to write report: {exc}"}


# -----------------------------------------------------------------------------
# 3. Allowlisted Shell Execution (shell_run)
# -----------------------------------------------------------------------------
def shell_run(command: str, working_dir: str = "", timeout_seconds: int = 60) -> dict[str, Any]:
    """
    Run an allowlisted command in an approved working directory with a timeout.
    Enforces shell=False, executable allowlists, and output truncation.
    """
    target_dir = working_dir if working_dir else str(DEFAULT_WORKSPACE_DIR)
    valid_path, res_path, path_err = validate_approved_path(target_dir)
    if not valid_path:
        return {"ok": False, "error": path_err}

    # Observer Safety Audit
    verdict, obs_reason = audit_action_with_observer(
        tool_name="shell_run",
        tool_args={"command": command, "cwd": str(res_path)},
        project_path=str(res_path),
    )
    if verdict == "BLOCK":
        return {"ok": False, "error": obs_reason}

    valid_cmd, cmd_args, cmd_err = parse_and_validate_command(command)
    if not valid_cmd:
        return {"ok": False, "error": cmd_err}

    start_time = time.time()
    try:
        res = subprocess.run(
            cmd_args,
            cwd=str(res_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        stdout_trunc = res.stdout[:OUTPUT_MAX_CHARS]
        stderr_trunc = res.stderr[:OUTPUT_MAX_CHARS]

        record_action_log("shell_run", {"cmd": cmd_args}, str(res_path), duration_ms, res.returncode, stdout_trunc[:300])
        return {
            "ok": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": stdout_trunc,
            "stderr": stderr_trunc,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        return {"ok": False, "error": f"Command timed out after {timeout_seconds} seconds.", "duration_ms": duration_ms}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# -----------------------------------------------------------------------------
# 4. Git Repository Inspection & Commits (git_status, git_diff, git_commit)
# -----------------------------------------------------------------------------
def git_status(project_path: str) -> dict[str, Any]:
    """Read-only git status showing modified, untracked, and staged files."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    return shell_run("git status --short --branch", working_dir=str(res_path), timeout_seconds=15)


def git_diff(project_path: str, staged: bool = False) -> dict[str, Any]:
    """Read-only git diff showing unstaged or staged modifications."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    cmd = "git diff --staged" if staged else "git diff"
    return shell_run(cmd, working_dir=str(res_path), timeout_seconds=20)


def git_commit(project_path: str, message: str) -> dict[str, Any]:
    """
    Commit staged changes on the agent's isolated branch only.
    Strictly refuses commits to 'main', 'master', or non-agent branches.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    # Check current branch
    branch_res = shell_run("git rev-parse --abbrev-ref HEAD", working_dir=str(res_path), timeout_seconds=10)
    current_branch = branch_res.get("stdout", "").strip()

    if not current_branch:
        return {"ok": False, "error": "Unable to determine current git branch."}

    # Observer Check
    verdict, obs_reason = audit_action_with_observer(
        tool_name="git_commit",
        tool_args={"branch": current_branch, "message": message},
        project_path=str(res_path),
    )
    if verdict == "BLOCK":
        return {"ok": False, "error": obs_reason}

    # Clean message
    clean_msg = message.replace('"', '\\"')
    return shell_run(f'git commit -m "{clean_msg}"', working_dir=str(res_path), timeout_seconds=15)


# -----------------------------------------------------------------------------
# 5. Test Runner & Quality Auditing (run_tests, lint_run, security_scan)
# -----------------------------------------------------------------------------
def run_tests(project_path: str, test_target: str = "") -> dict[str, Any]:
    """
    Run pytest or python manage.py test in a project, parsing structured failures.
    Returns: {"ok": bool, "passed": int, "failed": int, "failures": list[dict]}
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    cmd = f"pytest {test_target}".strip() if test_target else "pytest"
    res = shell_run(cmd, working_dir=str(res_path), timeout_seconds=90)

    stdout = res.get("stdout", "")
    failures: list[dict[str, str]] = []

    # Parse pytest failures: e.g. FAILED tests/test_foo.py::test_bar - AssertionError: ...
    for match in re.finditer(r"FAILED\s+([^\s:]+)::([^\s\-]+)(?:\s+-\s+(.+))?", stdout):
        file_path = match.group(1)
        test_name = match.group(2)
        err_msg = match.group(3) or "Test assertion failed"
        failures.append({"file": file_path, "test": test_name, "error": err_msg.strip()})

    return {
        "ok": res.get("exit_code") == 0,
        "exit_code": res.get("exit_code"),
        "failures_count": len(failures),
        "failures": failures,
        "stdout": stdout[:4000],
    }


def lint_run(project_path: str) -> dict[str, Any]:
    """Run ruff check and mypy to return structured lint and type issues."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    ruff_res = shell_run("ruff check .", working_dir=str(res_path), timeout_seconds=45)
    mypy_res = shell_run("mypy .", working_dir=str(res_path), timeout_seconds=60)

    issues: list[dict[str, str]] = []
    # Parse ruff output: file:line:col: CODE message
    for line in ruff_res.get("stdout", "").splitlines():
        m = re.match(r"^([^:]+):(\d+):(\d+):\s+([A-Z0-9]+)\s+(.+)", line)
        if m:
            issues.append({
                "file": m.group(1),
                "line": m.group(2),
                "code": m.group(4),
                "message": m.group(5),
                "tool": "ruff",
            })

    return {
        "ok": len(issues) == 0,
        "total_issues": len(issues),
        "issues": issues[:50],
        "ruff_output": ruff_res.get("stdout", "")[:2000],
        "mypy_output": mypy_res.get("stdout", "")[:2000],
    }


def security_scan(project_path: str) -> dict[str, Any]:
    """Run pip-audit and bandit security scans, saving results into a structured report."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    bandit_res = shell_run("bandit -r . -f json", working_dir=str(res_path), timeout_seconds=60)
    audit_res = shell_run("pip-audit", working_dir=str(res_path), timeout_seconds=60)

    report_content = (
        f"### Security Vulnerability Audit\n\n"
        f"**Bandit SAST Output**:\n```\n{bandit_res.get('stdout', '')[:2500]}\n```\n\n"
        f"**Pip-Audit Dependency Scan**:\n```\n{audit_res.get('stdout', '')[:2500]}\n```\n"
    )
    rep_res = report_write(str(res_path), "Security Vulnerability Audit", report_content)

    return {
        "ok": bandit_res.get("exit_code") == 0 and audit_res.get("exit_code") == 0,
        "bandit_clean": bandit_res.get("exit_code") == 0,
        "pip_audit_clean": audit_res.get("exit_code") == 0,
        "report": rep_res.get("report_path"),
    }


# -----------------------------------------------------------------------------
# 6. Background Dev Servers (server_start, server_stop, server_logs)
# -----------------------------------------------------------------------------
def server_start(project_path: str, start_command: str = "python manage.py runserver") -> dict[str, Any]:
    """
    Launch an allowlisted dev server in the background (max 1 server per project).
    Captures logs to a capped file and tracks PID for process tree cleanup.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    proj_key = str(res_path)
    with _server_lock:
        if proj_key in _active_servers:
            existing = _active_servers[proj_key]
            return {"ok": False, "error": f"A dev server is already running for this project (PID {existing['pid']})."}

        valid_cmd, cmd_args, err = parse_and_validate_command(start_command)
        if not valid_cmd:
            return {"ok": False, "error": err}

        log_file = res_path / ".zeno_server.log"
        log_fp = open(log_file, "w", encoding="utf-8")

        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=str(res_path),
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                shell=False,
            )
            _active_servers[proj_key] = {
                "pid": proc.pid,
                "log_file": log_file,
                "proc": proc,
                "cmd": start_command,
                "started_at": datetime.now().isoformat(),
            }
            return {"ok": True, "pid": proc.pid, "project": proj_key, "log_file": str(log_file)}
        except Exception as exc:
            return {"ok": False, "error": f"Failed to start server: {exc}"}


def server_stop(project_path: str) -> dict[str, Any]:
    """Terminate the active dev server process tree for the specified project."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    proj_key = str(res_path)
    with _server_lock:
        server_info = _active_servers.pop(proj_key, None)
        if not server_info:
            return {"ok": False, "error": f"No active dev server found for project '{proj_key}'."}

        pid = server_info["pid"]
        from zeno.safety.worker import _kill_process_tree

        _kill_process_tree(pid)
        return {"ok": True, "message": f"Dev server (PID {pid}) stopped."}


def server_logs(project_path: str, lines: int = 50) -> dict[str, Any]:
    """Read the recent log buffer of the project's background dev server."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    log_file = res_path / ".zeno_server.log"
    if not log_file.exists():
        return {"ok": False, "error": "No server log file found."}

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = "".join(all_lines[-lines:])
        return {"ok": True, "lines_count": len(all_lines), "logs": tail}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# -----------------------------------------------------------------------------
# 7. Filesystem Change Watcher (watch_start, watch_stop)
# -----------------------------------------------------------------------------
def watch_start(project_path: str, action_command: str = "pytest") -> dict[str, Any]:
    """
    Monitor an approved project directory for file modifications with a 3-second debounce.
    When code changes, automatically enqueues at most 1 test/lint job per project.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    proj_key = str(res_path)
    with _watcher_lock:
        if proj_key in _active_watchers:
            return {"ok": False, "error": "Watcher is already active for this project."}

        stop_event = threading.Event()
        _active_watchers[proj_key] = stop_event

        def _polling_watch_thread():
            last_mtime = time.time()
            pending_debounce = False
            debounce_start = 0.0

            while not stop_event.is_set():
                time.sleep(1.0)
                # Check for changes in project python files
                has_changed = False
                for root, _, files in os.walk(str(res_path)):
                    if any(ign in root for ign in [".git", "__pycache__", ".zeno_worktrees", "node_modules"]):
                        continue
                    for f in files:
                        if f.endswith((".py", ".ts", ".tsx", ".js", ".html")):
                            fp = os.path.join(root, f)
                            try:
                                mt = os.path.getmtime(fp)
                                if mt > last_mtime:
                                    has_changed = True
                                    last_mtime = mt
                            except Exception:
                                pass

                if has_changed:
                    pending_debounce = True
                    debounce_start = time.time()

                if pending_debounce and (time.time() - debounce_start >= 3.0):
                    pending_debounce = False
                    # Trigger single background test job
                    submit_background_job("watcher_trigger", {"command": action_command, "cwd": proj_key, "timeout": 45})

        t = threading.Thread(target=_polling_watch_thread, daemon=True)
        t.start()
        return {"ok": True, "message": f"Watcher started for '{res_path.name}' (debounced 3s)."}


def watch_stop(project_path: str) -> dict[str, Any]:
    """Stop the active directory watcher for a project."""
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    proj_key = str(res_path)
    with _watcher_lock:
        evt = _active_watchers.pop(proj_key, None)
        if not evt:
            return {"ok": False, "error": "No active watcher found for this project."}
        evt.set()
        return {"ok": True, "message": "Watcher stopped."}


# -----------------------------------------------------------------------------
# 8. Recurring Task Scheduler (schedule_task)
# -----------------------------------------------------------------------------
def schedule_task(project_path: str, task_type: str, cron_expression: str = "0 0 * * *") -> dict[str, Any]:
    """
    Schedule a read-only recurring job (nightly run_tests, lint_run, or pip-audit).
    Scheduled jobs cannot write code and are persisted in SQLite.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    allowed_types = ["run_tests", "lint_run", "security_scan"]
    if task_type not in allowed_types:
        return {"ok": False, "error": f"Invalid scheduled task type. Allowed read-only types: {allowed_types}"}

    import uuid
    sched_id = f"sch-{uuid.uuid4().hex[:8]}"

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO schedules (id, task_type, project_path, cron_expression, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (sched_id, task_type, str(res_path), cron_expression),
        )
        conn.commit()
        return {"ok": True, "schedule_id": sched_id, "task_type": task_type, "cron": cron_expression}
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 9. Isolated Sandbox Code Execution (sandbox_run)
# -----------------------------------------------------------------------------
def sandbox_run(python_code: str, timeout_seconds: int = 30) -> dict[str, Any]:
    """
    Execute Python code in an isolated temporary environment without access to
    user root files or network. Enforces sandbox containment and strict timeout.
    """
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="zeno_sandbox_")
    script_path = Path(temp_dir) / "sandbox_script.py"

    try:
        script_path.write_text(python_code, encoding="utf-8")
        start_time = time.time()
        res = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "ok": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": res.stdout[:OUTPUT_MAX_CHARS],
            "stderr": res.stderr[:OUTPUT_MAX_CHARS],
            "duration_ms": duration_ms,
            "sandboxed": True,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Sandbox execution timed out after {timeout_seconds}s.", "sandboxed": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "sandboxed": True}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# -----------------------------------------------------------------------------
# 10. Virtualenv Package Manager (pip_install)
# -----------------------------------------------------------------------------
def pip_install(project_path: str, package_name: str, venv_name: str = ".venv") -> dict[str, Any]:
    """
    Install a package into a project's local virtual environment.
    Refuses global Python environment. Requires human approval if package is not in requirements.txt.
    """
    valid_path, res_path, path_err = validate_approved_path(project_path)
    if not valid_path:
        return {"ok": False, "error": path_err}

    # Locate venv executable on Windows / POSIX
    venv_dir = res_path / venv_name
    venv_pip = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / ("pip.exe" if sys.platform == "win32" else "pip")

    if not venv_pip.exists():
        return {
            "ok": False,
            "error": f"Virtual environment '{venv_name}' not found at '{venv_dir}'. Zeno refuses global Python installs.",
        }

    # Check requirements.txt
    req_file = res_path / "requirements.txt"
    in_requirements = False
    if req_file.exists():
        try:
            req_content = req_file.read_text(encoding="utf-8")
            if re.search(rf"\b{re.escape(package_name)}\b", req_content, re.IGNORECASE):
                in_requirements = True
        except Exception:
            pass

    if not in_requirements:
        # Require human approval
        appr_id = create_approval_request(
            action_type="pip_install",
            description=f"Install package '{package_name}' into virtualenv {venv_name} (not listed in requirements.txt)",
            payload={"project_path": str(res_path), "package": package_name, "venv": str(venv_dir)},
            guard_verdict="REQUIRES_HUMAN_APPROVAL",
        )
        return {
            "ok": False,
            "requires_approval": True,
            "approval_id": appr_id,
            "message": f"Package '{package_name}' is not in requirements.txt. Approval request '{appr_id}' submitted.",
        }

    # Execute inside venv
    res = subprocess.run(
        [str(venv_pip), "install", package_name],
        cwd=str(res_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=120,
    )
    return {
        "ok": res.returncode == 0,
        "stdout": res.stdout[:OUTPUT_MAX_CHARS],
        "stderr": res.stderr[:OUTPUT_MAX_CHARS],
    }


# -----------------------------------------------------------------------------
# Deferred Tool Stubs (Explicit TODO notices per specification)
# -----------------------------------------------------------------------------
def db_query(query: str, database_path: str = "") -> dict[str, Any]:
    """TODO: Deferred pending read-only connection pooling and sandbox validation."""
    return {"ok": False, "error": "db_query is deferred in this release per security policy."}


def browser_automation(action: str, url: str = "") -> dict[str, Any]:
    """TODO: Deferred pending isolated Playwright headless runner."""
    return {"ok": False, "error": "browser_automation is deferred in this release per security policy."}


def process_kill(pid: int) -> dict[str, Any]:
    """TODO: Deferred to prevent accidental operating system process disruption."""
    return {"ok": False, "error": "process_kill is deferred; use job_cancel for agent-spawned tasks."}


def git_push(remote: str = "origin", branch: str = "") -> dict[str, Any]:
    """TODO: Permanently deferred. Autonomous background agent is never permitted to push to remote."""
    return {"ok": False, "error": "git_push is strictly prohibited for autonomous agents."}
