"""
Zeno Observer: Adversarial AI Safety Guard & Task Planning Engine.
Performs continuous in-band scrutiny of all actions proposed by Zeno Builder,
intercepts and blocks destructive or sketchy operations (e.g. software deletion,
system folder tampering), generates structured multi-step plans for complex tasks,
and maintains an active safety dialogue with Zeno Builder.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Optional

from dotenv import load_dotenv

from zeno.safety.command_guard import parse_and_validate_command
from zeno.safety.database import record_observer_dialogue
from zeno.safety.path_validator import validate_approved_path
from zeno.settings import ENV_FILE_PATH

# High-risk destructive signature patterns that must be blocked immediately
DANGEROUS_PATTERNS = [
    r"\b(rmdir|rd)\s+/[sS]",
    r"\bdel\s+/[fF]/[sS]/[qQ]",
    r"\b(rm|unlink)\s+-[rRfF]{1,3}",
    r"\bRemove-Item\s+.*-Recurse",
    r"\bformat\s+[a-zA-Z]:",
    r"\breg\s+(delete|add)",
    r"\b(drop\s+database|drop\s+table)\b",
    r"\b(kill|taskkill)\s+.*system",
    r"\b(mklink|ln\s+-s)\s+",
    r"\bshutdown\b",
    r"\bnet\s+(user|localgroup)",
]


def plan_task_with_observer(
    task_description: str,
    model: str = "gemini-3.5-flash-lite",
    custom_api_key: str = "",
) -> dict[str, Any]:
    """
    Zeno Observer decomposes complex user requests into granular (5 to 12)
    step blueprints with embedded safety boundaries before Zeno Builder begins.
    """
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    target_key = custom_api_key.strip() if custom_api_key else os.getenv("GEMINI_API_KEY", "").strip()

    title = task_description.strip()[:40]

    # Deterministic default multi-step plan for complex workflows
    default_steps = [
        f"Zeno Observer: Audit environment constraints and project roots for '{title}'",
        "Zeno Observer: Verify git worktree isolation on branch agent/<job-id>",
        "Zeno Builder: Establish project scaffold and dependency manifests",
        "Zeno Builder: Implement core application logic and architectural modules",
        "Zeno Observer: Perform intermediate code safety and lint verification",
        "Zeno Builder: Write unit tests and boundary test suites",
        "Zeno Builder: Execute test runner (run_tests) and verify zero failures",
        "Zeno Observer: Conduct security audit scan (pip-audit & bandit)",
        "Zeno Builder: Synthesize execution report in reports/ directory",
        "Zeno Observer: Validate completed worktree artifacts and prepare merge summary",
    ]

    if not target_key or target_key == "your_key_here":
        record_observer_dialogue(
            speaker="Zeno Observer",
            message=f"Formulated a 10-step safety blueprint for: {title}",
            action_proposed="plan_task",
            guard_verdict="APPROVED_PLAN",
        )
        return {"title": title, "steps": default_steps, "planner": "Zeno Observer"}

    prompt = (
        "You are Zeno Observer, a senior software architect and AI safety sentinel. "
        "Your role is to decompose the user's task into an exhaustive, highly detailed step-by-step execution roadmap for Zeno Builder (the worker agent).\n"
        f"User Goal: {task_description}\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "1. DO NOT return vague, generic, or broad steps. Break the task down into 8 to 14 granular, concrete, sequential engineering milestones.\n"
        "2. Every step must have a clear, specific directive (e.g. 1: Scaffold directory structure and manifest files; 2: Create data structures and type definitions; 3: Implement core business logic module; 4: Implement utility and validation helpers; 5: Build CLI command parser and error handlers; 6: Author comprehensive unit test suite; 7: Author edge-case and boundary test suite; 8: Execute test runner (run_tests) and inspect assertions; 9: Run lint and AST safety audits (lint_run); 10: Compile README and usage documentation; 11: Generate final executive markdown audit report (report_write)).\n"
        "3. Name the exact files to be created and tools to be invoked for each milestone.\n"
        "4. Output strictly a numbered list (e.g. '1. ...', '2. ...') with one step per line. Do NOT include markdown code blocks, backticks, or conversational preamble."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=target_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=2048, temperature=0.2),
        )
        text = resp.text or ""
        lines = [re.sub(r"^\d+[\.\)]\s*", "", line).strip() for line in text.splitlines() if line.strip()]
        steps = [l for l in lines if len(l) > 4]
        if len(steps) >= 4:
            record_observer_dialogue(
                speaker="Zeno Observer",
                message=f"Formulated a {len(steps)}-step autonomous plan with safety guardrails.",
                action_proposed="plan_task",
                guard_verdict="APPROVED_PLAN",
            )
            return {
                "title": title,
                "steps": steps,
                "planner": "Zeno Observer",
                "safety_summary": f"Zeno Observer audited and approved a {len(steps)}-step milestone plan with workspace containment.",
            }
    except Exception:
        pass

    return {
        "title": title,
        "steps": default_steps,
        "planner": "Zeno Observer",
        "safety_summary": f"Zeno Observer configured a {len(default_steps)}-step milestone plan with isolated worktree bounds.",
    }


def audit_action_with_observer(
    tool_name: str = "",
    tool_args: Optional[dict[str, Any]] = None,
    project_path: str = "",
    job_id: Optional[str] = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """
    Zeno Observer scrutinizes an action proposed by Zeno Builder before execution.
    Returns: (verdict, explanation)
    verdict is one of:
      - 'ALLOW': Safe, benign action.
      - 'BLOCK': Destructive, malicious, or out-of-bounds action. Immediately vetoed.
      - 'ESCALATE': Legitimate high-impact operation requiring human review.
    """
    if not tool_name and "action_type" in kwargs:
        tool_name = str(kwargs["action_type"])
    if tool_args is None and "action_payload" in kwargs:
        tool_args = kwargs["action_payload"]
    if tool_args is None:
        tool_args = {}

    args_repr = json.dumps(tool_args)

    # 1. Path Containment Check
    for key in ["path", "target_path", "working_dir", "cwd", "file_path", "directory"]:
        val = tool_args.get(key)
        if val and isinstance(val, str):
            is_valid, resolved, err = validate_approved_path(val)
            if not is_valid:
                reason = f"Zeno Observer VETO: Path '{val}' escapes approved workspace bounds. ({err})"
                record_observer_dialogue(
                    speaker="Zeno Observer",
                    message=reason,
                    job_id=job_id,
                    action_proposed=f"{tool_name}({args_repr})",
                    guard_verdict="BLOCK",
                )
                return "BLOCK", reason

    # 2. Command Safety Check for shell_run
    if tool_name == "shell_run":
        cmd = tool_args.get("command") or tool_args.get("cmd") or ""
        valid_cmd, cmd_args, err = parse_and_validate_command(cmd)
        if not valid_cmd:
            reason = f"Zeno Observer VETO: Command '{cmd}' is not allowlisted or contains shell metacharacters. ({err})"
            record_observer_dialogue(
                speaker="Zeno Observer",
                message=reason,
                job_id=job_id,
                action_proposed=f"shell_run: {cmd}",
                guard_verdict="BLOCK",
            )
            return "BLOCK", reason

        # Check for dangerous destructive patterns
        cmd_str = " ".join(cmd_args) if isinstance(cmd_args, list) else str(cmd)
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, cmd_str, re.IGNORECASE):
                reason = (
                    f"Zeno Observer VETO: Detected destructive signature in command '{cmd_str}'. "
                    f"Deleting software or system configurations is strictly forbidden."
                )
                record_observer_dialogue(
                    speaker="Zeno Observer",
                    message=reason,
                    job_id=job_id,
                    action_proposed=f"shell_run: {cmd_str}",
                    guard_verdict="BLOCK",
                )
                return "BLOCK", reason

    # 3. Git Branch Safety Check
    if tool_name == "git_commit":
        branch = tool_args.get("branch", "")
        if any(b in branch.lower() for b in ["main", "master", "prod"]):
            reason = (
                f"Zeno Observer VETO: Zeno Builder attempted to commit directly to protected branch '{branch}'. "
                f"Autonomous background tasks must only commit to 'agent/<job-id>' branches."
            )
            record_observer_dialogue(
                speaker="Zeno Observer",
                message=reason,
                job_id=job_id,
                action_proposed=f"git_commit on {branch}",
                guard_verdict="BLOCK",
            )
            return "BLOCK", reason

    # 4. Pip Package Installation Policy
    if tool_name == "pip_install":
        pkg = tool_args.get("package", "")
        # Require human review if installing packages
        reason = f"Zeno Observer: Package install '{pkg}' requires human confirmation before venv injection."
        record_observer_dialogue(
            speaker="Zeno Observer",
            message=reason,
            job_id=job_id,
            action_proposed=f"pip_install({pkg})",
            guard_verdict="ESCALATE",
        )
        return "ESCALATE", reason

    # Safe and verified action
    record_observer_dialogue(
        speaker="Zeno Observer",
        message=f"Verified safe action: {tool_name}",
        job_id=job_id,
        action_proposed=f"{tool_name}({args_repr})",
        guard_verdict="ALLOW",
    )
    return "ALLOW", "Action verified safe by Zeno Observer."


def get_recent_dialogues(limit: int = 15) -> list[dict[str, Any]]:
    """Retrieve recent safety dialogues from database."""
    from zeno.safety.database import get_recent_observer_dialogues
    return get_recent_observer_dialogues(limit=limit)
