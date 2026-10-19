"""
Command allowlist and execution guard for Zeno Autonomous Agents.
Enforces strict binary matching against an approved executable list,
prohibits shell metacharacters, and guarantees shell=False invocation.
"""

from __future__ import annotations

import json
from pathlib import Path
import shlex
from typing import Optional

from zeno.settings import BASE_DIR

CONFIG_PATH = BASE_DIR / "config" / "agent_safety.json"

DEFAULT_ALLOWLIST = [
    "git",
    "python",
    "pip",
    "pytest",
    "ruff",
    "mypy",
    "pip-audit",
    "bandit",
]

# Disallowed shell chaining and redirection metacharacters
FORBIDDEN_SHELL_TOKENS = {
    ";", "&&", "||", "|", ">", ">>", "<", "&", "`", "$", "(", ")", "\n", "\r"
}


def get_command_allowlist() -> list[str]:
    """Retrieve command allowlist from configuration."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("command_allowlist", DEFAULT_ALLOWLIST)
        except Exception:
            pass
    return DEFAULT_ALLOWLIST


def parse_and_validate_command(
    command_input: str | list[str],
) -> tuple[bool, list[str], str]:
    """
    Validate that command uses an approved binary without shell injection.
    Returns: (is_allowed, argument_list, error_reason)
    """
    if isinstance(command_input, str):
        raw_str = command_input.strip()
        if not raw_str:
            return False, [], "Empty command string."

        # Reject any shell metacharacters immediately
        for token in FORBIDDEN_SHELL_TOKENS:
            if token in raw_str:
                return (
                    False,
                    [],
                    f"Command contains forbidden shell metacharacter '{token}'. Commands must be safe, single processes.",
                )

        try:
            cmd_args = shlex.split(raw_str, posix=False)
        except Exception as exc:
            return False, [], f"Command parsing error: {exc}"
    elif isinstance(command_input, list):
        cmd_args = [str(x) for x in command_input]
        for arg in cmd_args:
            for token in FORBIDDEN_SHELL_TOKENS:
                if token in arg:
                    return (
                        False,
                        [],
                        f"Command argument contains forbidden shell metacharacter '{token}'.",
                    )
    else:
        return False, [], "Command must be a string or list of argument tokens."

    if not cmd_args:
        return False, [], "No executable specified."

    raw_exe = cmd_args[0].strip().lower()
    # Normalize path if given as full path or windows .exe
    exe_name = Path(raw_exe).name.lower()
    if exe_name.endswith(".exe"):
        exe_name = exe_name[:-4]

    allowlist = [x.lower() for x in get_command_allowlist()]

    # Special approved pattern: 'python manage.py ...'
    if exe_name == "python" and len(cmd_args) > 1 and "manage.py" in cmd_args[1].lower():
        return True, cmd_args, ""

    if exe_name in allowlist:
        return True, cmd_args, ""

    allowed_str = ", ".join(allowlist)
    return (
        False,
        [],
        f"Executable '{exe_name}' is not in the security allowlist ({allowed_str}).",
    )
