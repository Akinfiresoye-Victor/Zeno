"""
Persistent Long-Term Memory Engine for Zeno AI Assistant.
Claude/ChatGPT-style structured Markdown storage for user details,
preferences, habits, projects, and custom instructions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from typing import Optional

from zeno.settings import DEFAULT_MODEL, MEMORY_FILE_PATH

DEFAULT_MEMORY_TEMPLATE = """# User Profile & Persistent Memory

## Personal Details
- Assistant: Zeno Personal AI Assistant running locally.

## Preferences & Work Habits
- Tone: Direct, concise, technical, and helpful without unnecessary conversational fluff.
- Code style: Modern, typed, robust error handling, fenced code blocks.

## Projects & Context
- Active Workspace: Local laptop projects and development.

## Custom Instructions & Rules
- When asked hardware questions (e.g., battery), answer only the specific item requested.
- Autonomous agent tools must actively execute real file and system actions.
"""


def load_memory() -> str:
    """Read the active memory markdown file. Creates default if it does not exist."""
    try:
        if not MEMORY_FILE_PATH.exists():
            MEMORY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_FILE_PATH.write_text(DEFAULT_MEMORY_TEMPLATE, encoding="utf-8")
            return DEFAULT_MEMORY_TEMPLATE
        return MEMORY_FILE_PATH.read_text(encoding="utf-8")
    except Exception as exc:
        return f"Error loading memory: {exc}"


def save_memory(content: str) -> bool:
    """Overwrite the memory markdown file with updated content."""
    try:
        MEMORY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE_PATH.write_text(content.strip() + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def append_memory(fact: str, category: str = "General") -> bool:
    """
    Append an acquired fact to the appropriate section in the memory markdown.
    """
    fact = fact.strip()
    if not fact:
        return False

    current = load_memory()
    clean_fact = fact if fact.startswith("- ") else f"- {fact}"

    # Target heading match
    header_patterns = {
        "personal": r"(##\s*Personal Details.*?\n)",
        "preferences": r"(##\s*Preferences & Work Habits.*?\n)",
        "projects": r"(##\s*Projects & Context.*?\n)",
        "instructions": r"(##\s*Custom Instructions & Rules.*?\n)",
    }

    matched_key = None
    cat_lower = category.lower()
    for key in header_patterns:
        if key in cat_lower:
            matched_key = key
            break

    if matched_key and re.search(header_patterns[matched_key], current, re.IGNORECASE):
        # Insert after heading
        pattern = header_patterns[matched_key]
        replacement = r"\g<1>" + clean_fact + "\n"
        updated = re.sub(pattern, replacement, current, count=1, flags=re.IGNORECASE)
    else:
        # Append to the end
        if f"## {category}" in current:
            updated = current.replace(f"## {category}", f"## {category}\n{clean_fact}")
        else:
            updated = f"{current}\n\n## {category}\n{clean_fact}\n"

    return save_memory(updated)


def clear_memory() -> bool:
    """Reset memory back to default template."""
    return save_memory(DEFAULT_MEMORY_TEMPLATE)


def format_memory_for_prompt() -> str:
    """Format memory into XML tag block for injection into system instruction."""
    mem = load_memory()
    if not mem or mem.strip() == "":
        return ""
    return (
        f"\n\n<user_memory>\n{mem.strip()}\n</user_memory>\n"
        "The above block is your persistent memory about the user, their preferences, "
        "habits, and projects. Use it seamlessly to personalize your responses, remember "
        "their technical preferences, and recall key facts naturally without repeating the whole memory file back."
    )


def synthesize_memory_with_ai(
    new_notes: Any,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    """
    Send existing memory and imported notes/facts to the AI to intelligently
    synthesize, deduplicate, and organize into clean, structured Markdown sections.
    """
    if isinstance(new_notes, dict):
        notes_str = new_notes.get("notes") or new_notes.get("raw_text") or ""
        if not api_key:
            api_key = str(new_notes.get("customApiKey") or new_notes.get("apiKey") or "")
        if model == DEFAULT_MODEL:
            model = str(new_notes.get("model") or model)
        new_notes = str(notes_str)
    else:
        new_notes = str(new_notes or "")

    current_mem = load_memory()

    prompt = (
        "You are Zeno's neural memory synthesizer. Your task is to update and synthesize "
        "the user's persistent memory file (MEMORY.md) by intelligently integrating new notes, "
        "imported memories, or profile details into the existing memory.\n\n"
        "RULES:\n"
        "1. Output ONLY valid, clean Markdown with structured section headings.\n"
        "2. Categories to maintain:\n"
        "   - # User Profile & Persistent Memory\n"
        "   - ## Personal Details (name, role, background, location/timezone)\n"
        "   - ## Preferences & Work Habits (communication style, coding habits, favorite tools)\n"
        "   - ## Projects & Context (current repos, active projects, goals)\n"
        "   - ## Custom Instructions & Rules (rules Zeno must strictly obey)\n"
        "3. Deduplicate overlapping facts and merge updates intelligently.\n"
        "4. Do NOT output conversational chatter or markdown fences around the entire document. "
        "Start directly with `# User Profile & Persistent Memory`.\n\n"
        f"--- EXISTING MEMORY ---\n{current_mem}\n\n"
        f"--- NEW NOTES / IMPORTED MEMORIES TO MERGE ---\n{new_notes}\n"
    )

    if not api_key or api_key == "your_key_here":
        # Fallback local append if no API key is provided
        fallback_merged = (
            f"{current_mem.strip()}\n\n"
            f"## Imported Memories\n"
            + "\n".join(f"- {line.strip()}" for line in new_notes.splitlines() if line.strip())
        )
        save_memory(fallback_merged)
        return {"status": "success", "memory": fallback_merged, "source": "local"}

    # Attempt AI synthesis via google-genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        candidates = [model, "gemini-2.5-flash-lite"]
        for c in candidates:
            try:
                resp = client.models.generate_content(
                    model=c,
                    contents=prompt,
                    config=types.GenerateContentConfig(max_output_tokens=2048, temperature=0.2),
                )
                text = resp.text or ""
                # Strip markdown code block wrapper if model wrapped it
                clean_text = re.sub(r"^```markdown\s*", "", text)
                clean_text = re.sub(r"```\s*$", "", clean_text).strip()
                if clean_text.startswith("#"):
                    save_memory(clean_text)
                    return {"status": "success", "memory": clean_text, "source": "ai"}
            except Exception:
                continue
    except Exception:
        pass

    # REST fallback
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.2},
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            clean_text = re.sub(r"^```markdown\s*", "", text)
            clean_text = re.sub(r"```\s*$", "", clean_text).strip()
            if clean_text.startswith("#"):
                save_memory(clean_text)
                return {"status": "success", "memory": clean_text, "source": "ai"}
    except Exception:
        pass

    # Fallback to local append
    fallback_merged = (
        f"{current_mem.strip()}\n\n"
        f"## Imported Notes\n"
        + "\n".join(f"- {line.strip()}" for line in new_notes.splitlines() if line.strip())
    )
    save_memory(fallback_merged)
    return {"status": "success", "memory": fallback_merged, "source": "local"}
