"""
Status bar at the bottom of the main Zeno window (24 px).
Displays current state (Ready, Thinking..., last tool used) and cumulative token counts.
"""

from __future__ import annotations

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.i18n import t
from zeno.settings import STATUSBAR_HEIGHT
from zeno.theme import (
    COLOR_BORDER,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    COLOR_SIDEBAR_PANEL,
    FONT_STATUS,
)


class StatusBar:
    """
    Bottom 24px bar with status text on the left and token counts on the right.
    """

    def __init__(self, parent: any) -> None:
        if ctk is None:
            return

        self.frame = ctk.CTkFrame(
            parent,
            height=STATUSBAR_HEIGHT,
            fg_color=COLOR_SIDEBAR_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=0,
        )
        self.frame.pack(side="bottom", fill="x")
        self.frame.pack_propagate(False)

        # Status label left
        self.status_label = ctk.CTkLabel(
            self.frame,
            text=t("status_ready"),
            font=FONT_STATUS,
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
        )
        self.status_label.pack(side="left", padx=12)

        # Token count label right
        self.tokens_label = ctk.CTkLabel(
            self.frame,
            text=t("tokens_label", input_tokens=0, output_tokens=0),
            font=FONT_STATUS,
            text_color=COLOR_MUTED_TEXT,
            anchor="e",
        )
        self.tokens_label.pack(side="right", padx=12)

    def set_status(self, text: str, in_tokens: int = 0, out_tokens: int = 0) -> None:
        """Update status message and optional token counts."""
        if ctk is None:
            return
        self.status_label.configure(text=text)
        if in_tokens > 0 or out_tokens > 0:
            self.tokens_label.configure(
                text=t("tokens_label", input_tokens=in_tokens, output_tokens=out_tokens)
            )
