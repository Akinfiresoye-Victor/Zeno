"""
Main application window layout for Zeno Desktop AI Assistant.
Features:
- Dual Modes: Desktop Chat View vs Agentic Worker View
- In-chat Model & Thinking Level Selector
- Multi-step Agentic Planning with 'Give Plan to Agent to Work On' execution bridge
- Real-time Progress Tracking (Current Action & Next Action)
- Human Safety Review Modal for sensitive operations
- 3-day inactivity deletion flagging with 24-hour grace period and 'Keep' action
- Background threading for seamless responsiveness
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional
import uuid

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.agent import ZenoAgent
from zeno.chat_manager import (
    generate_chat_topic,
    load_chats_metadata,
    process_chat_retention,
    save_chats_metadata,
    unflag_chat,
)
from zeno.i18n import t
from zeno.settings import (
    DEFAULT_MODEL,
    DEFAULT_THINKING_LEVEL,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    TOPBAR_HEIGHT,
)
from zeno.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_ERROR,
    COLOR_INPUT_CARD,
    COLOR_MAIN_BG,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    COLOR_SUCCESS,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_SMALL,
    FONT_STATUS,
)
from zeno.ui.chat_view import ChatView
from zeno.ui.input_bar import InputBar
from zeno.ui.permission_dialog import ConfirmDestructiveDialog, PermissionDialog
from zeno.ui.settings_view import SettingsView
from zeno.ui.sidebar import Sidebar
from zeno.ui.status_bar import StatusBar


class HumanReviewModal:
    """Modal for human review of sensitive code/actions."""

    def __init__(self, parent: any, code: str, reason: str) -> None:
        self.result = False
        if ctk is None:
            return

        self.top = ctk.CTkToplevel(parent)
        self.top.title("Human Safety Review Required")
        self.top.geometry("520x360")
        self.top.resizable(False, False)
        self.top.configure(fg_color=COLOR_MAIN_BG)

        self.top.transient(parent)
        self.top.grab_set()

        frame = ctk.CTkFrame(self.top, fg_color=COLOR_INPUT_CARD, border_width=1, border_color=COLOR_BORDER)
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        title_lbl = ctk.CTkLabel(frame, text="Security Review Escalation", font=FONT_HEADING, text_color=COLOR_ERROR, anchor="w")
        title_lbl.pack(fill="x", padx=16, pady=(14, 4))

        reason_lbl = ctk.CTkLabel(frame, text=reason, font=FONT_BODY, text_color=COLOR_PRIMARY_TEXT, anchor="w", wraplength=460)
        reason_lbl.pack(fill="x", padx=16, pady=(0, 10))

        code_box = ctk.CTkTextbox(frame, fg_color="#0F0F13", text_color="#CBD5E1", height=140, corner_radius=4)
        code_box.pack(fill="x", padx=16, pady=(0, 16))
        code_box.insert("1.0", code)
        code_box.configure(state="disabled")

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        deny_btn = ctk.CTkButton(
            btn_row, text="Block Action", font=FONT_BODY_BOLD, fg_color="#2A2A34",
            hover_color="#3A3A46", width=120, height=32, command=self._deny
        )
        deny_btn.pack(side="right", padx=(8, 0))

        approve_btn = ctk.CTkButton(
            btn_row, text="Approve & Run", font=FONT_BODY_BOLD, fg_color=COLOR_ERROR,
            hover_color="#DC2626", width=120, height=32, command=self._approve
        )
        approve_btn.pack(side="right")

        self.top.protocol("WM_DELETE_WINDOW", self._deny)
        parent.wait_window(self.top)

    def _approve(self) -> None:
        self.result = True
        self.top.destroy()

    def _deny(self) -> None:
        self.result = False
        self.top.destroy()


class ZenoAppWindow:
    """Primary desktop window with Dual Chat / Agentic modes."""

    def __init__(self, root: any) -> None:
        self.root = root
        if ctk is None:
            return

        self.root.title("Zeno")
        self.root.geometry(f"{MIN_WINDOW_WIDTH}x{MIN_WINDOW_HEIGHT}")
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.root.configure(fg_color=COLOR_MAIN_BG)

        # Mode State: 'chat' vs 'agentic'
        self.current_mode: str = "chat"
        self.active_model_name: str = DEFAULT_MODEL
        self.active_thinking_level: str = DEFAULT_THINKING_LEVEL

        # Chat session management and retention
        saved_metadata = load_chats_metadata()
        retained_chats, _ = process_chat_retention(saved_metadata)
        self.sessions: list[dict[str, any]] = retained_chats or []
        self.active_session_id: str = str(uuid.uuid4())

        # Initialize agent
        self.agent = ZenoAgent(
            on_tool_used=self._on_agent_tool_used,
            on_status_change=self._on_agent_status_change,
            on_progress_update=self._on_progress_update,
            permission_dialog_callback=self._show_permission_dialog_modal,
            confirm_dialog_callback=self._show_confirm_dialog_modal,
            human_review_callback=self._show_human_review_modal,
        )

        self._build_layout()
        if not self.sessions:
            self._create_new_session(initial=True)
        else:
            self.active_session_id = self.sessions[0]["id"]
            self._switch_session(self.active_session_id)

    def _build_layout(self) -> None:
        # Left Sidebar (240 px)
        self.sidebar = Sidebar(
            self.root,
            on_new_chat=self._create_new_session,
            on_select_chat=self._switch_session,
            on_open_settings=self._show_settings_panel,
        )

        # Main Workspace
        self.main_container = ctk.CTkFrame(self.root, fg_color=COLOR_MAIN_BG, corner_radius=0)
        self.main_container.pack(side="right", fill="both", expand=True)

        # Top Bar (48 px)
        self.top_bar = ctk.CTkFrame(self.main_container, height=TOPBAR_HEIGHT, fg_color="#0D0D11", border_width=1, border_color=COLOR_BORDER)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        self.toggle_sidebar_btn = ctk.CTkButton(
            self.top_bar, text=t("hide_sidebar"), font=FONT_SMALL, fg_color="transparent",
            hover_color="#181822", text_color=COLOR_MUTED_TEXT, width=50, height=28, command=self._toggle_sidebar
        )
        self.toggle_sidebar_btn.pack(side="left", padx=(10, 6), pady=10)

        # Mode Selector Buttons: Chat View vs Agentic Worker
        mode_frame = ctk.CTkFrame(self.top_bar, fg_color="#14141A", corner_radius=4)
        mode_frame.pack(side="left", padx=8)

        self.chat_mode_btn = ctk.CTkButton(
            mode_frame, text="Chat Assistant", font=FONT_SMALL, fg_color=COLOR_ACCENT_BLUE,
            text_color="#FFFFFF", width=95, height=26, corner_radius=3, command=lambda: self._set_mode("chat")
        )
        self.chat_mode_btn.pack(side="left", padx=2, pady=2)

        self.agentic_mode_btn = ctk.CTkButton(
            mode_frame, text="Agentic Worker", font=FONT_SMALL, fg_color="transparent",
            text_color=COLOR_MUTED_TEXT, hover_color="#22222E", width=95, height=26, corner_radius=3, command=lambda: self._set_mode("agentic")
        )
        self.agentic_mode_btn.pack(side="left", padx=2, pady=2)

        # Right side: Model and Thinking Level
        controls_frame = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        controls_frame.pack(side="right", padx=12)

        self.thinking_badge = ctk.CTkLabel(controls_frame, text=f"Reasoning: {self.active_thinking_level}", font=FONT_STATUS, text_color=COLOR_MUTED_TEXT)
        self.thinking_badge.pack(side="right", padx=(6, 0))

        self.model_label = ctk.CTkLabel(controls_frame, text=self.active_model_name, font=FONT_SMALL, text_color=COLOR_PRIMARY_TEXT)
        self.model_label.pack(side="right", padx=(0, 6))

        # Bottom Status Bar (24 px)
        self.status_bar = StatusBar(self.main_container)

        # Bottom Input Bar
        self.input_bar = InputBar(
            self.main_container,
            on_send=self._handle_user_send,
            on_stop=self._handle_user_stop,
        )

        # Middle Scrollable Chat View
        self.chat_view = ChatView(self.main_container)

        # Full-panel Settings View
        self.settings_view = SettingsView(
            self.main_container,
            on_back=self._hide_settings_panel,
            on_settings_saved=self._on_settings_saved,
        )

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
        if mode == "chat":
            self.chat_mode_btn.configure(fg_color=COLOR_ACCENT_BLUE, text_color="#FFFFFF")
            self.agentic_mode_btn.configure(fg_color="transparent", text_color=COLOR_MUTED_TEXT)
            self.status_bar.set_status("Ready (Chat Mode)")
        else:
            self.agentic_mode_btn.configure(fg_color=COLOR_ACCENT_BLUE, text_color="#FFFFFF")
            self.chat_mode_btn.configure(fg_color="transparent", text_color=COLOR_MUTED_TEXT)
            self.status_bar.set_status("Ready (Agentic Workspace Mode)")

    def _toggle_sidebar(self) -> None:
        visible = self.sidebar.toggle()
        self.toggle_sidebar_btn.configure(text=t("hide_sidebar") if visible else t("show_sidebar"))

    def _show_settings_panel(self) -> None:
        self.chat_view.scroll_frame.pack_forget()
        self.input_bar.container.pack_forget()
        self.settings_view.frame.pack(fill="both", expand=True)

    def _hide_settings_panel(self) -> None:
        self.settings_view.frame.pack_forget()
        self.chat_view.scroll_frame.pack(fill="both", expand=True, padx=16, pady=8)
        self.input_bar.container.pack(side="bottom", fill="x", padx=16, pady=(8, 12))

    def _on_settings_saved(self, model: str, thinking: str, autoswitch: bool, workspace: str) -> None:
        self.active_model_name = model
        self.active_thinking_level = thinking
        self.model_label.configure(text=model)
        self.thinking_badge.configure(text=f"Reasoning: {thinking}")
        self.agent.active_model = model
        self.agent.thinking_level = thinking
        self.agent.auto_switch_enabled = autoswitch

    def _create_new_session(self, initial: bool = False) -> None:
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "title": "New Conversation",
            "messages": [],
            "created_at": time.time(),
            "last_activity": time.time(),
            "flagged_for_deletion": False,
        }
        self.sessions.insert(0, session)
        self.active_session_id = session_id
        self.agent.history = []

        if not initial:
            self.chat_view.clear()

        self._refresh_sidebar_chats()
        save_chats_metadata(self.sessions)

    def _switch_session(self, session_id: str) -> None:
        target = next((s for s in self.sessions if s["id"] == session_id), None)
        if not target:
            return
        self.active_session_id = session_id
        self.agent.history = list(target["messages"])
        self.chat_view.clear()

        for msg in target["messages"]:
            if msg["role"] == "user":
                self.chat_view.add_user_message(msg["content"])
            else:
                self.chat_view.add_assistant_message(msg["content"])

        self._refresh_sidebar_chats()

    def _refresh_sidebar_chats(self) -> None:
        self.sidebar.set_chats(
            [{"id": s["id"], "title": s["title"]} for s in self.sessions],
            active_id=self.active_session_id,
        )

    def _handle_user_send(self, user_text: str) -> None:
        self.chat_view.add_user_message(user_text)

        active_sess = next((s for s in self.sessions if s["id"] == self.active_session_id), None)
        if active_sess:
            # AI generates intelligent topic based on first message
            if active_sess["title"] == "New Conversation":
                new_topic = generate_chat_topic(user_text)
                active_sess["title"] = new_topic
                self._refresh_sidebar_chats()

            active_sess["last_activity"] = time.time()
            active_sess["flagged_for_deletion"] = False
            active_sess["messages"].append({"role": "user", "content": user_text})
            save_chats_metadata(self.sessions)

        thread = threading.Thread(
            target=self._run_agent_thread,
            args=(user_text, self.current_mode == "agentic"),
            daemon=True,
        )
        thread.start()

    def _run_agent_thread(self, prompt: str, is_agentic: bool) -> None:
        try:
            reply = self.agent.run_user_message(prompt, is_agentic_mode=is_agentic)
            self.root.after(0, lambda: self._on_agent_finished(reply))
        except Exception as exc:
            self.root.after(0, lambda: self._on_agent_finished(f"Error: {exc}"))

    def _on_agent_finished(self, reply: str) -> None:
        self.chat_view.add_assistant_message(reply)
        self.input_bar.set_running(False)
        self.input_bar.focus()

        active_sess = next((s for s in self.sessions if s["id"] == self.active_session_id), None)
        if active_sess:
            active_sess["messages"].append({"role": "assistant", "content": reply})
            save_chats_metadata(self.sessions)

    def _handle_user_stop(self) -> None:
        self.agent.stop()
        self.status_bar.set_status(t("status_stopped"))

    def _on_agent_tool_used(self, line: str) -> None:
        self.root.after(0, lambda: self.chat_view.add_tool_used_line(line))
        self.root.after(0, lambda: self.status_bar.set_status(line))

    def _on_agent_status_change(self, status: str, in_tok: int, out_tok: int) -> None:
        self.root.after(0, lambda: self.status_bar.set_status(status, in_tok, out_tok))

    def _on_progress_update(self, current_action: str, next_action: str) -> None:
        status_msg = f"{current_action} -> Next: {next_action}"
        self.root.after(0, lambda: self.status_bar.set_status(status_msg))

    def _show_permission_dialog_modal(self, category: str, description: str) -> bool:
        res_queue: queue.Queue[bool] = queue.Queue()
        self.root.after(0, lambda: res_queue.put(PermissionDialog(self.root, category, description).result))
        return res_queue.get()

    def _show_confirm_dialog_modal(self, path_str: str) -> bool:
        res_queue: queue.Queue[bool] = queue.Queue()
        self.root.after(0, lambda: res_queue.put(ConfirmDestructiveDialog(self.root, path_str).result))
        return res_queue.get()

    def _show_human_review_modal(self, code: str, reason: str) -> bool:
        res_queue: queue.Queue[bool] = queue.Queue()
        self.root.after(0, lambda: res_queue.put(HumanReviewModal(self.root, code, reason).result))
        return res_queue.get()
