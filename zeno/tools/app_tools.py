"""
Application and URL launching tools.
Category: app_launch
Strictly restricted to allowlisted applications and http/https web URLs.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from urllib.parse import urlparse
import webbrowser

from zeno.settings import APP_ALLOWLIST

# App command mapping per operating system
_APP_COMMAND_MAP: dict[str, dict[str, list[str] | str]] = {
    "Windows": {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "code": "code.cmd",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
    },
    "Darwin": {
        "notepad": "TextEdit",
        "calculator": "Calculator",
        "code": "Visual Studio Code",
        "chrome": "Google Chrome",
        "firefox": "Firefox",
    },
    "Linux": {
        "notepad": ["gedit", "xed", "mousepad", "kate", "nano"],
        "calculator": ["gnome-calculator", "kcalc", "galculator", "xcalc"],
        "code": ["code", "codium"],
        "chrome": ["google-chrome", "chromium-browser", "chromium"],
        "firefox": ["firefox"],
    },
}


def open_url(url: str) -> str:
    """
    Open an HTTP or HTTPS URL in the system default web browser.

    Args:
        url: Full web URL starting with http:// or https://.

    Returns:
        str: Status message.
    """
    clean_url = url.strip()
    parsed = urlparse(clean_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL. Only http:// and https:// URLs are permitted: {url}")

    success = webbrowser.open(clean_url)
    if success:
        return f"Opened web URL: {clean_url}"
    return f"Browser launch dispatched for: {clean_url}"


def open_app(name: str) -> str:
    """
    Launch an application from the approved allowlist.

    Args:
        name: Name of the application (one of: notepad, calculator, code, chrome, firefox).

    Returns:
        str: Status message.
    """
    clean_name = name.lower().strip()
    if clean_name not in APP_ALLOWLIST:
        allowed_str = ", ".join(APP_ALLOWLIST)
        raise PermissionError(
            f"Application '{name}' is not in the approved allowlist: {allowed_str}."
        )

    current_os = platform.system()
    os_commands = _APP_COMMAND_MAP.get(current_os, _APP_COMMAND_MAP["Linux"])
    app_target = os_commands.get(clean_name, clean_name)

    if current_os == "Windows":
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(app_target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen([str(app_target)], shell=False)
            return f"Launched {name} on Windows."
        except Exception as exc:
            return f"Failed to launch {name} on Windows: {exc}"

    elif current_os == "Darwin":
        try:
            subprocess.Popen(["open", "-a", str(app_target)], shell=False)
            return f"Launched {name} on macOS."
        except Exception as exc:
            return f"Failed to launch {name} on macOS: {exc}"

    else:
        # Linux
        candidates = app_target if isinstance(app_target, list) else [str(app_target)]
        found_binary = None
        for binary in candidates:
            if shutil.which(binary):
                found_binary = binary
                break

        if not found_binary:
            found_binary = candidates[0]

        try:
            subprocess.Popen([found_binary], shell=False)
            return f"Launched {name} ({found_binary}) on Linux."
        except Exception as exc:
            return f"Failed to launch {name} on Linux: {exc}"
