# Zeno Desktop AI Assistant

## 1. Overview and Architecture

Zeno is a local-first desktop AI assistant, autonomous agentic workspace, and Python pair programmer. It operates inside a native desktop application powered by `pywebview` with a high-throughput, bi-directional Python `js_api` bridge. It pairs local system execution capabilities with safety architecture and model routing across Gemini, Claude, OpenRouter, OpenAI, and Groq.

```
+-----------------------------------------------------------------------------------+
|                                  USER INTERFACE                                   |
|                      Native Desktop Window (pywebview / Edge WebView2)            |
|                                                                                   |
|  [Conversational Stream]  |  [Mission Control Workspace]  |  [Settings & Providers] |
+-----------------------------------------------------------------------------------+
                                         |
                            Dual-Channel js_api Bridge
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                              DUAL-AGENT ENGINE                                    |
|                                                                                   |
|  +-------------------------------------+   +------------------------------------+ |
|  |             ZENO BUILDER            |   |            ZENO OBSERVER           | |
|  |           (Execution Core)          |   |          (Safety Sentinel)         | |
|  | - File manipulation & scaffolding   |   | - 8-14 milestone roadmap planning  | |
|  | - Subprocess & shell runner         |<--| - Real-time AST safety audit       | |
|  | - Automated unit test execution     |   | - Destructive command interception | |
|  | - Document synthesis & reports      |   | - Human approval queue manager     | |
|  +-------------------------------------+   +------------------------------------+ |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                        LOCAL TOOLING & SYSTEM RUNTIME                             |
|  - Dev Tools: shell_run, run_tests, git_status, git_diff, git_commit, db_query    |
|  - File Ops: read_file, write_file, append_file, list_directory, search_files     |
|  - Local LLM: ollama_list, ollama_run                                             |
|  - Telemetry: Hardware diagnostics, process list, network IO, display captures     |
|  - Safety DB: SQLite safety.db, audit ledger, permissions manager                 |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Capabilities

### Dual-Agent Architecture
- **Zeno Builder (Worker)**: Autonomous execution engine that invokes native tools, scaffolds codebases, writes complete production implementations without placeholders, executes test suites, and verifies results.
- **Zeno Observer (Sentinel)**: Autonomous supervisory agent. Plans 8 to 14 granular engineering milestones, continuously audits actions against malicious patterns (e.g. destructive recursion, privilege escalation, credential scraping), blocks system corruption, and escalates risky operations to human review.

### Mission Control Agent Workspace
- **Telemetry HUD**: Live status indicators for Zeno Builder and Zeno Observer, progress percentage bar, active milestone tracker, and active workspace root indicator.
- **Engineering Roadmap**: 8 to 14 phased milestones with real-time status badges (Completed, Executing, Queued).
- **Execution Deck**: Active directive focus card, neural reasoning matrix ticker, working memory scratchpad, tool execution output feed, and visual screen verification cards.
- **Triple-Tab Ops Center**:
  - **Files**: Real-time workspace directory tree showing created and modified files.
  - **Observer Ledger**: Real-time security audit stream displaying builder action evaluations, vetoes, and operator approvals.
  - **Background Jobs**: Worker pool status displaying asynchronous CLI commands and test processes with one-click cancellation.

### Filesystem Roaming and System Shielding
- **User Space Roaming**: The agent has roaming permissions across the user directory (`C:\Users\<User>`), Desktop, Documents, Downloads, and custom project locations.
- **Operating System Shield**: System roots (`C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)`) are strictly forbidden and intercepted by `path_validator.py`.

### Developer Tooling Suite
- **shell_run**: Executes command-line processes with timeouts, stdout/stderr capture, and observer security scanning.
- **git_status, git_diff, git_commit**: Complete repository version control without external dependencies.
- **run_tests**: Automated test runner executing `pytest` or Python `unittest` suites and capturing tracebacks for self-healing.
- **db_query**: Read-only SQL inspection against SQLite or PostgreSQL databases.
- **ollama_list, ollama_run**: Local open-weights model integration.
- **report_write**: Compiles markdown audit reports into dedicated project report directories.

### Chat Retention and Context Compaction
- **Conversation Persistence**: Chat sessions are saved locally to `chats.json`.
- **Retention Lifecycle**: Chats remain active for 3 days and are flagged for cleanup after 4 days of inactivity.
- **Context Compaction**: Automated summary compaction condenses long conversations into structured memory anchors, preserving token budget while keeping project context intact.

---

## 3. System Requirements

- Python 3.10 or newer (Python 3.11 or 3.12 recommended).
- Node.js 18 or newer (with npm).
- An API key for at least one supported provider:
  - Google Gemini (API key from Google AI Studio)
  - Anthropic Claude
  - OpenRouter
  - OpenAI
  - Groq
  - Ollama (Local, no API key required)
- Platform Webview Runtime:
  - Windows: Microsoft Edge WebView2 (installed by default on Windows 10/11).
  - macOS: System WebKit (included with macOS).
  - Linux: `WebKit2GTK` (`sudo apt install libwebkit2gtk-4.1-0`).

---

## 4. Installation and Setup

### Windows

1. Clone or download the repository:
```cmd
git clone https://github.com/your-username/zeno-ai-assistant.git
cd zeno-ai-assistant
```

2. Create and activate a Python virtual environment:
```cmd
python -m venv .venv
.venv\Scripts\activate
```

3. Install Python dependencies:
```cmd
pip install -r requirements.txt
```

4. Install frontend dependencies and compile web assets:
```cmd
npm install --legacy-peer-deps
npm run build
```

5. Configure your API key:
```cmd
copy .env.example .env
```
Open `.env` in a text editor and add your key, or enter it directly in the app's Settings interface.

6. Launch the desktop assistant:
```cmd
python main.py
```

### macOS

1. Create and activate a Python virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
npm install --legacy-peer-deps
npm run build
```

