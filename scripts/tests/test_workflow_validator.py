import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "automations/n8n/workflows/system-health-check.json"


class WorkflowFixtures(unittest.TestCase):
    def check_fixture(self, mutate, expected=None):
        workflow = json.loads(EXPORT.read_text(encoding="utf-8"))
        content = mutate(workflow)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(content if isinstance(content, str) else json.dumps(workflow), encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_n8n_workflow.py"), str(path)],
                                    capture_output=True, text=True, timeout=15)
        if expected is None:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(path), result.stderr)
            self.assertIn(expected, result.stderr)
            self.assertNotIn("private-fixture-value", result.stderr)

    def test_valid(self):
        self.check_fixture(lambda w: None)

    def test_malformed(self):
        self.check_fixture(lambda w: "{", "invalid JSON")

    def test_duplicate(self):
        self.check_fixture(lambda w: w["nodes"].append(w["nodes"][0]), "Duplicate node name")

    def test_reference(self):
        def break_link(w):
            w["connections"]["Manual Trigger"]["main"][0][0]["node"] = "missing"
        self.check_fixture(break_link, "Invalid connection")

    def test_pinned(self):
        self.check_fixture(lambda w: w.update(pinData={"Manual Trigger": [{}]}), "unpinned")

    def test_missing_configuration(self):
        self.check_fixture(lambda w: w.pop("settings") and None, "required configuration")

    def test_credential_field(self):
        self.check_fixture(lambda w: w.update(token="private-fixture-value"), "sensitive fields")

    def test_logical_workflow_id(self):
        def wrong_id(w):
            context = next(n for n in w["nodes"] if n["name"] == "Initialize Context")
            assignments = context["parameters"]["assignments"]["assignments"]
            next(a for a in assignments if a["name"] == "workflow")["value"] = "other"
        self.check_fixture(wrong_id, "workflow ID")

    def test_unexpected_header(self):
        def add_header(w):
            probe = next(n for n in w["nodes"] if n["name"] == "Check API Health")
            probe["parameters"]["headerParameters"]["parameters"].append(
                {"name": "X-API-Key", "value": "private-fixture-value"})
        self.check_fixture(add_header, "Unexpected HTTP headers")
