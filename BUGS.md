# Zeno Desktop AI Assistant — Comprehensive Codebase Audit & Bug Report (BUGS.md)

This document contains the complete audit of the Zeno Desktop AI Assistant codebase (`c:\Users\User\Desktop\zeno-ai-assistant`), covering the Python backend (`zeno/`), the desktop shell (`main.py`, `build_desktop.py`), the web server/API bridge (`server.ts`, `zeno/desktop_api.py`), and the frontend interface (`src/App.tsx`, `index.css`).

---

## Table of Bugs

| Bug ID | Title | Component & Location | Severity |
| :--- | :--- | :--- | :--- |
| **BUG-01** | Assistant & Agentic Worker share single state and input; Stop replaces Send | `src/App.tsx:3346-3365, 4162-4178` | **Critical** |
| **BUG-02** | Files panel shows "No files in session workspace yet" even after files created | `src/App.tsx:1619-1647`, `zeno/desktop_api.py:1635-1660`, `zeno/tools/file_tools.py:41-48` | **High** |
| **BUG-03** | Jobs panel displays `(0)` despite active processes and tool invocations | `zeno/tools/dev_tools.py:180, 375`, `zeno/safety/worker.py:309`, `zeno/desktop_api.py:1568-1576` | **High** |
| **BUG-04** | "Open in file explorer" opens project root folder instead of selecting target file | `zeno/tools/download_tools.py:130-133`, `src/App.tsx:3457, 3494, 4490` | **Medium** |
| **BUG-05** | Clicking a file name in chat does nothing / fails to open in viewer | `src/App.tsx:417-443, 2199-2215`, `zeno/tools/download_tools.py:157-163` | **Medium** |
| **BUG-06** | "Stop Agent" does not reliably terminate the running step or its process tree | `zeno/desktop_api.py:118-123`, `zeno/agent.py:115, 139-140`, `src/App.tsx:457-472` | **Critical** |
| **BUG-07** | Failed model calls (e.g. SSL EOF) are treated as successful steps | `zeno/agent.py:154-182`, `zeno/desktop_api.py:1350-1363`, `src/App.tsx:1585-1600` | **Critical** |
| **BUG-08** | Step counter displays inconsistent numbers across header, sidebar, and chat | `src/App.tsx:1502, 2966, 3035` | **Medium** |
| **BUG-09** | Token counter stays at "Tokens: 0 in / 0 out" during active runs | `src/App.tsx:343, 1649, 4194`, `zeno/desktop_api.py:1223-1227` | **Medium** |
| **BUG-10** | Orchid Sentinel logs generic "Verified safe action" without command or reasoning | `zeno/safety/observer.py:328-335`, `src/App.tsx:3548-3561` | **Medium** |
| **BUG-11** | Agent folder naming uses raw truncated task sentence slugs | `zeno/desktop_api.py:1099-1102` | **Low** |
| **BUG-12** | File Viewer lacks code syntax highlighting, Markdown rendered preview, and PDF support | `src/App.tsx:4507-4535`, `zeno/tools/download_tools.py:167-200` | **Medium** |
| **BUG-13** | Memory and Personalization is buried in Settings rather than a dedicated page | `src/App.tsx:2663-2733` | **Low** |
| **BUG-14** | Chat retention silently purges chats after 4 days of inactivity | `zeno/chat_manager.py:86-90`, `zeno/settings.py:55-56` | **High** |
| **BUG-15** | Command allowlist blocks polyglot stacks (Node, Django runserver, etc.) | `zeno/safety/command_guard.py:18-27, 30-32, 60-66` | **High** |
| **BUG-16** | Python code runner executes in host interpreter rather than project `.venv` | `zeno/tools/python_tools.py:41-47` | **High** |
| **BUG-17** | No agent run queue: concurrent triggers overwrite active state | `src/App.tsx:1388-1415` | **High** |
| **BUG-18** | Express server in `server.ts` uses `python3` which fails on Windows | `server.ts:206` | **Low** |
| **BUG-19** | Human approval decisions in UI do not resume waiting agent tasks | `src/App.tsx:497-502`, `zeno/safety/approvals.py:20-35` | **Medium** |
| **BUG-20** | Monolithic frontend with 4,500 lines in single file and hardcoded colors | `src/App.tsx:1-4543` | **Medium** |

