"""
Tool registry and schema exports for Zeno Desktop AI Assistant.
Every tool is a fully typed Python function with clear docstring and category mapping.
"""

from __future__ import annotations

from typing import Any, Callable

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
from zeno.tools.memory_tools import save_user_memory, read_user_memory
from zeno.tools.dev_tools import (
    job_submit,
    job_status,
    job_cancel,
    report_write,
    shell_run,
    git_status,
    git_diff,
    git_commit,
    run_tests,
    lint_run,
    security_scan,
    server_start,
    server_stop,
    server_logs,
    watch_start,
    watch_stop,
    schedule_task,
    sandbox_run,
    pip_install,
)

# Complete list of callable tools exposed to the agent
ALL_TOOLS: list[Callable[..., Any]] = [
    system_info,
    capture_screen,
    list_screen_targets,
    read_clipboard,
    write_clipboard,
    list_directory,
    read_file,
    append_file,
    write_file,
    search_files,
    create_document,
    create_project_workspace,
    organize_documents,
    open_url,
    open_app,
    run_python,
    web_search,
    list_running_processes,
    get_network_status,
    save_user_memory,
    read_user_memory,
    # Development & Autonomous Safety Tools Suite
    job_submit,
    job_status,
    job_cancel,
    report_write,
    shell_run,
    git_status,
    git_diff,
    git_commit,
    run_tests,
    lint_run,
    security_scan,
    server_start,
    server_stop,
    server_logs,
    watch_start,
    watch_stop,
    schedule_task,
    sandbox_run,
    pip_install,
]

# Tool category mapping for permission checks
TOOL_CATEGORIES: dict[str, str] = {
    "system_info": "system_read",
    "list_running_processes": "system_read",
    "get_network_status": "system_read",
    "save_user_memory": "file_write",
    "read_user_memory": "file_read",
    "capture_screen": "screen_capture",
    "list_screen_targets": "screen_capture",
    "read_clipboard": "clipboard",
    "write_clipboard": "clipboard",
    "list_directory": "file_read",
    "read_file": "file_read",
    "search_files": "file_read",
    "write_file": "file_write",
    "append_file": "file_write",
    "create_document": "file_write",
    "create_project_workspace": "file_write",
    "organize_documents": "file_write",
    "open_url": "app_launch",
    "open_app": "app_launch",
    "run_python": "python_exec",
    "web_search": "web_search",
    # Dev tools mapped to single grouped permission category: dev_tools
    "job_submit": "dev_tools",
    "job_status": "dev_tools",
    "job_cancel": "dev_tools",
    "report_write": "dev_tools",
    "shell_run": "dev_tools",
    "git_status": "dev_tools",
    "git_diff": "dev_tools",
    "git_commit": "dev_tools",
    "run_tests": "dev_tools",
    "lint_run": "dev_tools",
    "security_scan": "dev_tools",
    "server_start": "dev_tools",
    "server_stop": "dev_tools",
    "server_logs": "dev_tools",
    "watch_start": "dev_tools",
    "watch_stop": "dev_tools",
    "schedule_task": "dev_tools",
    "sandbox_run": "dev_tools",
    "pip_install": "dev_tools",
}

# Dictionary lookup by function name
TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    func.__name__: func for func in ALL_TOOLS
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_CATEGORIES",
    "TOOL_REGISTRY",
    "system_info",
    "capture_screen",
    "list_screen_targets",
    "read_clipboard",
    "write_clipboard",
    "list_directory",
    "read_file",
    "append_file",
    "write_file",
    "search_files",
    "create_document",
    "create_project_workspace",
    "organize_documents",
    "open_url",
    "open_app",
    "run_python",
    "web_search",
    "list_running_processes",
    "get_network_status",
]
