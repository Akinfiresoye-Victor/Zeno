"""
Checklist Task Engine for Zeno Desktop AI Assistant.
Enforces Rule C: Python-verified checklist as the single source of truth.
Manages step dependencies, verification gating, step jump-backs, retries, and checkpointing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("zeno.checklist")


class StepStatus:
    PENDING = "pending"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"
    NEEDS_REVISION = "needs_revision"
    CANCELLED = "cancelled"


@dataclass
class StepEvidence:
    files_created: list[str] = field(default_factory=list)
    command_exit_codes: list[int] = field(default_factory=list)
    test_results: Optional[dict[str, Any]] = None
    screenshot_path: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class OrchidVerdictRecord:
    verdict: str = "ALLOW"  # ALLOW, DENY, ASK_USER
    rule: str = "rule_default"
    reason: str = "Pre-approved safe operation."
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ChecklistStep:
    id: str
    title: str
    dependencies: list[str] = field(default_factory=list)
    status: str = StepStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    evidence: StepEvidence = field(default_factory=StepEvidence)
    orchid_verdict: Optional[OrchidVerdictRecord] = None
    required_files: list[str] = field(default_factory=list)
    required_tests: list[str] = field(default_factory=list)
    revision_reason: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChecklistStep":
        evidence_data = data.get("evidence") or {}
        evidence = StepEvidence(
            files_created=evidence_data.get("files_created", []),
            command_exit_codes=evidence_data.get("command_exit_codes", []),
            test_results=evidence_data.get("test_results"),
            screenshot_path=evidence_data.get("screenshot_path"),
            notes=evidence_data.get("notes"),
        )
        orchid_data = data.get("orchid_verdict")
        orchid = (
            OrchidVerdictRecord(
                verdict=orchid_data.get("verdict", "ALLOW"),
                rule=orchid_data.get("rule", "rule_default"),
                reason=orchid_data.get("reason", ""),
                timestamp=orchid_data.get("timestamp", datetime.now().isoformat()),
            )
            if orchid_data
            else None
        )
        return cls(
            id=data["id"],
            title=data["title"],
            dependencies=data.get("dependencies", []),
            status=data.get("status", StepStatus.PENDING),
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            evidence=evidence,
            orchid_verdict=orchid,
            required_files=data.get("required_files", []),
            required_tests=data.get("required_tests", []),
            revision_reason=data.get("revision_reason"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            duration_seconds=data.get("duration_seconds", 0.0),
        )


class ChecklistEngine:
    """
    Checklist engine managing checklist.json inside the project folder.
    Guarantees Python verification gating: The model cannot mark a step done by itself.
    """

    def __init__(self, project_dir: Path | str, plan_title: str = "Project Task"):
        self.project_dir = Path(project_dir).resolve()
        self.plan_title = plan_title
        self.checklist_file = self.project_dir / "checklist.json"
        self.steps: list[ChecklistStep] = []
        self.history_jumps: list[dict[str, Any]] = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.active_step_id: Optional[str] = None
        self.is_paused: bool = False
        self.pause_reason: Optional[str] = None

        if self.checklist_file.exists():
            self.load()

    def initialize_steps(self, steps_data: list[dict[str, Any] | str]) -> None:
        """Initialize steps list from structured dicts or plain text strings."""
        self.steps = []
        for idx, item in enumerate(steps_data):
            step_id = f"step-{idx + 1}"
            if isinstance(item, str):
                deps = [f"step-{idx}"] if idx > 0 else []
                step = ChecklistStep(id=step_id, title=item.strip(), dependencies=deps)
            else:
                deps = item.get("dependencies")
                if deps is None:
                    deps = [f"step-{idx}"] if idx > 0 else []
                step = ChecklistStep(
                    id=item.get("id", step_id),
                    title=item.get("title", f"Step {idx + 1}"),
                    dependencies=deps,
                    max_attempts=item.get("max_attempts", 3),
                    required_files=item.get("required_files", []),
                    required_tests=item.get("required_tests", []),
                )
            self.steps.append(step)
        self.save()

    def save(self) -> None:
        """Persist checklist state atomically to checklist.json."""
        self.updated_at = datetime.now().isoformat()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": self.plan_title,
            "project_dir": str(self.project_dir),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "active_step_id": self.active_step_id,
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "jumps": self.history_jumps,
            "steps": [s.to_dict() for s in self.steps],
        }
        temp_file = self.project_dir / "checklist.json.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(self.checklist_file)

    def load(self) -> bool:
        """Load checklist state from checklist.json."""
        if not self.checklist_file.exists():
            return False
        try:
            with open(self.checklist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.plan_title = data.get("title", self.plan_title)
            self.created_at = data.get("created_at", self.created_at)
            self.updated_at = data.get("updated_at", self.updated_at)
            self.active_step_id = data.get("active_step_id")
            self.is_paused = data.get("is_paused", False)
            self.pause_reason = data.get("pause_reason")
            self.history_jumps = data.get("jumps", [])
            self.steps = [ChecklistStep.from_dict(s) for s in data.get("steps", [])]
            return True
        except Exception as exc:
            logger.error("Failed to load checklist.json: %s", exc)
            return False

    def get_step(self, step_id: str) -> Optional[ChecklistStep]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def can_start_step(self, step_id: str) -> tuple[bool, str]:
        """A step cannot start until every step it depends on is 'verified'."""
        step = self.get_step(step_id)
        if not step:
            return False, f"Step '{step_id}' does not exist."

        for dep_id in step.dependencies:
            dep_step = self.get_step(dep_id)
            if not dep_step:
                return False, f"Dependency step '{dep_id}' not found."
            if dep_step.status != StepStatus.VERIFIED:
                return False, f"Dependency '{dep_id}' ({dep_step.title}) is not verified (status: {dep_step.status})."

        return True, ""

    def start_step(self, step_id: str) -> tuple[bool, str]:
        """Mark a step as RUNNING if dependencies are met and attempts limit not exceeded."""
        step = self.get_step(step_id)
        if not step:
            return False, f"Step '{step_id}' not found."

        allowed, reason = self.can_start_step(step_id)
        if not allowed:
            return False, reason

        if step.attempts >= step.max_attempts:
            step.status = StepStatus.FAILED
            self.is_paused = True
            self.pause_reason = f"Step '{step_id}' exhausted maximum retry attempts ({step.max_attempts})."
            self.save()
            return False, self.pause_reason

        step.attempts += 1
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now().isoformat()
        self.active_step_id = step_id
        self.is_paused = False
        self.pause_reason = None
        self.save()
        return True, ""

    def verify_step(
        self,
        step_id: str,
        files_created: Optional[list[str]] = None,
        command_exit_codes: Optional[list[int]] = None,
        test_results: Optional[dict[str, Any]] = None,
        screenshot_path: Optional[str] = None,
        orchid_verdict: Optional[dict[str, Any]] = None,
        custom_validator: Optional[Callable[[ChecklistStep], tuple[bool, str]]] = None,
    ) -> tuple[bool, str]:
        """
        Python decides when a step is complete.
        Verification gating:
        1. Required output files exist and are non-empty.
        2. All command exit codes are 0.
        3. Automated tests pass (if any).
        4. Orchid approved the step's actions.
        """
        step = self.get_step(step_id)
        if not step:
            return False, f"Step '{step_id}' not found."

        # Collect evidence
        if files_created:
            step.evidence.files_created = list(set(step.evidence.files_created + files_created))
        if command_exit_codes is not None:
            step.evidence.command_exit_codes = list(command_exit_codes)
        if test_results:
            step.evidence.test_results = test_results
        if screenshot_path:
            step.evidence.screenshot_path = screenshot_path

        if orchid_verdict:
            step.orchid_verdict = OrchidVerdictRecord(
                verdict=orchid_verdict.get("verdict", "ALLOW"),
                rule=orchid_verdict.get("rule", "rule_general"),
                reason=orchid_verdict.get("reason", "Approved by Orchid"),
            )

        # 1. Orchid Safety Gate
        if step.orchid_verdict and step.orchid_verdict.verdict == "DENY":
            step.status = StepStatus.FAILED
            self.save()
            return False, f"Verification failed: Orchid rejected step action: {step.orchid_verdict.reason}"

        # 2. Command Exit Code Gate
        for code in step.evidence.command_exit_codes:
            if code != 0:
                step.status = StepStatus.FAILED
                self.save()
                return False, f"Verification failed: Subprocess command returned non-zero exit code ({code})."

        # 3. Required Files Gate
        for req_rel in step.required_files:
            file_path = self.project_dir / req_rel
            if not file_path.exists():
                step.status = StepStatus.FAILED
                self.save()
                return False, f"Verification failed: Required output file '{req_rel}' does not exist."
            if file_path.is_file() and file_path.stat().st_size == 0:
                step.status = StepStatus.FAILED
                self.save()
                return False, f"Verification failed: Required output file '{req_rel}' is empty (0 bytes)."

        # 4. Test Suite Gate
        if step.evidence.test_results:
            failed_tests = step.evidence.test_results.get("failed", 0)
            errors = step.evidence.test_results.get("errors", 0)
            if failed_tests > 0 or errors > 0:
                step.status = StepStatus.FAILED
                self.save()
                return False, f"Verification failed: Tests failed ({failed_tests} failed, {errors} errors)."

        # 5. Optional Custom Validator
        if custom_validator:
            passed, val_err = custom_validator(step)
            if not passed:
                step.status = StepStatus.FAILED
                self.save()
                return False, f"Verification failed: {val_err}"

        # ALL checks passed -> Step is officially VERIFIED
        step.status = StepStatus.VERIFIED
        step.finished_at = datetime.now().isoformat()
        if step.started_at:
            try:
                start_dt = datetime.fromisoformat(step.started_at)
                step.duration_seconds = max(0.0, (datetime.now() - start_dt).total_seconds())
            except Exception:
                pass

        if self.active_step_id == step_id:
            self.active_step_id = None

        self.save()
        return True, "Step verified successfully."

    def find_dependent_steps(self, target_step_id: str) -> list[str]:
        """Find all steps directly or transitively dependent on target_step_id."""
        dependents: set[str] = set()
        queue = [target_step_id]

        while queue:
            current = queue.pop(0)
            for s in self.steps:
                if current in s.dependencies and s.id not in dependents:
                    dependents.add(s.id)
                    queue.append(s.id)

        # Return ordered by index in plan
        step_order = {s.id: idx for idx, s in enumerate(self.steps)}
        return sorted(list(dependents), key=lambda sid: step_order.get(sid, 999))

    def jump_back_for_revision(
        self,
        from_step_id: str,
        to_step_id: str,
        reason: str,
    ) -> tuple[bool, list[str]]:
        """
        Revisiting earlier steps:
        Mark target step as 'needs_revision', log the jump,
        and invalidate only the steps that depend on target_step_id.
        """
        to_step = self.get_step(to_step_id)
        if not to_step:
            return False, []

        to_step.status = StepStatus.NEEDS_REVISION
        to_step.revision_reason = reason

        # Find downstream steps that depend on to_step_id
        downstream = self.find_dependent_steps(to_step_id)
        for dep_id in downstream:
            dep_step = self.get_step(dep_id)
            if dep_step and dep_step.status == StepStatus.VERIFIED:
                dep_step.status = StepStatus.NEEDS_REVISION

        # Record jump in history
        jump_record = {
            "from_step": from_step_id,
            "to_step": to_step_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "invalidated_steps": downstream,
        }
        self.history_jumps.append(jump_record)
        self.active_step_id = to_step_id
        self.save()
        return True, downstream

    def get_next_runnable_step(self) -> Optional[ChecklistStep]:
        """Find the next step ready to execute (dependencies met, not verified)."""
        # First priority: any step marked needs_revision
        for s in self.steps:
            if s.status == StepStatus.NEEDS_REVISION:
                allowed, _ = self.can_start_step(s.id)
                if allowed:
                    return s

        # Second priority: next pending step whose dependencies are satisfied
        for s in self.steps:
            if s.status == StepStatus.PENDING:
                allowed, _ = self.can_start_step(s.id)
                if allowed:
                    return s

        return None

    def is_all_verified(self) -> bool:
        """Return True if all steps in the plan are VERIFIED."""
        if not self.steps:
            return False
        return all(s.status == StepStatus.VERIFIED for s in self.steps)

    def get_progress_summary(self) -> dict[str, Any]:
        """Return accurate, unified step progress metrics."""
        total = len(self.steps)
        verified = sum(1 for s in self.steps if s.status == StepStatus.VERIFIED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        needs_rev = sum(1 for s in self.steps if s.status == StepStatus.NEEDS_REVISION)

        current_idx = 0
        if self.active_step_id:
            for idx, s in enumerate(self.steps):
                if s.id == self.active_step_id:
                    current_idx = idx + 1
                    break
        elif verified < total:
            current_idx = verified + 1
        else:
            current_idx = total

        return {
            "total_steps": total,
            "verified_steps": verified,
            "failed_steps": failed,
            "needs_revision_steps": needs_rev,
            "current_step_number": current_idx,
            "active_step_id": self.active_step_id,
            "is_complete": self.is_all_verified(),
            "is_paused": self.is_paused,
            "pause_reason": self.pause_reason,
            "percent": round((verified / total * 100), 1) if total > 0 else 0,
        }
