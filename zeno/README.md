# Zeno Desktop AI Assistant

## 1. What Zeno Is

Zeno is a personal desktop AI assistant and Python coding companion built with CustomTkinter for native performance. It gives you private, local control over your computer through safe system tools, screen capture, file operations, document creation, and code execution.

```
+--------------------------------------------------------+
|                      User Input                        |
+--------------------------------------------------------+
                           |
                           v
+--------------------------------------------------------+
|             Desktop UI (CustomTkinter)                 |
|  [Sidebar]  [Chat Stream]  [Input Bar]  [Status Bar]   |
+--------------------------------------------------------+
                           |
                           v
+--------------------------------------------------------+
|                  Agent Loop (agent.py)                 |
|  - Gemini 3.8 / Fallback Providers                     |
|  - Max 15 steps per message                            |
|  - Auto-switch on quota exhaustion                     |
+--------------------------------------------------------+
        |                                       |
        v                                       v
+-----------------------+             +------------------+
| Permissions & Audit   |             | Native Tools     |
| - permissions.json    |             | - System Info    |
| - actions.log         |             | - Screen Capture |
| - Destructive Confirm |             | - File Sandbox   |
+-----------------------+             | - Document Write |
                                      | - App Launch     |
                                      | - Isolated Python|
                                      +------------------+
```

## 2. What You Need

- Python 3.11 or newer.
- A free Gemini API key from aistudio.google.com.
- An active internet connection.

## 3. Installation Steps

### Windows

1. Check Python version:
```cmd
python --version
```

2. Create a virtual environment:
```cmd
python -m venv .venv
```

3. Activate the virtual environment:
```cmd
.venv\Scripts\activate
```

4. Install required packages:
```cmd
pip install -r requirements.txt
```

5. Create the key file:
```cmd
copy .env.example .env
```
Open `.env` in Notepad and paste your key after `GEMINI_API_KEY=`.

6. Run the app:
```cmd
python main.py
```

### macOS

1. Check Python version:
```bash
python3 --version
```

2. Create a virtual environment:
```bash
python3 -m venv .venv
```

3. Activate the virtual environment:
```bash
source .venv/bin/activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

5. Create the key file:
```bash
cp .env.example .env
```
Open `.env` in a text editor and paste your key after `GEMINI_API_KEY=`.

6. Run the app:
```bash
python3 main.py
```

### Linux

1. Check Python version:
```bash
python3 --version
```

2. Create a virtual environment:
```bash
python3 -m venv .venv
```

3. Activate the virtual environment:
```bash
source .venv/bin/activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

5. Create the key file:
```bash
cp .env.example .env
```
Open `.env` in a text editor and paste your key after `GEMINI_API_KEY=`.

6. Run the app:
```bash
python3 main.py
```

## 4. Operating System Notes

- macOS: The first screenshot needs Screen Recording permission. Go to System Settings, Privacy and Security, Screen Recording, and allow Terminal or your Python app. Restart the app after changing it.
- Linux: Screenshots work on X11. On Wayland, the screenshot may show only a blank or partial image. Log in to an X11 session to use screen capture. On Debian or Ubuntu, if Tkinter is missing, run: sudo apt install python3-tk.
- Windows: Some apps running as administrator cannot be captured. Run Zeno normally, not as administrator.

## 5. Troubleshooting

| Issue | Cause | Fix |
| :--- | :--- | :--- |
| API key missing | The GEMINI_API_KEY variable is empty or not found in the .env file. | Open .env and paste your key after GEMINI_API_KEY=, or enter it in Settings inside the app. |
| No module named customtkinter | The required dependencies have not been installed in the active virtual environment. | Run pip install -r requirements.txt while your virtual environment is activated. |
| Permission denied | The required tool category was denied or turned off in settings. | Open Settings from the sidebar and switch on the required category. |
| Rate limit reached | The current AI model exceeded provider token or request frequency quotas. | Wait a few moments, or enable auto-switch in Settings to failover to alternative providers automatically. |
| Screenshot is black or blank | The desktop display compositor or permissions blocked pixel grabbing. | Grant Screen Recording permissions on macOS, or log into an X11 desktop session on Linux. |
| Window freezes | A heavy task blocked the main thread. | Zeno runs all agent tasks in background threads, but if an external process hangs, press the Stop button to cancel execution. |

## 6. How Permissions Work

Zeno asks for your permission the first time a tool in any category is called. When you click Allow, your choice is saved to permissions.json so you are never asked again for that category. If you click Deny, the tool is blocked and you can turn it back on at any time in the Settings view.

## 7. Where Your Files Are

- permissions.json: Stores your granted and denied permissions across app launches.
- actions.log: Contains an audit trail of every tool call with timestamps, arguments, and result summaries.
- screenshots/: Stores timestamped PNG captures created by the screen capture tool.

## 8. Planned Features (Phase 2)

The following features are planned for Phase 2 and are not in this version:
- Browser tab capture
- Single window capture
- Global hotkey invocation
- System tray minimization and background resident mode
- Scheduled tasks and periodic automation
- Direct keyboard and mouse synthetic control

## 9. Building a Standalone Desktop Executable (PyInstaller)

You can package Zeno into a standalone desktop application that runs without opening a terminal:

1. Install build requirements:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

2. Run the packaging script:
```bash
python build_desktop.py
```
Or directly using the spec file:
```bash
pyinstaller zeno.spec
```

3. The packaged desktop application will be available in the `dist/Zeno/` directory:
- **Windows**: `dist/Zeno/Zeno.exe` (can be pinned to Taskbar or Desktop)
- **macOS**: `dist/Zeno/Zeno.app`
- **Linux**: `dist/Zeno/Zeno`
