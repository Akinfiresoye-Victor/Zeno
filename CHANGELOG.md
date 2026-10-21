# Zeno Desktop AI Assistant — Redesign & Architectural Changelog

**Release Date:** October 21, 2026  
**Version:** 2.4.0  
**Stack:** React 19, TypeScript, Vite 8, Tailwind CSS v4, Lucide Icons, Python 3, PyInstaller, PyWebView.

---

## 1. Executive Summary

This release completes a comprehensive architectural and user experience redesign of the Zeno Desktop AI Assistant. Every core subsystem—conversation state management, agent task planning and verification, error classification, filesystem sandboxing, process supervision, and security auditing—has been restructured and reinforced according to architectural Rules A through G. All 20 audited bugs from `BUGS.md` have been fixed with 100% passing test coverage.

---

## 2. Architectural Rules Implemented

### Rule A: Separate Assistant & Agentic Worker Stores
- **Assistant Chat Threads** (`assistant_chats.json`): Isolated conversational memory with independent thread creation, history, attachments, and markdown rendering. The Assistant chat input is unlocked and responsive at all times—even while the autonomous agent runs.
- **Agent Runs & Queue** (`agent_runs.json`): Autonomous agent tasks run in their own dedicated queue with step-by-step progress, scratchpads, and evidence tracking.
- **Agent Run Inspector Tool**: Chat Assistant can inspect the active agent run in real time via `api.assistant.inspectAgentRun()` and report live checklist progress without sharing conversational turn state.
- **Automatic Migration**: Automatically upgrades legacy shared `chats.json` into separated stores upon first boot.

### Rule B: Isolated Project Folder & Naming
- Every agent run creates a single dedicated folder inside `~/Documents/ZenoWorkspace/` with a creative, descriptive 2–4 word name (e.g. `car-dash-tkinter`, `django-core-api`, `mathlab-core`).
- Enforces strict Python-level sanitization (lowercase, hyphens, max 32 characters, non-alphanumeric strip) and collision detection with 4-character hex suffixes.
- Full renaming support (`api.agent.renameProjectFolder()`).
- Python-enforced workspace containment: relative paths resolve inside the project directory, and all write operations outside the project folder are strictly rejected.

### Rule C: Checklist Task Engine & Jump-Back
- `checklist.json` serves as the single source of truth saved inside the project folder.
- Dynamic dependency gating: steps cannot start until all prerequisite steps are verified.
- Concrete evidence collection: created file paths, command exit codes (0 required), automated test outputs, and GUI screenshots.
- **Step Jump-Back**: Allows operators or error handlers to jump back to any previous step. Marks the target step and all dependent steps as `pending`, while preserving completed, non-dependent steps.

### Rule D: Granular Error Classifier & Backoff
- Categorizes errors into actionable classes: `TRANSIENT_NETWORK` (SSL EOF, connection drops), `RATE_LIMIT` (429), `SERVER_OVERLOAD` (503), `AUTHENTICATION` (401/403), `BAD_REQUEST` (400), and `TOOL_COMMAND_ERROR`.
- Exponential backoff with randomized jitter (`2s, 4s, 8s, 16s, 32s + random(0, 1)s`) and real-time status updates (`"Gemini connection dropped. Retry 2 of 5 in 8s..."`).
- Work protection: saves partial step output drafts into `<project>/.drafts/` before retrying. Model calls are never silently marked complete upon error.

### Rule E: Process Supervision, Health Checks & GUI Screenshots
- Process lifecycle management tracking PIDs, working directories, start times, and streaming stdout/stderr logs.
- Dedicated virtual environment (`.venv`) initialized inside each project folder. Commands execute directly using `.venv/Scripts/python.exe` on Windows (`.venv/bin/python` on POSIX).
- HTTP Health Checks: dev servers (Django, Flask, FastAPI) are automatically tested against `http://127.0.0.1:<port>` until status code 200 is verified.
- Screen Capture: automatically captures window screenshots for GUI applications (Tkinter, Pygame, Qt) and attaches them as visual verification evidence.
- Full process tree termination via `taskkill /T /F` on Windows and `psutil` or `os.killpg` on POSIX.

### Rule F: Layered Orchid Security Kernel
- Non-bypassable security evaluations for all tool actions with three-tier verdicts: `ALLOW`, `DENY`, and `ASK_USER`.
- Real, visible verdicts: every action log includes the specific matched rule name (e.g. `rule_deny_destructive_wipe`, `rule_allow_venv_dependency_install`), human-readable rationale, and action target.
- Pre-approves safe `.venv` dependency installation, automated test runners (`pytest`, `unittest`), and contained project file writes.
- Prohibits destructive commands (`rm -rf /`, `format`, registry edits, system folder writes).
- Escalates public port bindings (`0.0.0.0`) and unrecognized binaries to the operator via the Orchid Human Review Queue.

---

## 3. Bug Fixes Summary (from BUGS.md)

