"""
Engine Handlers for Zeno Desktop API.
Implements:
- Assistant chat and run inspection (Rule A).
- Agent run lifecycle, queue, and project workspace creation (Rule B).
- Python-verified step execution and jump-back (Rule C).
- Error classification and backoff (Rule D).
- Process supervision, health checks, screenshots, and kill-tree (Rule E).
"""

from __future__ import annotations

import base64
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Optional

from google.genai import types

from zeno.agent import ZenoAgent
from zeno.engine.checklist import ChecklistEngine, ChecklistStep, StepStatus
from zeno.engine.errors import ErrorClassifier, RetryHandler, save_step_draft
from zeno.engine.jobs import JobSupervisor
from zeno.engine.storage import StorageManager
from zeno.engine.workspace import ProjectWorkspace, generate_creative_folder_name, sanitize_folder_name
from zeno.memory import load_memory, save_memory, clear_memory, synthesize_memory_with_ai
from zeno.safety.observer import plan_task_with_observer
from zeno.safety.rules import OrchidSecurityKernel
from zeno.settings import DEFAULT_MODEL, DEFAULT_WORKSPACE_DIR, ENV_FILE_PATH, MEMORY_FILE_PATH, SCREENSHOTS_DIR
from zeno.tools.file_tools import get_active_project_dir, set_active_project_dir

logger = logging.getLogger("zeno.api_handlers")


