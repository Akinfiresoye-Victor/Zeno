"""
Root launcher for Zeno Desktop AI Assistant.
Forwards execution to zeno.main:main().
"""

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

from zeno.main import main

if __name__ == "__main__":
    main()
