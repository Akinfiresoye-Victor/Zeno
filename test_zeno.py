"""
Comprehensive unit test suite for Zeno core logic, security, safety checker, and tools.
"""

import json
import os
from pathlib import Path
import time
import unittest

from zeno.audit import log_tool_action, sanitize_text
from zeno.chat_manager import (
    generate_chat_topic,
    process_chat_retention,
    unflag_chat,
)
from zeno.i18n import t
from zeno.permissions import (
    CATEGORIES,
    is_category_allowed,
    request_permission_if_needed,
    set_category_permission,
)
from zeno.safety_checker import (
    CodeSafetyStatus,
    analyze_python_code_ast,
    verify_code_safety,
)
from zeno.settings import ALLOWED_FOLDERS, HOME_DIR
from zeno.tools import ALL_TOOLS, TOOL_CATEGORIES, TOOL_REGISTRY
from zeno.tools.file_tools import validate_and_resolve_path
from zeno.tools.python_tools import run_python
from zeno.tools.workspace_tools import create_project_workspace


class TestZenoExtended(unittest.TestCase):

    def test_safety_checker_blocks_destructive_commands(self):
        # Critical destructive wipe
        code_dangerous = "import os\nos.system('rm -rf /')"
        status, reason = analyze_python_code_ast(code_dangerous)
        self.assertEqual(status, CodeSafetyStatus.DANGEROUS)

        # Accessing .env
        code_env = "with open('.env') as f:\n    key = f.read()"
        status, reason = analyze_python_code_ast(code_env)
        self.assertEqual(status, CodeSafetyStatus.DANGEROUS)

        # Safe arithmetic code
        code_safe = "x = [i**2 for i in range(10)]\nprint(sum(x))"
        status, reason = analyze_python_code_ast(code_safe)
        self.assertEqual(status, CodeSafetyStatus.SAFE)

    def test_multi_threaded_safety_verification(self):
        # Safe code auto-approved
        is_safe, msg = verify_code_safety("print('hello world')", auto_approve=True)
        self.assertTrue(is_safe)

        # Dangerous code blocked
        is_safe, msg = verify_code_safety("rm -rf /", auto_approve=True)
        self.assertFalse(is_safe)

    def test_chat_retention_flagging_and_purging(self):
        now = 1000000.0
        day = 86400.0

        chats = [
            {"id": "c1", "title": "Active Chat", "last_activity": now - (1 * day), "flagged_for_deletion": False},
            {"id": "c2", "title": "Old Chat", "last_activity": now - (3.5 * day), "flagged_for_deletion": False},
            {"id": "c3", "title": "Dead Chat", "last_activity": now - (4.2 * day), "flagged_for_deletion": True},
        ]

        retained, purged = process_chat_retention(chats, current_time_epoch=now)

        # c3 should be purged (>= 4 days and flagged)
        self.assertIn("c3", purged)

        # c2 should be flagged for deletion (>= 3 days)
        c2 = next(c for c in retained if c["id"] == "c2")
        self.assertTrue(c2["flagged_for_deletion"])

        # Unflagging chat resets activity
        unflagged = unflag_chat(c2)
        self.assertFalse(unflagged["flagged_for_deletion"])

    def test_ai_topic_generation(self):
        topic_battery = generate_chat_topic("Can you check what my battery level is?")
        self.assertEqual(topic_battery, "System Diagnostic & Specs")

        topic_screen = generate_chat_topic("Capture my browser tab on screen")
        self.assertEqual(topic_screen, "Screen & Tab Capture")

        topic_doc = generate_chat_topic("Write summary of downloads to summary.docx")
        self.assertEqual(topic_doc, "Document Synthesis & Export")

    def test_project_workspace_creation(self):
        ws = create_project_workspace("TestProject_UnitTest")
        self.assertEqual(ws["project_name"], "TestProject_UnitTest")
        self.assertTrue(Path(ws["project_root"]).exists())
        self.assertIn("src", ws["subfolders"])
        self.assertIn("docs", ws["subfolders"])

    def test_sandbox_path_validation(self):
        # Traversal blocked
        with self.assertRaises(PermissionError):
            validate_and_resolve_path("Documents/../../../../etc/passwd")

        # Allowed path
        p = validate_and_resolve_path("Documents/notes.txt")
        self.assertTrue(str(p).endswith("notes.txt"))


if __name__ == "__main__":
    unittest.main()
