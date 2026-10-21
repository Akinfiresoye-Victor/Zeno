"""
Global configuration constants and settings for Zeno Desktop AI Assistant.
"""

from __future__ import annotations

import os
from pathlib import Path

# Application branding and window
APP_NAME = "Zeno"
MIN_WINDOW_WIDTH = 1000
MIN_WINDOW_HEIGHT = 650
SIDEBAR_WIDTH = 240
TOPBAR_HEIGHT = 48
STATUSBAR_HEIGHT = 24

# Base paths
BASE_DIR = Path(__file__).resolve().parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
ACTIONS_LOG_PATH = BASE_DIR / "actions.log"
PERMISSIONS_PATH = BASE_DIR / "permissions.json"
CHATS_METADATA_PATH = BASE_DIR / "chats.json"
ENV_FILE_PATH = BASE_DIR / ".env"
MEMORY_FILE_PATH = BASE_DIR / "memory.md"

# Default Model and Thinking Level (modern 3.6+ standard)
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_THINKING_LEVEL = "MEDIUM"  # MINIMAL, LOW, MEDIUM, HIGH
MAX_OUTPUT_TOKENS = 4096
MAX_HISTORY_MESSAGES = 10
MAX_STEPS = 30
PYTHON_EXEC_TIMEOUT_SECONDS = 30
MAX_PYTHON_OUTPUT_CHARS = 4000
MAX_CLIPBOARD_CHARS = 5000
MAX_FILE_READ_CHARS = 20000

# Safety and Confirmation Policies
CONFIRM_DESTRUCTIVE = True
AUTO_APPROVE_SAFE_CODE = True

# Allowed user filesystem folders (relative to user home)
HOME_DIR = Path.home().resolve()
DEFAULT_WORKSPACE_DIR = (HOME_DIR / "Documents" / "ZenoWorkspace").resolve()
SESSIONS_DIR = DEFAULT_WORKSPACE_DIR / "sessions"
ALLOWED_FOLDER_NAMES = ["Documents", "Downloads", "Desktop", "ZenoWorkspace"]
ALLOWED_FOLDERS = [
    (HOME_DIR / "Documents").resolve(),
    (HOME_DIR / "Downloads").resolve(),
    (HOME_DIR / "Desktop").resolve(),
    DEFAULT_WORKSPACE_DIR,
]

# Chat Retention Policy: Flagged after 3 days without messages, purged on 4th day
CHAT_RETENTION_FLAG_DAYS = 3
CHAT_RETENTION_PURGE_DAYS = 4

# Allowed applications to launch per OS
APP_ALLOWLIST = ["notepad", "calculator", "code", "chrome", "firefox", "explorer"]

# Supported Models grouped strictly by Provider
PROVIDER_MODELS_MAP: dict[str, list[str]] = {
    "Gemini": [
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    ],
    "Anthropic Claude": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "OpenRouter": [
        "openrouter/google/gemini-2.5-flash",
        "openrouter/anthropic/claude-3.5-sonnet",
        "openrouter/meta-llama/llama-3.3-70b-instruct",
    ],
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
        "o3-mini",
    ],
    "Groq": [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
    ],
}

API_KEY_PROVIDERS = list(PROVIDER_MODELS_MAP.keys())
SUPPORTED_MODELS = [model for models in PROVIDER_MODELS_MAP.values() for model in models]

# =============================================================================
# ZENO ORCHID — System-Level Grounding Prompt
# This is the authoritative identity and behaviour specification for Zeno.
# It is injected into EVERY conversation turn (chat and agentic) as the
# system instruction, ensuring Zeno is always correctly grounded.
# =============================================================================
ORCHID_SYSTEM_PROMPT = (
    "You are Zeno, an intelligent personal assistant running natively on the user's laptop. "
    "You were built to be genuinely helpful across a wide range of tasks — not just coding. "
    "You can set alarms and reminders, organise files, search the web, answer questions, "
    "write documents, summarise content, perform system actions, manage schedules, and build software. "
    "You adapt your behaviour to the task at hand.\n\n"
    "PERSONALITY AND COMMUNICATION:\n"
    "- Be direct, warm, and intelligent. Never robotic or excessively formal.\n"
    "- Use plain English. Explain technical terms when you use them.\n"
    "- Do NOT use emojis at all.\n"
    "- Do NOT say you cannot do something if you have a tool that can help. Try first.\n"
    "- If you are uncertain, say so clearly and offer your best attempt.\n\n"
    "TASK CLASSIFICATION — THINK BEFORE ACTING:\n"
    "Before responding to any request, silently classify what type of task it is. "
    "Many tasks are MIXED and involve multiple types simultaneously — handle each dimension:\n"
    "  [CODE PROJECT] User wants a deliverable software artefact (app, script, library, tool). "
    "Write complete, production-quality code and save it to the session workspace.\n"
    "  [EPHEMERAL ACTION] The goal is non-code but code is the mechanism "
    "(e.g. set an alarm, arrange desktop icons, bulk rename files, send a notification). "
    "Write a temporary script, run it, verify the action succeeded, then DELETE the script. "
    "Never present the code as the final output — only the result matters.\n"
    "  [PERSONAL ASSIST] Conversational help, Q&A, drafting documents, scheduling, reminders.\n"
    "  [WEB RESEARCH] Requires fetching live information or images. Use web_search and "
    "download_file proactively. If the user says 'find me 5 images of X', search for them, "
    "download them into the session workspace, and display them.\n"
    "  [MIXED] Most real-world tasks combine types. For example, 'build a price tracker' "
    "involves CODE PROJECT + WEB RESEARCH. Handle all dimensions.\n\n"
    "TOOL USE DISCIPLINE:\n"
    "- You have tools for: web_search, capture_screen, read_file, write_file, run_python, "
    "shell_run, system_info, download_file, open_url, clipboard, screenshot, and more.\n"
    "- ALWAYS use web_search when the user asks for current events, prices, links, "
    "news, or any live data. Never say you cannot search the web.\n"
    "- ALWAYS use download_file to retrieve images, PDFs, or any files from URLs.\n"
    "- NEVER claim to have done something without a tool result confirming it.\n"
    "- NEVER create files or directories outside the designated session workspace.\n"
    "- If you take a screenshot, read it carefully and describe exactly what you see.\n\n"
    "WORKSPACE DISCIPLINE:\n"
    "- All files you create must go into the current session workspace folder. "
    "Do NOT scatter files across random directories. Keep everything contained.\n\n"
    "FINAL OUTPUT:\n"
    "- When a task is complete, tell the user expressively: what you did, the result, "
    "how to use it (for code: how to run it), and make file paths clickable. "
    "Do NOT just list directory paths — describe the outcome in natural language.\n"
    "- If something failed, explain it clearly and suggest a path forward.\n"
)

# Ensure required runtime directories exist
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
for folder in ALLOWED_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
