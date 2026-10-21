"""
PyDesktop JavaScript API Bridge for Zeno Desktop AI Assistant.
Exposes Python tools, safety verification, chat completion, and settings
to pywebview via js_api.
"""

from __future__ import annotations

import base64
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from dotenv import load_dotenv

import warnings

# Suppress verbose Google GenAI AFC recommendations and warnings
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
warnings.filterwarnings("ignore", message=".*AFC.*")
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.genai.models").setLevel(logging.ERROR)

from zeno.agent import SYSTEM_PROMPT, ZenoAgent
from zeno.chat_manager import generate_chat_topic, process_chat_retention
from zeno.memory import (
    clear_memory,
    format_memory_for_prompt,
    load_memory,
    save_memory,
    synthesize_memory_with_ai,
)
from zeno.permissions import (
    CATEGORIES,
    load_permissions,
    save_permissions,
    set_category_permission,
)
from zeno.safety_checker import verify_code_safety
from zeno.safety.approvals import (
    decide_approval,
    get_approval_status,
    list_pending_approvals,
)
from zeno.safety.database import (
    get_recent_action_logs,
    init_safety_database,
    recover_interrupted_jobs,
)
from zeno.safety.observer import (
    get_recent_dialogues,
    plan_task_with_observer,
)
from zeno.safety.worker import (
    get_worker_pool,
)
from zeno.settings import (
    CHATS_METADATA_PATH,
    DEFAULT_WORKSPACE_DIR,
    ENV_FILE_PATH,
    HOME_DIR,
    ORCHID_SYSTEM_PROMPT,
    PERMISSIONS_PATH,
    SCREENSHOTS_DIR,
    SESSIONS_DIR,
)
from zeno.tools.app_tools import open_app, open_url
from zeno.tools.clipboard_tools import read_clipboard, write_clipboard
from zeno.tools.document_tools import create_document
from zeno.tools.file_tools import (
    append_file,
    list_directory,
    read_file,
    search_files,
    write_file,
)
from zeno.tools.process_tools import get_network_status, list_running_processes
from zeno.tools.python_tools import run_python
from zeno.tools.screen_tools import capture_screen, list_screen_targets
from zeno.tools.system_tools import system_info
from zeno.tools.web_tools import web_search
from zeno.tools.workspace_tools import create_project_workspace, organize_documents
from zeno.tools.download_tools import (
    download_file as _download_file,
    open_in_explorer as _open_in_explorer,
    read_file_as_base64 as _read_file_as_base64,
)

# New Zeno Architecture Engine Modules
from zeno.engine.checklist import ChecklistEngine, StepStatus
from zeno.engine.errors import ErrorClassifier, RetryHandler, save_step_draft
from zeno.engine.jobs import JobSupervisor
from zeno.engine.storage import StorageManager
from zeno.engine.workspace import (
    ProjectWorkspace,
    generate_creative_folder_name,
    sanitize_folder_name,
)
from zeno.safety.rules import OrchidSecurityKernel
from zeno.tools.file_tools import get_active_project_dir, set_active_project_dir


from zeno.engine.api_handlers import ZenoEngineHandlers


