import unittest
from pathlib import Path
import tempfile
import shutil

from zeno.safety.rules import OrchidSecurityKernel


class TestOrchidRules(unittest.TestCase):
    def test_destructive_command_deny(self):
        # rm -rf /
        eval1 = OrchidSecurityKernel.evaluate_command("rm -rf /")
        self.assertEqual(eval1.verdict, "DENY")
        self.assertEqual(eval1.rule_name, "rule_deny_destructive_wipe")

        # format c:
        eval2 = OrchidSecurityKernel.evaluate_command("format c: /fs:NTFS")
        self.assertEqual(eval2.verdict, "DENY")
        self.assertEqual(eval2.rule_name, "rule_deny_drive_format")

        # system directory access
        eval3 = OrchidSecurityKernel.evaluate_command("del C:\\Windows\\System32\\test.dll")
        self.assertEqual(eval3.verdict, "DENY")
        self.assertEqual(eval3.rule_name, "rule_deny_system_folder_access")

    def test_safe_operations_allow(self):
        # pip install inside .venv
        eval1 = OrchidSecurityKernel.evaluate_command(".venv\\Scripts\\pip install django")
        self.assertEqual(eval1.verdict, "ALLOW")
        self.assertEqual(eval1.rule_name, "rule_allow_venv_dependency_install")

        # pytest execution
        eval2 = OrchidSecurityKernel.evaluate_command("pytest tests/")
        self.assertEqual(eval2.verdict, "ALLOW")
        self.assertEqual(eval2.rule_name, "rule_allow_test_runner")

        # python manage.py runserver
        eval3 = OrchidSecurityKernel.evaluate_command("python manage.py runserver 127.0.0.1:8000")
        self.assertEqual(eval3.verdict, "ALLOW")
        self.assertEqual(eval3.rule_name, "rule_allow_project_python_exec")

    def test_unrecognized_command_ask_user(self):
        eval1 = OrchidSecurityKernel.evaluate_command("custom_unknown_binary.exe --flags")
        self.assertEqual(eval1.verdict, "ASK_USER")
        self.assertEqual(eval1.rule_name, "rule_escalate_unrecognized_command")

        # public interface binding
        eval2 = OrchidSecurityKernel.evaluate_command("python -m http.server 8080 --bind 0.0.0.0")
        self.assertEqual(eval2.verdict, "ASK_USER")
        self.assertEqual(eval2.rule_name, "rule_escalate_public_port_binding")

    def test_file_write_containment_evaluation(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="zeno_orchid_test_"))
        try:
            proj_dir = tmp_dir / "my-project"
            proj_dir.mkdir()

            # Inside project: ALLOW
            inside_file = proj_dir / "src" / "main.py"
            eval_inside = OrchidSecurityKernel.evaluate_file_write(inside_file, project_dir=proj_dir)
            self.assertEqual(eval_inside.verdict, "ALLOW")
            self.assertEqual(eval_inside.rule_name, "rule_allow_project_file_write")

            # Outside project: DENY
            outside_file = tmp_dir / "unauthorized.txt"
            eval_outside = OrchidSecurityKernel.evaluate_file_write(outside_file, project_dir=proj_dir)
            self.assertEqual(eval_outside.verdict, "DENY")
            self.assertEqual(eval_outside.rule_name, "rule_deny_write_outside_project")

            # System folder write: DENY
            sys_file = "C:\\Windows\\System32\\drivers\\etc\\hosts"
            eval_sys = OrchidSecurityKernel.evaluate_file_write(sys_file, project_dir=proj_dir)
            self.assertEqual(eval_sys.verdict, "DENY")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