---

## Detailed Bug Descriptions

### BUG-01: Chat Assistant & Agentic Worker Share Single State and Input
- **Location:** `src/App.tsx`, lines 1388–1415, 3346–3365, 4162–4178.
- **What the user sees:**
  When an agent task is triggered in Agentic Worker mode, switching to Chat Assistant mode disables the chat input box. The "Send" button is replaced with a red "Stop" button. The user cannot ask questions, look up information, or chat with the assistant while an agent task is in flight.
- **Why it happens:**
  Both modes share a single state variable `isRunning` and a single active session pointer `activeSessionId`. In `App.tsx`:
  ```tsx
  {isRunning ? (
    <button onClick={handleStop} className="rounded bg-[#F87171] ...">Stop</button>
  ) : (
    <button onClick={() => executeTurn(inputText)} ...>Send</button>
  )}
  ```
  `isRunning` globally locks the entire UI, and both modes write to the same `sessions` array.
- **How to reproduce:**
  1. Open the app and click "Agentic Worker".
  2. Enter a task (e.g. "Build a utility module").
  3. While step 1 is executing, click "Chat Assistant" in the header.
  4. Notice the chat input has "Stop" instead of "Send" and typing a message cannot be sent.

---

### BUG-02: Files Panel Shows "No files in session workspace yet"
- **Location:** `src/App.tsx:1619–1647, 3465–3471`, `zeno/desktop_api.py:1635–1660`, `zeno/tools/file_tools.py:41–48`.
- **What the user sees:**
  During an agent execution and even after an agent claims to have created files, the "Files" tab in the right column displays: `No files in session workspace yet`.
- **Why it happens:**
  1. `list_session_files` is ONLY invoked in `App.tsx` *after* the entire agent loop finishes (after line 1618). It is never polled or refreshed after each step.
  2. When tools such as `write_file` are invoked with relative paths (e.g. `write_file("app.py", "...")`), `zeno/tools/file_tools.py` defaults relative paths to `HOME_DIR / "Documents" / p` instead of the project directory. The files are physically written to `~/Documents/app.py` instead of the session folder.
  3. `desktop_api.py` passes `session_workspace` (e.g. `~/.zeno/sessions/...`) while `create_agent_plan` creates `project_folder` as a subfolder (`session_dir / slug`). `list_session_files` scans `session_workspace` which may not include files if the path passed is mismatched.
- **How to reproduce:**
  1. In Agentic Worker mode, instruct Zeno to create a 3-step Python project.
  2. Observe the Files panel on the right while steps 1 and 2 complete. The panel displays `(0)` and "No files in session workspace yet".
  3. Check the user's `~/Documents` directory to find files mistakenly written there.

---

### BUG-03: Jobs Panel Displays `(0)` Despite Active Tool Executions
- **Location:** `zeno/tools/dev_tools.py:180, 375`, `zeno/safety/worker.py:309`, `zeno/desktop_api.py:1568–1576`.
- **What the user sees:**
  The "Jobs" tab in the operations panel always shows `Jobs (0)`. When tools like `shell_run`, `run_tests`, or `server_start` execute, no job logs appear in the Jobs tab.
- **Why it happens:**
  1. The frontend queries `window.pywebview.api.get_active_jobs()`, which queries `WorkerPoolManager.list_active_jobs()` in `zeno/safety/worker.py`.
  2. However, `dev_tools.py` (`shell_run`, `run_tests`, `lint_run`) executes commands using synchronous `subprocess.run(...)` directly, completely bypassing `WorkerPoolManager`.
  3. `server_start` starts background processes using `subprocess.Popen(...)` and stores them in a local dictionary `_active_servers` inside `dev_tools.py`, which is never connected to `WorkerPoolManager`. As a result, `get_active_jobs()` always returns an empty list `[]`.
