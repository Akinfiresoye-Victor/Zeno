"""
Full-panel Settings view with dynamic 3-provider checklist slots,
default workspace directory, AI safety auto-approve toggle, model thinking level,
and permission category switches.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from zeno.i18n import t
from zeno.permissions import (
    CATEGORIES,
    get_category_description,
    is_category_allowed,
    load_permissions,
    set_category_permission,
)
from zeno.settings import (
    API_KEY_PROVIDERS,
    DEFAULT_MODEL,
    DEFAULT_WORKSPACE_DIR,
    ENV_FILE_PATH,
    SUPPORTED_MODELS,
)
from zeno.theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_INPUT_CARD,
    COLOR_MAIN_BG,
    COLOR_MUTED_TEXT,
    COLOR_PRIMARY_TEXT,
    COLOR_SUCCESS,
    FONT_BODY,
    FONT_BODY_BOLD,
    FONT_HEADING,
    FONT_SMALL,
    FONT_TITLE,
)


class SettingsView:
    """
    Full-panel desktop configuration view with dynamic 3-slot API key checklist.
    """

    def __init__(
        self,
        parent: any,
        on_back: Callable[[], None],
        on_settings_saved: Callable[[str, str, bool, str], None],
    ) -> None:
        self.parent = parent
        self.on_back = on_back
        self.on_settings_saved = on_settings_saved
        self._switches: dict[str, ctk.CTkSwitch] = {}

        if ctk is None:
            return

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=COLOR_MAIN_BG,
            corner_radius=0,
        )

        # Header bar with Back button
        header = ctk.CTkFrame(self.frame, fg_color="#111115", height=48, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        back_btn = ctk.CTkButton(
            header,
            text=f"< {t('settings_back')}",
            font=FONT_BODY_BOLD,
            fg_color="transparent",
            hover_color="#1E1E26",
            text_color=COLOR_ACCENT_BLUE,
            width=70,
            height=32,
            corner_radius=4,
            command=self.on_back,
        )
        back_btn.pack(side="left", padx=12, pady=8)

        title_label = ctk.CTkLabel(
            header,
            text=t("settings_title"),
            font=FONT_TITLE,
            text_color=COLOR_PRIMARY_TEXT,
            anchor="w",
        )
        title_label.pack(side="left", padx=8)

        # Scrollable content area
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.frame,
            fg_color="transparent",
            scrollbar_button_color=COLOR_BORDER,
            scrollbar_button_hover_color=COLOR_MUTED_TEXT,
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=24, pady=16)

        # Section 1: Active Model & Thinking Level
        self._build_model_section()

        # Section 2: 3 Dynamic Provider API Key Slots (Checklist System)
        self._build_dynamic_api_keys_section()

        # Section 3: Workspace & AI Safety Guard
        self._build_workspace_safety_section()

        # Section 4: Tool Permissions
        self._build_permissions_section()

    def _build_model_section(self) -> None:
        sec = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_INPUT_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        sec.pack(fill="x", pady=(0, 16), padx=4)

        sec_title = ctk.CTkLabel(sec, text="Model & Reasoning Configuration", font=FONT_HEADING, text_color=COLOR_PRIMARY_TEXT, anchor="w")
        sec_title.pack(fill="x", padx=16, pady=(14, 10))

        # Model selector
        lbl = ctk.CTkLabel(sec, text="Primary Model", font=FONT_BODY, text_color=COLOR_MUTED_TEXT, anchor="w")
        lbl.pack(fill="x", padx=16, pady=(0, 4))

        self.model_var = ctk.StringVar(value=DEFAULT_MODEL)
        self.model_dropdown = ctk.CTkOptionMenu(
            sec,
            variable=self.model_var,
            values=SUPPORTED_MODELS,
            fg_color="#22222E",
            button_color=COLOR_ACCENT_BLUE,
            button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_PRIMARY_TEXT,
            font=FONT_BODY,
            height=32,
        )
        self.model_dropdown.pack(fill="x", padx=16, pady=(0, 10))

        # Thinking Level selector
        lbl_thinking = ctk.CTkLabel(sec, text="Thinking / Reasoning Level", font=FONT_BODY, text_color=COLOR_MUTED_TEXT, anchor="w")
        lbl_thinking.pack(fill="x", padx=16, pady=(0, 4))

        self.thinking_var = ctk.StringVar(value="MEDIUM")
        self.thinking_dropdown = ctk.CTkOptionMenu(
            sec,
            variable=self.thinking_var,
            values=["MINIMAL", "LOW", "MEDIUM", "HIGH"],
            fg_color="#22222E",
            button_color=COLOR_ACCENT_BLUE,
            button_hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_PRIMARY_TEXT,
            font=FONT_BODY,
            height=32,
        )
        self.thinking_dropdown.pack(fill="x", padx=16, pady=(0, 12))

        # Auto-switch toggle
        self.autoswitch_var = ctk.BooleanVar(value=True)
        self.autoswitch_switch = ctk.CTkSwitch(
            sec,
            text="Auto-switch models when rate limited or quota exhausted",
            font=FONT_BODY,
            variable=self.autoswitch_var,
            progress_color=COLOR_ACCENT_BLUE,
            text_color=COLOR_PRIMARY_TEXT,
        )
        self.autoswitch_switch.pack(anchor="w", padx=16, pady=(0, 16))

    def _build_dynamic_api_keys_section(self) -> None:
        sec = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_INPUT_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        sec.pack(fill="x", pady=(0, 16), padx=4)

        sec_title = ctk.CTkLabel(sec, text="API Keys (Up to 3 Provider Slots)", font=FONT_HEADING, text_color=COLOR_PRIMARY_TEXT, anchor="w")
        sec_title.pack(fill="x", padx=16, pady=(14, 6))

        sub_desc = ctk.CTkLabel(
            sec,
            text="Configure up to 3 custom API keys. Choose the provider for each slot and enter your key below.",
            font=FONT_SMALL,
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
            wraplength=480,
            justify="left",
        )
        sub_desc.pack(fill="x", padx=16, pady=(0, 12))

        load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)

        self.slots = []
        default_providers = ["Gemini", "OpenRouter", "Anthropic Claude"]
        default_keys = [
            os.getenv("GEMINI_API_KEY", ""),
            os.getenv("OPENROUTER_API_KEY", ""),
            os.getenv("ANTHROPIC_API_KEY", ""),
        ]

        for i in range(3):
            slot_frame = ctk.CTkFrame(sec, fg_color="#131318", border_width=1, border_color=COLOR_BORDER, corner_radius=4)
            slot_frame.pack(fill="x", padx=16, pady=6)

            top_row = ctk.CTkFrame(slot_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=12, pady=(8, 4))

            slot_label = ctk.CTkLabel(top_row, text=f"Key Slot {i + 1}", font=FONT_BODY_BOLD, text_color=COLOR_PRIMARY_TEXT)
            slot_label.pack(side="left")

            prov_var = ctk.StringVar(value=default_providers[i])
            prov_menu = ctk.CTkOptionMenu(
                top_row,
                variable=prov_var,
                values=API_KEY_PROVIDERS,
                fg_color="#1E1E26",
                button_color=COLOR_ACCENT_BLUE,
                text_color=COLOR_PRIMARY_TEXT,
                height=26,
                width=140,
            )
            prov_menu.pack(side="right")

            key_entry = ctk.CTkEntry(
                slot_frame,
                placeholder_text="Enter API key for selected provider...",
                font=FONT_BODY,
                fg_color="#0F0F13",
                border_width=1,
                border_color=COLOR_BORDER,
                text_color=COLOR_PRIMARY_TEXT,
                show="*",
                height=30,
            )
            key_entry.pack(fill="x", padx=12, pady=(0, 10))
            if default_keys[i]:
                key_entry.insert(0, default_keys[i])

            self.slots.append((prov_var, key_entry))

        # Save button & Status
        btn_row = ctk.CTkFrame(sec, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 16))

        save_btn = ctk.CTkButton(
            btn_row,
            text=t("settings_save_button"),
            font=FONT_BODY_BOLD,
            fg_color=COLOR_ACCENT_BLUE,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#FFFFFF",
            width=120,
            height=32,
            corner_radius=4,
            command=self._save_settings,
        )
        save_btn.pack(side="left")

        self.save_status_label = ctk.CTkLabel(
            btn_row,
            text="",
            font=FONT_SMALL,
            text_color=COLOR_SUCCESS,
            anchor="w",
        )
        self.save_status_label.pack(side="left", padx=12)

    def _build_workspace_safety_section(self) -> None:
        sec = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_INPUT_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        sec.pack(fill="x", pady=(0, 16), padx=4)

        sec_title = ctk.CTkLabel(sec, text="Workspace & AI Safety Guard", font=FONT_HEADING, text_color=COLOR_PRIMARY_TEXT, anchor="w")
        sec_title.pack(fill="x", padx=16, pady=(14, 10))

        # Workspace directory
        lbl = ctk.CTkLabel(sec, text="Default AI Project Workspace Directory", font=FONT_BODY, text_color=COLOR_MUTED_TEXT, anchor="w")
        lbl.pack(fill="x", padx=16, pady=(0, 4))

        self.workspace_entry = ctk.CTkEntry(
            sec,
            font=FONT_BODY,
            fg_color="#0F0F13",
            border_width=1,
            border_color=COLOR_BORDER,
            text_color=COLOR_PRIMARY_TEXT,
            height=30,
        )
        self.workspace_entry.pack(fill="x", padx=16, pady=(0, 12))
        self.workspace_entry.insert(0, str(DEFAULT_WORKSPACE_DIR))

        # AI Safety Auto-Approve switch
        self.auto_approve_var = ctk.BooleanVar(value=True)
        self.auto_approve_switch = ctk.CTkSwitch(
            sec,
            text="AI Safety Guard: Auto-Approve safe operations with secondary AI verification",
            font=FONT_BODY,
            variable=self.auto_approve_var,
            progress_color=COLOR_ACCENT_BLUE,
            text_color=COLOR_PRIMARY_TEXT,
        )
        self.auto_approve_switch.pack(anchor="w", padx=16, pady=(0, 8))

        safety_desc = ctk.CTkLabel(
            sec,
            text="A secondary AI safety thread audits code before execution. Only actions deleting system files or exposing keys are halted.",
            font=FONT_SMALL,
            text_color=COLOR_MUTED_TEXT,
            anchor="w",
            wraplength=480,
            justify="left",
        )
        safety_desc.pack(fill="x", padx=16, pady=(0, 16))

    def _build_permissions_section(self) -> None:
        sec = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_INPUT_CARD, border_width=1, border_color=COLOR_BORDER, corner_radius=6)
        sec.pack(fill="x", pady=(0, 16), padx=4)

        sec_title = ctk.CTkLabel(sec, text=t("settings_permissions_section"), font=FONT_HEADING, text_color=COLOR_PRIMARY_TEXT, anchor="w")
        sec_title.pack(fill="x", padx=16, pady=(14, 10))

        load_permissions()
        for cat in CATEGORIES:
            row = ctk.CTkFrame(sec, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=8)

            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True)

            cat_label = ctk.CTkLabel(info_frame, text=cat, font=FONT_BODY_BOLD, text_color=COLOR_PRIMARY_TEXT, anchor="w")
            cat_label.pack(fill="x")

            desc = get_category_description(cat)
            desc_label = ctk.CTkLabel(info_frame, text=desc, font=FONT_SMALL, text_color=COLOR_MUTED_TEXT, anchor="w", wraplength=480, justify="left")
            desc_label.pack(fill="x", pady=(2, 0))

            is_on = is_category_allowed(cat)
            switch = ctk.CTkSwitch(
                row,
                text="",
                width=46,
                progress_color=COLOR_ACCENT_BLUE,
                command=lambda c=cat: self._on_permission_toggle(c),
            )
            switch.pack(side="right", padx=(8, 0))
            if is_on:
                switch.select()
            else:
                switch.deselect()

            self._switches[cat] = switch

    def _on_permission_toggle(self, category: str) -> None:
        switch = self._switches.get(category)
        if not switch:
            return
        allowed = bool(switch.get())
        set_category_permission(category, allowed)

    def _save_settings(self) -> None:
        # Save dynamic slots into .env
        env_lines = []
        if ENV_FILE_PATH.exists():
            try:
                with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if any(stripped.startswith(k) for k in [
                            "GEMINI_API_KEY=", "OPENROUTER_API_KEY=", "ANTHROPIC_API_KEY=", "OPENAI_API_KEY=", "GROQ_API_KEY="
                        ]):
                            continue
                        env_lines.append(line)
            except Exception:
                pass

        provider_map = {
            "Gemini": "GEMINI_API_KEY",
            "Anthropic Claude": "ANTHROPIC_API_KEY",
            "OpenRouter": "OPENROUTER_API_KEY",
            "OpenAI": "OPENAI_API_KEY",
            "Groq": "GROQ_API_KEY",
        }

        for prov_var, key_entry in self.slots:
            prov = prov_var.get()
            key_val = key_entry.get().strip()
            env_var_name = provider_map.get(prov, f"{prov.upper()}_API_KEY")
            if key_val:
                env_lines.append(f"{env_var_name}={key_val}\n")
                os.environ[env_var_name] = key_val

        with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
            f.writelines(env_lines)

        selected_model = self.model_var.get()
        selected_thinking = self.thinking_var.get()
        autoswitch = bool(self.autoswitch_var.get())
        workspace_dir = self.workspace_entry.get().strip()

        self.on_settings_saved(selected_model, selected_thinking, autoswitch, workspace_dir)

        self.save_status_label.configure(text=t("settings_saved_notice"))
        self.parent.after(3000, lambda: self.save_status_label.configure(text=""))
