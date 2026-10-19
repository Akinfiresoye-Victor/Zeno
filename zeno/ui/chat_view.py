"""
Scrollable message stream rendering user, assistant, tool usage lines, and code blocks.
Follows strict typography, alignment, and palette rules.
"""

from __future__ import annotations

import re
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.i18n import t
from zeno.theme import (
    COLOR_BORDER,
    COLOR_CODE_BG,
    COLOR_MAIN_BG,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    COLOR_USER_BUBBLE,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_CODE,
    FONT_CODE_TITLE,
    FONT_SMALL,
)

try:
    import pyperclip
except ImportError:
    pyperclip = None


class ChatView:
    """
    Scrollable chat history container rendering formatted messages,
    plain tool notifications, and copyable syntax-fenced code blocks.
    """

    def __init__(self, parent: any) -> None:
        self.parent = parent
        if ctk is None:
            return

        self.scroll_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color=COLOR_MAIN_BG,
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_MUTED_TEXT,
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=8)

        # Show initial welcome message
        self.add_system_notice(t("welcome_message"))

    def clear(self) -> None:
        """Clear all messages in view."""
        if ctk is None:
            return
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self.add_system_notice(t("welcome_message"))

    def add_user_message(self, text: str) -> None:
        """Add user message on the right in blue-tinted block."""
        if ctk is None:
            return

        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row.pack(fill="x", pady=6)

        bubble_container = ctk.CTkFrame(row, fg_color="transparent")
        bubble_container.pack(side="right", anchor="e")

        label = ctk.CTkLabel(
            bubble_container,
            text=t("user_label"),
            font=FONT_SMALL,
            text_color=COLOR_MUTED_TEXT,
            anchor="e",
        )
        label.pack(fill="x", anchor="e", padx=4, pady=(0, 2))

        bubble = ctk.CTkFrame(
            bubble_container,
            fg_color=COLOR_USER_BUBBLE,
            border_width=1,
            border_color="#1E3A8A",
            corner_radius=6,
        )
        bubble.pack(side="right", anchor="e")

        msg_label = ctk.CTkLabel(
            bubble,
            text=text,
            font=FONT_BODY,
            text_color=COLOR_PRIMARY_TEXT,
            wraplength=600,
            justify="left",
            anchor="w",
        )
        msg_label.pack(padx=14, pady=10)

        self._scroll_to_bottom()

    def add_assistant_message(self, text: str) -> None:
        """
        Add assistant message on the left as plain text with label 'Zeno' and no background.
        Fenced code blocks are extracted and rendered with Copy buttons.
        """
        if ctk is None:
            return

        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row.pack(fill="x", pady=6)

        label = ctk.CTkLabel(
            row,
            text=t("assistant_label"),
            font=FONT_BODY_BOLD,
            text_color=COLOR_PRIMARY_TEXT,
            anchor="w",
        )
        label.pack(fill="x", anchor="w", padx=4, pady=(0, 4))

        # Parse markdown code blocks: ```lang ... ```
        segments = self._parse_message_segments(text)
        for seg_type, lang, content in segments:
            if seg_type == "code":
                self._render_code_block(row, lang, content)
            else:
                if content.strip():
                    text_label = ctk.CTkLabel(
                        row,
                        text=content.strip(),
                        font=FONT_BODY,
                        text_color=COLOR_PRIMARY_TEXT,
                        wraplength=720,
                        justify="left",
                        anchor="w",
                    )
                    text_label.pack(fill="x", anchor="w", padx=4, pady=2)

        self._scroll_to_bottom()

    def add_tool_used_line(self, line: str) -> None:
        """Add plain line in chat for tool usage."""
        if ctk is None:
            return

        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)

        line_label = ctk.CTkLabel(
            row,
            text=line,
            font=FONT_SMALL,
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
        )
        line_label.pack(fill="x", anchor="w", padx=6)

        self._scroll_to_bottom()

    def add_system_notice(self, notice: str) -> None:
        """Add center muted system notice."""
        if ctk is None:
            return

        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row.pack(fill="x", pady=8)

        notice_label = ctk.CTkLabel(
            row,
            text=notice,
            font=FONT_SMALL,
            text_color=COLOR_MUTED_TEXT,
            anchor="center",
        )
        notice_label.pack(fill="x")

        self._scroll_to_bottom()

    def _render_code_block(self, parent: any, lang: str, code: str) -> None:
        """Render code block with background #0F0F13, 1px border, language name, and Copy button."""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_CODE_BG,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=4,
        )
        card.pack(fill="x", expand=True, padx=4, pady=6)

        # Header bar
        header = ctk.CTkFrame(card, fg_color="#14141A", height=28, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        lang_label = ctk.CTkLabel(
            header,
            text=lang.lower() if lang else "code",
            font=FONT_CODE_TITLE,
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
        )
        lang_label.pack(side="left", padx=10)

        copy_btn = ctk.CTkButton(
            header,
            text=t("copy_code"),
            font=FONT_SMALL,
            fg_color="transparent",
            hover_color="#22222E",
            text_color=COLOR_PRIMARY_TEXT,
            width=50,
            height=24,
            corner_radius=3,
        )
        copy_btn.pack(side="right", padx=6)

        def _do_copy() -> None:
            if pyperclip is not None:
                pyperclip.copy(code)
            copy_btn.configure(text=t("copied_code"))
            self.parent.after(2000, lambda: copy_btn.configure(text=t("copy_code")))

        copy_btn.configure(command=_do_copy)

        # Code body
        code_box = ctk.CTkTextbox(
            card,
            fg_color="transparent",
            text_color="#CBD5E1",
            font=FONT_CODE,
            wrap="none",
            height=max(40, min(300, len(code.splitlines()) * 18 + 12)),
            corner_radius=0,
            border_width=0,
        )
        code_box.pack(fill="x", padx=10, pady=(6, 8))
        code_box.insert("1.0", code)
        code_box.configure(state="disabled")

    def _parse_message_segments(self, text: str) -> list[tuple[str, str, str]]:
        """Split text into ('text', '', content) and ('code', lang, code_content)."""
        pattern = re.compile(r"```([a-zA-Z0-9_\-\.\+]*)\n(.*?)```", re.DOTALL)
        segments: list[tuple[str, str, str]] = []
        last_idx = 0

        for match in pattern.finditer(text):
            start, end = match.span()
            if start > last_idx:
                segments.append(("text", "", text[last_idx:start]))
            lang = match.group(1).strip()
            code = match.group(2)
            segments.append(("code", lang, code))
            last_idx = end

        if last_idx < len(text):
            segments.append(("text", "", text[last_idx:]))

        return segments

    def _scroll_to_bottom(self) -> None:
        if ctk is None:
            return
        self.parent.after(50, lambda: self.scroll_frame._parent_canvas.yview_moveto(1.0))
