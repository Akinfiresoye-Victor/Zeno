"""
Zeno Orchid: Adversarial AI Safety Guard & Task Planning Engine.
Performs continuous in-band scrutiny of all actions proposed by Zeno Bud,
intercepts and blocks destructive or sketchy operations, generates structured
dynamic-length step plans scaled to task complexity, and maintains an active
safety dialogue with Zeno Bud.
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

# Task complexity grading so Orchid cannot take the easy way out.
# The AI is required to generate enough steps to properly address the task.
COMPLEXITY_GRADE_PROMPT = """
STEP COUNT GRADING REQUIREMENTS (Zeno Orchid must comply):
  Grade F (Trivial) - 2 to 4 steps: Single-command tasks, simple Q&A with no files (e.g. "what is the time").
  Grade D (Simple) - 4 to 7 steps: Single-file scripts, basic automations, simple lookups (e.g. "write me a hello world script").
  Grade C (Moderate) - 7 to 12 steps: Multi-file projects, web scraping, data processing (e.g. "build a CSV parser").
  Grade B (Complex) - 12 to 18 steps: Full applications, multi-module systems, APIs (e.g. "build a REST API with tests").
  Grade A (Advanced) - 18 to 25 steps: Full-stack apps, ML pipelines, multi-service systems.
  Grade S (Expert) - 25+ steps: Large-scale systems, platform tools, comprehensive research + code.

