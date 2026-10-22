"""
Root launcher for Zeno Desktop AI Assistant.
Forwards execution to zeno.main:main().
"""

import os
import sys
import warnings
from pathlib import Path

# Suppress verbose Google GenAI AFC recommendations and warnings
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
warnings.filterwarnings("ignore", message=".*AFC.*")

# Add project root and zeno directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR / "zeno") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "zeno"))

if __name__ == "__main__":
    venv_python = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    if sys.prefix == sys.base_prefix and venv_python.is_file():
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])

from zeno.main import main

if __name__ == "__main__":
    main()
