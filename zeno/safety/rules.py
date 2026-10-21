"""
Layered Orchid Security Rules Engine for Zeno Desktop AI Assistant.
Enforces Rule F:
- Real, visible, and non-bypassable security evaluations for all tool actions.
- Three-tier verdicts: ALLOW, DENY, ASK_USER.
- Every verdict includes: verdict, rule_name, reason, and action details.
- Prohibits destructive commands and out-of-boundary file writes.
- Pre-approves safe venv, test, and project operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Optional

from zeno.settings import ALLOWED_FOLDERS, HOME_DIR

logger = logging.getLogger("zeno.safety_rules")


@dataclass
class OrchidEvaluation:
    verdict: str  # "ALLOW", "DENY", "ASK_USER"
    rule_name: str
    reason: str
    action_type: str
    action_target: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "rule_name": self.rule_name,
            "reason": self.reason,
            "action_type": self.action_type,
            "action_target": self.action_target,
            "timestamp": self.timestamp,
        }


class OrchidSecurityKernel:
    """
    Evaluates tool actions against layered security policies before execution.
    """

    # Prohibited destructive system command patterns (DENY)
    DESTRUCTIVE_COMMAND_PATTERNS = [
        (r"rm\s+-rf\s+[/~]", "rule_deny_destructive_wipe", "Prohibited: Attempting to delete root or home directory."),
        (r"format\s+[a-z]:", "rule_deny_drive_format", "Prohibited: Attempting to format a disk volume."),
        (r"reg\s+(add|delete)", "rule_deny_registry_edit", "Prohibited: Modifying the Windows system registry."),
        (r":(){ :|:& };:", "rule_deny_fork_bomb", "Prohibited: Shell fork bomb signature detected."),
        (r"del(\s+/[a-zA-Z]+)*\s+[cC]:\\(?:\s|\*|$)", "rule_deny_win_wipe", "Prohibited: Recursive deletion of system drive."),
        (r"curl.*?\|\s*(bash|sh|powershell)", "rule_deny_pipe_exec", "Prohibited: Direct execution of piped remote web payload."),
        (r"powershell\s+.*-(enc|encodedcommand)", "rule_deny_obfuscated_ps", "Prohibited: Obfuscated PowerShell execution."),
    ]

    # Critical system folders that cannot be written or modified (DENY)
    SYSTEM_FOLDERS = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "/etc",
        "/usr",
        "/var",
        "/bin",
        "/sbin",
    ]

    @classmethod
    def evaluate_command(
        cls,
        command_str: str,
        project_dir: Optional[Path | str] = None,
        is_in_venv: bool = False,
    ) -> OrchidEvaluation:
        """Evaluate a shell/process execution against Orchid security policies."""
        clean_cmd = (command_str or "").strip()
        lower_cmd = clean_cmd.lower()

        # 1. Check DENY list: destructive patterns
        for pattern, rule_id, reason in cls.DESTRUCTIVE_COMMAND_PATTERNS:
            if re.search(pattern, lower_cmd):
                return OrchidEvaluation(
                    verdict="DENY",
                    rule_name=rule_id,
                    reason=reason,
                    action_type="shell_run",
                    action_target=clean_cmd[:80],
                )

        # Check DENY list: targeting system directories
        for sys_dir in cls.SYSTEM_FOLDERS:
            if sys_dir in lower_cmd:
                return OrchidEvaluation(
                    verdict="DENY",
                    rule_name="rule_deny_system_folder_access",
                    reason=f"Prohibited: Command references critical system directory '{sys_dir}'.",
                    action_type="shell_run",
                    action_target=clean_cmd[:80],
                )

        # 2. Check ALLOW list: Safe Venv and Project Operations
        if ".venv" in lower_cmd or "pip install" in lower_cmd:
            return OrchidEvaluation(
                verdict="ALLOW",
                rule_name="rule_allow_venv_dependency_install",
                reason="Package installation into project isolated virtual environment (.venv) is safe and permitted.",
                action_type="shell_run",
                action_target=clean_cmd[:80],
            )

        # Test runner allow list
        if any(lower_cmd.startswith(x) or f"python -m {x}" in lower_cmd for x in ["pytest", "unittest", "npm test"]):
            return OrchidEvaluation(
                verdict="ALLOW",
                rule_name="rule_allow_test_runner",
                reason="Automated test suite execution inside project workspace is pre-approved.",
                action_type="shell_run",
                action_target=clean_cmd[:80],
            )

        # Check ASK_USER: external public network bindings
        if "0.0.0.0" in lower_cmd:
            return OrchidEvaluation(
                verdict="ASK_USER",
                rule_name="rule_escalate_public_port_binding",
                reason="Process attempts to bind to public interface 0.0.0.0. Requires user confirmation.",
                action_type="shell_run",
                action_target=clean_cmd[:80],
            )

        # Python execution inside project
        if lower_cmd.startswith("python") or "manage.py" in lower_cmd or "app.py" in lower_cmd:
            return OrchidEvaluation(
                verdict="ALLOW",
                rule_name="rule_allow_project_python_exec",
                reason="Executing Python scripts within the project workspace is pre-approved.",
                action_type="shell_run",
                action_target=clean_cmd[:80],
            )

        # Git operations (non-destructive)
        if lower_cmd.startswith("git ") and not any(x in lower_cmd for x in ["push --force", "reset --hard"]):
            return OrchidEvaluation(
                verdict="ALLOW",
                rule_name="rule_allow_git_inspection",
                reason="Non-destructive git version control operations are pre-approved.",
                action_type="shell_run",
                action_target=clean_cmd[:80],
            )

        # 3. Fallback: ASK_USER for unknown commands

        return OrchidEvaluation(
            verdict="ASK_USER",
            rule_name="rule_escalate_unrecognized_command",
            reason=f"Command '{clean_cmd[:60]}' is not on the pre-approved allowlist and requires operator review.",
            action_type="shell_run",
            action_target=clean_cmd[:80],
        )

    @classmethod
    def evaluate_file_write(
        cls,
        target_path: Path | str,
        project_dir: Optional[Path | str] = None,
    ) -> OrchidEvaluation:
        """Evaluate a file write/overwrite operation against containment rules."""
        try:
            target = Path(target_path).resolve()
        except Exception as exc:
            return OrchidEvaluation(
                verdict="DENY",
                rule_name="rule_deny_invalid_path",
                reason=f"Invalid file path: {exc}",
                action_type="write_file",
                action_target=str(target_path),
            )

        target_str = str(target).lower()

        # Check system directory write attempts
        for sys_dir in cls.SYSTEM_FOLDERS:
            if target_str.startswith(sys_dir):
                return OrchidEvaluation(
                    verdict="DENY",
                    rule_name="rule_deny_system_file_write",
                    reason=f"Prohibited: Attempting to write into protected system path '{sys_dir}'.",
                    action_type="write_file",
                    action_target=str(target),
                )

        # If project_dir is provided, enforce Rule B containment
        if project_dir:
            proj = Path(project_dir).resolve()
            if target != proj and proj not in target.parents:
                return OrchidEvaluation(
                    verdict="DENY",
                    rule_name="rule_deny_write_outside_project",
                    reason=f"Rule B Violation: Attempting to write to '{target}' which is outside project folder '{proj}'.",
                    action_type="write_file",
                    action_target=str(target),
                )
            return OrchidEvaluation(
                verdict="ALLOW",
                rule_name="rule_allow_project_file_write",
                reason=f"File write is contained strictly inside project folder '{proj.name}'.",
                action_type="write_file",
                action_target=str(target),
            )

        # Fallback check against user allowed folders
        is_allowed = any(
            target == allowed.resolve() or allowed.resolve() in target.parents
            for allowed in ALLOWED_FOLDERS
        )
        if not is_allowed:
            return OrchidEvaluation(
                verdict="DENY",
                rule_name="rule_deny_write_outside_allowed_folders",
                reason=f"File path '{target}' is outside user allowed workspace directories.",
                action_type="write_file",
                action_target=str(target),
            )

        return OrchidEvaluation(
            verdict="ALLOW",
            rule_name="rule_allow_user_folder_write",
            reason="File write is located inside user workspace directory.",
            action_type="write_file",
            action_target=str(target),
        )
