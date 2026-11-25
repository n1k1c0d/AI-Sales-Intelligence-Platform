import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.validate_n8n_workflow import ValidationError, validate_report

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


class ReportConsistency(unittest.TestCase):
    def example(self, status):
        path = EXPORT.parents[1] / "examples/system-health-check" / (status + ".json")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_operational_requires_three_confirmed_services(self):
        for name, status in (("database", "unknown"), ("database", "not_ready"),
                             ("readiness", "unknown"), ("backend", "unavailable")):
            with self.subTest(name=name, status=status):
                report = self.example("operational")
                report["services"][name]["status"] = status
                with self.assertRaises(ValidationError):
                    validate_report(report, "operational")

    def test_aggregate_matches_the_actual_outcome(self):
        for actual, claimed in (("degraded", "unknown"), ("unknown", "unavailable"),
                                ("unavailable", "degraded")):
            with self.subTest(actual=actual, claimed=claimed):
                report = self.example(actual)
                report["overall_status"] = claimed
                with self.assertRaises(ValidationError):
                    validate_report(report, claimed)

    def test_readiness_requires_matching_http_and_database_evidence(self):
        for example, key, field, value in (
            ("operational", "readiness", "http_status", 503),
            ("operational", "backend", "http_status", 502),
            ("degraded", "database", "status", "operational"),
            ("degraded", "readiness", "http_status", 200),
            ("unknown", "readiness", "status", "unavailable"),
            ("unavailable", "database", "status", "not_ready"),
        ):
            with self.subTest(example=example, key=key, field=field, value=value):
                report = self.example(example)
                report["services"][key][field] = value
                with self.assertRaises(ValidationError):
                    validate_report(report, example)

    def test_diagnostic_errors_must_match_the_probe(self):
        for mutation in ("missing", "duplicate", "wrong_source"):
            with self.subTest(mutation=mutation):
                report = self.example("unknown")
                errors = report["errors"]
                if mutation == "missing":
                    errors.pop()
                elif mutation == "duplicate":
                    errors.append(errors[0].copy())
                else:
                    errors[0]["code"] = "DATABASE_NOT_READY"
                with self.assertRaises(ValidationError):
                    validate_report(report, "unknown")

    def test_valid_partial_evidence(self):
        uncertain = self.example("unknown")
        healthy = self.example("operational")
        # A good liveness probe and malformed readiness leave the database unknown.
        uncertain["overall_status"] = "degraded"
        uncertain["services"]["backend"] = healthy["services"]["backend"]
        uncertain["errors"] = [e for e in uncertain["errors"] if e["source"] == "readiness"]
        validate_report(uncertain, "degraded")

        # A working readiness probe can establish database health even if liveness failed.
        partial = self.example("unavailable")
        partial["overall_status"] = "degraded"
        partial["services"]["backend"]["status"] = "degraded"
        partial["services"]["readiness"] = healthy["services"]["readiness"]
        partial["services"]["database"] = healthy["services"]["database"]
        partial["errors"] = [e for e in partial["errors"] if e["source"] == "health"]
        validate_report(partial, "degraded")

        startup = self.example("degraded")
        startup["services"]["database"]["status"] = "unknown"
        startup["errors"][0].update(code="APPLICATION_NOT_READY", message="Application lifecycle is not ready")
        validate_report(startup, "degraded")
