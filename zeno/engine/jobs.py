"""
Job Supervisor & Process Execution Engine for Zeno Desktop AI Assistant.
Enforces Rule E & Rule G:
- Flexible command execution for any stack (Django, Flask, tkinter, Node, etc.).
- Process tracking with PID, live streaming logs, execution duration, and exit codes.
- Long-running dev server supervision with automated HTTP health check verification.
- Visual evidence capture: GUI window capture (mss/Pillow) and web snapshots.
- Reliable whole-process-tree termination (taskkill /T /F on Windows, psutil fallback).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Optional
import urllib.error
import urllib.request

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("zeno.jobs")


@dataclass
class JobRecord:
    job_id: str
    command: str
    cwd: str
    pid: Optional[int] = None
    status: str = "queued"  # queued, running, finished, stopped_by_user, failed
    exit_code: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0
    log_file: Optional[str] = None
    is_server: bool = False
    server_url: Optional[str] = None
    health_check_passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "cwd": self.cwd,
            "pid": self.pid,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 1),
            "log_file": self.log_file,
            "is_server": self.is_server,
            "server_url": self.server_url,
            "health_check_passed": self.health_check_passed,
        }


class JobSupervisor:
    """
    Central process supervisor tracking all commands, scripts, and background servers.
    Provides live streaming logs and reliable whole-process-tree termination.
    """

    _instance: Optional["JobSupervisor"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.jobs: dict[str, JobRecord] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.log_buffers: dict[str, list[str]] = {}
        self._monitor_threads: dict[str, threading.Thread] = {}

    @classmethod
    def get_instance(cls) -> "JobSupervisor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def kill_process_tree(self, pid: int) -> bool:
        """
        Kill a process and ALL its children.
        On Windows, invokes 'taskkill /PID <pid> /T /F'.
        Falls back to psutil recursive kill.
        """
        if not pid:
            return False

        logger.info("Terminating process tree for PID %s...", pid)

        # 1. Windows taskkill /T /F
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            except Exception as exc:
                logger.warning("taskkill failed for PID %s: %s", pid, exc)

        # 2. psutil recursive cleanup fallback
        if psutil is not None:
            try:
                parent = psutil.Process(pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                parent.kill()
                return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return True
            except Exception as exc:
                logger.warning("psutil kill failed for PID %s: %s", pid, exc)

        return True

    def start_job(
        self,
        command_args: list[str] | str,
        cwd: Path | str,
        job_id: Optional[str] = None,
        is_server: bool = False,
        server_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> JobRecord:
        """
        Start a tracked job with streaming stdout/stderr captured to log file.
        """
        cwd_path = Path(cwd).resolve()
        cwd_path.mkdir(parents=True, exist_ok=True)

        if not job_id:
            job_id = f"job-{int(time.time() * 1000)}-{os.getpid()}"

        cmd_display = " ".join(command_args) if isinstance(command_args, list) else command_args

        # Set up log file in project folder or cwd
        log_dir = cwd_path / ".zeno_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{job_id}.log"

        record = JobRecord(
            job_id=job_id,
            command=cmd_display,
            cwd=str(cwd_path),
            status="running",
            started_at=datetime.now().isoformat(),
            log_file=str(log_file),
            is_server=is_server,
            server_url=server_url,
        )
        self.jobs[job_id] = record
        self.log_buffers[job_id] = []

        # Open log file
        log_fp = open(log_file, "w", encoding="utf-8", errors="replace")

        try:
            # Start process with direct pipes
            proc = subprocess.Popen(
                command_args,
                cwd=str(cwd_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=False,
            )
            record.pid = proc.pid
            self.processes[job_id] = proc

            def stream_reader():
                start_t = time.time()
                try:
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        log_fp.write(line)
                        log_fp.flush()
                        self.log_buffers[job_id].append(line)
                        if len(self.log_buffers[job_id]) > 1000:
                            self.log_buffers[job_id].pop(0)
                        if log_callback:
                            try:
                                log_callback(line)
                            except Exception:
                                pass

                    proc.wait()
                    record.exit_code = proc.returncode
                    record.finished_at = datetime.now().isoformat()
                    record.duration_seconds = time.time() - start_t
                    if record.status == "running":
                        record.status = "finished" if record.exit_code == 0 else "failed"
                except Exception as exc:
                    logger.error("Error streaming logs for job %s: %s", job_id, exc)
                    record.status = "failed"
                finally:
                    log_fp.close()

            t = threading.Thread(target=stream_reader, daemon=True)
            t.start()
            self._monitor_threads[job_id] = t

            return record

        except Exception as exc:
            log_fp.close()
            record.status = "failed"
            record.exit_code = -1
            record.finished_at = datetime.now().isoformat()
            self.log_buffers[job_id].append(f"Failed to start process: {exc}\n")
            return record

    def stop_job(self, job_id: str) -> bool:
        """Terminate a specific job and its process tree."""
        record = self.jobs.get(job_id)
        if not record:
            return False

        proc = self.processes.get(job_id)
        pid = record.pid or (proc.pid if proc else None)

        if pid:
            self.kill_process_tree(pid)

        record.status = "stopped_by_user"
        record.finished_at = datetime.now().isoformat()
        return True

    def stop_all_jobs_for_cwd(self, cwd: Path | str) -> int:
        """Terminate all active jobs belonging to a project folder."""
        target_cwd = str(Path(cwd).resolve())
        stopped_count = 0
        for jid, rec in list(self.jobs.items()):
            if rec.status == "running" and rec.cwd == target_cwd:
                self.stop_job(jid)
                stopped_count += 1
        return stopped_count

    def perform_health_check(
        self,
        url: str,
        max_attempts: int = 15,
        delay_seconds: float = 1.0,
        expected_status: tuple[int, ...] = (200, 301, 302, 404),
    ) -> bool:
        """
        Perform automated HTTP health check against server URL.
        Rule E: Verify dev server responds before marking step complete.
        """
        for _ in range(max_attempts):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Zeno-HealthCheck/1.0"},
                )
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status in expected_status:
                        return True
            except urllib.error.HTTPError as he:
                if he.code in expected_status:
                    return True
            except Exception:
                pass
            time.sleep(delay_seconds)
        return False

    def capture_gui_window_screenshot(self, output_path: Path | str) -> Optional[Path]:
        """
        Capture a screenshot of a running desktop GUI window (e.g. tkinter).
        Saves screenshot to output_path.
        """
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                # Capture primary monitor
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img.save(str(out))
                return out
        except Exception as exc:
            logger.warning("GUI screenshot capture fallback: %s", exc)

        # Fallback using Pillow ImageGrab
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(str(out))
            return out
        except Exception as exc:
            logger.error("All screenshot capture methods failed: %s", exc)
            return None

    def get_job_logs(self, job_id: str, max_lines: int = 200) -> str:
        """Retrieve the recent lines from a job's log file or memory buffer."""
        record = self.jobs.get(job_id)
        if record and record.log_file and Path(record.log_file).exists():
            try:
                with open(record.log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                return "".join(lines[-max_lines:])
            except Exception:
                pass

        buf = self.log_buffers.get(job_id, [])
        return "".join(buf[-max_lines:])

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return list of all registered jobs formatted for the UI."""
        # Update running durations
        now = time.time()
        for jid, rec in self.jobs.items():
            if rec.status == "running" and rec.started_at:
                try:
                    s_dt = datetime.fromisoformat(rec.started_at)
                    rec.duration_seconds = now - s_dt.timestamp()
                except Exception:
                    pass

        return [j.to_dict() for j in self.jobs.values()]

    def clear_jobs(self, job_ids: Optional[list[str]] = None) -> dict[str, Any]:
        """Stop specified (or all) jobs and remove them from the supervisor list."""
        target_ids = list(job_ids) if job_ids is not None else list(self.jobs.keys())
        stopped_count = 0
        removed_count = 0
        with self._lock:
            for jid in target_ids:
                if jid in self.jobs:
                    if self.jobs[jid].status == "running":
                        self.stop_job(jid)
                        stopped_count += 1
                    del self.jobs[jid]
                    removed_count += 1
        return {"stopped": stopped_count, "removed": removed_count}