- **How to reproduce:**
  1. Start an agent task that runs shell commands or starts a server.
  2. Click the "Jobs" tab in the right column.
  3. Notice it says `Jobs (0)` and "No background jobs currently running."

---

### BUG-04: "Open in File Explorer" Opens Root Folder Instead of Selecting File
- **Location:** `zeno/tools/download_tools.py:130–133`, `src/App.tsx:3457, 3494, 4490`.
- **What the user sees:**
  Clicking "Explorer" next to any file in the Files panel or in the File Viewer opens the Windows Explorer window at the root Documents or project directory, but does not highlight or select the file.
- **Why it happens:**
  In `zeno/tools/download_tools.py`:
  ```python
  if sys.platform == "win32":
      if resolved.is_file():
          subprocess.Popen(["explorer", "/select,", str(resolved)], shell=False)
  ```
  On Windows, passing `["explorer", "/select,", str(resolved)]` splits `/select,` and the path into two separate command-line tokens separated by whitespace. Windows `explorer.exe` fails to parse `/select, <path>` and defaults to opening the parent or user Documents folder without selecting the file. To highlight a file on Windows, `explorer.exe` requires the syntax `explorer /select,"C:\path\to\file"`.
- **How to reproduce:**
  1. Create any file in the workspace.
  2. Click the "Explorer" button on that file.
  3. Windows Explorer opens, but the file is not selected.

---

### BUG-05: Clicking a File Name in Chat Does Nothing
- **Location:** `src/App.tsx:417–443, 2199–2215`, `zeno/tools/download_tools.py:157–163`.
- **What the user sees:**
  File names rendered in the chat stream (or inside markdown formatted responses) do not open when clicked.
- **Why it happens:**
  1. In `App.tsx`, click handling on markdown HTML is bound only to `<a>` tags (`target.closest('a')`). File names mentioned in assistant responses are commonly formatted as inline code (`<code>app.py</code>`), bold text, or plain text, which have no click listener.
  2. When an actual markdown link `[app.py](app.py)` is clicked, `openFileInViewer(href)` sends `{ path: "app.py" }` to Python. In `zeno/tools/download_tools.py:157-163`, `Path("app.py").resolve()` searches the current working directory of the process (which is the app root), and then checks `DEFAULT_WORKSPACE_DIR / "app.py"`. Because the file was created inside the task's project folder or session folder, resolution fails with `File not found`.
  3. On error, `openFileInViewer` silently sets dummy metadata text: `Viewing file metadata: app.py`, which shows "No preview content available".
- **How to reproduce:**
  1. In chat or agent output, see a file reference such as `math_utils.py`.
  2. Click on it. Nothing happens or a blank preview appears.

---

### BUG-06: "Stop Agent" Does Not Reliably Terminate Task or Child Processes
- **Location:** `zeno/desktop_api.py:118–123`, `zeno/agent.py:115, 139–140`, `src/App.tsx:457–472`.
- **What the user sees:**
  Clicking "Stop Agent" or "Stop" updates the frontend button, but the background Python process continues executing commands, eating CPU, or hanging on network calls. Dev servers started by the task remain running indefinitely.
- **Why it happens:**
  1. In `zeno/desktop_api.py`:
  ```python
  def abort_agent_task(self):
      with ZenoDesktopApi._agent_abort_lock:
          ZenoDesktopApi._agent_abort = True
      return {"ok": True, "message": "Abort signal sent. Agent will stop after current step."}
  ```
  `abort_agent_task` only sets a Python boolean flag checked between steps. If the agent is currently blocked inside a long-running subprocess (`subprocess.run`, `pip install`, test runner) or model API call, execution is not interrupted.
  2. `ZenoAgent` has an internal `self._stop_event`, but `abort_agent_task` in `desktop_api.py` never calls `agent.stop()`.
  3. No process tree termination (`taskkill /T /F` on Windows or `psutil` process tree kill) is performed for child processes spawned by tools.
