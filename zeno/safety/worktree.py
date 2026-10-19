"""
Git Worktree Isolation and Checkpoint Manager for Zeno Autonomous Agents.
Guarantees background tasks operate exclusively inside isolated git worktrees
on 'agent/<job-id>' branches, preventing any modification of the user's active
working directory or the main/master branches.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Optional


class WorktreeError(Exception):
    """Raised when git repository validation or worktree operations fail."""
    pass


def is_git_repository(project_path: str | Path) -> bool:
    """Check if project_path is a valid git repository worktree."""
    try:
        p = Path(project_path).resolve()
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(p),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=False,
            timeout=5,
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_current_commit_hash(project_path: str | Path) -> str:
    """Get the current HEAD commit hash of the git repository."""
    p = Path(project_path).resolve()
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(p),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=5,
    )
    if res.returncode != 0:
        raise WorktreeError(f"Failed to read HEAD commit hash: {res.stderr.strip()}")
    return res.stdout.strip()


def setup_agent_worktree(project_path: str | Path, job_id: str) -> dict[str, str]:
    """
    Establish an isolated git worktree for a background job:
    1. Validates git repository.
    2. Records base commit checkpoint.
    3. Creates worktree at .zeno_worktrees/<job-id> on branch agent/<job-id>.
    Returns: {"worktree_path": str, "base_commit": str, "branch": str}
    """
    proj = Path(project_path).resolve()
    if not is_git_repository(proj):
        raise WorktreeError(
            f"Project directory '{proj}' is not a git repository. "
            f"Autonomous background tasks require git version control for worktree isolation."
        )

    base_commit = get_current_commit_hash(proj)
    branch_name = f"agent/{job_id}"
    worktree_dir = proj / ".zeno_worktrees" / job_id

    # Create parent folder
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing worktree if stale
    if worktree_dir.exists():
        cleanup_agent_worktree(proj, job_id)

    # git worktree add -b <branch> <path> HEAD
    cmd = ["git", "worktree", "add", "-b", branch_name, str(worktree_dir), "HEAD"]
    res = subprocess.run(
        cmd,
        cwd=str(proj),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=15,
    )
    if res.returncode != 0:
        raise WorktreeError(f"Failed to create git worktree: {res.stderr.strip()}")

    return {
        "worktree_path": str(worktree_dir),
        "base_commit": base_commit,
        "branch": branch_name,
    }


def rollback_agent_worktree(
    project_path: str | Path,
    job_id: str,
    checkpoint_hash: str,
    force: bool = False,
) -> dict[str, Any]:
    """
    Reset the agent's worktree to the recorded checkpoint commit.
    Requires force=True if uncommitted changes exist.
    """
    proj = Path(project_path).resolve()
    worktree_dir = proj / ".zeno_worktrees" / job_id
    if not worktree_dir.exists():
        return {"ok": False, "error": f"Worktree for job '{job_id}' does not exist."}

    # Check for uncommitted changes
    status_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(worktree_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=5,
    )
    has_uncommitted = bool(status_res.stdout.strip())
    if has_uncommitted and not force:
        return {
            "ok": False,
            "requires_approval": True,
            "error": "Worktree contains uncommitted modifications. Rollback requires approval to discard them.",
        }

    # git reset --hard <checkpoint_hash>
    reset_res = subprocess.run(
        ["git", "reset", "--hard", checkpoint_hash],
        cwd=str(worktree_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        timeout=10,
    )
    if reset_res.returncode != 0:
        return {"ok": False, "error": f"Git reset failed: {reset_res.stderr.strip()}"}

    return {"ok": True, "checkpoint": checkpoint_hash, "worktree": str(worktree_dir)}


def cleanup_agent_worktree(project_path: str | Path, job_id: str) -> bool:
    """Remove worktree and prune metadata."""
    proj = Path(project_path).resolve()
    worktree_dir = proj / ".zeno_worktrees" / job_id
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_dir)],
            cwd=str(proj),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=10,
        )
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(proj),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=5,
        )
        return True
    except Exception:
        return False


def rollback_worktree(project_path: str | Path, branch_name: str, approved: bool = False) -> tuple[bool, str]:
    """Safeguard: check that branch is an agent isolated branch and not protected main/master."""
    if branch_name.lower() in ("main", "master"):
        return False, "Protected branch: rolling back main/master is strictly refused."
    return True, f"Rollback permitted on isolated branch {branch_name}."
