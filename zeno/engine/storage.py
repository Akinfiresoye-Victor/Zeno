"""
Storage, Data Migration, and Run Queue Engine for Zeno Desktop AI Assistant.
Enforces Rule A:
- Two separate areas: Assistant (Chat) and Agent Workspace.
- Independent history stores: zeno/assistant_chats.json and zeno/agent_runs.json.
- Automatic zero-loss migration from existing zeno/chats.json.
- Run Queue Engine with configurable concurrency (default: 1 active run, others queued).
- Read-only Agent Run Inspector allowing Assistant to analyze agent runs without mutating them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Any, Optional

from zeno.settings import BASE_DIR, CHATS_METADATA_PATH

logger = logging.getLogger("zeno.storage")

ASSISTANT_CHATS_PATH = BASE_DIR / "assistant_chats.json"
AGENT_RUNS_PATH = BASE_DIR / "agent_runs.json"


@dataclass
class AssistantMessage:
    id: str
    role: str  # user, assistant, system
    content: str
    timestamp: str
    tokens: Optional[dict[str, int]] = None
    attachments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AssistantThread:
    id: str
    title: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    model: str = "gemini-3.5-flash-lite"
    total_tokens: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRunRecord:
    id: str
    task_prompt: str
    title: str
    project_folder: str
    workspace_name: str
    status: str = "queued"  # queued, active, paused, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    model_used: str = "gemini-3.5-flash-lite"
    tokens: dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0})
    error_summary: Optional[str] = None
    evidence_screenshots: list[str] = field(default_factory=list)
    active_step_id: Optional[str] = None
    total_steps: int = 0
    verified_steps: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StorageManager:
    """Manages separate Assistant threads and Agent Workspace runs with a robust queue."""

    def __init__(self):
        self._ensure_migration()
        self.assistant_threads: list[AssistantThread] = self._load_assistant_threads()
        self.agent_runs: list[AgentRunRecord] = self._load_agent_runs()
        self.max_concurrent_runs: int = 1

    def _ensure_migration(self) -> None:
        """Migrate legacy chats.json into assistant_chats.json and agent_runs.json without data loss."""
        if not CHATS_METADATA_PATH.exists():
            return

        need_assistant = not ASSISTANT_CHATS_PATH.exists()
        need_agent = not AGENT_RUNS_PATH.exists()

        if not (need_assistant or need_agent):
            return

        try:
            with open(CHATS_METADATA_PATH, "r", encoding="utf-8") as f:
                legacy_chats = json.load(f)

            if not isinstance(legacy_chats, list):
                return

            migrated_assistant = []
            migrated_agent = []

            for chat in legacy_chats:
                cid = chat.get("id", f"sess-{int(time.time()*1000)}")
                title = chat.get("title", "Conversation")
                msgs = chat.get("messages", [])
                c_at = chat.get("created_at", time.time())
                l_at = chat.get("last_activity", c_at)
                ast = chat.get("agentState") or {}

                # Check if this chat was an agentic task
                if ast.get("hasTask") or ast.get("plan") or len(ast.get("thoughts", [])) > 0:
                    run = AgentRunRecord(
                        id=f"run-{cid}",
                        task_prompt=title,
                        title=title,
                        project_folder=ast.get("sessionWorkspace", ""),
                        workspace_name=Path(ast.get("sessionWorkspace", "workspace")).name,
                        status="completed" if ast.get("status") == "completed" else "paused",
                        created_at=c_at,
                        started_at=c_at,
                        finished_at=l_at,
                        messages=msgs + ast.get("messages", []),
                        total_steps=len(ast.get("plan", {}).get("steps", []) if isinstance(ast.get("plan"), dict) else []),
                        verified_steps=len([s for s in ast.get("plan", {}).get("steps", []) if s.get("completed")]) if isinstance(ast.get("plan"), dict) else 0,
                    )
                    migrated_agent.append(run.to_dict())
                else:
                    thread = AssistantThread(
                        id=cid,
                        title=title,
                        messages=msgs,
                        created_at=c_at,
                        last_activity=l_at,
                    )
                    migrated_assistant.append(thread.to_dict())

            if need_assistant and migrated_assistant:
                with open(ASSISTANT_CHATS_PATH, "w", encoding="utf-8") as f:
                    json.dump(migrated_assistant, f, indent=2)

            if need_agent and migrated_agent:
                with open(AGENT_RUNS_PATH, "w", encoding="utf-8") as f:
                    json.dump(migrated_agent, f, indent=2)

            # Preserve backup
            shutil.copyfile(CHATS_METADATA_PATH, BASE_DIR / "chats.json.bak")
            logger.info("Migrated %d assistant chats and %d agent runs.", len(migrated_assistant), len(migrated_agent))

        except Exception as exc:
            logger.error("Migration error from chats.json: %s", exc)

    def _load_assistant_threads(self) -> list[AssistantThread]:
        if ASSISTANT_CHATS_PATH.exists():
            try:
                with open(ASSISTANT_CHATS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [AssistantThread(**item) for item in data if isinstance(item, dict)]
            except Exception as exc:
                logger.error("Failed to load assistant_chats.json: %s", exc)
        return []

    def _load_agent_runs(self) -> list[AgentRunRecord]:
        if AGENT_RUNS_PATH.exists():
            try:
                with open(AGENT_RUNS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [AgentRunRecord(**item) for item in data if isinstance(item, dict)]
            except Exception as exc:
                logger.error("Failed to load agent_runs.json: %s", exc)
        return []

    def save_assistant_threads(self) -> None:
        try:
            with open(ASSISTANT_CHATS_PATH, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self.assistant_threads], f, indent=2)
        except Exception as exc:
            logger.error("Failed to save assistant_chats.json: %s", exc)

    def save_agent_runs(self) -> None:
        try:
            with open(AGENT_RUNS_PATH, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.agent_runs], f, indent=2)
        except Exception as exc:
            logger.error("Failed to save agent_runs.json: %s", exc)

    # -------------------------------------------------------------------------
    # Assistant Thread Methods
    # -------------------------------------------------------------------------
    def get_assistant_thread(self, thread_id: str) -> Optional[AssistantThread]:
        for t in self.assistant_threads:
            if t.id == thread_id:
                return t
        return None

    def create_assistant_thread(self, title: str = "New Chat") -> AssistantThread:
        tid = f"thread-{int(time.time() * 1000)}"
        thread = AssistantThread(id=tid, title=title)
        self.assistant_threads.insert(0, thread)
        self.save_assistant_threads()
        return thread

    def delete_assistant_thread(self, thread_id: str) -> bool:
        initial_len = len(self.assistant_threads)
        self.assistant_threads = [t for t in self.assistant_threads if t.id != thread_id]
        if len(self.assistant_threads) != initial_len:
            self.save_assistant_threads()
            return True
        return False

    # -------------------------------------------------------------------------
    # Agent Run Queue Methods
    # -------------------------------------------------------------------------
    def get_agent_run(self, run_id: str) -> Optional[AgentRunRecord]:
        for r in self.agent_runs:
            if r.id == run_id:
                return r
        return None

    def enqueue_agent_run(
        self,
        task_prompt: str,
        title: str,
        project_folder: str,
    ) -> AgentRunRecord:
        """Create a new run and place it in the queue."""
        rid = f"run-{int(time.time() * 1000)}"
        run = AgentRunRecord(
            id=rid,
            task_prompt=task_prompt,
            title=title,
            project_folder=str(project_folder),
            workspace_name=Path(project_folder).name,
            status="queued",
            created_at=time.time(),
        )
        self.agent_runs.insert(0, run)
        self.save_agent_runs()
        return run

    def get_active_agent_runs(self) -> list[AgentRunRecord]:
        return [r for r in self.agent_runs if r.status == "active"]

    def get_queued_agent_runs(self) -> list[AgentRunRecord]:
        return [r for r in self.agent_runs if r.status == "queued"]

    def can_start_next_run(self) -> bool:
        active_count = len(self.get_active_agent_runs())
        return active_count < self.max_concurrent_runs

    def update_run_status(self, run_id: str, status: str, error_summary: Optional[str] = None) -> bool:
        run = self.get_agent_run(run_id)
        if not run:
            return False
        run.status = status
        if status == "active" and not run.started_at:
            run.started_at = time.time()
        elif status in ["completed", "failed", "cancelled"]:
            run.finished_at = time.time()
        if error_summary:
            run.error_summary = error_summary
        self.save_agent_runs()
        return True

    # -------------------------------------------------------------------------
    # Cross-Area Read-Only Agent Inspector (Rule A)
    # -------------------------------------------------------------------------
    def inspect_agent_run(self, run_id_or_title: str) -> dict[str, Any]:
        """
        Allows Assistant to read the agent run record (steps, checklist, logs, files)
        to answer user questions without mutating state.
        """
        target_run: Optional[AgentRunRecord] = None
        for r in self.agent_runs:
            if r.id == run_id_or_title or r.title.lower() == run_id_or_title.lower():
                target_run = r
                break

        if not target_run:
            # Fallback to most recent run
            if self.agent_runs:
                target_run = self.agent_runs[0]
            else:
                return {"found": False, "message": "No agent runs recorded."}

        pdir = Path(target_run.project_folder)
        checklist_data: Optional[dict[str, Any]] = None
        checklist_file = pdir / "checklist.json"
        if checklist_file.exists():
            try:
                with open(checklist_file, "r", encoding="utf-8") as f:
                    checklist_data = json.load(f)
            except Exception:
                pass

        # Scan files in project
        files_found = []
        if pdir.exists():
            for p in pdir.rglob("*"):
                if not any(x in p.parts for x in [".venv", ".git", "__pycache__"]):
                    files_found.append(str(p.relative_to(pdir)))

        return {
            "found": True,
            "run_id": target_run.id,
            "title": target_run.title,
            "status": target_run.status,
            "project_folder": target_run.project_folder,
            "created_at": target_run.created_at,
            "started_at": target_run.started_at,
            "finished_at": target_run.finished_at,
            "total_steps": target_run.total_steps,
            "verified_steps": target_run.verified_steps,
            "error_summary": target_run.error_summary,
            "files_created": files_found[:30],
            "checklist": checklist_data,
            "messages": target_run.messages[-10:],
        }