- **How to reproduce:**
  1. Launch a task that runs a long build or starts a web server.
  2. Click "Stop Agent".
  3. Inspect Windows Task Manager; python child processes and web servers continue running in the background.

---

### BUG-07: Failed Model Calls (e.g. SSL EOF) Are Treated as Successful Steps
- **Location:** `zeno/agent.py:154–182`, `zeno/desktop_api.py:1350–1363`, `src/App.tsx:1585–1600`.
- **What the user sees:**
  If an API call fails with `[SSL: UNEXPECTED_EOF_WHILE_READING]` or socket disconnect, the step is marked with a green checkmark as completed, and the agent moves to the next step. The intended work of that step is never done.
- **Why it happens:**
  1. In `zeno/agent.py:154-182`, when an SSL or connection error occurs during `generate_content`, `_execute_agent_loop` raises an exception. The exception is caught, but `is_quota_or_rate` does not match SSL EOF, so it breaks the loop and returns a string:
  `return f"Error communicating with AI model: {last_error_message}"`
  2. `desktop_api.py:1386` returns this error string as the `reply` property of the step payload.
  3. In `src/App.tsx:1585-1600`, the loop treats any returned `stepData` as step completion:
  ```ts
  const updatedSteps = st.plan!.steps.map((s, i) =>
    i === stepIdx ? { ...s, completed: true } : s
  );
  ```
  The step is marked `completed: true`, `currentStepIdx` increments, and execution continues to the next step.
- **How to reproduce:**
  1. Disconnect network or simulate an SSL EOF / reset during an agent step.
  2. Observe the step checklist: the failed step is marked with a checkmark, and the agent proceeds to the next step.

---

### BUG-08: Inconsistent Step Counters Across Header, Sidebar, and Chat
- **Location:** `src/App.tsx:1502, 2966, 3035`.
- **What the user sees:**
  When executing step 10 of a 19-step plan:
  - Top header displays: `Milestone 10 of 19`
  - Left roadmap displays: `9 / 19 Done`
  - Chat assistant banner displays: `Step 10/19: ...`
  - If a step is retried or revisited, the counts drift even further apart.
- **Why it happens:**
  Different components calculate progress using three different conventions:
  1. Header uses 1-based index: `currentStepIdx + 1` (e.g. `10`).
  2. Sidebar counts steps where `completed === true`: `completedStepsCount` (which is `9` while step 10 is running).
  3. Chat assistant references `currentStepText`, which is formatted independently. There is no unified state object representing active step vs completed steps.
- **How to reproduce:**
  1. Run any multi-step agent task.
  2. While any step is executing, compare the header text, sidebar checklist badge, and status bar text.

---

### BUG-09: Token Counter Stays at "Tokens: 0 in / 0 out"
- **Location:** `src/App.tsx:343, 1649, 4194`, `zeno/desktop_api.py:1223–1227`.
- **What the user sees:**
  Throughout the entire duration of an agent task, the status bar displays: `Tokens: 0 in / 0 out`.
- **Why it happens:**
  In `src/App.tsx`, `totalInTokens` and `totalOutTokens` are accumulated in local variables inside `executeTurn`. `setTokenCounts` is only called once at line 1649 *after the entire multi-step task has completed*. While steps 1 through 19 are running, `tokenCounts` is never updated. If a task is aborted, paused, or fails, line 1649 is never reached, leaving the counter at `0 in / 0 out` forever.
- **How to reproduce:**
  1. Start an agent task with 5 steps.
  2. Watch the bottom status bar during steps 1 to 4: tokens remain `0 in / 0 out`.

---

### BUG-10: Orchid Sentinel Logs "Verified safe action" Without Details
- **Location:** `zeno/safety/observer.py:328–335`, `src/App.tsx:3548–3561`.
- **What the user sees:**
  In the Orchid tab of the operations panel, every entry shows: `Verified safe action: <tool_name>` (e.g. `Verified safe action: run_python`), without displaying the command, parameters, safety verdict rationale, or matched security rule.