| Bug ID | Component | Description & Resolution |
|---|---|---|
| **Bug 1** | Assistant & Agent | Chat Assistant and Agentic Worker shared one conversation state. Resolved via Rule A: separated storage, independent inputs, and read-only run inspection tool. |
| **Bug 2** | Files Panel | Files panel showed "No files in session workspace yet". Resolved via Rule B: `list_project_files` accurately queries the active project workspace directory. |
| **Bug 3** | Jobs Panel | Jobs panel showed (0) while background processes were active. Resolved via Rule E: `JobSupervisor` tracks real OS process PIDs and streams live logs. |
| **Bug 4** | Explorer Integration | `open_in_explorer` failed to select files due to space separation in arguments. Fixed to `explorer /select,"<path>"`. |
| **Bug 5** | Settings | Provider key slots were rigid and confusing. Replaced with flexible multi-provider key slots supporting Gemini, Claude, OpenRouter, OpenAI, and Groq. |
| **Bug 6** | UI Aesthetics | Neon blue/green glows, low contrast cards, and harsh AI gradients replaced with restrained slate dark theme (`#0B0D13`, slate text, single indigo accent, WCAG AA compliance). |
| **Bug 7** | Memory | Memory editor lacked validation and clear reset capabilities. Added Markdown preview toggle, AI note synthesizer, and clean template reset. |
| **Bug 8** | Orchid Audit | Audit log repeatedly output generic "Verified safe action". Upgraded to `OrchidSecurityKernel` with explicit rule IDs and reasoning. |
| **Bug 9** | Checklist Gating | Tasks were marked complete without real exit code verification. Enforced python-verified checklist with zero exit code requirement. |
| **Bug 10** | Error Recovery | SSL EOF or socket drops crashed agent turns without draft saving. Handled via `ErrorClassifier` with exponential backoff, jitter, and `.drafts/` persistence. |
| **Bug 11** | File Containment | Tool actions could write outside workspace. Strictly enforced Rule B project containment in `file_tools.py`. |
| **Bug 12** | Virtual Environment | Code execution relied on unstable global Python. Enforced dedicated project `.venv` creation and binary resolution. |
| **Bug 13–20** | Desktop Bridge & Types | Fixed duplicate object keys in `App.tsx`, Windows python runner path resolution in `server.ts`, and pywebview asset bundling. |

---

## 4. Verification & Testing

- **Backend Unit Tests**: 19 tests executed across `tests/test_checklist_engine.py`, `tests/test_error_classifier.py`, `tests/test_folder_naming.py`, and `tests/test_orchid_rules.py` with 100% pass rate.
- **Frontend Compilation & Linting**: `npm run lint` (`tsc --noEmit`) passes with 0 errors.
- **Frontend Production Bundle**: `npm run build` compiles clean production bundle in 1.07s.
- **Desktop Executable**: Standalone Windows package compiled using PyInstaller into `dist/Zeno/Zeno.exe`.

---

## 5. Patch 2.4.1 (Runtime Bridge & File Viewer Fixes)

- **`get_system_status` Argument Handling**: Made `get_system_status(self, payload=None, *args, **kwargs)` and all bridge methods accept optional payload parameters, resolving `TypeError: ZenoDesktopApi.get_system_status() takes 1 positional argument but 2 were given` when called from pywebview.
- **`open_in_explorer` User Path Expansion**: Fixed `open_in_explorer` and `read_file_as_base64` to expand `~` using `.expanduser().resolve()` and search within the active project directory first.
- **Missing Module Imports**: Added missing module-level import of `DEFAULT_WORKSPACE_DIR` and `get_active_project_dir` in [download_tools.py](file:///c:/Users/User/Desktop/zeno-ai-assistant/zeno/tools/download_tools.py).
- **Windows Explorer Subprocess**: Corrected Windows Explorer invocation to use `explorer.exe "<normpath>"` for directories (navigating directly inside) and `explorer.exe /select,"<normpath>"` for files (highlighting the file).

---

## 6. Patch 2.4.2 (Viewer Popups, Multi-Select Deletions, Task Grouping & Permissions)

- **In-App Directory Viewer Popup**: When clicking a directory or unsupported file type, the viewer displays a dedicated modal window stating *"Directory / Unsupported File Preview - Folder and directory previews cannot be displayed in the text viewer"* with a prominent **Reveal in Explorer** button.
- **Deep Directory Navigation in Reveal**: Windows Explorer opens directly *inside* folders when revealed, rather than highlighting the folder from the parent.
- **Multi-Select Deletion Across Tabs**:
  - **Files Tab**: Checkboxes for individual files, Select All, Delete Selected, and Delete All with confirmation dialog.
  - **Jobs Tab**: Checkboxes for background jobs, Select All, Delete Selected, and Clear All.
  - **Orchid Security Tab**: Checkboxes for audit logs, Select All, Delete Selected, and Clear All Logs.
- **File Organization by Agent Task**: Added view toggle (`All Files` vs `By Agent Task`) in `FilesPage.tsx` allowing users to view files grouped by the agent task/run that produced them.
- **System & Agent Permissions in Settings**: Added comprehensive permission toggles in `SettingsPage.tsx` for all 8 security capabilities (`file_read`, `file_write`, `python_exec`, `web_search`, `screen_capture`, `clipboard`, `app_launch`, `dev_tools`) with instant auto-save and Orchid kernel enforcement.
- **Personal AI Memory Extraction Prompt**: Added extraction prompt helper with one-click copy button and synthesis import card in `MemoryPage.tsx` enabling seamless memory migration from ChatGPT, Claude, and Gemini into Zeno.


