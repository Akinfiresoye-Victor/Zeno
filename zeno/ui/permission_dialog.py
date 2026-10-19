"""
Modal permission request and destructive confirmation dialogs.
Strict adherence to Zeno UI styling: no emojis, plain text, clean contrast.
"""

from __future__ import annotations

from typing import Optional

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
    COLOR_MAIN_BG,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
)


class PermissionDialog:
    """
    Modal dialog requesting permission for a tool category.
    Includes Allow and Deny buttons and blocks until user resolves.
    """

    def __init__(self, parent: any, category: str, description: str) -> None:
        self.result: bool = False
        if ctk is None:
            # Fallback if headless / no GUI
            return

        self.top = ctk.CTkToplevel(parent)
        self.top.title(t("permission_dialog_title", category=category))
        self.top.geometry("460x220")
        self.top.resizable(False, False)
        self.top.configure(fg_color=COLOR_MAIN_BG)

        # Make modal
        self.top.transient(parent)
        self.top.grab_set()

        # Content frame
        frame = ctk.CTkFrame(
            self.top,
            fg_color=COLOR_INPUT_CARD,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
        )
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        title_label = ctk.CTkLabel(
            frame,
            text=f"Permission Required: {category}",
            font=FONT_HEADING,
            text_color=COLOR_PRIMARY_TEXT,
            anchor="w",
        )
        title_label.pack(fill="x", padx=16, pady=(16, 8))

        desc_label = ctk.CTkLabel(
            frame,
            text=description,
            font=FONT_BODY,
            text_color=COLOR_MUTED_TEXT,
            wraplength=400,
            justify="left",
            anchor="w",
        )
        desc_label.pack(fill="x", padx=16, pady=(0, 20))

        # Buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        deny_btn = ctk.CTkButton(
            btn_frame,
            text=t("permission_deny"),
            font=FONT_BODY_BOLD,
            fg_color="#2A2A34",
            hover_color="#3A3A46",
            text_color=COLOR_PRIMARY_TEXT,
            width=100,
            height=32,
            corner_radius=4,
            command=self._on_deny,
        )
        deny_btn.pack(side="right", padx=(8, 0))

        allow_btn = ctk.CTkButton(
            btn_frame,
            text=t("permission_allow"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            width=100,
            height=32,
            corner_radius=4,
            command=self._on_allow,
        )
        allow_btn.pack(side="right")

        self.top.protocol("WM_DELETE_WINDOW", self._on_deny)
        parent.wait_window(self.top)

    def _on_allow(self) -> None:
        self.result = True
        self.top.destroy()

    def _on_deny(self) -> None:
        self.result = False
        self.top.destroy()


class ConfirmDestructiveDialog:
    """
    Modal dialog confirming destructive overwrite of an existing file.
    """

    def __init__(self, parent: any, path_str: str) -> None:
        self.result: bool = False
        if ctk is None:
            return

        self.top = ctk.CTkToplevel(parent)
        self.top.title(t("confirm_destructive_title"))
        self.top.geometry("480x210")
        self.top.resizable(False, False)
        self.top.configure(fg_color=COLOR_MAIN_BG)

        self.top.transient(parent)
        self.top.grab_set()

        frame = ctk.CTkFrame(
            self.top,
            fg_color=COLOR_INPUT_CARD,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
        )
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        title_label = ctk.CTkLabel(
            frame,
            text=t("confirm_destructive_title"),
            font=FONT_HEADING,
            text_color=COLOR_ERROR,
            anchor="w",
        )
        title_label.pack(fill="x", padx=16, pady=(16, 8))

        prompt_text = t("confirm_destructive_prompt", path=path_str)
        desc_label = ctk.CTkLabel(
            frame,
            text=prompt_text,
            font=FONT_BODY,
            text_color=COLOR_PRIMARY_TEXT,
            wraplength=420,
            justify="left",
            anchor="w",
        )
        desc_label.pack(fill="x", padx=16, pady=(0, 20))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text=t("confirm_no"),
            font=FONT_BODY_BOLD,
            fg_color="#2A2A34",
            hover_color="#3A3A46",
            text_color=COLOR_PRIMARY_TEXT,
            width=100,
            height=32,
            corner_radius=4,
            command=self._on_cancel,
        )
        cancel_btn.pack(side="right", padx=(8, 0))

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text=t("confirm_yes"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ERROR,
            hover_color="#DC2626",
            text_color="#FFFFFF",
            width=100,
            height=32,
            corner_radius=4,
            command=self._on_confirm,
        )
        confirm_btn.pack(side="right")

        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        parent.wait_window(self.top)

    def _on_confirm(self) -> None:
        self.result = True
        self.top.destroy()

    def _on_cancel(self) -> None:
        self.result = False
        self.top.destroy()
