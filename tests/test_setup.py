import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from judgment_layer.model import JudgmentError
from judgment_layer.setup import AGENTS, setup
from judgment_layer.store import Store


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="judgment setup ")
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_all_agents_share_self_contained_skills_and_manual_store(self):
        result = setup(self.root, ".judgment", list(AGENTS), "human:synthetic-owner")
        self.assertEqual(len(result["agents"]), 12)
        self.assertEqual(len(result["skill_directories"]), 3)
        self.assertFalse(result["hooks_installed"])
        for path in result["skill_directories"]:
            skill = Path(path)
            body = (skill / "SKILL.md").read_text()
            argument = body.split("`--workspace ", 1)[1].split("`", 1)[0]
            self.assertEqual(shlex.split(argument), [str(self.root / ".judgment")])
            self.assertNotIn("{{WORKSPACE_ARGUMENT}}", body)
            doc = json.loads((skill / "references/coding.json").read_text())
            json.loads((skill / "references/ajf.schema.json").read_text())
            self.assertTrue((skill / "references/workflow.md").is_file())
        store = Store(self.root / ".judgment")
        try:
            with store.transaction():
                candidate = store.capture(doc)
                self.assertEqual(candidate["state"], "proposed")
                packet = store.context("coding/generated-files", {"generated_file": True},
                                       "agent:test", "Synthetic installer test")
                self.assertEqual(packet["judgments"], [])
        finally:
            store.close()
        self.assertEqual((self.root / ".judgment/.gitignore").read_text(), "*\n")

    def test_dry_run_changes_nothing(self):
        result = setup(self.root, ".judgment", list(AGENTS), dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_repeat_preserves_store_and_rejects_owner_change(self):
        setup(self.root, ".judgment", ["codex"], "human:synthetic-owner")
        config = self.root / ".judgment/config.json"
        db = self.root / ".judgment/store.sqlite3"
        before = (config.read_bytes(), db.read_bytes())
        result = setup(self.root, ".judgment", ["codex"])
        self.assertEqual(result["created"], [])
        self.assertEqual(before, (config.read_bytes(), db.read_bytes()))
        with self.assertRaises(JudgmentError):
            setup(self.root, ".judgment", ["codex"], "human:someone-else")
        self.assertEqual(before, (config.read_bytes(), db.read_bytes()))

    def test_conflict_prevents_store_and_all_other_writes(self):
        target = self.root / ".claude/skills/proofpress/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("Keep my instructions")
        with self.assertRaises(JudgmentError):
            setup(self.root, ".judgment", list(AGENTS), "human:synthetic-owner")
        self.assertEqual(target.read_text(), "Keep my instructions")
        self.assertFalse((self.root / ".agents").exists())
        self.assertFalse((self.root / ".judgment").exists())

    def test_legacy_skill_is_not_duplicated_or_deleted(self):
        legacy = self.root / ".agents/skills/judgment-layer/SKILL.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("User-edited legacy skill")
        with self.assertRaises(JudgmentError):
            setup(self.root, ".judgment", ["codex"], "human:synthetic-owner")
        self.assertEqual(legacy.read_text(), "User-edited legacy skill")
        self.assertFalse((self.root / ".agents/skills/proofpress").exists())
        self.assertFalse((self.root / ".judgment").exists())

    def test_broken_existing_store_is_not_reported_ready(self):
        setup(self.root, ".judgment", ["codex"], "human:synthetic-owner")
        (self.root / ".judgment/store.sqlite3").unlink()
        with self.assertRaises(JudgmentError):
            setup(self.root, ".judgment", ["claude-code"])
        self.assertFalse((self.root / ".claude").exists())

    def test_symlink_cannot_redirect_setup_outside_project(self):
        outside = self.root / "outside"
        outside.mkdir()
        project = self.root / "project"
        project.mkdir()
        (project / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(JudgmentError):
            setup(project, ".judgment", ["codex"], "human:synthetic-owner")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((project / ".judgment").exists())

    def test_workspace_selection_is_project_local_and_explicit(self):
        result = setup(self.root, "private/store", ["cursor"], "human:synthetic-owner")
        self.assertEqual(result["workspace"], str(self.root / "private/store"))
        with self.assertRaises(JudgmentError):
            setup(self.root, "../escape", ["cursor"], "human:synthetic-owner")
        with self.assertRaises(JudgmentError):
            setup(self.root, "new-store", ["cursor"])
        self.assertFalse((self.root / "new-store").exists())

    def test_cli_setup_and_example_work_outside_checkout(self):
        def cli(*args):
            return subprocess.run([sys.executable, "-m", "judgment_layer.cli", *args],
                                  cwd=self.root, text=True, capture_output=True)
        result = cli("setup", "--agents", "grok", "devin", "hermes", "--owner", "human:synthetic-owner", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        example = cli("example")
        self.assertEqual(example.returncode, 0, example.stderr)
        candidate = self.root / "candidate.json"
        candidate.write_text(example.stdout)
        captured = cli("capture", "--from", str(candidate), "--json")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        self.assertEqual(json.loads(captured.stdout)["state"], "proposed")
        self.assertEqual(cli("schema").returncode, 0)


if __name__ == "__main__":
    unittest.main()
