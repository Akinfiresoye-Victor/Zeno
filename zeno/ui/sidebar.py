"""
Sidebar component (240px) with New Chat, chat search, session chat list, and Settings button.
Active chat displays a distinctive blue left accent border.
"""

from __future__ import annotations

from typing import Callable, Optional

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.i18n import t
from zeno.settings import SIDEBAR_WIDTH
from zeno.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_INPUT_CARD,
    COLOR_MAIN_BG,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    COLOR_SIDEBAR_PANEL,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_SMALL,
)


class Sidebar:
    """
    240px navigation sidebar managing conversation sessions.
    """

    def __init__(
        self,
        parent: any,
        on_new_chat: Callable[[], None],
        on_select_chat: Callable[[str], None],
        on_open_settings: Callable[[], None],
    ) -> None:
        self.parent = parent
        self.on_new_chat = on_new_chat
        self.on_select_chat = on_select_chat
        self.on_open_settings = on_open_settings

        self.chats: list[dict[str, str]] = []
        self.active_chat_id: Optional[str] = None
        self.is_visible: bool = True
        self._chat_buttons: dict[str, ctk.CTkFrame] = {}

        if ctk is None:
            return

        self.frame = ctk.CTkFrame(
            parent,
            width=SIDEBAR_WIDTH,
            fg_color=COLOR_SIDEBAR_PANEL,
            border_width=1,
            border_color=COLOR_BORDER,
            corner_radius=0,
        )
        self.frame.pack(side="left", fill="y")
        self.frame.pack_propagate(False)

        # Header with App Name and New Chat
        header_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(16, 8))

        app_label = ctk.CTkLabel(
            header_frame,
            text=t("app_title"),
            font=FONT_BODY_BOLD,
            text_color=COLOR_PRIMARY_TEXT,
            anchor="w",
        )
        app_label.pack(side="left")

        # New chat button
        self.new_chat_btn = ctk.CTkButton(
            self.frame,
            text=t("new_chat"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            height=32,
            corner_radius=4,
            command=self._handle_new_chat,
        )
        self.new_chat_btn.pack(fill="x", padx=12, pady=(8, 8))

        # Search box
        self.search_entry = ctk.CTkEntry(
            self.frame,
            placeholder_text=t("search_placeholder"),
            font=FONT_SMALL,
            fg_color=COLOR_INPUT_CARD,
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_PRIMARY_TEXT,
            placeholder_text_color=COLOR_MUTED_TEXT,
            height=30,
            corner_radius=4,
        )
        self.search_entry.pack(fill="x", padx=12, pady=(0, 12))
        self.search_entry.bind("<KeyRelease>", self._handle_search)

        # Scrollable chats list
        self.chat_list_frame = ctk.CTkScrollableFrame(
            self.frame,
            fg_color="transparent",
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_MUTED_TEXT,
        )
        self.chat_list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        # Bottom footer with Settings link
        footer_frame = ctk.CTkFrame(
            self.frame,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_BORDER,
            height=44,
        )
        footer_frame.pack(side="bottom", fill="x", padx=8, pady=8)

        settings_btn = ctk.CTkButton(
            footer_frame,
            text=t("settings_title"),
            font=FONT_BODY,
            fg_color="transparent",
            hover_color="#1E1E26",
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
            height=32,
            corner_radius=4,
            command=self.on_open_settings,
        )
        settings_btn.pack(fill="x", padx=4, pady=4)

    def _handle_new_chat(self) -> None:
        self.on_new_chat()

    def _handle_search(self, event: any) -> None:
        query = self.search_entry.get().lower().strip()
        self._render_chats(query)

    def set_chats(self, chats: list[dict[str, str]], active_id: str) -> None:
        """Update chats collection and re-render."""
        self.chats = chats
        self.active_chat_id = active_id
        if ctk is None:
            return
        query = self.search_entry.get().lower().strip()
        self._render_chats(query)

    def _render_chats(self, query: str = "") -> None:
        if ctk is None:
            return

        for child in self.chat_list_frame.winfo_children():
            child.destroy()
        self._chat_buttons.clear()

        for chat in self.chats:
            chat_id = chat["id"]
            title = chat.get("title", "New Conversation")
            if query and query not in title.lower():
                continue

            is_active = (chat_id == self.active_chat_id)

            # Container row
            row_frame = ctk.CTkFrame(
                self.chat_list_frame,
                fg_color="#181820" if is_active else "transparent",
                corner_radius=4,
                height=34,
            )
            row_frame.pack(fill="x", pady=2)
            row_frame.pack_propagate(False)

            # Left border accent if active
            if is_active:
                indicator = ctk.CTkFrame(
                    row_frame,
                    width=3,
                    fg_color=COLOR_ACCENT_BLUE,
                    corner_radius=0,
                )
                indicator.pack(side="left", fill="y")

            btn = ctk.CTkButton(
                row_frame,
                text=title,
                font=FONT_BODY if not is_active else FONT_BODY_BOLD,
                fg_color="transparent",
                hover_color="#1D1D27",
                text_color=COLOR_PRIMARY_TEXT if is_active else COLOR_MUTED_TEXT,
                anchor="w",
                corner_radius=4,
                command=lambda cid=chat_id: self.on_select_chat(cid),
            )
            btn.pack(side="left", fill="both", expand=True, padx=(4, 4))
            self._chat_buttons[chat_id] = row_frame

    def toggle(self) -> bool:
        """Toggle sidebar visibility."""
        if ctk is None:
            return False
        if self.is_visible:
            self.frame.pack_forget()
            self.is_visible = False
        else:
            self.frame.pack(side="left", fill="y", before=self.parent.winfo_children()[0])
            self.is_visible = True
        return self.is_visible