class ZenoEngineHandlers:
    """Consolidated handlers for Assistant, Agent Workspace, Jobs, Files, and Memory."""

    def __init__(self, storage: StorageManager, job_supervisor: JobSupervisor):
        self.storage = storage
        self.job_supervisor = job_supervisor

    # -------------------------------------------------------------------------
    # Assistant (Rule A: Independent Chat & Read-Only Inspection)
    # -------------------------------------------------------------------------
    def get_assistant_threads(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self.storage.assistant_threads]

    def create_assistant_thread(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        title = (payload.get("title") if payload else None) or "New Chat"
        thread = self.storage.create_assistant_thread(title=title)
        return thread.to_dict()

    def delete_assistant_thread(self, payload: dict[str, Any]) -> dict[str, Any]:
        tid = payload.get("thread_id", "")
        success = self.storage.delete_assistant_thread(tid)
        return {"ok": success, "thread_id": tid}

    def inspect_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query") or payload.get("run_id") or ""
        return self.storage.inspect_agent_run(query)

    # -------------------------------------------------------------------------
    # Agent Workspace (Rule B, C, E: Workspace, Checklist, Execution)
    # -------------------------------------------------------------------------
    def get_agent_runs(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.storage.agent_runs]

    def create_agent_run(self, payload: dict[str, Any], api_client_fn: Optional[Callable] = None) -> dict[str, Any]:
        """
        Creates an isolated project folder with a creative 2-4 word name,
        initializes .venv, writes checklist.json, and enqueues the run.
        """
        task = payload.get("task") or payload.get("message", "")
        model = payload.get("model", DEFAULT_MODEL)
        custom_key = payload.get("customApiKey", "")
        project_name = payload.get("projectName")

        # Rule B: Creative folder naming (e.g. car-dash-tkinter, mathlab-core)
        ws = ProjectWorkspace(
            workspace_root=DEFAULT_WORKSPACE_DIR,
            project_name=project_name,
            task_hint=task,
        )
        set_active_project_dir(ws.project_dir)

        # Rule E: Initialize virtual environment (.venv) inside the project folder
        ws.ensure_virtualenv()

        # Generate plan steps
        try:
            plan = plan_task_with_observer(
                task_description=task,
                api_key=custom_key,
                model=model,
            )
            raw_steps = plan.get("steps", [])
        except Exception as exc:
            logger.warning("Observer plan generation fallback: %s", exc)
            raw_steps = [
                f"Scaffold project architecture and requirements for {ws.project_name}",
                "Implement primary modules and core domain logic",
                "Author automated test suite and edge-case verification",
                "Execute tests and verify passing exit code",
                "Finalize documentation and executive summary",
            ]

        # Rule C: Initialize checklist.json as single source of truth
        engine = ChecklistEngine(ws.project_dir, plan_title=task[:60])
        engine.initialize_steps(raw_steps)

        # Rule A: Enqueue run
        run_record = self.storage.enqueue_agent_run(
            task_prompt=task,
            title=ws.project_name,
            project_folder=str(ws.project_dir),
        )
        run_record.total_steps = len(engine.steps)
        self.storage.save_agent_runs()

        return {
            "run": run_record.to_dict(),
            "project_folder": str(ws.project_dir),
            "project_name": ws.project_name,
            "checklist": engine.get_progress_summary(),
            "steps": [s.to_dict() for s in engine.steps],
        }

    def rename_project_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rule B: Let user rename the project folder."""
        run_id = payload.get("run_id", "")
        new_name = payload.get("new_name", "")
        run = self.storage.get_agent_run(run_id)
        if not run:
            return {"ok": False, "error": f"Run '{run_id}' not found"}

        ws = ProjectWorkspace.from_existing_dir(run.project_folder)
        success, res = ws.rename_project(new_name)
        if success:
            run.project_folder = str(ws.project_dir)
            run.workspace_name = res
            self.storage.save_agent_runs()
            return {"ok": True, "new_name": res, "project_folder": str(ws.project_dir)}
        return {"ok": False, "error": res}

    def get_run_checklist(self, payload: dict[str, Any]) -> dict[str, Any]:
        pdir = payload.get("project_folder")
        if not pdir or not Path(pdir).exists():
            return {"steps": [], "progress": {}, "jumps": []}
        engine = ChecklistEngine(pdir)
        return {
            "steps": [s.to_dict() for s in engine.steps],
            "progress": engine.get_progress_summary(),
            "jumps": engine.history_jumps,
        }

    def execute_agent_step(
        self,
        payload: dict[str, Any],
        agent_executor_fn: Callable[..., Any],
    ) -> dict[str, Any]:
        """
        Executes one step in the checklist with:
        - Python verification gating (Rule C).
        - Error classifier & exponential backoff with jitter on SSL EOF / drops (Rule D).
        - Dedicated .venv python execution (Rule E).
        - Automated health checks for dev servers (Rule E).
        - Screen evidence capture (Rule E).
        """
        run_id = payload.get("run_id", "")
        step_id = payload.get("step_id", "")
        project_folder = payload.get("project_folder", "")
        model = payload.get("model", DEFAULT_MODEL)
        custom_key = payload.get("customApiKey", "")
        history = payload.get("history", [])

        ws = ProjectWorkspace.from_existing_dir(project_folder)
        set_active_project_dir(ws.project_dir)
        ws.ensure_virtualenv()

        engine = ChecklistEngine(ws.project_dir)
        step = engine.get_step(step_id) if step_id else engine.get_next_runnable_step()
        if not step:
            return {
                "error": "NO_RUNNABLE_STEP",
                "reply": "All steps verified or no runnable steps.",
                "progress": engine.get_progress_summary(),
            }

        # Rule C: Gating check - step cannot start until dependencies verified
        can_start, start_reason = engine.start_step(step.id)
        if not can_start:
            return {
                "error": "DEPENDENCY_NOT_MET",
                "reply": start_reason,
                "progress": engine.get_progress_summary(),
            }

        # Update run record to active
        self.storage.update_run_status(run_id, "active")

        tool_actions: list[str] = []
        live_logs: list[dict[str, Any]] = []

        def on_tool(line: str) -> None:
            tool_actions.append(line)
            live_logs.append({
                "type": "tool",
                "text": line,
                "ts": datetime.now().strftime("%H:%M:%S"),
            })

        # Rule E: Task prompt enforcing .venv python binary
        venv_py = ws.get_venv_python()
        step_prompt = (
            f"Project Directory: {ws.project_dir}\n"
            f"Dedicated Python Binary: {venv_py}\n"
            f"Step {step.id}: {step.title}\n\n"
            f"EXECUTION RULES:\n"
            f"1. ALL files MUST be created inside {ws.project_dir}\n"
            f"2. Run all Python commands using: {venv_py}\n"
            f"3. If dependencies are needed, install into .venv using pip_install or shell_run\n"
            f"4. If a server is started, verify it responds to HTTP requests\n"
            f"5. Create real, working code. Run tests to verify correctness."
        )

        # Rule D: RetryHandler with exponential backoff & jitter for SSL EOF / transient network
        retry_handler = RetryHandler(
            max_attempts=4,
            on_status=lambda msg: live_logs.append({"type": "retry", "text": msg, "ts": datetime.now().strftime("%H:%M:%S")}),
        )

        def step_operation():
            return agent_executor_fn(
                prompt=step_prompt,
                model=model,
                custom_key=custom_key,
                history=history,
                on_tool=on_tool,
            )

        success, agent_result, classified_err = retry_handler.execute_with_retry(
            operation=step_operation,
            provider_name=model,
            save_draft_fn=lambda txt: save_step_draft(ws.project_dir, step.id, txt),
        )

        if not success or not agent_result:
            err_msg = classified_err.user_friendly_summary if classified_err else "Step failed."
            # Rule D: A model error NEVER marks a step complete
            step.status = StepStatus.FAILED
            engine.is_paused = True
            engine.pause_reason = err_msg
            engine.save()
            return {
                "error": "MODEL_ERROR",
                "reply": f"Step {step.id} paused: {err_msg}",
                "progress": engine.get_progress_summary(),
                "step": step.to_dict(),
                "live_logs": live_logs,
                "canResume": True,
            }

        reply_text = agent_result.get("reply", "")
        in_tokens = agent_result.get("inputTokens", 0)
        out_tokens = agent_result.get("outputTokens", 0)

        # Rule E: Server health check verification
        server_checked = True
        for action in tool_actions:
            if "server_start" in action or "runserver" in action:
                port_match = re.search(r":(\d{4,5})", action)
                port = port_match.group(1) if port_match else "8000"
                health_ok = self.job_supervisor.perform_health_check(f"http://127.0.0.1:{port}/")
                if not health_ok:
                    server_checked = False
                    live_logs.append({
                        "type": "error",
                        "text": f"Health check failed: Server on port {port} did not respond.",
                        "ts": datetime.now().strftime("%H:%M:%S"),
                    })

        # Rule E: Screenshot visual evidence capture
        captured_screenshots: list[dict[str, Any]] = []
        screenshot_path = None
        evidence_dir = ws.project_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        gui_shot = evidence_dir / f"screenshot_{step.id}.png"

        # Capture GUI window if tkinter/PyQt mentioned
        if any(k in step.title.lower() or k in reply_text.lower() for k in ["tkinter", "game", "window", "gui", "canvas"]):
            shot = self.job_supervisor.capture_gui_window_screenshot(gui_shot)
            if shot and shot.exists():
                try:
                    with open(shot, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    captured_screenshots.append({
                        "name": shot.name,
                        "path": str(shot),
                        "base64": f"data:image/png;base64,{b64}",
                    })
                    screenshot_path = str(shot)
                except Exception:
                    pass

        # Rule C: Python verification gating
        # Step becomes 'verified' ONLY when all checks pass
        command_codes = [0] if server_checked else [1]
        verified, ver_msg = engine.verify_step(
            step_id=step.id,
            command_exit_codes=command_codes,
            screenshot_path=screenshot_path,
        )

        progress = engine.get_progress_summary()
        run = self.storage.get_agent_run(run_id)
        if run:
            run.verified_steps = progress["verified_steps"]
            if progress["is_complete"]:
                run.status = "completed"
            self.storage.save_agent_runs()

        return {
            "reply": reply_text,
            "step": step.to_dict(),
            "progress": progress,
            "toolActions": tool_actions,
            "live_logs": live_logs,
            "inputTokens": in_tokens,
            "outputTokens": out_tokens,
            "screenshots": captured_screenshots,
            "canResume": False,
        }

    def jump_back_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Rule C: Jump back to earlier step, mark it needs_revision,
        re-verifying dependent steps only.
        """
        from_step = payload.get("from_step_id", "")
        to_step = payload.get("to_step_id", "")
        reason = payload.get("reason", "Operator requested revision.")
        pdir = payload.get("project_folder", "")

        engine = ChecklistEngine(pdir)
        success, invalidated = engine.jump_back_for_revision(from_step, to_step, reason)
        return {
            "ok": success,
            "invalidated_steps": invalidated,
            "active_step_id": to_step,
            "progress": engine.get_progress_summary(),
        }

    def abort_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rule E: Stop every job the run started, including child processes."""
        run_id = payload.get("run_id", "")
        pdir = payload.get("project_folder", "")

        stopped_jobs = self.job_supervisor.stop_all_jobs_for_cwd(pdir)
        self.storage.update_run_status(run_id, "cancelled")
        return {"ok": True, "stopped_jobs_count": stopped_jobs, "run_id": run_id}

    # -------------------------------------------------------------------------
    # Jobs Panel (Rule E & G: Live Streaming Logs & Process Tree)
    # -------------------------------------------------------------------------
    def get_all_jobs(self) -> list[dict[str, Any]]:
        return self.job_supervisor.list_jobs()

    def get_job_logs(self, payload: dict[str, Any]) -> dict[str, Any]:
        jid = payload.get("job_id", "")
        return {"logs": self.job_supervisor.get_job_logs(jid)}

    def stop_single_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        jid = payload.get("job_id", "")
        success = self.job_supervisor.stop_job(jid)
        return {"ok": success, "job_id": jid}

    # -------------------------------------------------------------------------
    # Files Panel (Rule G: Real Project Tree)
    # -------------------------------------------------------------------------
    def list_project_files(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        pdir = payload.get("project_folder", "") or str(DEFAULT_WORKSPACE_DIR)
        ws = ProjectWorkspace.from_existing_dir(pdir)
        return ws.list_files()

    # -------------------------------------------------------------------------
    # Memory Page (Dedicated Memory Editor & Timestamp)
    # -------------------------------------------------------------------------
    def get_memory_data(self) -> dict[str, Any]:
        text = load_memory()
        mtime = None
        if MEMORY_FILE_PATH.exists():
            mtime = datetime.fromtimestamp(MEMORY_FILE_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        return {"memory": text, "last_modified": mtime or "Unknown"}
