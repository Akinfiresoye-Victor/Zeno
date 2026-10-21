"""
Unit tests for ChecklistEngine (Rule C).
Verifies:
1. Step dependency gating (cannot start until dependencies are verified).
2. Python verification gating (model cannot self-certify).
3. Jump-back logic (marks earlier step needs_revision, re-verifies dependent steps only).
4. Retry limits (pauses after 3 failed attempts).
5. Checkpoint resume (reloading from checklist.json preserves state).
"""

import json
from pathlib import Path
import tempfile
import unittest

from zeno.engine.checklist import ChecklistEngine, ChecklistStep, StepStatus


class TestChecklistEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
        self.engine = ChecklistEngine(self.project_path, plan_title="Unit Test Task")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dependency_gating(self):
        steps = [
            {"id": "step-1", "title": "Scaffold environment", "dependencies": []},
            {"id": "step-2", "title": "Implement core engine", "dependencies": ["step-1"]},
            {"id": "step-3", "title": "Run test suite", "dependencies": ["step-2"]},
        ]
        self.engine.initialize_steps(steps)

        # Step 2 cannot start because Step 1 is pending
        can_start, reason = self.engine.can_start_step("step-2")
        self.assertFalse(can_start)
        self.assertIn("not verified", reason)

        # Start and verify Step 1
        self.engine.start_step("step-1")
        verified, vmsg = self.engine.verify_step("step-1", command_exit_codes=[0])
        self.assertTrue(verified)

        # Now Step 2 can start
        can_start_2, _ = self.engine.can_start_step("step-2")
        self.assertTrue(can_start_2)

    def test_python_verification_gating(self):
        steps = [
            {"id": "step-1", "title": "Create config", "required_files": ["config.json"]},
        ]
        self.engine.initialize_steps(steps)
        self.engine.start_step("step-1")

        # 1. Verification fails if required file does not exist
        ok, err = self.engine.verify_step("step-1", command_exit_codes=[0])
        self.assertFalse(ok)
        self.assertIn("does not exist", err)

        # 2. Verification fails if file exists but is 0 bytes
        cfg_file = self.project_path / "config.json"
        cfg_file.write_text("", encoding="utf-8")
        ok, err = self.engine.verify_step("step-1", command_exit_codes=[0])
        self.assertFalse(ok)
        self.assertIn("empty", err)

        # 3. Verification fails if command returned non-zero exit code
        cfg_file.write_text('{"key": "value"}', encoding="utf-8")
        ok, err = self.engine.verify_step("step-1", command_exit_codes=[1])
        self.assertFalse(ok)
        self.assertIn("non-zero exit code", err)

        # 4. Verification fails if Orchid denied the action
        ok, err = self.engine.verify_step(
            "step-1",
            command_exit_codes=[0],
            orchid_verdict={"verdict": "DENY", "reason": "Destructive wipe"},
        )
        self.assertFalse(ok)
        self.assertIn("Orchid rejected", err)

        # 5. Verification succeeds when all gates pass
        ok, msg = self.engine.verify_step(
            "step-1",
            command_exit_codes=[0],
            orchid_verdict={"verdict": "ALLOW", "reason": "Safe"},
        )
        self.assertTrue(ok)
        step = self.engine.get_step("step-1")
        self.assertEqual(step.status, StepStatus.VERIFIED)

    def test_jump_back_and_dependent_invalidation(self):
        # 5-step workflow: step-1 -> step-2 -> step-3 -> step-4 -> step-5
        # step-3 depends on step-2. step-4 does NOT depend on step-2 (e.g. docs). step-5 depends on step-3.
        steps = [
            {"id": "step-1", "title": "Setup", "dependencies": []},
            {"id": "step-2", "title": "Math utility", "dependencies": ["step-1"]},
            {"id": "step-3", "title": "Math tests", "dependencies": ["step-2"]},
            {"id": "step-4", "title": "Independent docs", "dependencies": ["step-1"]},
            {"id": "step-5", "title": "Final release", "dependencies": ["step-3", "step-4"]},
        ]
        self.engine.initialize_steps(steps)

        # Mark all steps 1 through 4 as verified
        for sid in ["step-1", "step-2", "step-3", "step-4"]:
            self.engine.start_step(sid)
            self.engine.verify_step(sid, command_exit_codes=[0])

        # Step 5 discovers a bug in Step 2's implementation
        success, invalidated = self.engine.jump_back_for_revision(
            from_step_id="step-5",
            to_step_id="step-2",
            reason="Step 5 discovered bug in step 2 factorial implementation",
        )
        self.assertTrue(success)

        # Step 2 must be marked needs_revision
        self.assertEqual(self.engine.get_step("step-2").status, StepStatus.NEEDS_REVISION)

        # Step 3 depends on Step 2 -> must be invalidated
        self.assertIn("step-3", invalidated)
        self.assertEqual(self.engine.get_step("step-3").status, StepStatus.NEEDS_REVISION)

        # Step 4 is independent of Step 2 -> must remain VERIFIED
        self.assertNotIn("step-4", invalidated)
        self.assertEqual(self.engine.get_step("step-4").status, StepStatus.VERIFIED)

        # Jump record logged
        self.assertEqual(len(self.engine.history_jumps), 1)
        self.assertEqual(self.engine.history_jumps[0]["from_step"], "step-5")
        self.assertEqual(self.engine.history_jumps[0]["to_step"], "step-2")

    def test_retry_limits(self):
        steps = [
            {"id": "step-1", "title": "Flaky task", "dependencies": [], "max_attempts": 3},
        ]
        self.engine.initialize_steps(steps)

        # Attempt 1
        self.engine.start_step("step-1")
        self.engine.verify_step("step-1", command_exit_codes=[1])

        # Attempt 2
        self.engine.start_step("step-1")
        self.engine.verify_step("step-1", command_exit_codes=[1])

        # Attempt 3
        self.engine.start_step("step-1")
        self.engine.verify_step("step-1", command_exit_codes=[1])

        # Attempt 4 should be rejected and pause the engine
        can_start, reason = self.engine.start_step("step-1")
        self.assertFalse(can_start)
        self.assertTrue(self.engine.is_paused)
        self.assertIn("exhausted maximum retry attempts", self.engine.pause_reason)

    def test_checkpoint_resume(self):
        steps = [
            {"id": "step-1", "title": "Initial setup", "dependencies": []},
            {"id": "step-2", "title": "Data processing", "dependencies": ["step-1"]},
        ]
        self.engine.initialize_steps(steps)

        # Execute and verify Step 1
        self.engine.start_step("step-1")
        self.engine.verify_step("step-1", command_exit_codes=[0])

        # Reload engine from disk (simulating application restart after crash)
        new_engine = ChecklistEngine(self.project_path)
        self.assertTrue(new_engine.load())

        step1 = new_engine.get_step("step-1")
        self.assertEqual(step1.status, StepStatus.VERIFIED)

        # Can immediately proceed to Step 2 without re-running Step 1
        can_start_2, _ = new_engine.can_start_step("step-2")
        self.assertTrue(can_start_2)


if __name__ == "__main__":
    unittest.main()
