"""
Main entry point for Zeno Desktop AI Assistant.
Initializes pywebview, launches a local web server for the UI,
and connects native Python tools through js_api.
"""

from __future__ import annotations

import http.server
import os
from pathlib import Path
import socket
import socketserver
import sys
import threading

# Ensure zeno and root package are on sys.path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from dotenv import load_dotenv

from zeno.desktop_api import ZenoDesktopApi
from zeno.settings import ENV_FILE_PATH, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH

load_dotenv(dotenv_path=ENV_FILE_PATH)

import warnings

# Suppress verbose Google GenAI AFC recommendations and warnings
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
warnings.filterwarnings("ignore", message=".*AFC.*")
logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.genai.models").setLevel(logging.ERROR)


class QuietStaticFileHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler serving the built web UI assets with suppressed access logs."""

    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Suppress standard HTTP request logging for quiet operation."""
        pass


def find_available_port() -> int:
    """Find and return an unused local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_local_server(assets_dir: Path, port: int) -> socketserver.TCPServer:
    """Start local threaded HTTP server serving frontend assets."""
    handler_factory = lambda *args, **kwargs: QuietStaticFileHandler(*args, directory=str(assets_dir), **kwargs)
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler_factory)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd


def locate_web_assets() -> Path:
    """Locate the built frontend web assets directory."""
    candidates = [
        PROJECT_ROOT / "dist",
        CURRENT_DIR / "dist",
        PROJECT_ROOT,
    ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return PROJECT_ROOT / "dist"


def main() -> None:
    """Launch the Zeno native desktop window via pywebview."""
    try:
        import webview
    except ImportError:
        print("Error: Required desktop webview package is not installed.")
        print("Please install requirements using:")
        print("    pip install -r requirements.txt")
        sys.exit(1)

    assets_dir = locate_web_assets()
    if not (assets_dir / "index.html").exists():
        print(f"Warning: Built web assets not found at {assets_dir}. Running with root directory.")
        assets_dir = PROJECT_ROOT

    port = find_available_port()
    start_local_server(assets_dir, port)
    app_url = f"http://127.0.0.1:{port}/index.html"

    # Initialize Python tools API bridge
    desktop_api = ZenoDesktopApi()

    # Create native desktop window with text selection and copying enabled
    window = webview.create_window(
        title="Zeno Desktop AI Assistant",
        url=app_url,
        js_api=desktop_api,
        width=1280,
        height=840,
        min_size=(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT),
        background_color="#0A0A0C",
        text_select=True,
    )

    # Start native desktop event loop with custom Zeno app icon
    icon_path = PROJECT_ROOT / "zeno_icon.ico"
    webview.start(debug=False, icon=str(icon_path) if icon_path.exists() else None)


if __name__ == "__main__":
    main()