3. Configure environment and launch:
```bash
cp .env.example .env
python3 main.py
```

### Linux (Ubuntu/Debian)

1. Install required system webview dependencies:
```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-0
```

2. Create virtual environment, build, and run:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install --legacy-peer-deps
npm run build
cp .env.example .env
python3 main.py
```

---

## 5. Desktop API Specification

The desktop frontend communicates with the Python core through `window.pywebview.api`. Key exposed endpoints include:

| Method | Parameters | Description |
| :--- | :--- | :--- |
| `create_agent_plan` | `payload: {task, model, customApiKey}` | Generates an 8 to 14 milestone engineering roadmap via Zeno Observer. |
| `run_agent_task` | `payload: {message, currentStep, planTitle, stepIndex, totalSteps}` | Dispatches active milestone directive to Zeno Builder with tool execution. |
| `get_pending_approvals`| `None` | Lists operations awaiting operator review. |
| `decide_approval` | `payload: {approval_id, approved}` | Grants or denies an audited sensitive operation. |
| `get_recent_action_logs`| `payload: {limit}` | Retrieves chronological security audit records from `safety.db`. |
| `list_active_jobs` | `None` | Lists running background CLI and test processes in the worker pool. |
| `cancel_job` | `payload: {job_id}` | Terminates a background worker task. |
| `chat` | `payload: {message, history, model, thinkingLevel, mode}` | Standard conversational chat turn with memory integration. |
| `get_system_status` | `None` | Returns CPU utilization, memory, disk, and battery statistics. |
| `capture_screen` | `target, tab_name` | Captures displays or specific windows. |
| `run_python` | `code` | Executes Python code inside a sandboxed subprocess. |
| `load_chats` | `None` | Retrieves stored chat threads and compaction state. |
| `save_chats` | `payload: {chats}` | Persists conversation records. |

---

## 6. Testing and Quality Verification

Run the comprehensive test suites to verify system integrity:

```cmd
# Run safety and development tool validation tests
python -m unittest test_safety_and_dev_tools.py

# Run core assistant and memory tests
python -m unittest test_zeno.py
```

---

## 7. Project Layout

```
zeno-ai-assistant/
|-- .gitignore                  # Git ignore rules for secrets, builds, and user data
|-- build_desktop.py            # PyInstaller standalone desktop packager
|-- index.html                  # Frontend HTML shell
|-- main.py                     # Primary desktop entry point
|-- package.json                # Frontend dependencies and Vite configuration
|-- requirements.txt            # Python dependencies
|-- test_safety_and_dev_tools.py# Unit tests for safety, path validation, and tools
|-- test_zeno.py                # Core unit tests for desktop API and memory
|-- vite.config.ts              # Vite bundling configuration
|-- src/                        # React / TypeScript interface
|   |-- App.tsx                 # Mission Control UI, chat interface, and settings
|   |-- index.css               # Core design system and utility styles
|   `-- main.tsx                # React DOM mount point
`-- zeno/                       # Python application package
    |-- agent.py                # Autonomous agent loop and provider routing
    |-- chat_manager.py         # Session persistence and retention management
    |-- desktop_api.py          # pywebview bridge implementation
    |-- memory.py               # Memory management and context compaction
    |-- settings.py             # Global constants, folder rules, and model lists
    |-- safety/                 # Dual-agent safety subsystems
    |   |-- database.py         # SQLite safety.db action logs and approval tables
    |   |-- observer.py         # Zeno Observer milestone planning and audit logic
    |   |-- path_validator.py   # Path traversal and system folder containment
    |   `-- worker.py           # Background CLI process worker pool
    `-- tools/                  # Native system tool implementations
        |-- dev_tools.py        # shell_run, git, test runner, db_query, reports
        |-- system_tools.py     # Hardware metrics, processes, network stats
        `-- file_tools.py       # Sandboxed filesystem operations
```

---

## 8. License

This project is licensed under the MIT License. See LICENSE for details.
