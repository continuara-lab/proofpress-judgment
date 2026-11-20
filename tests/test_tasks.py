"""Synthetic owner fixtures; no real provider or host calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from judgment_layer.model import JudgmentError
from judgment_layer.runtime import bind, gate, hook
from judgment_layer.store import Store, initialize
from judgment_layer.tasks import start_task, finish_task, check_release

ROOT = Path(__file__).resolve().parents[1]


class TaskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        initialize(self.root / "store", "human:synthetic-owner")
        self.store = Store(self.root / "store")
        self.doc = json.loads((ROOT / "examples/coding.json").read_text())
        self.doc["applicability"]["when"] = []
        self.item = self.admit(self.doc)
        self.scope = self.doc["applicability"]["scope"]
        self.outputs = {"generated/result.py": "complete fixture output"}
        self.model = patch("judgment_layer.tasks.assess", return_value={"choice": "pass"})
        self.assess = self.model.start()

    def tearDown(self):
        self.model.stop()
        self.store.close()
        self.temp.cleanup()

    def admit(self, doc):
        item = self.store.capture(doc)
        self.store.owner_action(item["id"], item["version"], item["digest"],
                                "admit", "Synthetic fixture only", True)
        return item

    def start(self, facts=None):
        return start_task(self.store, "fixture-task", self.scope, facts or {},
                          "Change source schema and regenerate the output.")

    def finish(self, facts=None):
        return finish_task(self.store, "fixture-task", facts or {}, self.outputs,
                           "Synthetic review evidence")

    def binding(self):
        return {"project_root": str(self.root), "scope": self.scope,
                "judgment_id": self.item["id"], "version": self.item["version"],
                "digest": self.item["digest"], "verifier": "task_boundary",
                "paths": ["generated/*"]}

    def event(self, path="generated/result.py", tool="Edit"):
        return {"cwd": str(self.root), "tool_name": tool,
                "proofpress_task_id": "fixture-task",
                "tool_input": {"file_path": str(self.root / path)}}

    def test_normal_path_uses_exactly_two_model_calls(self):
        bind(self.store, self.binding(), True)
        self.assertTrue(self.start()["ok"])
        for unused in range(5):
            self.assertTrue(gate(self.store, self.event())["ok"])
        self.assertEqual(self.assess.call_count, 1)
        self.assertTrue(self.finish()["ok"])
        for unused in range(3):
            self.assertTrue(check_release(self.store, "fixture-task", {}, self.outputs)["ok"])
        self.assertEqual(self.assess.call_count, 2)

    def test_missing_and_unknown_start_do_not_authorize_actions(self):
        bind(self.store, self.binding(), True)
        missing = self.event()
        del missing["proofpress_task_id"]
        self.assertFalse(gate(self.store, missing)["ok"])
        self.assertFalse(gate(self.store, self.event())["ok"])
        self.assess.return_value = {"choice": "unknown"}
        self.assertFalse(self.start()["ok"])
        self.assertFalse(gate(self.store, self.event())["ok"])
        self.assertFalse(self.finish()["ok"])
        self.assertEqual(self.assess.call_count, 1)

    def test_path_filter_and_read_fast_path_do_not_call_model(self):
        bind(self.store, self.binding(), True)
        self.assertTrue(gate(self.store, self.event("src/unrelated.py"))["ok"])
        with patch("judgment_layer.store.Store") as opened:
            self.assertEqual(hook(self.root / "absent",
                                  {"tool_name": "Read", "tool_input": {}}, managed=True), {})
            opened.assert_not_called()
        self.assess.assert_not_called()

    def test_unknown_tool_and_malformed_read_do_not_use_fast_path(self):
        self.assertIn("hookSpecificOutput", hook(self.root / "absent",
                      {"tool_name": "Bash", "tool_input": {}}, managed=True))
        self.assertIn("hookSpecificOutput", hook(self.root / "absent",
                      {"tool_name": "Read", "tool_input": None}, managed=True))

    def test_finish_and_exact_output_are_required(self):
        self.start()
        self.assertFalse(check_release(self.store, "fixture-task", {}, self.outputs)["ok"])
        self.finish()
        changed = {**self.outputs, "extra.py": "new output"}
        self.assertIn("artifacts_changed", check_release(
            self.store, "fixture-task", {}, changed)["reasons"])
        self.assess.return_value = {"choice": "violation"}
        self.assertFalse(self.finish()["ok"])
        self.assertFalse(check_release(self.store, "fixture-task", {}, self.outputs)["ok"])

    def test_restart_and_later_action_invalidate_release(self):
        bind(self.store, self.binding(), True)
        self.start()
        self.finish()
        self.assertTrue(gate(self.store, self.event())["ok"])
        self.assertIn("action_after_finish", check_release(
            self.store, "fixture-task", {}, self.outputs)["reasons"])
        self.finish()
        self.assertTrue(check_release(self.store, "fixture-task", {}, self.outputs)["ok"])
        self.start()
        self.assertIn("task_restarted", check_release(
            self.store, "fixture-task", {}, self.outputs)["reasons"])

    def test_withdrawal_blocks_finish_without_another_model_call(self):
        self.start()
        self.store.owner_action(self.item["id"], 1, self.item["digest"],
                                "withdraw", "Synthetic fixture only", True)
        self.assertFalse(self.finish()["ok"])
        self.assertEqual(self.assess.call_count, 1)

    def test_new_admitted_judgment_and_changed_facts_require_restart(self):
        self.start()
        doc = copy.deepcopy(self.doc)
        doc["name"] = "Another synthetic judgment"
        self.admit(doc)
        self.assertIn("judgment_set_changed", self.finish()["reasons"])
        self.assertEqual(self.assess.call_count, 1)
        self.start()
        self.assertIn("facts_changed", self.finish({"new_fact": True})["reasons"])

    def test_no_empty_context_or_empty_artifact_pass(self):
        self.assertFalse(start_task(self.store, "empty", "absent-scope", {}, "Fixture plan")["ok"])
        self.assess.assert_not_called()
        self.start()
        with self.assertRaises(JudgmentError):
            finish_task(self.store, "fixture-task", {}, {})
        with self.assertRaises(JudgmentError):
            check_release(self.store, "fixture-task", {}, {"x": None})

    def test_existing_action_verifier_is_not_silently_migrated(self):
        policy = {**self.binding(), "verifier": "decision_model_output"}
        bind(self.store, policy, True)
        self.start()
        with patch("judgment_layer.runtime.assess") as original_model:
            self.assertFalse(gate(self.store, self.event())["ok"])
            original_model.assert_not_called()  # Existing partial-edit denial remains.

    def test_cli_failed_checkpoint_has_nonzero_exit(self):
        facts = self.root / "facts.json"
        plan = self.root / "plan.txt"
        facts.write_text("{}")
        plan.write_text("Synthetic task plan")
        result = subprocess.run(
            [sys.executable, "-m", "judgment_layer.cli", "--workspace",
             str(self.root / "store"), "task-start", "--task", "cli-fixture",
             "--scope", "absent-scope", "--facts", str(facts), "--plan", str(plan), "--json"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertFalse(json.loads(result.stdout)["ok"])
