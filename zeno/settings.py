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
MAX_OUTPUT_TOKENS = 2048
MAX_HISTORY_MESSAGES = 10
MAX_STEPS = 15
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
APP_ALLOWLIST = ["notepad", "calculator", "code", "chrome", "firefox"]

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

# Ensure required runtime directories exist
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
for folder in ALLOWED_FOLDERS:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
