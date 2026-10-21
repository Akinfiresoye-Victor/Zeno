"""
Isolated Python code runner executing scripts in a separate process.
Category: python_exec
Never executes inside the main Zeno process. Never uses shell=True.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from zeno.settings import (
    MAX_PYTHON_OUTPUT_CHARS,
    PYTHON_EXEC_TIMEOUT_SECONDS,
)


def run_python(code: str) -> dict:
    """
    Execute arbitrary Python code in an isolated subprocess.

    Args:
        code: Python source code string to execute.

    Returns:
        dict: Process execution result with keys:
              - stdout: standard output string (truncated to 4000 characters)
              - stderr: standard error string (truncated to 4000 characters)
              - exit_code: integer exit status code (0 indicates success)
              - timed_out: boolean indicating if process exceeded 30-second timeout
    """
    # Write code to a secure temporary file
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            temp_file = f.name
            f.write(code)

        from zeno.tools.file_tools import get_active_project_dir

        active_dir = get_active_project_dir()
        py_exe = sys.executable

        # Rule E: Use venv python if present inside project folder
        if active_dir:
            venv_bin_win = active_dir / ".venv" / "Scripts" / "python.exe"
            venv_bin_posix = active_dir / ".venv" / "bin" / "python"
            if venv_bin_win.exists():
                py_exe = str(venv_bin_win)
            elif venv_bin_posix.exists():
                py_exe = str(venv_bin_posix)

        exec_cwd = str(active_dir) if active_dir else None

        proc = subprocess.run(
            [py_exe, temp_file],
            cwd=exec_cwd,
            capture_output=True,
            text=True,
            timeout=PYTHON_EXEC_TIMEOUT_SECONDS,
            shell=False,
        )

        stdout_clean = (proc.stdout or "")[:MAX_PYTHON_OUTPUT_CHARS]
        stderr_clean = (proc.stderr or "")[:MAX_PYTHON_OUTPUT_CHARS]
        exit_code = proc.returncode
        timed_out = False

    except subprocess.TimeoutExpired as exc:
        stdout_clean = (exc.stdout or "")[:MAX_PYTHON_OUTPUT_CHARS] if hasattr(exc, "stdout") else ""
        stderr_clean = f"Process timed out after {PYTHON_EXEC_TIMEOUT_SECONDS} seconds."
        exit_code = -1
        timed_out = True

    except Exception as exc:
        stdout_clean = ""
        stderr_clean = f"Execution error: {exc}"
        exit_code = -1
        timed_out = False

    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass

    return {
        "stdout": stdout_clean,
        "stderr": stderr_clean,
        "exit_code": exit_code,
        "timed_out": timed_out,
    }
