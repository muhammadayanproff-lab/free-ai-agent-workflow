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

    def test_meta_requires_explicit_approval_and_four_captions(self):
        source = (ROOT / "agents" / "meta_publisher.py").read_text(encoding="utf-8")
        self.assertIn('required("PUBLISH_APPROVAL")', source)
        self.assertIn('!= "APPROVE"', source)
        for key in ("instagram_image_caption", "facebook_image_caption", "instagram_video_caption", "facebook_video_caption"):
            self.assertIn(key, source)

    def test_video_generation_removed_prompt_agent_present(self):
        self.assertTrue((ROOT / "agents" / "video_prompt_agent.py").is_file())
        self.assertFalse((ROOT / "agents" / "video_creator.py").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "video_prompt.yml").exists())
        self.assertFalse((ROOT / "agents" / "manager.py").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "manager.yml").exists())
        self.assertFalse((ROOT / "agents" / "trend_analyst.py").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "trend_analyst.yml").exists())
        self.assertFalse((ROOT / "agents" / "video_creator.py").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "video_creator.yml").exists())
        self.assertFalse((ROOT / ".github" / "workflows" / "daily_campaign.yml").exists())

    def test_product_discovery_artifact_handoff_path_matches(self):
        discovery = (ROOT / ".github" / "workflows" / "product_discovery.yml").read_text(encoding="utf-8")
        campaign = (ROOT / ".github" / "workflows" / "campaign_assets.yml").read_text(encoding="utf-8")
        prepare = (ROOT / "agents" / "prepare_product.py").read_text(encoding="utf-8")
        self.assertIn("product_discovery_output/", discovery)
        self.assertIn("--dir product_discovery_output", campaign)
        self.assertIn("product_discovery_output/selected_product.json", prepare)

    def test_video_upload_preset_is_automated(self):
        self.assertTrue((ROOT / "agents" / "configure_video_upload.py").is_file())
        self.assertTrue((ROOT / ".github" / "workflows" / "configure_video_upload.yml").is_file())
        page = (ROOT / "docs" / "upload-video.html").read_text(encoding="utf-8")
        self.assertIn("click_collect_manual_video", page)


    def test_alternate_day_2pm_pakistan_schedule_and_auto_handoff(self):
        discovery = (ROOT / ".github" / "workflows" / "product_discovery.yml").read_text(encoding="utf-8")
        campaign = (ROOT / ".github" / "workflows" / "campaign_assets.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "0 9 * * *"', discovery)
        self.assertIn('ZoneInfo("Asia/Karachi")', discovery)
        self.assertIn("days % 2 == 0", discovery)
        self.assertIn('workflows: ["Pakistan Product Discovery"]', campaign)
        self.assertIn("workflow_run:", campaign)
        self.assertNotIn("cod_confirmed:", campaign)
        self.assertIn("Notify owner that the video prompt is ready", campaign)
        self.assertIn("gh issue create", campaign)
        self.assertIn("issues: write", campaign)

    def test_video_upload_auto_approval_and_owner_gate(self):
        watcher = (ROOT / ".github" / "workflows" / "video_upload_watcher.yml").read_text(encoding="utf-8")
        publisher = (ROOT / ".github" / "workflows" / "meta_publisher.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "*/5 * * * *"', watcher)
        self.assertIn("agents/video_upload_watcher.py", watcher)
        self.assertIn("issue_comment:", publisher)
        self.assertIn("github.event.comment.body == 'APPROVE'", publisher)
        self.assertIn("github.event.comment.user.login == github.repository_owner", publisher)
        self.assertTrue((ROOT / "agents" / "video_upload_watcher.py").is_file())

    def test_checkout_claims_are_not_assumed(self):
        prepare = (ROOT / "agents" / "prepare_product.py").read_text(encoding="utf-8")
        copywriter = (ROOT / "agents" / "campaign_copywriter.py").read_text(encoding="utf-8")
        self.assertIn('"cod_confirmed_by_owner": False', prepare)
        self.assertIn("never promise COD", copywriter)

    def test_manual_video_upload_page_present(self):
        self.assertTrue((ROOT / "docs" / "upload-video.html").is_file())

if __name__ == "__main__":
    unittest.main()