- **Why it happens:**
  In `zeno/safety/observer.py`:
  ```python
  record_observer_dialogue(
      speaker="Zeno Orchid",
      message=f"Verified safe action: {tool_name}",
      job_id=job_id,
      action_proposed=f"{tool_name}({args_repr})",
      guard_verdict="ALLOW",
  )
  ```
  The message string is hardcoded to `Verified safe action: {tool_name}`. It omits the rule that allowed it, why it was deemed safe, and what parameters were verified. The UI simply renders `dlg.message`.
- **How to reproduce:**
  1. Run any tool action.
  2. Open the Orchid tab.
  3. Notice all entries say "Verified safe action: shell_run" without explaining what command was run.

---

### BUG-11: Agent Creates Folders Named After Raw Task Sentences
- **Location:** `zeno/desktop_api.py:1099–1102`.
- **What the user sees:**
  Workspace directories are created with names like `build_a_math_utility_module_with` or `create_a_django_server_and_run_`.
- **Why it happens:**
  `desktop_api.py` derives the folder name using:
  ```python
  slug = _re.sub(r"[^a-zA-Z0-9]+", "_", task[:32].strip().lower()).strip("_") or "project"
  ```
  It simply takes the first 32 characters of the user prompt and replaces non-alphanumeric characters with underscores. It does not use the LLM to generate a creative 2–4 word title (e.g. `mathlab-core`, `car-dash-tkinter`).
- **How to reproduce:**
  1. Submit task: "Build a math utility module with unit tests".
  2. Inspect the created folder: it is named `build_a_math_utility_module_with`.

---

### BUG-12: File Viewer Lacks Syntax Highlighting, Markdown Rendering, and PDF Support
- **Location:** `src/App.tsx:4507–4535`, `zeno/tools/download_tools.py:167–200`.
- **What the user sees:**
  Opening code files in the file viewer displays plain unhighlighted text inside a `<pre>` block. Markdown files are displayed as raw unrendered text with hash symbols and asterisks. PDF files cannot be viewed.
- **Why it happens:**
  The in-app viewer in `App.tsx` only checks `viewerFile.mime_type.startsWith('image/')` and falls back to:
  ```tsx
  <pre className="text-[11px] font-mono ...">{viewerFile.text}</pre>
  ```
  No syntax highlighter (such as Prism or highlight.js) is integrated, markdown parsing is not applied in the viewer modal, and PDF rendering is not supported.
- **How to reproduce:**
  1. Open a `.py`, `.ts`, `.md`, or `.pdf` file in the File Viewer.
  2. Observe plain mono text with no syntax colors and no markdown rendering.

---

### BUG-13: Memory Feature Buried Inside Settings View
- **Location:** `src/App.tsx:2663–2733`.
- **What the user sees:**
  There is no direct "Memory" tab or page in the main navigation. The user must click the Settings gear icon, scroll past API keys and workspace configs, to locate the memory editor.
- **Why it happens:**
  Memory was implemented as a sub-card inside the monolithic `Settings` view rather than a primary navigation destination.
- **How to reproduce:**
  1. Look at the primary navigation rail. There is no Memory item.

---

### BUG-14: Chat Retention Silently Purges User Chats After 4 Days
- **Location:** `zeno/chat_manager.py:86–90`, `zeno/settings.py:55–56`.
- **What the user sees:**
  If a user does not open the assistant for 4 days, their chat history disappears.
- **Why it happens:**
  `zeno/chat_manager.py` implements an aggressive retention policy:
  - Chats inactive for 3 days are flagged for deletion.
  - Chats inactive for 4 days are permanently purged without asking the user.
- **How to reproduce:**
  1. Set system clock ahead 5 days.
  2. Launch Zeno.
  3. All chat history in `chats.json` is purged.

---

