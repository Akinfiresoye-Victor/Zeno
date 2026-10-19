"""
User memory acquisition and recall tools for Zeno.
Category: file_write / file_read
Allows autonomous agent and conversational copilot to remember personal details,
habits, preferences, and project facts.
"""

from __future__ import annotations

from zeno.memory import append_memory, load_memory, save_memory


def save_user_memory(fact: str, category: str = "General") -> str:
    """
    Save an important fact, habit, or preference about the user into persistent memory.
    Use this when the user mentions their name, coding habits, favorite libraries,
    project details, or specific workflow rules.

    Args:
        fact: The specific user detail, preference, or habit to remember (e.g. 'Prefers TypeScript over plain JavaScript').
        category: Section heading: 'Personal Details', 'Preferences & Work Habits', 'Projects & Context', or 'Custom Instructions & Rules'.

    Returns:
        str: Confirmation message that the memory was saved.
    """
    success = append_memory(fact=fact, category=category)
    if success:
        return f"Successfully saved memory under '{category}': {fact}"
    return f"Failed to save memory: {fact}"


def read_user_memory() -> str:
    """
    Read the entire persistent user memory file to recall user preferences,
    past details, active projects, and custom instructions.

    Returns:
        str: The full content of the user memory markdown file.
    """
    return load_memory()
