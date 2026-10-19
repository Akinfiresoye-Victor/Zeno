"""
Bottom input bar with multi-line text input, Send button, and Stop task button.
Enter key sends the message; Shift+Enter inserts a new line.
"""

from __future__ import annotations

from typing import Callable, Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.i18n import t
from zeno.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_INPUT_CARD,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    FONT_BODY,
    FONT_BODY_BOLD,
)


class InputBar:
    """
    Bottom message entry bar with Send and Stop controls.
    """

    def __init__(
        self,
        parent: any,
        on_send: Callable[[str], None],
        on_stop: Callable[[], None],
    ) -> None:
        self.on_send = on_send
        self.on_stop = on_stop
        self._is_running = False

        if ctk is None:
            return

        self.container = ctk.CTkFrame(
            parent,
            fg_color="transparent",
            height=80,
        )
        self.container.pack(side="bottom", fill="x", padx=16, pady=(8, 12))

        # Text input card
        self.card = ctk.CTkFrame(
            self.container,
            fg_color=COLOR_INPUT_CARD,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=6,
        )
        self.card.pack(fill="x", expand=True)

        # Internal layout
        self.textbox = ctk.CTkTextbox(
            self.card,
            fg_color="transparent",
            text_color=COLOR_PRIMARY_TEXT,
            font=FONT_BODY,
            wrap="word",
            height=54,
            corner_radius=0,
            border_width=0,
        )
        self.textbox.pack(side="left", fill="both", expand=True, padx=(12, 8), pady=8)

        # Key bindings: Enter sends, Shift+Enter new line
        self.textbox.bind("<Return>", self._handle_return)
        self.textbox.bind("<Shift-Return>", self._handle_shift_return)

        # Action button container
        self.btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.btn_frame.pack(side="right", padx=(0, 10), pady=10)

        # Stop button (hidden when idle)
        self.stop_btn = ctk.CTkButton(
            self.btn_frame,
            text=t("stop_button"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ERROR,
            hover_color="#DC2626",
            text_color="#FFFFFF",
            width=70,
            height=34,
            corner_radius=4,
            command=self._handle_stop,
        )

        # Send button
        self.send_btn = ctk.CTkButton(
            self.btn_frame,
            text=t("send_button"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            width=70,
            height=34,
            corner_radius=4,
            command=self._handle_send,
        )
        self.send_btn.pack(side="right")

    def _handle_return(self, event: any) -> str:
        # Check if Shift key is pressed
        if event.state & 0x0001:  # Shift mask
            return ""  # Allow default newline
        self._handle_send()
        return "break"  # Prevent default newline

    def _handle_shift_return(self, event: any) -> None:
        pass

    def _handle_send(self) -> None:
        if self._is_running:
            return
        text = self.textbox.get("1.0", "end-1c").strip()
        if not text:
            return
        self.textbox.delete("1.0", "end")
        self.set_running(True)
        self.on_send(text)

    def _handle_stop(self) -> None:
        self.on_stop()
        self.set_running(False)

    def set_running(self, running: bool) -> None:
        self._is_running = running
        if ctk is None:
            return
        if running:
            self.send_btn.pack_forget()
            self.stop_btn.pack(side="right")
        else:
            self.stop_btn.pack_forget()
            self.send_btn.pack(side="right")

    def focus(self) -> None:
        if ctk and hasattr(self, "textbox"):
            self.textbox.focus_set()