class ZenoDesktopApi:
    """
    pywebview JavaScript API bridge exposing native system tools,
    file sandbox operations, screen capture, process telemetry, and
    conversational AI dispatch to the web UI.
    """

    # Global abort flag so the frontend can stop the agent loop between steps
    _agent_abort: bool = False
    _agent_abort_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        load_dotenv(dotenv_path=ENV_FILE_PATH)
        try:
            init_safety_database()
            recover_interrupted_jobs()
        except Exception as exc:
            logging.error("Failed to initialize safety DB / recovery: %s", exc)

        # Initialize Architecture Engines (Rule A, Rule C, Rule E)
        self.storage = StorageManager()
        self.job_supervisor = JobSupervisor.get_instance()
        self.engine_handlers = ZenoEngineHandlers(self.storage, self.job_supervisor)

    # -------------------------------------------------------------------------
    # Rule A: Assistant Threads & Cross-Area Read-Only Run Inspector
    # -------------------------------------------------------------------------
    def get_assistant_threads(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Return conversational Assistant chat threads (independent of agent runs)."""
        return self.engine_handlers.get_assistant_threads()

    def create_assistant_thread(self, payload: Optional[dict[str, Any]] = None, *args, **kwargs) -> dict[str, Any]:
        """Create a new conversational Assistant thread."""
        return self.engine_handlers.create_assistant_thread(payload)

    def delete_assistant_thread(self, payload: dict[str, Any], *args, **kwargs) -> dict[str, Any]:
        """Delete an Assistant thread."""
        return self.engine_handlers.delete_assistant_thread(payload)

    def inspect_agent_run(self, payload: dict[str, Any], *args, **kwargs) -> dict[str, Any]:
        """Rule A: Allow Assistant to inspect agent run state, checklist, files, and logs read-only."""
        return self.engine_handlers.inspect_agent_run(payload)

    # -------------------------------------------------------------------------
    # Rule B & C: Agent Workspace Runs, Creative Folders & Checklist Engine
    # -------------------------------------------------------------------------
    def get_agent_runs(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Return all agent runs in history and queue."""
        return self.engine_handlers.get_agent_runs()

    def _get_client(self, *args: Any, **kwargs: Any) -> Any:
        """Helper for client instantiation if requested."""
        return None

    def create_agent_run(self, payload: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        """
        Rule B: Create project folder with creative 2-4 word name,
        initialize .venv, generate checklist.json (Rule C), and enqueue run.
        """
        return self.engine_handlers.create_agent_run(payload, self._get_client)

    def rename_project_folder(self, payload: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Rule B: Rename project folder on disk and update run records."""
        return self.engine_handlers.rename_project_folder(payload)

    def get_run_checklist(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rule C: Return checklist.json as single source of truth."""
        return self.engine_handlers.get_run_checklist(payload)

    def execute_agent_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Rule C, D, E: Execute a step with Python verification gating,
        transient network backoff (SSL EOF), health checks, and screenshots.
        """
        return self.engine_handlers.execute_agent_step(payload, self._execute_agent_for_step)

    def revisit_agent_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rule C: Jump back to earlier step, re-verifying dependent steps only."""
        return self.engine_handlers.jump_back_step(payload)

    def abort_agent_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Rule E: Stop every job started by the run, killing child process tree."""
        return self.engine_handlers.abort_agent_run(payload)

    def list_project_files(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Rule G: Return real project directory tree."""
        return self.engine_handlers.list_project_files(payload or {})

    def _execute_agent_for_step(
        self,
        prompt: str,
        model: str,
        custom_key: str,
        history: list[dict[str, Any]],
        on_tool: Any,
    ) -> dict[str, Any]:
        agent = ZenoAgent(
            on_tool_used=on_tool,
            on_status_change=lambda status, in_t, out_t: None,
        )
        agent.active_model = model
        agent.auto_approve_safe = True
        agent.auto_switch_enabled = False

        for h in history[-8:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if content:
                agent.history.append({"role": "user" if role == "user" else "assistant", "content": content})

        reply, in_tokens, out_tokens = agent._execute_agent_loop(
            model_name=model,
            recent_history=agent.history[-10:],
            user_message=prompt,
            is_agentic_mode=True,
        )
        return {
            "reply": reply,
            "inputTokens": in_tokens,
            "outputTokens": out_tokens,
        }

    def abort_agent_task(self) -> dict[str, Any]:
        """Signal the running agent loop to stop after the current step completes."""
        with ZenoDesktopApi._agent_abort_lock:
            ZenoDesktopApi._agent_abort = True
        logging.info("Agent abort signal set by user.")
        return {"ok": True, "message": "Abort signal sent. Agent will stop after current step."}

    def _check_abort(self) -> bool:
        """Return True if the user has requested abort."""
        with ZenoDesktopApi._agent_abort_lock:
            return ZenoDesktopApi._agent_abort

    def _clear_abort(self) -> None:
        """Clear the abort flag at the start of a new task."""
        with ZenoDesktopApi._agent_abort_lock:
            ZenoDesktopApi._agent_abort = False

    # -------------------------------------------------------------------------
    # System and Diagnostics Tools
    # -------------------------------------------------------------------------
    def get_system_status(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Return real-time hardware telemetry and operating system specs."""
        try:
            return system_info()
        except Exception as exc:
            return {
                "os_name": os.name,
                "os_version": "Unknown",
                "python_version": "3.11+",
                "battery": "Unavailable",
                "cpu_percent": 0.0,
                "ram_used_gb": 0.0,
                "ram_total_gb": 0.0,
                "ram_percent": 0.0,
                "disk_free_gb": 0.0,
                "disk_total_gb": 0.0,
                "uptime": "Unknown",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(exc),
            }

    def list_running_processes(self, limit: int = 15) -> list[dict[str, Any]]:
        """Return list of top active processes ordered by memory usage."""
        try:
            return list_running_processes(limit=limit)
        except Exception as exc:
            return [{"name": "system", "pid": 1, "cpu_percent": 0.0, "memory_mb": 0.0, "error": str(exc)}]

    def get_network_status(self) -> dict[str, Any]:
        """Return network interface information and connectivity status."""
        try:
            return get_network_status()
        except Exception as exc:
            return {
                "hostname": "localhost",
                "local_ip": "127.0.0.1",
                "internet_connected": False,
                "network_io": {},
                "error": str(exc),
            }

    # -------------------------------------------------------------------------
    # Screen Capture Tools
    # -------------------------------------------------------------------------
    def list_screen_targets(self) -> list[dict[str, Any]]:
        """Return available screen monitors and window targets."""
        try:
            return list_screen_targets()
        except Exception as exc:
            return [
                {"id": "all", "name": "All Monitors Combined", "description": "Full desktop canvas"},
                {"id": "monitor_1", "name": "Primary Display", "description": "Main physical screen"},
            ]

    def capture_screen(self, target: str = "all", tab_name: str = "") -> dict[str, Any]:
        """
        Capture the screen, physical monitor, or window and return metadata
        with base64 image data URI for direct web preview.
        """
        try:
            filepath = capture_screen(target=target, tab_name=tab_name)
            p = Path(filepath)
            with open(filepath, "rb") as f:
                img_bytes = f.read()
            b64_str = base64.b64encode(img_bytes).decode("utf-8")
            size_kb = f"{round(len(img_bytes) / 1024)} KB"
            return {
                "file_path": str(p.resolve()),
                "name": p.name,
                "size": size_kb,
                "type": "image/png",
                "base64": f"data:image/png;base64,{b64_str}",
                "status": "success",
            }
        except Exception as exc:
            return {
                "error": str(exc),
                "status": "failed",
                "name": f"screenshot_{target}.png",
                "size": "0 KB",
                "type": "image/png",
                "base64": "",
            }

    # -------------------------------------------------------------------------
    # Clipboard Tools
    # -------------------------------------------------------------------------
    def read_clipboard(self) -> str:
        """Read content from system clipboard."""
        try:
            return read_clipboard()
        except Exception as exc:
            return f"Error reading clipboard: {exc}"

    def write_clipboard(self, text: str) -> str:
        """Write string content to system clipboard."""
        try:
            return write_clipboard(text)
        except Exception as exc:
            return f"Error writing to clipboard: {exc}"

    # -------------------------------------------------------------------------
    # Filesystem & Workspace Tools
    # -------------------------------------------------------------------------
    def list_directory(self, path: str = "Documents") -> list[dict[str, Any]]:
        """List files and folders within allowed directories."""
        try:
            return list_directory(path)
        except Exception as exc:
            return [{"error": str(exc), "name": path, "type": "error"}]

    def read_file(self, path: str) -> str:
        """Read file contents inside allowed sandbox directories."""
        try:
            return read_file(path)
        except Exception as exc:
            return f"Error reading file: {exc}"

    def write_file(self, path: str, content: str) -> str:
        """Write file contents inside allowed sandbox directories."""
        try:
            return write_file(path, content)
        except Exception as exc:
            return f"Error writing file: {exc}"

    def append_file(self, path: str, content: str) -> str:
        """Append text to file inside allowed sandbox directories."""
        try:
            return append_file(path, content)
        except Exception as exc:
            return f"Error appending file: {exc}"

    def search_files(self, pattern: str, dir_path: str = "Documents") -> list[str]:
        """Search files matching wildcard pattern inside allowed folders."""
        try:
            return search_files(pattern, dir_path)
        except Exception as exc:
            return [f"Search error: {exc}"]

    def create_document(
        self,
        title: str,
        content: str,
        file_type: str = "docx",
        folder: str = "Documents",
    ) -> str:
        """Create formatted document (.docx, .md, .txt) in allowed directory."""
        try:
            return create_document(title=title, content=content, file_type=file_type, folder=folder)
        except Exception as exc:
            return f"Document creation error: {exc}"

    def create_project_workspace(self, project_name: str, folder_type: str = "project") -> dict[str, Any]:
        """Initialize clean project workspace with structured subdirectories."""
        try:
            return create_project_workspace(project_name=project_name, folder_type=folder_type)
        except Exception as exc:
            return {"error": str(exc), "status": "failed"}

    def organize_documents(self, source_folder: str = "Documents") -> dict[str, Any]:
        """Sort and categorize loose documents into typed subdirectories."""
        try:
            return organize_documents(source_folder=source_folder)
        except Exception as exc:
            return {"error": str(exc), "status": "failed"}

    # -------------------------------------------------------------------------
    # App & Process Execution
    # -------------------------------------------------------------------------
    def open_url(self, url: str) -> str:
        """Open web URL in system default browser."""
        try:
            return open_url(url)
        except Exception as exc:
            return f"URL launch error: {exc}"

    def open_app(self, name: str) -> str:
        """Launch allowlisted desktop application."""
        try:
            return open_app(name)
        except Exception as exc:
            return f"Application launch error: {exc}"

    def run_python(self, code: str) -> dict[str, Any]:
        """Execute arbitrary Python snippet in isolated subprocess with safety guard."""
        # Safety verification thread
        is_safe, reason = verify_code_safety(code, auto_approve=True)
        if not is_safe:
            return {
                "stdout": "",
                "stderr": f"Blocked by AI Safety Guard: {reason}",
                "exit_code": 1,
                "timed_out": False,
                "is_safe": False,
            }

        result = run_python(code)
        result["is_safe"] = True
        return result

    def web_search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Retrieve web documentation and programming references."""
        try:
            return web_search(query=query, max_results=max_results)
        except Exception as exc:
            return [{
                "title": f"Search Query: {query}",
                "url": f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}",
                "snippet": f"Search error: {exc}",
            }]

    # -------------------------------------------------------------------------
    # Permissions and Settings Persistence
    # -------------------------------------------------------------------------
    def get_permissions(self) -> dict[str, bool]:
        """Load granted and denied permissions."""
        return load_permissions()

    def set_permission(self, category: str, allowed: bool) -> bool:
        """Update permission for specified category."""
        try:
            set_category_permission(category, allowed)
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Persistent Long-Term Memory (Claude / ChatGPT Logic)
    # -------------------------------------------------------------------------
    def get_memory(self) -> str:
        """Load persistent user memory file."""
        return load_memory()

    def save_memory(self, content: str) -> bool:
        """Save updated memory markdown content directly."""
        return save_memory(content)

    def clear_memory(self) -> bool:
        """Reset memory file to default template."""
        return clear_memory()

    def import_memory_ai(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Merge and synthesize imported notes/memories into existing memory.md
        using the selected AI model.
        """
        notes = payload.get("notes", "")
        model = payload.get("model", "gemini-3.5-flash-lite")
        custom_key = payload.get("customApiKey", "")
        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        target_key = custom_key.strip() if custom_key else os.getenv("GEMINI_API_KEY", "").strip()
        return synthesize_memory_with_ai(notes, target_key, model)

    def get_settings(self) -> dict[str, Any]:
        """Load stored application settings and configured API keys."""
        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        return {
            "defaultWorkspace": os.getenv("ZENO_WORKSPACE", str(DEFAULT_WORKSPACE_DIR)),
            "autoApproveSafe": os.getenv("ZENO_AUTO_APPROVE", "true").lower() == "true",
            "autoSwitch": os.getenv("ZENO_AUTO_SWITCH", "true").lower() == "true",
            "thinkingLevel": os.getenv("ZENO_THINKING_LEVEL", "Medium"),
            "defaultModel": os.getenv("ZENO_DEFAULT_MODEL", "gemini-3.5-flash-lite"),
            "keys": {
                "Gemini": os.getenv("GEMINI_API_KEY", ""),
                "Anthropic Claude": os.getenv("ANTHROPIC_API_KEY", ""),
                "OpenRouter": os.getenv("OPENROUTER_API_KEY", ""),
                "OpenAI": os.getenv("OPENAI_API_KEY", ""),
                "Groq": os.getenv("GROQ_API_KEY", ""),
            },
            "permissions": load_permissions(),
        }

    def save_settings(self, settings: dict[str, Any]) -> bool:
        """Persist updated API keys and configuration to .env and permissions.json."""
        try:
            # Update permissions if provided
            perms = settings.get("permissions")
            if isinstance(perms, dict):
                save_permissions(perms)

            # Update .env
            env_lines: list[str] = []
            existing_env: dict[str, str] = {}
            if ENV_FILE_PATH.exists():
                with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            k, v = stripped.split("=", 1)
                            existing_env[k.strip()] = v.strip()

            # Handle dynamic key slots or direct keys mapping
            slots = settings.get("apiKeySlots")
            if isinstance(slots, list):
                for slot in slots:
                    prov = slot.get("provider", "")
                    key = slot.get("key", "").strip()
                    if prov == "Gemini":
                        existing_env["GEMINI_API_KEY"] = key
                    elif prov == "Anthropic Claude":
                        existing_env["ANTHROPIC_API_KEY"] = key
                    elif prov == "OpenRouter":
                        existing_env["OPENROUTER_API_KEY"] = key
                    elif prov == "OpenAI":
                        existing_env["OPENAI_API_KEY"] = key
                    elif prov == "Groq":
                        existing_env["GROQ_API_KEY"] = key

            keys = settings.get("keys")
            if isinstance(keys, dict):
                if "Gemini" in keys:
                    existing_env["GEMINI_API_KEY"] = keys["Gemini"].strip()
                if "Anthropic Claude" in keys:
                    existing_env["ANTHROPIC_API_KEY"] = keys["Anthropic Claude"].strip()
                if "OpenRouter" in keys:
                    existing_env["OPENROUTER_API_KEY"] = keys["OpenRouter"].strip()
                if "OpenAI" in keys:
                    existing_env["OPENAI_API_KEY"] = keys["OpenAI"].strip()
                if "Groq" in keys:
                    existing_env["GROQ_API_KEY"] = keys["Groq"].strip()

            if "defaultWorkspace" in settings:
                existing_env["ZENO_WORKSPACE"] = str(settings["defaultWorkspace"])
            if "autoApproveSafe" in settings:
                existing_env["ZENO_AUTO_APPROVE"] = "true" if settings["autoApproveSafe"] else "false"
            if "autoSwitch" in settings:
                existing_env["ZENO_AUTO_SWITCH"] = "true" if settings["autoSwitch"] else "false"
            if "thinkingLevel" in settings:
                existing_env["ZENO_THINKING_LEVEL"] = str(settings["thinkingLevel"])
            if "activeModel" in settings and settings["activeModel"]:
                existing_env["ZENO_DEFAULT_MODEL"] = str(settings["activeModel"])

            for k, v in existing_env.items():
                env_lines.append(f"{k}={v}")

            with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(env_lines) + "\n")

            load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
            return True
        except Exception as exc:
            print(f"Error saving settings: {exc}")
            return False

    # -------------------------------------------------------------------------
    # Persistent Long-Term Memory (Claude / ChatGPT style)
    # -------------------------------------------------------------------------
    def get_memory(self) -> str:
        """Load persistent memory markdown."""
        return load_memory()

    def save_memory(self, content: str) -> bool:
        """Save persistent memory markdown."""
        return save_memory(content)

    def clear_memory(self) -> bool:
        """Reset persistent memory to default template."""
        return clear_memory()

    def import_memory_ai(self, payload: Any = None, model: str = "gemini-3.5-flash-lite") -> dict[str, Any]:
        """Synthesize and merge raw memory notes into structured markdown using AI."""
        if isinstance(payload, dict):
            notes = payload.get("notes") or payload.get("raw_text") or ""
            target_model = payload.get("model") or model or "gemini-3.5-flash-lite"
            custom_key = payload.get("customApiKey") or ""
        else:
            notes = str(payload or "")
            target_model = model or "gemini-3.5-flash-lite"
            custom_key = ""

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        api_key = custom_key.strip() if custom_key else os.getenv("GEMINI_API_KEY", "").strip()

        return synthesize_memory_with_ai(notes, api_key=api_key, model=target_model)

    # -------------------------------------------------------------------------
    # Chat Sessions Persistence
    # -------------------------------------------------------------------------
    def load_chats(self) -> list[dict[str, Any]]:
        """Load stored chat sessions from chats.json."""
        if CHATS_METADATA_PATH.exists():
            try:
                with open(CHATS_METADATA_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        retained, _ = process_chat_retention(data)
                        return retained
            except Exception:
                pass
        return []

    def save_chats(self, chats: list[dict[str, Any]]) -> bool:
        """Save chat sessions to chats.json."""
        try:
            with open(CHATS_METADATA_PATH, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=2)
            return True
        except Exception:
            return False

    def delete_chat(self, chat_id: str) -> bool:
        """Manually delete a specific chat session by ID."""
        try:
            chats = self.load_chats()
            updated = [c for c in chats if c.get("id") != chat_id]
            return self.save_chats(updated)
        except Exception as exc:
            print(f"Error deleting chat {chat_id}: {exc}")
            return False

    # -------------------------------------------------------------------------
    # Conversational AI Dispatch
    # -------------------------------------------------------------------------
    # Model catalog and fallback order for Gemini (as requested: cheapest -> second smartest -> smartest)
    GEMINI_MODELS_ORDER = [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    ]

    GEMINI_MODEL_CANDIDATES: dict[str, list[str]] = {
        "gemini-3.5-flash-lite": ["gemini-3.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash-8b", "gemini-1.5-flash"],
        "gemini-3.6-flash": ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
        "gemini-3.8-flash": ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
    }

    def chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute conversational AI turn using configured API keys and models.
        Supports text, attachments, images, and tools.
        Automatically handles 503 UNAVAILABLE / high demand by falling back
        across the 3 Gemini models (gemini-3.5-flash-lite, gemini-3.6-flash, gemini-3.8-flash).
        """
        message = payload.get("message", "")
        history = payload.get("history", [])
        requested_model = (payload.get("model", "") or "gemini-3.5-flash-lite").strip()
        thinking_level = payload.get("thinkingLevel", "Medium")
        custom_api_key = payload.get("customApiKey", "")
        mode = payload.get("mode", "chat")
        attachments = payload.get("attachments", [])
        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)

        # Automatic live web search & website inspection enrichment
        url_matches = re.findall(
            r'(?:https?://)?([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|io|ng|co|ai|app|dev|xyz|info)(?:/[^\s]*)?)',
            message,
            re.IGNORECASE,
        )
        if url_matches:
            target_site = url_matches[0]
            try:
                from zeno.tools.web_tools import fetch_webpage_content
                web_res = fetch_webpage_content(target_site)
                if web_res.get("ok"):
                    message += (
                        f"\n\n[Live Web Inspection for {web_res.get('url')}]:\n"
                        f"Page Title: {web_res.get('title')}\n"
                        f"Meta Description: {web_res.get('description')}\n"
                        f"Page Content:\n{web_res.get('content')}\n"
                        f"[End of Live Web Inspection. Use the verified information above to provide a complete, informative answer.]\n"
                    )
                elif web_res.get("fallback_search"):
                    message += f"\n\n[Web Search Results for {target_site}]:\n{web_res.get('fallback_search')}\n"
            except Exception as e:
                logger.warning("Automatic webpage inspection failed: %s", e)
        elif any(k in message.lower() for k in ["search the web", "search online", "latest info on", "duckduckgo", "google search"]):
            try:
                from zeno.tools.web_tools import web_search
                clean_q = re.sub(r"(?i)^(search the web for|search online for|search for|google|browse)\s*", "", message).strip()
                s_results = web_search(clean_q or message, max_results=4)
                if s_results:
                    snippets = "\n".join(f"- {r.get('title')} ({r.get('url')}): {r.get('snippet')}" for r in s_results)
                    message += f"\n\n[Live Web Search Grounding for '{clean_q}']:\n{snippets}\n"
            except Exception as e:
                logger.warning("Automatic web search failed: %s", e)

        # 1. Non-Gemini models routing (Claude, OpenRouter, OpenAI, Groq)
        if "claude" in requested_model.lower():
            claude_key = (custom_api_key if custom_api_key else os.getenv("ANTHROPIC_API_KEY", "")).strip()
            if not claude_key:
                return {"error": "API_KEY_MISSING", "reply": "Anthropic Claude API key missing. Please configure it in Settings."}
            return self._call_anthropic_chat(claude_key, requested_model, history, message, attachments)

        elif "openrouter" in requested_model.lower():
            openrouter_key = (custom_api_key if custom_api_key else os.getenv("OPENROUTER_API_KEY", "")).strip()
            if not openrouter_key:
                return {"error": "API_KEY_MISSING", "reply": "OpenRouter API key missing. Please configure it in Settings."}
            return self._call_openai_compat_chat("https://openrouter.ai/api/v1/chat/completions", openrouter_key, requested_model, history, message)

        elif any(requested_model.lower().startswith(x) for x in ["gpt", "o3"]):
            openai_key = (custom_api_key if custom_api_key else os.getenv("OPENAI_API_KEY", "")).strip()
            if not openai_key:
                return {"error": "API_KEY_MISSING", "reply": "OpenAI API key missing. Please configure it in Settings."}
            return self._call_openai_compat_chat("https://api.openai.com/v1/chat/completions", openai_key, requested_model, history, message)

        elif any(requested_model.lower().startswith(x) for x in ["llama", "mixtral"]):
            groq_key = (custom_api_key if custom_api_key else os.getenv("GROQ_API_KEY", "")).strip()
            if not groq_key:
                return {"error": "API_KEY_MISSING", "reply": "Groq API key missing. Please configure it in Settings."}
            return self._call_openai_compat_chat("https://api.groq.com/openai/v1/chat/completions", groq_key, requested_model, history, message)

        # 2. Gemini models
        target_key = custom_api_key.strip() if custom_api_key else os.getenv("GEMINI_API_KEY", "").strip()
        if not target_key or target_key == "your_key_here":
            return {
                "error": "API_KEY_MISSING",
                "reply": "API key missing. Open Settings and add your API key in Key Slot 1, 2, or 3 to enable models.",
            }

        is_agentic = mode == "agentic"
        memory_block = format_memory_for_prompt()
        system_instruction = (
            f"{ORCHID_SYSTEM_PROMPT}{memory_block}"
            f"{' You are in Agentic Worker mode. Break down tasks into numbered action steps and execute them using available tools. You are supervised by Zeno Orchid.' if is_agentic else ' If asked for a complex multi-step agentic task on the system or files, present a clear step-by-step plan that can be delegated to the agentic worker.'}"
        )

        # Order of Gemini models to try: user's selected model first!
        models_to_try = [requested_model]
        for m in self.GEMINI_MODELS_ORDER:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = ""
        switched_due_to_demand = False

        for current_primary in models_to_try:
            candidates = self.GEMINI_MODEL_CANDIDATES.get(current_primary, [current_primary])
            for candidate in candidates:
                res = self._execute_gemini_turn(target_key, candidate, system_instruction, history, message, attachments, thinking_level)
                if not res.get("error"):
                    # Success!
                    res["modelUsed"] = current_primary
                    return res

                # Check error type
                err_msg = str(res.get("error", "")).lower()
                last_error = res.get("error", "")
                is_retryable = any(
                    x in err_msg for x in [
                        "503", "unavailable", "high demand", "service unavailable",
                        "429", "quota", "exhausted", "rate limit", "overloaded",
                        "404", "not found"
                    ]
                )
                if is_retryable:
                    switched_due_to_demand = True
                    continue
                else:
                    # Non-retryable error (e.g. invalid key format)
                    return res

        # If all candidates of all models failed with 503 / high demand
        if switched_due_to_demand:
            return {
                "error": "SERVICE_UNAVAILABLE",
                "reply": "All Gemini models are currently experiencing high demand on Google's servers (503 UNAVAILABLE). Please try again in a few moments.",
                "inputTokens": 0,
                "outputTokens": 0,
                "modelUsed": requested_model,
            }

        return {
            "error": last_error,
            "reply": f"Error communicating with AI model: {last_error}",
            "inputTokens": 0,
            "outputTokens": 0,
            "modelUsed": requested_model,
        }

    def _execute_gemini_turn(
        self,
        api_key: str,
        model: str,
        system_instruction: str,
        history: list[dict[str, Any]],
        message: str,
        attachments: list[dict[str, Any]],
        thinking_level: str = "Medium",
    ) -> dict[str, Any]:
        """Attempt a turn via google-genai SDK, with automatic REST fallback."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            contents: list[Any] = []
            if isinstance(history, list):
                compacted_anchor = None
                recent_items = []
                for h in history:
                    content_str = h.get("content", "")
                    if "Compacted Conversation Memory" in content_str or "[CONVERSATION COMPACTED CONTEXT" in content_str:
                        compacted_anchor = h
                    else:
                        recent_items.append(h)

                effective_history = ([compacted_anchor] if compacted_anchor else []) + recent_items[-8:]
                for h in effective_history:
                    role = "user" if h.get("role") == "user" else "model"
                    content_str = h.get("content", "")
                    if content_str:
                        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=content_str)]))

            user_parts: list[Any] = []
            if isinstance(attachments, list):
                for att in attachments:
                    att_type = att.get("type", "")
                    att_base64 = att.get("base64", "")
                    att_content = att.get("content", "")
                    att_name = att.get("name", "file")

                    if att_type.startswith("image/") and att_base64:
                        raw_base64 = re.sub(r"^data:image/[a-zA-Z]+;base64,", "", att_base64)
                        user_parts.append(
                            types.Part.from_bytes(
                                data=base64.b64decode(raw_base64),
                                mime_type=att_type,
                            )
                        )
                    elif att_content:
                        user_parts.append(
                            types.Part.from_text(
                                text=f"[Attached File: {att_name}]\n```\n{att_content}\n```"
                            )
                        )

            if message:
                user_parts.append(types.Part.from_text(text=message))

            contents.append(types.Content(role="user", parts=user_parts))

            # Try with Google Search grounding tool, falling back to standard config if model/key rejects it
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=2048,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                )
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            except Exception:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=2048,
                )
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )

            reply_text = ""
            if getattr(response, "text", None):
                reply_text = response.text
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    extracted: list[str] = []
                    for p in candidate.content.parts:
                        t = getattr(p, "text", None)
                        if t:
                            extracted.append(t)
                        elif hasattr(p, "thought") and p.thought:
                            extracted.append(p.thought)
                    reply_text = "".join(extracted)

            if not reply_text and hasattr(response, "candidates") and response.candidates:
                # Check for grounding metadata or citations
                gm = getattr(response.candidates[0], "grounding_metadata", None)
                if gm and getattr(gm, "grounding_chunks", None):
                    chunks = [c.web.title for c in gm.grounding_chunks if hasattr(c, "web") and getattr(c.web, "title", None)]
                    if chunks:
                        reply_text = f"Found relevant search sources: {', '.join(chunks)}"

            if not reply_text:
                reply_text = "I received and analyzed your request. Please let me know how you would like me to assist you with this."

            usage = getattr(response, "usage_metadata", None)
            in_tokens = getattr(usage, "prompt_token_count", 38) or 38
            out_tokens = getattr(usage, "candidates_token_count", 88) or 88

            return {
                "reply": reply_text,
                "inputTokens": in_tokens,
                "outputTokens": out_tokens,
                "modelUsed": model,
            }
        except Exception as exc:
            return self._fallback_rest_chat(api_key, model, system_instruction, history, message, attachments)

    def _fallback_rest_chat(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        history: list[dict[str, Any]],
        message: str,
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """REST fallback for Gemini endpoints with HTTP error extraction."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

            contents = []
            compacted_anchor = None
            recent_items = []
            for h in history:
                content_str = h.get("content", "")
                if "Compacted Conversation Memory" in content_str or "[CONVERSATION COMPACTED CONTEXT" in content_str:
                    compacted_anchor = h
                else:
                    recent_items.append(h)

            effective_history = ([compacted_anchor] if compacted_anchor else []) + recent_items[-8:]
            for h in effective_history:
                contents.append({
                    "role": "user" if h.get("role") == "user" else "model",
                    "parts": [{"text": h.get("content", "")}],
                })

            user_parts: list[dict[str, Any]] = []
            for att in attachments:
                if att.get("type", "").startswith("image/") and att.get("base64"):
                    raw_b64 = re.sub(r"^data:image/[a-zA-Z]+;base64,", "", att["base64"])
                    user_parts.append({
                        "inline_data": {
                            "mime_type": att.get("type", "image/png"),
                            "data": raw_b64,
                        }
                    })
                elif att.get("content"):
                    user_parts.append({
                        "text": f"[Attached File: {att.get('name')}]\n```\n{att.get('content')}\n```"
                    })

            user_parts.append({"text": message})
            contents.append({"role": "user", "parts": user_parts})

            body = json.dumps({
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"maxOutputTokens": 2048},
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    reply = "".join(p.get("text", "") for p in parts)
                    usage = data.get("usageMetadata", {})
                    return {
                        "reply": reply or "Task completed.",
                        "inputTokens": usage.get("promptTokenCount", 40),
                        "outputTokens": usage.get("candidatesTokenCount", 90),
                        "modelUsed": model,
                    }

            return {"reply": "Task completed.", "inputTokens": 30, "outputTokens": 60, "modelUsed": model}
        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                parsed = json.loads(err_body)
                msg = parsed.get("error", {}).get("message", str(http_err))
                code = parsed.get("error", {}).get("code", http_err.code)
                return {"error": f"HTTP {code}: {msg}"}
            except Exception:
                return {"error": str(http_err)}
        except Exception as exc:
            return {"error": str(exc)}

    def _call_openai_compat_chat(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        history: list[dict[str, Any]],
        message: str,
    ) -> dict[str, Any]:
        try:
            messages = []
            for h in history[-8:]:
                role = "user" if h.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": h.get("content", "")})
            messages.append({"role": "user", "content": message})

            body = json.dumps({
                "model": model,
                "messages": messages,
            }).encode("utf-8")

            req = urllib.request.Request(
                endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                reply = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                return {
                    "reply": reply or "Task completed.",
                    "inputTokens": usage.get("prompt_tokens", 40),
                    "outputTokens": usage.get("completion_tokens", 80),
                    "modelUsed": model,
                }
        except Exception as exc:
            return {
                "error": str(exc),
                "reply": f"Error communicating with {model}: {exc}",
                "inputTokens": 0,
                "outputTokens": 0,
                "modelUsed": model,
            }

    def _call_anthropic_chat(
        self,
        api_key: str,
        model: str,
        history: list[dict[str, Any]],
        message: str,
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            messages = []
            for h in history[-8:]:
                role = "user" if h.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": h.get("content", "")})
            messages.append({"role": "user", "content": message})

            body = json.dumps({
                "model": model,
                "messages": messages,
                "max_tokens": 2048,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("content", [{}])
                reply = "".join(c.get("text", "") for c in content if c.get("type") == "text")
                usage = data.get("usage", {})
                return {
                    "reply": reply or "Task completed.",
                    "inputTokens": usage.get("input_tokens", 40),
                    "outputTokens": usage.get("output_tokens", 80),
                    "modelUsed": model,
                }
        except Exception as exc:
            return {
                "error": str(exc),
                "reply": f"Error communicating with Claude ({model}): {exc}",
                "inputTokens": 0,
                "outputTokens": 0,
                "modelUsed": model,
            }

    # -------------------------------------------------------------------------
    # Context Compaction & Token Optimization
    # -------------------------------------------------------------------------
    def compact_conversation(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Intelligently compact and summarize older chat history into high-density
        structured contextual memory to save tokens while keeping the AI fully informed.
        """
        messages = payload.get("messages", [])
        model = payload.get("model", "gemini-3.5-flash-lite")
        custom_api_key = payload.get("customApiKey", "")

        if not messages or len(messages) <= 2:
            return {"error": "Not enough messages to compact", "summary": "", "compactedCount": 0}

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        target_key = custom_api_key.strip() if custom_api_key else os.getenv("GEMINI_API_KEY", "").strip()

        # Build conversation text transcript to compact
        transcript_lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if content and not ("Compacted Conversation Memory" in content or "[CONVERSATION COMPACTED CONTEXT" in content):
                speaker = "User" if role == "user" else "Zeno Assistant" if role == "assistant" else "Tool Action"
                transcript_lines.append(f"{speaker}: {content}")

        transcript_text = "\n\n".join(transcript_lines)
        if len(transcript_text) < 50:
            return {"error": "Conversation is already very short", "summary": "", "compactedCount": 0}

        prompt = (
            "You are an expert context compression engine for an AI assistant. "
            "Compress the provided conversation history into a concise, high-density structured memory that preserves ALL critical technical information, decisions, constraints, and current state so that the AI remains 100% capable, intelligent, and context-aware in future turns.\n\n"
            "CRITICAL RULES:\n"
            "1. Do NOT make vague general statements like 'the user asked questions'.\n"
            "2. Extract and preserve: Primary goals & requirements, exact technical decisions/architecture, files created/edited/read, tools used, specific code/variable names, and user preferences.\n"
            "3. State the exact current working status and next steps.\n\n"
            "Output format strictly as markdown:\n"
            "### 🧠 Compacted Conversation Memory\n"
            "- **Primary Objective**: <clear statement of what was being built or discussed>\n"
            "- **Key Decisions & Constraints**: <bulleted list of specific architectural choices, user instructions, preferences>\n"
            "- **Files, Code & Artifacts**: <specific file paths modified/created, tools invoked, key parameters>\n"
            "- **Active State & Next Actions**: <where the conversation left off and what is pending>\n\n"
            f"--- CONVERSATION TO COMPRESS ---\n{transcript_text}"
        )

        if not target_key or target_key == "your_key_here":
            summary = self._fallback_local_compaction(transcript_lines)
            return {
                "summary": summary,
                "compactedCount": len(messages),
                "savedTokens": max(0, int(len(transcript_text) / 4) - int(len(summary) / 4)),
            }

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=target_key)
            candidates = self.GEMINI_MODEL_CANDIDATES.get(model, [model])
            response = None
            for c_model in candidates:
                try:
                    response = client.models.generate_content(
                        model=c_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=1024,
                            temperature=0.2,
                        ),
                    )
                    break
                except Exception:
                    continue

            if response is None:
                raise RuntimeError("All candidate models failed for compaction")

            summary = response.text or "### 🧠 Compacted Conversation Memory\n- Core conversation context preserved."
            estimated_saved_tokens = max(0, int(len(transcript_text) / 4) - int(len(summary) / 4))
            return {
                "summary": summary,
                "compactedCount": len(messages),
                "savedTokens": estimated_saved_tokens,
            }
        except Exception as exc:
            # Fallback local deterministic distillation if API fails
            summary = self._fallback_local_compaction(transcript_lines)
            return {
                "summary": summary,
                "compactedCount": len(messages),
                "savedTokens": max(0, int(len(transcript_text) / 4) - int(len(summary) / 4)),
                "warning": f"Used local summarizer: {exc}",
            }

    def _fallback_local_compaction(self, lines: list[str]) -> str:
        """Deterministic fallback compaction when network or API is unreachable."""
        files_mentioned = set()
        user_requests = []
        for line in lines:
            if line.startswith("User:"):
                user_requests.append(line.replace("User:", "").strip()[:80])
            for word in line.split():
                if "." in word and any(word.endswith(ext) for ext in [".py", ".ts", ".tsx", ".js", ".css", ".json", ".md", ".html", ".txt"]):
                    clean_w = word.strip("`'\",:;()")
                    if len(clean_w) > 3:
                        files_mentioned.add(clean_w)

        summary_parts = [
            "### 🧠 Compacted Conversation Memory",
            f"- **Primary Objective**: {'; '.join(user_requests[:3]) if user_requests else 'Technical assistance and development'}",
            f"- **Files & State**: {', '.join(sorted(files_mentioned)[:8]) if files_mentioned else 'Workspace code files'}",
            "- **Context Note**: Historical turns summarized to reduce token overhead while retaining active milestone context and instructions.",
        ]
        return "\n".join(summary_parts)

    def create_agent_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Zeno Orchid generates a dynamic complexity-graded plan.
        Always prepends Step 0: create project subfolder.
        Returns sessionId, sessionWorkspace, and projectFolder.
        """
        task = payload.get("task") or payload.get("message", "")
        model = payload.get("model", "gemini-3.5-flash-lite")
        custom_key = payload.get("customApiKey", "")
        session_id = payload.get("sessionId", "")

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        api_key = custom_key.strip() if custom_key else os.getenv("GEMINI_API_KEY", "").strip()

        # Create isolated session workspace
        import uuid, re as _re
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:8]}"
        session_dir = SESSIONS_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        # Derive project folder name from task (slugified)
        slug = _re.sub(r"[^a-zA-Z0-9]+", "_", task[:32].strip().lower()).strip("_") or "project"
        project_folder = session_dir / slug
        project_folder.mkdir(parents=True, exist_ok=True)

        step0 = (
            f"Zeno Bud: Create project folder '{slug}/' inside the session workspace "
            f"({str(session_dir)}) and confirm it exists. ALL subsequent files for this "
            f"task MUST be written inside {str(project_folder)} and nowhere else."
        )

        try:
            plan = plan_task_with_observer(
                task_description=task,
                api_key=api_key,
                model=model,
            )
            steps = plan.get("steps", [])
            # Prepend the mandatory subfolder step
            plan["steps"] = [step0] + steps
            plan["sessionId"] = session_id
            plan["sessionWorkspace"] = str(session_dir)
            plan["projectFolder"] = str(project_folder)
            return plan
        except Exception as exc:
            logging.error("Plan generation error: %s", exc)
            from zeno.safety.observer import _build_default_plan
            default_steps = _build_default_plan(task)
            return {
                "title": f"Execute: {task[:40]}",
                "steps": [step0] + default_steps,
                "safety_summary": "Zeno Orchid formulated an execution blueprint.",
                "sessionId": session_id,
                "sessionWorkspace": str(session_dir),
                "projectFolder": str(project_folder),
            }

    def run_agent_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute one agentic step using ZenoAgent with real tool calling.
        - Max 2 retries on retryable errors (SSL, 503, 429) with 10s / 20s waits.
        - After 2 retries, tries next model. After all models, stops and sets canResume=True.
        - Returns live_logs list so UI can display tool calls and retry notices.
        - Checks abort signal before every retry/model switch.
        - Includes canResume flag for when user needs to decide to continue or not.
        """
        message = payload.get("message", "")
        model = payload.get("model", "gemini-3.5-flash-lite")
        history = payload.get("history", [])
        custom_api_key = payload.get("customApiKey", "")
        current_step = payload.get("currentStep", "")
        plan_title = payload.get("planTitle", "")
        step_index = payload.get("stepIndex", None)
        total_steps = payload.get("totalSteps", None)
        session_workspace = payload.get("sessionWorkspace", str(DEFAULT_WORKSPACE_DIR))
        project_folder = payload.get("projectFolder", session_workspace)
        revisit = payload.get("revisit", False)  # True = re-run without advancing

        if not message and not current_step:
            return {
                "error": "NO_MESSAGE",
                "reply": "No task was specified.",
                "toolActions": [],
                "live_logs": [],
                "inputTokens": 0,
                "outputTokens": 0,
                "modelUsed": model,
            }

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        target_key = (
            custom_api_key.strip() if custom_api_key
            else os.getenv("GEMINI_API_KEY", "").strip()
        )

        if not target_key or target_key == "your_key_here":
            return {
                "error": "API_KEY_MISSING",
                "reply": "API key missing. Open Settings and add your API key.",
                "toolActions": [],
                "live_logs": [{"type": "error", "text": "API key missing"}],
                "inputTokens": 0,
                "outputTokens": 0,
                "modelUsed": model,
            }

        # Clear any stale abort from a previous task start
        if step_index == 0:
            self._clear_abort()

        # Build task prompt with project folder enforcement
        if current_step:
            step_header = f"Step {step_index + 1} of {total_steps}: " if step_index is not None and total_steps else ""
            revisit_note = " NOTE: This is a REVISION run — fix any mistakes from the previous attempt at this step." if revisit else ""
            task_prompt = (
                f"Overall Project: {plan_title or message}\n"
                f"Project Folder (ALL files MUST go here): {project_folder}\n"
                f"Session Workspace: {session_workspace}\n"
                f"Active Directive: {step_header}{current_step}{revisit_note}\n\n"
                f"You are Zeno Bud, supervised by Zeno Orchid.\n"
                f"EXECUTION REQUIREMENTS:\n"
                f"1. ALL files MUST be saved inside: {project_folder}\n"
                f"2. Use write_file, run_python, shell_run tools to do actual work.\n"
                f"3. Write complete, production-ready code — NO placeholders or ellipsis.\n"
                f"4. For shell commands: use 'python -m venv .venv', 'pip install ...', etc. as needed.\n"
                f"5. For servers: start them, wait briefly, screenshot, then terminate the process.\n"
                f"6. Verification: run tests, check outputs, confirm files exist before summarizing.\n"
                f"7. Once done, provide a concise summary of exactly what was accomplished."
            )
        else:
            task_prompt = (
                f"{message}\n\n"
                f"Project Folder (ALL files MUST go here): {project_folder}\n"
                f"You are Zeno Bud. Use tools to actively complete this task."
            )

        tool_actions: list[str] = []
        live_logs: list[dict[str, Any]] = []
        status_info: dict[str, Any] = {"text": "Running", "in_tokens": 0, "out_tokens": 0}

        def on_tool_used(line: str) -> None:
            tool_actions.append(line)
            live_logs.append({"type": "tool", "text": line, "ts": datetime.now().strftime("%H:%M:%S")})

        def on_status_change(status: str, in_tok: int, out_tok: int) -> None:
            status_info["text"] = status
            status_info["in_tokens"] = in_tok
            status_info["out_tokens"] = out_tok

        def on_progress_update(current: str, next_step: str) -> None:
            pass

        # SSL / network error detection helper
        RETRYABLE_SIGNATURES = [
            "ssl", "eof", "connection", "wsarecv", "503", "429",
            "unavailable", "rate limit", "quota", "exhausted",
            "high demand", "overloaded", "timeout", "timed out",
            "network", "socket", "broken pipe", "reset by peer",
        ]

        def is_retryable(err: str) -> bool:
            el = err.lower()
            return any(x in el for x in RETRYABLE_SIGNATURES)

        # Build models-to-try list
        all_models_to_try = [model]
        for m in self.GEMINI_MODELS_ORDER:
            if m not in all_models_to_try:
                all_models_to_try.append(m)

        MAX_RETRIES_PER_MODEL = 2
        retry_waits = [10, 20]  # seconds
        last_error = ""
        last_reply = ""

        for model_idx, model_candidate in enumerate(all_models_to_try):
            # Check abort before trying each model
            if self._check_abort():
                live_logs.append({"type": "abort", "text": "Agent stopped by user.", "ts": datetime.now().strftime("%H:%M:%S")})
                return {
                    "error": "ABORTED",
                    "reply": "Agent was stopped by the user.",
                    "toolActions": tool_actions,
                    "live_logs": live_logs,
                    "inputTokens": status_info["in_tokens"],
                    "outputTokens": status_info["out_tokens"],
                    "modelUsed": model_candidate,
                    "canResume": False,
                    "aborted": True,
                }

            if model_idx > 0:
                live_logs.append({
                    "type": "model_switch",
                    "text": f"Zeno Orchid: Switching to model {model_candidate} after exhausting {all_models_to_try[model_idx-1]}.",
                    "ts": datetime.now().strftime("%H:%M:%S"),
                })
                logging.info("Orchid model switch -> %s", model_candidate)

            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                # Check abort before each attempt
                if self._check_abort():
                    live_logs.append({"type": "abort", "text": "Agent stopped by user.", "ts": datetime.now().strftime("%H:%M:%S")})
                    return {
                        "error": "ABORTED",
                        "reply": "Agent was stopped by the user.",
                        "toolActions": tool_actions,
                        "live_logs": live_logs,
                        "inputTokens": status_info["in_tokens"],
                        "outputTokens": status_info["out_tokens"],
                        "modelUsed": model_candidate,
                        "canResume": False,
                        "aborted": True,
                    }

                if attempt > 0:
                    wait_secs = retry_waits[min(attempt - 1, len(retry_waits) - 1)]
                    live_logs.append({
                        "type": "retry",
                        "text": f"Zeno Orchid: Retry {attempt}/{MAX_RETRIES_PER_MODEL} on {model_candidate} — waiting {wait_secs}s...",
                        "wait_secs": wait_secs,
                        "ts": datetime.now().strftime("%H:%M:%S"),
                    })
                    logging.info("Orchid retry %d/%d on %s — sleeping %ds", attempt, MAX_RETRIES_PER_MODEL, model_candidate, wait_secs)
                    time.sleep(wait_secs)

                    # Check abort again after sleep
                    if self._check_abort():
                        live_logs.append({"type": "abort", "text": "Agent stopped by user.", "ts": datetime.now().strftime("%H:%M:%S")})
                        return {
                            "error": "ABORTED",
                            "reply": "Agent was stopped by the user.",
                            "toolActions": tool_actions,
                            "live_logs": live_logs,
                            "inputTokens": status_info["in_tokens"],
                            "outputTokens": status_info["out_tokens"],
                            "modelUsed": model_candidate,
                            "canResume": False,
                            "aborted": True,
                        }

                agent = ZenoAgent(
                    on_tool_used=on_tool_used,
                    on_status_change=on_status_change,
                    on_progress_update=on_progress_update,
                )
                agent.active_model = model_candidate
                agent.auto_approve_safe = True
                agent.auto_switch_enabled = False

                # Seed history
                if isinstance(history, list):
                    compacted_anchor = None
                    recent_items = []
                    for h in history:
                        content_str = h.get("content", "")
                        if "Compacted Conversation Memory" in content_str:
                            compacted_anchor = h
                        else:
                            recent_items.append(h)
                    effective_history = ([compacted_anchor] if compacted_anchor else []) + recent_items[-6:]
                    for h in effective_history:
                        role = h.get("role", "user")
                        content = h.get("content", "")
                        if content:
                            agent.history.append({
                                "role": "user" if role == "user" else "assistant",
                                "content": content,
                            })

                try:
                    reply = agent.run_user_message(task_prompt, is_agentic_mode=True)
                    last_reply = reply

                    # Check if reply itself is an error message
                    is_error_reply = any(x in reply.lower() for x in [
                        "error communicating", "api_key_missing", "ssl", "eof",
                        "503", "429", "service unavailable", "rate limit", "quota",
                        "connection", "wsarecv", "timeout",
                    ])
                    if is_error_reply and attempt < MAX_RETRIES_PER_MODEL:
                        last_error = reply
                        live_logs.append({"type": "error", "text": f"Step error (will retry): {reply[:120]}", "ts": datetime.now().strftime("%H:%M:%S")})
                        continue  # retry

                    # Collect screenshots
                    captured_screenshots: list[dict[str, Any]] = []
                    for action_text in tool_actions:
                        if "screenshots" in action_text or ".png" in action_text:
                            m_match = re.search(r"screenshots[/\\\\]([^\s\)\"',]+\.png)", action_text)
                            if m_match:
                                img_name = m_match.group(1)
                                img_path = SCREENSHOTS_DIR / img_name
                                if img_path.exists():
                                    try:
                                        with open(img_path, "rb") as f:
                                            b64 = base64.b64encode(f.read()).decode("utf-8")
                                        captured_screenshots.append({
                                            "name": img_name,
                                            "path": str(img_path.resolve()),
                                            "base64": f"data:image/png;base64,{b64}",
                                        })
                                    except Exception:
                                        pass

                    live_logs.append({"type": "done", "text": f"Step complete on {model_candidate}", "ts": datetime.now().strftime("%H:%M:%S")})

                    return {
                        "reply": reply,
                        "inputTokens": status_info["in_tokens"],
                        "outputTokens": status_info["out_tokens"],
                        "modelUsed": model_candidate,
                        "toolActions": tool_actions,
                        "live_logs": live_logs,
                        "screenshots": captured_screenshots,
                        "canResume": False,
                    }

                except Exception as exc:
                    last_error = str(exc)
                    live_logs.append({
                        "type": "error",
                        "text": f"Exception on {model_candidate} attempt {attempt+1}: {last_error[:200]}",
                        "ts": datetime.now().strftime("%H:%M:%S"),
                    })
                    if is_retryable(last_error) and attempt < MAX_RETRIES_PER_MODEL:
                        continue  # retry
                    break  # non-retryable or retries exhausted — try next model

        # All models and retries exhausted — user must decide
        live_logs.append({
            "type": "exhausted",
            "text": f"Zeno Orchid: All retry attempts and model fallbacks exhausted. Last error: {last_error[:200]}",
            "ts": datetime.now().strftime("%H:%M:%S"),
        })
        return {
            "error": last_error or "All models and retries exhausted.",
            "reply": (
                f"Zeno Orchid has exhausted all retry attempts and model fallbacks. "
                f"Last error: {last_error or 'Unknown error'}. "
                f"Type 'continue' to retry this step, or 'skip' to move to the next step."
            ),
            "inputTokens": status_info["in_tokens"],
            "outputTokens": status_info["out_tokens"],
            "modelUsed": model,
            "toolActions": tool_actions,
            "live_logs": live_logs,
            "canResume": True,
        }

    def verify_step_completion(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Ask Zeno Orchid (via AI) to verify a step was actually completed.
        Checks for: file existence, test output, server response, etc.
        Returns {verified: bool, reason: str, checks: list}.
        """
        step_text = payload.get("step_text", "")
        step_output = payload.get("step_output", "")
        project_folder = payload.get("project_folder", "")
        custom_key = payload.get("customApiKey", "")

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        api_key = custom_key.strip() if custom_key else os.getenv("GEMINI_API_KEY", "").strip()

        # List files in project folder for context
        files_summary = ""
        if project_folder:
            try:
                pf = Path(project_folder)
                if pf.exists():
                    file_list = [str(p.relative_to(pf)) for p in sorted(pf.rglob("*")) if p.is_file()]
                    files_summary = "Files present: " + ", ".join(file_list[:20]) if file_list else "No files found in project folder."
            except Exception:
                pass

        if not api_key or api_key == "your_key_here":
            # Heuristic check without AI
            has_output = len(step_output.strip()) > 50
            no_obvious_error = not any(x in step_output.lower() for x in ["traceback", "error:", "exception:", "failed"])
            verified = has_output and no_obvious_error
            return {
                "verified": verified,
                "reason": "Heuristic check (no API key): output present and no traceback detected.",
                "checks": ["output_present", "no_traceback"],
            }

        verification_prompt = (
            f"You are Zeno Orchid, the safety and quality guard. "
            f"Determine whether the following task step was successfully completed based on the agent output and project state.\n\n"
            f"Step directive: {step_text}\n\n"
            f"Agent output:\n{step_output[:3000]}\n\n"
            f"{files_summary}\n\n"
            f"Answer ONLY with a JSON object like: {{\"verified\": true, \"reason\": \"...\", \"checks\": [\"...\"]}}\n"
            f"Set verified=true only if the step is genuinely complete with no critical errors. "
            f"Set verified=false if there are exceptions, missing files, or incomplete work."
        )

        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=verification_prompt,
                config=types.GenerateContentConfig(max_output_tokens=512, temperature=0.1),
            )
            raw = (response.text or "").strip()
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "verified": bool(result.get("verified", False)),
                    "reason": result.get("reason", ""),
                    "checks": result.get("checks", []),
                }
        except Exception as exc:
            logging.warning("Step verification AI call failed: %s", exc)

        # Fallback heuristic
        has_output = len(step_output.strip()) > 50
        no_obvious_error = not any(x in step_output.lower() for x in ["traceback", "error:", "exception:", "failed", "ssl:"])
        return {
            "verified": has_output and no_obvious_error,
            "reason": "Heuristic fallback: output present and no error keywords detected.",
            "checks": ["output_length", "no_error_keywords"],
        }

    def run_agent_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Companion chat for the agent workspace — answers questions about what
        Zeno Bud is building without interfering with the agent loop.
        Always uses the cheapest model (gemini-2.0-flash-lite).
        """
        message = payload.get("message", "")
        agent_context = payload.get("agentContext", "")
        history = payload.get("history", [])
        custom_key = payload.get("customApiKey", "")

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
        api_key = custom_key.strip() if custom_key else os.getenv("GEMINI_API_KEY", "").strip()

        if not api_key or api_key == "your_key_here":
            return {"error": "API_KEY_MISSING", "reply": "API key missing."}

        system_prompt = (
            f"{ORCHID_SYSTEM_PROMPT}\n\n"
            f"You are the Zeno Agent Companion. You answer questions about the work Zeno Bud is doing. "
            f"Be helpful, concise, and knowledgeable about the project context below.\n\n"
            f"AGENT CONTEXT:\n{agent_context}\n"
            if agent_context else
            f"{ORCHID_SYSTEM_PROMPT}\nYou are the Zeno Agent Companion — a helpful assistant for questions about the project being built."
        )

        res = self._execute_gemini_turn(
            api_key=api_key,
            model="gemini-2.0-flash-lite",
            system_instruction=system_prompt,
            history=history,
            message=message,
            attachments=[],
            thinking_level="Low",
        )
        return res

    # -------------------------------------------------------------------------
    # Autonomous Agent & Safety Observer Bridge
    # -------------------------------------------------------------------------
    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Return list of actions currently awaiting human operator approval."""
        try:
            return list_pending_approvals()
        except Exception as exc:
            logging.error("Error fetching approvals: %s", exc)
            return []

    def decide_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Approve or reject a pending risky action in the safety queue."""
        approval_id = payload.get("approval_id", "")
        approved = bool(payload.get("approved", False))
        try:
            success = decide_approval(approval_id, approved)
            return {"status": "ok" if success else "not_found", "approval_id": approval_id, "approved": approved}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "approval_id": approval_id}

    def get_active_jobs(self) -> list[dict[str, Any]]:
        """Return active background jobs running under JobSupervisor (Rule E & G)."""
        try:
            return self.job_supervisor.list_jobs()
        except Exception as exc:
            logging.error("Error fetching active jobs: %s", exc)
            return []

    def get_job_logs(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return streaming stdout/stderr logs for a specific job."""
        job_id = payload.get("job_id", "")
        return {"logs": self.job_supervisor.get_job_logs(job_id)}

    def cancel_background_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel a running background job and terminate its entire process tree (Rule E)."""
        job_id = payload.get("job_id", "")
        try:
            success = self.job_supervisor.stop_job(job_id)
            return {"status": "cancelled" if success else "not_running", "job_id": job_id}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "job_id": job_id}

    def get_observer_dialogues(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return real-time safety dialogues between Zeno Bud and Zeno Orchid."""
        try:
            return get_recent_dialogues(limit=limit)
        except Exception as exc:
            logging.error("Error fetching Orchid dialogues: %s", exc)
            return []

    def get_action_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return audited actions from SQLite safety action_log."""
        try:
            return get_recent_action_logs(limit=limit)
        except Exception as exc:
            logging.error("Error fetching action logs: %s", exc)
            return []

    def list_background_jobs(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Return active background jobs running under JobSupervisor."""
        return self.get_active_jobs()

    def get_safety_evaluations(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Return safety evaluations log."""
        limit = 50
        if isinstance(payload, dict):
            limit = payload.get("limit", 50)
        return self.get_action_audit_log(limit=limit)

    def list_pending_approvals(self, payload: Any = None, *args, **kwargs) -> list[dict[str, Any]]:
        """Return pending human review actions."""
        return self.get_pending_approvals()

    def get_user_memory(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Return user persistent memory."""
        return {"memory": self.get_memory()}

    def save_user_memory(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Save user persistent memory."""
        content = payload.get("content", "") if isinstance(payload, dict) else str(payload or "")
        success = self.save_memory(content)
        return {"ok": success}

    def jump_to_step(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Rule C: Jump back to earlier step."""
        return self.revisit_agent_step(payload or {})

    def stop_agent_run(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Rule E: Stop agent run and kill background jobs."""
        return self.abort_agent_run(payload or {})

    def assistant_send_message(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Assistant conversation turn."""
        return self.chat(payload or {})

    def clear_background_jobs(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Clear finished or selected background jobs from JobSupervisor."""
        job_ids = None
        if isinstance(payload, dict):
            job_ids = payload.get("job_ids")
        return self.job_supervisor.clear_jobs(job_ids)

    def delete_workspace_files(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Delete specified or all files in active project workspace."""
        from zeno.tools.file_tools import get_active_project_dir
        from zeno.settings import DEFAULT_WORKSPACE_DIR

        paths = []
        delete_all = False
        project_folder = None
        if isinstance(payload, dict):
            paths = payload.get("paths", [])
            delete_all = payload.get("all", False)
            project_folder = payload.get("project_folder")

        target_dir = Path(project_folder).expanduser().resolve() if project_folder else (get_active_project_dir() or DEFAULT_WORKSPACE_DIR)
        deleted = []
        errors = []

        if delete_all:
            for item in target_dir.rglob("*"):
                if item.is_file() and ".venv" not in str(item) and ".git" not in str(item):
                    try:
                        item.unlink()
                        deleted.append(str(item))
                    except Exception as e:
                        errors.append(f"{item.name}: {e}")
        else:
            for p_str in paths:
                p = Path(p_str).expanduser().resolve()
                if not p.exists():
                    p = (target_dir / p_str).resolve()
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                        deleted.append(str(p))
                    except Exception as e:
                        errors.append(f"{p.name}: {e}")

        return {"ok": len(errors) == 0, "deleted": deleted, "errors": errors}

    def clear_safety_evaluations(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Clear action logs from SQLite safety database."""
        from zeno.safety.database import clear_action_logs
        log_ids = None
        if isinstance(payload, dict):
            log_ids = payload.get("log_ids")
        success = clear_action_logs(log_ids)
        return {"ok": success}

    def save_all_permissions(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Save whole permissions dict."""
        from zeno.permissions import save_permissions
        perms = payload.get("permissions", {}) if isinstance(payload, dict) else {}
        save_permissions(perms)
        return {"ok": True, "permissions": perms}

    # -------------------------------------------------------------------------
    # In-App File Viewer & Explorer Bridge
    # -------------------------------------------------------------------------
    def open_in_explorer(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """Open a file or folder in the system file explorer."""
        path = ""
        if isinstance(payload, dict):
            path = payload.get("path", "")
        elif isinstance(payload, str):
            path = payload
        elif args and len(args) > 0:
            path = args[0].get("path", "") if isinstance(args[0], dict) else str(args[0])
        try:
            return _open_in_explorer(path)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def read_file_for_viewer(self, payload: Any = None, *args, **kwargs) -> dict[str, Any]:
        """
        Read a file and return its contents as base64 + raw text for in-app viewing.
        Supports images (PNG/JPG/GIF/WebP), text, markdown, code, and JSON.
        """
        path = ""
        if isinstance(payload, dict):
            path = payload.get("path", "")
        elif isinstance(payload, str):
            path = payload
        elif args and len(args) > 0:
            path = args[0].get("path", "") if isinstance(args[0], dict) else str(args[0])
        try:
            return _read_file_as_base64(path)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def download_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Download a file from a URL into the session workspace."""
        url = payload.get("url", "") if isinstance(payload, dict) else str(payload)
        dest = payload.get("destination_path", "") if isinstance(payload, dict) else ""
        fname = payload.get("filename", "") if isinstance(payload, dict) else ""
        try:
            return _download_file(url=url, destination_path=dest, filename=fname)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def list_session_files(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """
        List files created/modified in the current session workspace.
        Returns rich metadata including mime type for viewer routing.
        """
        import mimetypes
        session_workspace = payload.get("sessionWorkspace", "") if isinstance(payload, dict) else str(payload)
        if not session_workspace:
            session_workspace = str(DEFAULT_WORKSPACE_DIR)

        target_dir = Path(session_workspace)
        if not target_dir.exists():
            return []

        result = []
        try:
            for entry in sorted(target_dir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
                if entry.is_file() and not entry.name.startswith("."):
                    mime_type, _ = mimetypes.guess_type(str(entry))
                    if not mime_type:
                        ext = entry.suffix.lower()
                        mime_map = {
                            ".py": "text/x-python", ".ts": "text/typescript",
                            ".tsx": "text/typescript", ".js": "text/javascript",
                            ".json": "application/json", ".md": "text/markdown",
                            ".html": "text/html", ".css": "text/css",
                            ".txt": "text/plain", ".csv": "text/csv",
                        }
                        mime_type = mime_map.get(ext, "application/octet-stream")
                    stat = entry.stat()
                    result.append({
                        "name": entry.name,
                        "path": str(entry.resolve()),
                        "relative": str(entry.relative_to(target_dir)),
                        "size_bytes": stat.st_size,
                        "size": f"{round(stat.st_size / 1024, 1)} KB" if stat.st_size >= 1024 else f"{stat.st_size} B",
                        "mime_type": mime_type,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%H:%M:%S"),
                    })
                    if len(result) >= 50:
                        break
        except Exception as exc:
            logging.warning("list_session_files error: %s", exc)

        return result

