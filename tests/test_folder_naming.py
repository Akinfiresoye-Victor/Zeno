import unittest
from pathlib import Path
import tempfile
import shutil

from zeno.engine.workspace import (
    sanitize_folder_name,
    generate_creative_folder_name,
    ProjectWorkspace,
)


class TestFolderNamingAndWorkspace(unittest.TestCase):
    def test_sanitize_folder_name_constraints(self):
        # Long phrase should be truncated to 2-4 words and max 32 chars
        raw = "Create A High Performance Full Stack Django REST API Service For Users"
        sanitized = sanitize_folder_name(raw)
        self.assertLessEqual(len(sanitized), 32)
        self.assertTrue(sanitized.islower())
        words = sanitized.split("-")
        self.assertTrue(2 <= len(words) <= 4)

        # Special characters removal
        raw_special = "My Project $$$ #1 @! Super Cool"
        sanitized_special = sanitize_folder_name(raw_special)
        self.assertTrue(sanitized_special.replace("-", "").isalnum())

        # Empty fallback
        self.assertEqual(sanitize_folder_name(""), "project-core")

    def test_generate_creative_folder_name(self):
        django_name = generate_creative_folder_name("Build a Django server for inventory")
        self.assertEqual(django_name, "django-core-api")

        car_name = generate_creative_folder_name("Build a 2D car racing game in Tkinter")
        self.assertEqual(car_name, "car-dash-tkinter")

    def test_collision_detection_suffix(self):
        tmp_root = Path(tempfile.mkdtemp(prefix="zeno_ws_test_"))
        try:
            ws1 = ProjectWorkspace(workspace_root=tmp_root, project_name="alpha-project")
            self.assertEqual(ws1.project_name, "alpha-project")
            self.assertTrue(ws1.project_dir.exists())

            # Second project with exact same name should get unique suffix
            ws2 = ProjectWorkspace(workspace_root=tmp_root, project_name="alpha-project")
            self.assertNotEqual(ws2.project_name, "alpha-project")
            self.assertTrue(ws2.project_name.startswith("alpha-project-") or "alpha" in ws2.project_name)
            self.assertLessEqual(len(ws2.project_name), 32)
            self.assertTrue(ws2.project_dir.exists())
            self.assertNotEqual(ws1.project_dir, ws2.project_dir)
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)

    def test_containment_check(self):
        tmp_root = Path(tempfile.mkdtemp(prefix="zeno_ws_test_"))
        try:
            ws = ProjectWorkspace(workspace_root=tmp_root, project_name="contained-app")
            # Inside project
            inside_file = ws.project_dir / "src" / "index.py"
            self.assertTrue(ws.is_path_inside(inside_file))

            # Outside project
            outside_file = tmp_root / "evil.txt"
            self.assertFalse(ws.is_path_inside(outside_file))
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