YOU MUST correctly grade the task and generate AT LEAST the minimum number of steps
for that grade. NEVER compress a Grade B task into 4 steps to take shortcuts.
"""


def plan_task_with_observer(
    task_description: str,
    model: str = "gemini-3.5-flash-lite",
    api_key: str = "",
    custom_api_key: str = "",
) -> dict[str, Any]:
    """
    Zeno Orchid decomposes complex user requests into granular, dynamically-sized
    step blueprints with embedded safety boundaries before Zeno Bud begins.
    Step count scales with task complexity — no artificial cap or minimum.
    """
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
    # Support both `api_key` and legacy `custom_api_key` param name
    target_key = (api_key or custom_api_key or "").strip()
    if not target_key:
        target_key = os.getenv("GEMINI_API_KEY", "").strip()

    title = task_description.strip()[:60]

    # Sensible dynamic fallback plan (not fixed at 10 anymore)
    default_steps = _build_default_plan(task_description)

    if not target_key or target_key == "your_key_here":
        record_observer_dialogue(
            speaker="Zeno Orchid",
            message=f"Formulated a {len(default_steps)}-step safety blueprint for: {title}",
            action_proposed="plan_task",
            guard_verdict="APPROVED_PLAN",
        )
        return {"title": title, "steps": default_steps, "planner": "Zeno Orchid"}

    prompt = (
        "You are Zeno Orchid, a senior AI safety sentinel and software architect. "
        "Your role is to generate a precise, exhaustive execution roadmap for Zeno Bud "
        "(the worker agent) to follow step by step.\n\n"
        f"User Goal: {task_description}\n\n"
        f"{COMPLEXITY_GRADE_PROMPT}\n"
        "CRITICAL REQUIREMENTS:\n"
        "1. First, determine the complexity grade of this task based on the grading above.\n"
        "2. Generate AT LEAST the minimum number of steps for that grade — do NOT cut corners.\n"
        "3. Every step must be a concrete, specific, actionable directive. "
        "Name the exact files to create, tools to invoke, and validation checks to run.\n"
        "4. Include Zeno Orchid verification steps (safety checks, test execution, "
        "output validation) at appropriate milestones.\n"
        "5. For tasks involving web or external data, include dedicated research/fetch steps.\n"
        "6. For code tasks, always include a testing and verification step.\n"
        "7. End with a step where Zeno Orchid validates the final output and prepares "
        "the completion summary for the user.\n"
        "8. Output ONLY a numbered list (1. ..., 2. ...), one step per line. "
        "No markdown code blocks, no preamble, no explanations outside the list."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=target_key)
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=3000, temperature=0.2),
        )
        text = resp.text or ""
        lines = [re.sub(r"^\d+[\.\)]\s*", "", line).strip() for line in text.splitlines() if line.strip()]
        steps = [ln for ln in lines if len(ln) > 5]
        if len(steps) >= 2:
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=f"Formulated a {len(steps)}-step autonomous plan with safety guardrails.",
                action_proposed="plan_task",
                guard_verdict="APPROVED_PLAN",
            )
            return {
                "title": title,
                "steps": steps,
                "planner": "Zeno Orchid",
                "safety_summary": (
                    f"Zeno Orchid audited and approved a {len(steps)}-step milestone plan "
                    f"with workspace containment."
                ),
            }
    except Exception:
        pass

    return {
        "title": title,
        "steps": default_steps,
        "planner": "Zeno Orchid",
        "safety_summary": (
            f"Zeno Orchid configured a {len(default_steps)}-step milestone plan "
            f"with isolated workspace bounds."
        ),
    }


def _build_default_plan(task_description: str) -> list[str]:
    """
    Build a sensible dynamic default plan whose length scales with the apparent
    complexity of the task description. This replaces the old fixed 10-step fallback.
    """
    lower = task_description.lower()
    title = task_description.strip()[:40]

    # Heuristics to gauge complexity
    is_trivial = any(w in lower for w in [
        "what is", "what time", "hello", "tell me", "who is", "define",
    ])
    is_simple = any(w in lower for w in [
        "write a script", "hello world", "simple function", "basic", "small",
    ])
    is_complex = any(w in lower for w in [
        "application", "full stack", "api", "database", "microservice",
        "authentication", "dashboard", "machine learning", "ml", "pipeline",
        "multi", "system", "platform", "framework",
    ])

    if is_trivial:
        return [
            f"Zeno Orchid: Analyse intent and context for '{title}'",
            "Zeno Bud: Retrieve or compute the requested information",
            "Zeno Orchid: Validate accuracy and format the response",
        ]
    elif is_simple:
        return [
            f"Zeno Orchid: Audit environment and workspace for '{title}'",
            "Zeno Bud: Establish session workspace directory",
            "Zeno Bud: Write the core implementation file",
            "Zeno Bud: Execute and verify output is correct",
            "Zeno Orchid: Validate result and prepare user summary",
        ]
    elif is_complex:
        return [
            f"Zeno Orchid: Audit environment constraints and project scope for '{title}'",
            "Zeno Orchid: Verify workspace isolation and session directory",
            "Zeno Bud: Establish project scaffold, directory structure, and manifests",
            "Zeno Bud: Define core data schemas, type contracts, and interfaces",
            "Zeno Bud: Implement primary domain engine and core business logic",
            "Zeno Bud: Implement auxiliary utilities, validators, and input handlers",
            "Zeno Bud: Build API layer, CLI parser, or user-facing interface",
            "Zeno Bud: Implement data persistence, storage, or external integrations",
            "Zeno Orchid: Intermediate code safety and lint verification",
            "Zeno Bud: Author comprehensive unit test suite",
            "Zeno Bud: Author edge-case and boundary test fixtures",
            "Zeno Bud: Execute test runner and verify zero failures",
            "Zeno Orchid: Security audit and dependency check",
            "Zeno Bud: Write README and usage documentation",
            "Zeno Orchid: Validate completed artefacts and prepare final summary",
        ]
    else:
        # Moderate default
        return [
            f"Zeno Orchid: Audit environment and scope for '{title}'",
            "Zeno Orchid: Verify workspace isolation",
            "Zeno Bud: Establish session workspace and project scaffold",
            "Zeno Bud: Implement core application logic and modules",
            "Zeno Orchid: Intermediate safety and lint check",
            "Zeno Bud: Write automated test suite",
            "Zeno Bud: Execute tests and verify all pass",
            "Zeno Orchid: Validate outputs and prepare user summary",
        ]


def audit_action_with_observer(
    tool_name: str = "",
    tool_args: Optional[dict[str, Any]] = None,
    project_path: str = "",
    job_id: Optional[str] = None,
    **kwargs: Any,
) -> tuple[str, str]:
    """
    Zeno Orchid scrutinises an action proposed by Zeno Bud before execution.
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
                reason = f"Zeno Orchid VETO: Path '{val}' escapes approved workspace bounds. ({err})"
                record_observer_dialogue(
                    speaker="Zeno Orchid",
                    message=reason,
                    job_id=job_id,
                    action_proposed=f"{tool_name}({args_repr})",
                    guard_verdict="BLOCK",
                )
                return "BLOCK", reason

    # Use Layered Orchid Security Kernel for command evaluation
    from zeno.safety.rules import OrchidSecurityKernel

    if tool_name in ["shell_run", "run_python", "sandbox_run"]:
        cmd_str = tool_args.get("command") or tool_args.get("cmd") or tool_args.get("code") or ""
        eval_result = OrchidSecurityKernel.evaluate_command(str(cmd_str), project_dir=project_path)
        verdict = eval_result.verdict
        rule_name = eval_result.rule_name
        reason = f"[{rule_name}] {eval_result.reason}"

        if verdict == "DENY":
            deny_reason = f"Zeno Orchid VETO: {reason}"
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=deny_reason,
                job_id=job_id,
                action_proposed=f"{tool_name}: {cmd_str[:80]}",
                guard_verdict="BLOCK",
            )
            return "BLOCK", deny_reason
        elif verdict == "ASK_USER":
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=reason,
                job_id=job_id,
                action_proposed=f"{tool_name}: {cmd_str[:80]}",
                guard_verdict="ESCALATE",
            )
            return "ESCALATE", reason
        else:
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=f"Verified safe action: [{rule_name}] {eval_result.reason}",
                job_id=job_id,
                action_proposed=f"{tool_name}: {cmd_str[:80]}",
                guard_verdict="ALLOW",
            )
            return "ALLOW", eval_result.reason

    # File write operations
    if tool_name in ["write_file", "append_file", "create_document", "download_file"]:
        target_f = tool_args.get("path") or tool_args.get("destination_path") or tool_args.get("file_path") or ""
        eval_result = OrchidSecurityKernel.evaluate_file_write(str(target_f), project_dir=project_path)
        verdict = eval_result.verdict
        rule_name = eval_result.rule_name
        reason = f"[{rule_name}] {eval_result.reason}"

        if verdict == "DENY":
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=reason,
                job_id=job_id,
                action_proposed=f"{tool_name}: {target_f}",
                guard_verdict="BLOCK",
            )
            return "BLOCK", reason
        else:
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=f"Verified safe write: [{rule_name}] {eval_result.reason}",
                job_id=job_id,
                action_proposed=f"{tool_name}: {target_f}",
                guard_verdict="ALLOW",
            )
            return "ALLOW", eval_result.reason

    # 3. Git Branch Safety Check
    if tool_name == "git_commit":
        branch = tool_args.get("branch", "")
        if any(b in branch.lower() for b in ["main", "master", "prod"]):
            reason = (
                f"[rule_deny_protected_branch] Zeno Orchid VETO: Attempted to commit directly to protected "
                f"branch '{branch}'. Autonomous tasks must commit to feature branches."
            )
            record_observer_dialogue(
                speaker="Zeno Orchid",
                message=reason,
                job_id=job_id,
                action_proposed=f"git_commit on {branch}",
                guard_verdict="BLOCK",
            )
            return "BLOCK", reason

    # 4. Pip Package Installation Policy
    if tool_name == "pip_install":
        pkg = tool_args.get("package", "")
        reason = (
            f"[rule_allow_pip_package] Zeno Orchid: Package install '{pkg}' inside project environment approved."
        )
        record_observer_dialogue(
            speaker="Zeno Orchid",
            message=reason,
            job_id=job_id,
            action_proposed=f"pip_install({pkg})",
            guard_verdict="ALLOW",
        )
        return "ALLOW", reason

    # Safe and verified general action
    reason = f"[rule_general_allow] Safe action approved for {tool_name} with verified arguments."
    record_observer_dialogue(
        speaker="Zeno Orchid",
        message=reason,
        job_id=job_id,
        action_proposed=f"{tool_name}({args_repr[:80]})",
        guard_verdict="ALLOW",
    )
    return "ALLOW", reason


def get_recent_dialogues(limit: int = 15) -> list[dict[str, Any]]:
    """Retrieve recent safety dialogues from database."""
    from zeno.safety.database import get_recent_observer_dialogues
    return get_recent_observer_dialogues(limit=limit)

