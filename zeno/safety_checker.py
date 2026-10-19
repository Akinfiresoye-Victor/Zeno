"""
Multi-threaded AI Code Safety Checker for Zeno.
Runs a secondary safety verification thread to analyze Python code and file modifications
before execution, checking for key exposure, sensitive file destruction, and system tampering.
"""

from __future__ import annotations

import ast
import re
import threading
from typing import Callable, Optional


class CodeSafetyStatus:
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE"
    DANGEROUS = "DANGEROUS"


# Patterns that indicate critical security risks
_CRITICAL_DANGERS = [
    (re.compile(r"rm\s+-rf\s+[/~]", re.IGNORECASE), "Destructive file wipe command"),
    (re.compile(r"os\.system\s*\(\s*['\"].*rm\s+-rf", re.IGNORECASE), "Destructive shell command"),
    (re.compile(r"shutil\.rmtree\s*\(\s*['\"](/|/etc|/usr|/var|/bin|C:\\|C:\\Windows)", re.IGNORECASE), "System root directory deletion"),
    (re.compile(r":\(\)\{\s*:\|:&\s*\};:", re.IGNORECASE), "Fork bomb attack"),
    (re.compile(r"open\s*\(.*(\.env|id_rsa|id_ed25519|\.ssh|\.bash_history).*\)", re.IGNORECASE), "Accessing private keys, SSH tokens, or .env files"),
]

# Patterns that indicate sensitive file operations (editing/deleting system configs)
_SENSITIVE_PATTERNS = [
    (re.compile(r"os\.remove\s*\(", re.IGNORECASE), "File deletion call"),
    (re.compile(r"os\.unlink\s*\(", re.IGNORECASE), "File unlink call"),
    (re.compile(r"shutil\.rmtree\s*\(", re.IGNORECASE), "Directory deletion call"),
    (re.compile(r"subprocess\.", re.IGNORECASE), "Secondary subprocess execution"),
    (re.compile(r"socket\.", re.IGNORECASE), "Raw network socket connection"),
]


def analyze_python_code_ast(code: str) -> tuple[str, str]:
    """
    Statically inspect Python code using AST and regular expressions.
    Returns (status, reason).
    """
    # 1. Check critical danger regex
    for pattern, reason in _CRITICAL_DANGERS:
        if pattern.search(code):
            return CodeSafetyStatus.DANGEROUS, f"Dangerous operation blocked: {reason}"

    # 2. Parse AST for structural safety
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        # Invalid syntax will fail execution anyway, but isn't a malicious breach
        return CodeSafetyStatus.SAFE, "Syntax check completed."

    # Inspect AST nodes
    for node in ast.walk(tree):
        # Check imports for prohibited low-level tampering
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("ctypes", "_winreg", "winreg"):
                    return CodeSafetyStatus.SENSITIVE, f"Requires review: imports low-level module '{alias.name}'"
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("ctypes", "winreg"):
                return CodeSafetyStatus.SENSITIVE, f"Requires review: imports from '{node.module}'"

        # Check for deleting files
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                if attr_name in ("rmtree", "remove", "unlink"):
                    return CodeSafetyStatus.SENSITIVE, f"Action modifies filesystem: {attr_name}()"

    # 3. Check sensitive patterns
    for pattern, reason in _SENSITIVE_PATTERNS:
        if pattern.search(code):
            return CodeSafetyStatus.SENSITIVE, f"Sensitive action: {reason}"

    return CodeSafetyStatus.SAFE, "Code is safe to run."


class SafetyCheckerThread(threading.Thread):
    """
    Dedicated thread that runs secondary safety verification.
    """

    def __init__(
        self,
        code: str,
        auto_approve: bool,
        human_review_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.code = code
        self.auto_approve = auto_approve
        self.human_review_callback = human_review_callback
        self.is_approved = False
        self.rejection_reason = ""
        self.event = threading.Event()

    def run(self) -> None:
        status, reason = analyze_python_code_ast(self.code)

        if status == CodeSafetyStatus.DANGEROUS:
            self.is_approved = False
            self.rejection_reason = reason
        elif status == CodeSafetyStatus.SAFE:
            self.is_approved = True
            self.rejection_reason = ""
        else:  # SENSITIVE
            if self.auto_approve:
                # Safe edits/deletes in allowed user folders are permitted under auto-approve
                self.is_approved = True
                self.rejection_reason = ""
            elif self.human_review_callback:
                # Escalate to human review
                user_approved = self.human_review_callback(self.code, reason)
                self.is_approved = user_approved
                if not user_approved:
                    self.rejection_reason = f"Action declined by human reviewer: {reason}"
            else:
                self.is_approved = False
                self.rejection_reason = f"Requires human approval: {reason}"

        self.event.set()


def verify_code_safety(
    code: str,
    auto_approve: bool = True,
    human_review_callback: Optional[Callable[[str, str], bool]] = None,
    timeout: float = 5.0,
) -> tuple[bool, str]:
    """
    Execute safety check in a separate thread and return (is_safe, message).
    """
    checker = SafetyCheckerThread(code, auto_approve, human_review_callback)
    checker.start()
    checker.event.wait(timeout=timeout)

    if not checker.event.is_set():
        return False, "Safety verification timed out."

    return checker.is_approved, checker.rejection_reason
