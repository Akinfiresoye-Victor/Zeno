"""
Clipboard interaction tools using pyperclip.
Category: clipboard
"""

from __future__ import annotations

try:
    import pyperclip
except ImportError:
    pyperclip = None

from zeno.settings import MAX_CLIPBOARD_CHARS


def read_clipboard() -> str:
    """
    Read text currently on the operating system clipboard.

    Returns:
        str: Clipboard text content, truncated to at most 5000 characters.
    """
    if pyperclip is None:
        raise RuntimeError("pyperclip is not installed. Install with: pip install pyperclip==1.9.0")
    try:
        content = pyperclip.paste() or ""
        if len(content) > MAX_CLIPBOARD_CHARS:
            return content[:MAX_CLIPBOARD_CHARS] + "... (truncated to 5000 chars)"
        return content
    except Exception as exc:
        return f"Error reading clipboard: {exc}"


def write_clipboard(text: str) -> str:
    """
    Write text to the operating system clipboard.

    Args:
        text: The string to copy to the clipboard.

    Returns:
        str: Confirmation message with character count.
    """
    if pyperclip is None:
        raise RuntimeError("pyperclip is not installed. Install with: pip install pyperclip==1.9.0")
    try:
        pyperclip.copy(text)
        return f"Copied {len(text)} characters to clipboard."
    except Exception as exc:
        return f"Error writing to clipboard: {exc}"
