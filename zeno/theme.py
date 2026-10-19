"""
Design system, theme palette, typography, and CustomTkinter appearance settings.
Strictly follows the Zeno desktop UI specifications:
No gradients, shadows, or glow.
"""

from __future__ import annotations

import platform

# Color palette
COLOR_MAIN_BG = "#0A0A0C"
COLOR_SIDEBAR_PANEL = "#111115"
COLOR_INPUT_CARD = "#17171D"
COLOR_BORDER = "#22222A"
COLOR_PRIMARY_TEXT = "#E6E8EE"
COLOR_MUTED_TEXT = "#7C8091"
COLOR_ACCENT_BLUE = "#3B82F6"
COLOR_ACCENT_HOVER = "#2563EB"
COLOR_ERROR = "#F87171"
COLOR_SUCCESS = "#4ADE80"
COLOR_CODE_BG = "#0F0F13"

# User message bubble (blue-tinted block ~ #1E3A8A at 35% opacity blended on #0A0A0C)
COLOR_USER_BUBBLE = "#131C35"

# Typography selection per operating system
CURRENT_OS = platform.system()

if CURRENT_OS == "Windows":
    FONT_FAMILY_MAIN = "Segoe UI"
    FONT_FAMILY_MONO = "Consolas"
elif CURRENT_OS == "Darwin":
    FONT_FAMILY_MAIN = "SF Pro Text"
    FONT_FAMILY_MONO = "Menlo"
else:
    # Linux and other UNIX systems
    FONT_FAMILY_MAIN = "Ubuntu"
    FONT_FAMILY_MONO = "DejaVu Sans Mono"

# Font size presets
FONT_TITLE = (FONT_FAMILY_MAIN, 15, "bold")
FONT_HEADING = (FONT_FAMILY_MAIN, 13, "bold")
FONT_BODY = (FONT_FAMILY_MAIN, 12, "normal")
FONT_BODY_BOLD = (FONT_FAMILY_MAIN, 12, "bold")
FONT_SMALL = (FONT_FAMILY_MAIN, 11, "normal")
FONT_STATUS = (FONT_FAMILY_MAIN, 10, "normal")
FONT_CODE = (FONT_FAMILY_MONO, 11, "normal")
FONT_CODE_TITLE = (FONT_FAMILY_MONO, 10, "bold")
