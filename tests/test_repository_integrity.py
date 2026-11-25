import ast
import pathlib
import unittest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]

class RepositoryIntegrityTests(unittest.TestCase):
    def test_agent_python_syntax(self):
        for path in (ROOT / "agents").glob("*.py"):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_workflow_yaml_and_jobs(self):
        paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)
                self.assertTrue(data.get("jobs"))

    def test_docs_and_dependencies(self):
        for name in ("README.md", "requirements.txt", ".gitignore"):
            self.assertTrue((ROOT / name).is_file())

    def test_meta_requires_explicit_approval_and_separate_posts(self):
        source = (ROOT / "agents" / "meta_publisher.py").read_text(encoding="utf-8")
        self.assertIn('required("PUBLISH_APPROVAL") != "APPROVE"', source)
        self.assertIn("IMAGE_CAPTION", source)
        self.assertIn("VIDEO_CAPTION", source)

    def test_video_generation_removed_prompt_agent_present(self):
        self.assertTrue((ROOT / "agents" / "video_prompt_agent.py").is_file())
        self.assertFalse((ROOT / "agents" / "video_creator.py").exists())

if __name__ == "__main__":
    unittest.main()
