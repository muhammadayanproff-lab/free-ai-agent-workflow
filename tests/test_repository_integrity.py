import ast
import pathlib
import unittest
import yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
class RepositoryIntegrityTests(unittest.TestCase):
 def test_agent_python_syntax(self):
  for path in (ROOT/'agents').glob('*.py'):
   with self.subTest(path=path.name): ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
 def test_workflow_yaml_and_jobs(self):
  paths=sorted((ROOT/'.github'/'workflows').glob('*.yml'))
  self.assertTrue(paths)
  for path in paths:
   with self.subTest(path=path.name):
    data=yaml.safe_load(path.read_text(encoding='utf-8'))
    self.assertIsInstance(data,dict)
    self.assertTrue(data.get('jobs'))
 def test_docs_and_dependencies(self):
  for name in ('README.md','requirements.txt','.gitignore'): self.assertTrue((ROOT/name).is_file())
 def test_meta_requires_explicit_approval(self):
  s=(ROOT/'agents'/'meta_publisher.py').read_text(encoding='utf-8')
  self.assertIn('approval != "APPROVE"',s)
 def test_vertical_video_contract(self):
  s=(ROOT/'agents'/'video_creator.py').read_text(encoding='utf-8')
  self.assertIn('duration < 10',s); self.assertIn('width=1080',s); self.assertIn('height=1920',s)
if __name__=='__main__': unittest.main()
