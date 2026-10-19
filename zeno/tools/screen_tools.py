"""
Screen and browser tab capture tools using mss and Windows Win32 API.
Category: screen_capture
Supports full virtual desktop, individual physical displays, application windows, and browser tab targeting.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Optional

from zeno.settings import SCREENSHOTS_DIR

try:
    import mss
    import mss.tools
except ImportError:
    mss = None

try:
    from PIL import Image
except ImportError:
    Image = None


def _get_windows_app_windows() -> list[dict]:
    """Enumerate visible application windows on Windows using user32."""
    windows: list[dict] = []
    if sys.platform != "win32":
        return windows

    try:
        user32 = ctypes.windll.user32

        def enum_windows_proc(hwnd, lparam):
            if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value.strip()

                    # Filter out system utility and empty frames
                    ignored = (
                        "Program Manager",
                        "Settings",
                        "Windows Shell Experience Host",
                        "Start",
                        "Default IME",
                        "MSCTFIME UI",
                    )
                    if title and title not in ignored and len(title) > 1:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        if width > 150 and height > 150:
                            is_browser = any(
                                b in title.lower()
                                for b in ["chrome", "edge", "firefox", "brave", "opera", "vivaldi", "http", ".com", ".org"]
                            )
                            app_type = "browser_tab" if is_browser else "app_window"
                            windows.append({
                                "id": f"hwnd_{hwnd}",
                                "hwnd": hwnd,
                                "name": title,
                                "description": f"{'Browser Window/Tab' if is_browser else 'Application Window'} ({width}x{height})",
                                "type": app_type,
                                "rect": {
                                    "left": rect.left,
                                    "top": rect.top,
                                    "width": width,
                                    "height": height,
                                },
                            })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    except Exception:
        pass

    return windows


def list_screen_targets() -> list[dict]:
    """
    List selectable screen capture targets, including all monitors combined,
    individual physical screens, active browser windows, and open application tabs.

    Returns:
        list[dict]: Available targets with id, name, description, and type.
    """
    targets = [
        {"id": "all", "name": "All Monitors Combined", "description": "Full multi-monitor desktop view", "type": "display"},
        {"id": "monitor_1", "name": "Primary Display", "description": "Main physical monitor", "type": "display"},
    ]

    # Enumerate physical monitors
    if mss is not None:
        try:
            with mss.mss() as sct:
                for idx, m in enumerate(sct.monitors[1:], start=1):
                    if idx > 1:
                        targets.append({
                            "id": f"monitor_{idx}",
                            "name": f"Physical Monitor {idx} ({m['width']}x{m['height']})",
                            "description": f"Display at offset x={m['left']}, y={m['top']}",
                            "type": "display",
                        })
        except Exception:
            pass

    # Enumerate actual open application and browser windows
    app_windows = _get_windows_app_windows()
    if app_windows:
        targets.extend(app_windows)
    else:
        # Fallback targets if running outside Windows or headless
        targets.extend([
            {"id": "browser_tab", "name": "Active Browser Tab", "description": "Currently focused browser tab with URL and tab bar", "type": "browser_tab"},
            {"id": "active_window", "name": "Focused Application Window", "description": "Active foreground desktop application", "type": "app_window"},
        ])

    return targets


def capture_screen(target: str = "all", tab_name: str = "") -> str:
    """
    Capture the screen, specific physical display, open application, or active browser tab,
    saving the result as a PNG file.

    Args:
        target: Target identifier: 'all', 'monitor_1', 'monitor_2', 'hwnd_<id>',
                'browser_tab', or 'active_window'.
        tab_name: Optional browser tab or window name filter.

    Returns:
        str: Absolute filesystem path to the saved screenshot image file.
    """
    if mss is None:
        raise RuntimeError("mss package is not installed. Install with: pip install mss==9.0.1")

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    clean_tab = tab_name.replace(" ", "_")[:20] if tab_name else ""
    suffix = f"_{clean_tab}" if clean_tab else ""
    filename = datetime.now().strftime(f"%Y-%m-%d-%H%M%S{suffix}.png")
    output_path = SCREENSHOTS_DIR / filename

    with mss.mss() as sct:
        num_monitors = len(sct.monitors)

        # 1. Target is a specific window by HWND
        if target.startswith("hwnd_") and sys.platform == "win32":
            try:
                hwnd_val = int(target.replace("hwnd_", ""))
                user32 = ctypes.windll.user32
                rect = wintypes.RECT()
                if user32.GetWindowRect(hwnd_val, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w > 10 and h > 10:
                        monitor_target = {
                            "left": max(0, rect.left),
                            "top": max(0, rect.top),
                            "width": w,
                            "height": h,
                        }
                        sct_img = sct.grab(monitor_target)
                        mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(output_path))
                        return str(output_path.resolve())
            except Exception:
                pass

        # 2. Target is full desktop or specific physical monitor
        if target == "all" or num_monitors <= 1:
            monitor_target = sct.monitors[0]
        elif target.startswith("monitor_"):
            try:
                idx = int(target.split("_")[1])
                monitor_target = sct.monitors[idx] if idx < num_monitors else sct.monitors[1]
            except Exception:
                monitor_target = sct.monitors[1]
        elif target in ("browser_tab", "active_window"):
            base_monitor = sct.monitors[1] if num_monitors > 1 else sct.monitors[0]
            monitor_target = {
                "top": base_monitor["top"],
                "left": base_monitor["left"],
                "width": base_monitor["width"],
                "height": min(base_monitor["height"], 950),
            }
        else:
            monitor_target = sct.monitors[0]

        sct_img = sct.grab(monitor_target)
        mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(output_path))

    return str(output_path.resolve())