### BUG-15: Command Guard Blocks Polyglot Stacks
- **Location:** `zeno/safety/command_guard.py:18–27, 30–32, 60–66`.
- **What the user sees:**
  Tasks requiring Node/npm, Django dev server, Flask, Playwright, or tkinter fail with "Command contains forbidden shell metacharacter" or "Executable not allowed".
- **Why it happens:**
  `DEFAULT_ALLOWLIST` only contains 8 binaries (`git`, `python`, `pip`, `pytest`, `ruff`, `mypy`, `pip-audit`, `bandit`). Furthermore, `FORBIDDEN_SHELL_TOKENS` contains `(`, `)`, which causes safe commands like `python -c "import tkinter"` to be rejected.
- **How to reproduce:**
  1. Ask agent to run `npm test` or a python inline command containing parentheses.
  2. Command is blocked by `parse_and_validate_command`.

---

### BUG-16: Python Runner Uses Host Interpreter Instead of Project `.venv`
- **Location:** `zeno/tools/python_tools.py:41–47`.
- **What the user sees:**
  Packages installed during a task cannot be imported when running code via `run_python`, failing with `ModuleNotFoundError`.
- **Why it happens:**
  `run_python` invokes `subprocess.run([sys.executable, temp_file])`. `sys.executable` points to the global Python interpreter that started Zeno, not the isolated project virtual environment (`.venv/Scripts/python.exe`). Furthermore, `cwd` is omitted, causing relative file reads to fail.
- **How to reproduce:**
  1. Pip install a package into a task venv.
  2. Invoke `run_python` to import that package. It fails with `ModuleNotFoundError`.

---

### BUG-17: Concurrent Agent Trigger Overwrites Active State (No Run Queue)
- **Location:** `src/App.tsx:1388–1415`.
- **What the user sees:**
  Triggering an agent task while another task is running overwrites `activeAgentState` and cancels or corrupts the active task.
- **Why it happens:**
  There is no queue data structure. The application supports only one global active task at a time and overrides state variables directly.
- **How to reproduce:**
  1. Trigger an agent task.
  2. Trigger a second agent task before the first completes. The first task state is lost.

---

### BUG-18: `server.ts` Uses `python3` Failing on Windows
- **Location:** `server.ts:206`.
- **What the user sees:**
  When testing the web server in Windows dev mode, running Python via `/api/run-python` returns exit code error `spawn python3 ENOENT`.
- **Why it happens:**
  Windows does not have `python3.exe` by default (it uses `python.exe` or `py.exe`).
- **How to reproduce:**
  1. Start `npm run dev` on Windows.
  2. Send a POST request to `/api/run-python`. It fails with `python3: command not found`.

---

### BUG-19: Human Approval Decisions in UI Do Not Resume Waiting Agent Tasks
- **Location:** `src/App.tsx:497–502`, `zeno/safety/approvals.py:20–35`.
- **What the user sees:**
  When a pending approval appears in the UI and the user clicks "Approve", the approval card disappears, but the agent does not continue the blocked task.
- **Why it happens:**
  `handleDecideApproval` calls `window.pywebview.api.decide_approval`, which updates SQLite, but there is no notification mechanism or resume hook signaling the agent execution engine that approval was granted.
- **How to reproduce:**
  1. Trigger a tool requiring human approval (e.g. `pip_install`).
  2. Click "Approve" in the UI.
  3. The agent remains halted.

---

### BUG-20: Monolithic Frontend with Hardcoded Colors and No Design Tokens
- **Location:** `src/App.tsx:1–4543`.
- **What the user sees:**
  Inconsistent aesthetics, garish neon accents (`#3B82F6`, `#4ADE80`, `#818CF8`, `#EF4444`), visual clutter, and lack of cohesive design hierarchy.
- **Why it happens:**
  All UI logic, state, styles, and dialogs are placed inside a single 4,543-line file (`App.tsx`) with thousands of hardcoded inline Tailwind classes and hex color values. There is no central token system or component modularity.
- **How to reproduce:**
  1. Inspect `src/App.tsx` and observe the lack of modular components and hardcoded inline styles.
