"""Build a disposable Compose stack and verify either HTTP integration or n8n."""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from validate_n8n_workflow import ROOT as N8N_ROOT
from validate_n8n_workflow import STATUSES, require, validate_report, validate_workflow

ROOT = Path(__file__).resolve().parents[1]
EXPORT = N8N_ROOT / "workflows/system-health-check.json"


def command(args, env, timeout=150):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"command exited {result.returncode}")
    return result.stdout.strip()


def project_name(mode, cleanup):
    run, attempt = (os.environ.get(k, "") for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"))
    if os.environ.get("GITHUB_ACTIONS") == "true" and run.isdecimal() and attempt.isdecimal():
        return f"dealmind-ci-{mode}-{run}-{attempt}"
    if cleanup:
        raise ValueError("Standalone cleanup requires a hosted run identity")
    return f"dealmind-ci-{mode}-{uuid4().hex[:12]}"


def compose_config(temp, project):
    template = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    settings = dict(line.split("=", 1) for line in template if line and not line.startswith("#"))
    settings.update(COMPOSE_PROJECT_NAME=project, APP_ENV="test", POSTGRES_USER="dealmind_test",
                    POSTGRES_DB="dealmind_test", POSTGRES_PASSWORD=secrets.token_hex(24),
                    N8N_ENCRYPTION_KEY=secrets.token_hex(32))
    dotenv = temp / "ci.env"
    dotenv.write_text("".join(f"{key}={value}\n" for key, value in settings.items()), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in settings and not k.startswith("COMPOSE_")}
    env.update(MSYS_NO_PATHCONV="1", MSYS2_ARG_CONV_EXCL="*")
    flags = ["--env-file", str(dotenv), "-p", project, "-f", "docker-compose.yml",
             "-f", "infra/docker/ci/compose.yml"]
    return flags, env


def verify_mount(compose, env, project, service, volume, directory):
    cid = compose("ps", "-q", service)
    mounts = json.loads(command(["docker", "inspect", "--format", "{{json .Mounts}}", cid], env))
    actual, = [m for m in mounts if m["Destination"] == directory]
    require(actual["Type"] == "volume" and actual["Name"] == f"{project}_{volume}", "Unexpected mount")
    owner = command(["docker", "volume", "inspect", "--format",
                     '{{index .Labels "com.docker.compose.project"}}', actual["Name"]], env)
    require(owner == project, "Unexpected volume owner")


def import_workflow(compose, temp):
    tracked = json.loads(EXPORT.read_text(encoding="utf-8"))
    validate_workflow(tracked)
    def cli(*args):
        return compose("exec", "-T", "n8n", "n8n", *args)
    require("--input" in cli("import:workflow", "--help"), "Missing import CLI")
    compose("cp", str(EXPORT), "n8n:/tmp/ci-workflow.json")
    cli("import:workflow", "--input=/tmp/ci-workflow.json")
    ids = re.findall(r"^[A-Za-z0-9_-]{8,64}$", cli("list:workflow", "--onlyId"), re.M)
    require(len(ids) == 1, "Expected one imported workflow")
    cli("export:workflow", "--id=" + ids[0], "--output=/tmp/ci-export.json")
    dest = temp / "round-trip.json"
    compose("cp", "n8n:/tmp/ci-export.json", str(dest))
    saved, = json.loads(dest.read_text(encoding="utf-8"))
    require(all(saved[k] == tracked[k] for k in ("name", "active", "nodes", "connections")),
            "Imported graph differs from export")
    return ids[0]


def execute(compose, workflow_id, expected):
    output = compose("exec", "-T", "-e", "N8N_RUNNERS_BROKER_PORT=5680", "n8n", "n8n",
                     "execute", "--id=" + workflow_id, "--rawOutput")
    start = re.search(r"^\{\s*$", output, re.M)
    require(start is not None, "Missing execution JSON")
    execution, _ = json.JSONDecoder().raw_decode(output[start.start():])
    result = execution["data"]["resultData"]
    terminal = expected.title() + " Result"
    branches = {s.title() + " Result" for s in STATUSES}
    require(result["lastNodeExecuted"] == terminal and branches.intersection(result["runData"]) == {terminal},
            "Unexpected terminal path")
    step, = result["runData"][terminal]
    items, = step["data"]["main"]
    item, = items
    report = item["json"]
    validate_report(report, expected)
    example_path = N8N_ROOT / "examples/system-health-check" / (expected + ".json")
    example = json.loads(example_path.read_text(encoding="utf-8"))
    services = report["services"]
    require(report["execution_id"].isascii() and report["execution_id"].isdecimal()
            and int(report["execution_id"]) > 0, "Invalid execution ID")
    for name in ("backend", "readiness"):
        actual, reference = services[name], example["services"][name]
        require(all(actual[k] == reference[k] for k in ("status", "http_status")), "Unexpected HTTP outcome")
        require((actual["request_id"] is None) == (reference["request_id"] is None), "Unexpected request ID")
    if services["backend"]["request_id"] is not None:
        require(services["backend"]["request_id"] != services["readiness"]["request_id"], "Reused request ID")
    require(services["database"] == example["services"]["database"], "Wrong database status")
    require(report["errors"] == example["errors"], "Unexpected diagnostic errors")
    # Only the validated report goes into artifacts. Raw executions stay in memory.
    return report


def run(mode, cleanup):
    project = project_name(mode, cleanup)
    report = {"project": project, "phase": "configure", "passed": False}
    path = ROOT / "reports" / (mode + ".json")
    def phase(label):
        report["phase"] = label
        print(f"{project}: {label}", flush=True)
    with tempfile.TemporaryDirectory(prefix="dealmind-ci-") as directory:
        temp = Path(directory)
        flags, env = compose_config(temp, project)
        def compose(*args, timeout=150):
            return command(["docker", "compose", *flags, *args], env, timeout)
        if cleanup:
            compose("--profile", "invalid-response", "down", "--timeout", "8")
            return
        path.parent.mkdir(exist_ok=True)
        allocated = False
        try:
            compose("config", "--quiet")
            owned = ["--filter", "label=com.docker.compose.project=" + project, "-q"]
            require(not command(["docker", "ps", "-a", *owned], env) and
                    not command(["docker", "volume", "ls", *owned], env), "Project must be fresh")
            allocated = True
            phase("build")
            apps = ["api", "web"] if mode == "smoke" else ["api"]
            compose("build", *apps, timeout=900)
            phase("migrate")
            compose("up", "-d", "--wait", "--wait-timeout", "90", "db")
            verify_mount(compose, env, project, "db", "postgres_data", "/var/lib/postgresql/data")
            compose("run", "--rm", "--no-deps", "api", "alembic", "upgrade", "head")
            phase("startup")
            compose("up", "-d", "--wait", "--wait-timeout", "150", *apps, "n8n", timeout=200)
            verify_mount(compose, env, project, "n8n", "n8n_data", "/home/node/.n8n")
            if mode == "smoke":
                phase("smoke")
                bash = shutil.which("bash")
                if os.name == "nt":
                    git_bash = Path(os.environ["ProgramFiles"]) / "Git/bin/bash.exe"
                    if git_bash.exists():
                        bash = str(git_bash)
                require(bash, "Bash required")
                output = command([bash, "scripts/smoke_infra.sh", *flags], env, timeout=120)
                report["checks"] = [line for line in output.splitlines() if line.startswith("PASS: ")]
                require(len(report["checks"]) == 4, "Incomplete smoke checks")
            else:
                phase("import")
                workflow_id = import_workflow(compose, temp)
                phase("operational")
                report["operational"] = execute(compose, workflow_id, "operational")
                phase("degraded")
                compose("stop", "db")
                report["degraded"] = execute(compose, workflow_id, "degraded")
                # Keep DNS deterministic while the actual API is stopped. Port 8000 initially refuses TCP.
                phase("unavailable")
                compose("stop", "api")
                env["CI_FIXTURE_PORT"] = "8001"
                compose("up", "-d", "--wait", "--wait-timeout", "45", "invalid-api")
                report["unavailable"] = execute(compose, workflow_id, "unavailable")
                phase("unknown")
                env["CI_FIXTURE_PORT"] = "8000"
                compose("up", "-d", "--wait", "--wait-timeout", "45", "invalid-api")
                report["unknown"] = execute(compose, workflow_id, "unknown")
                require(len({report[s]["execution_id"] for s in STATUSES}) == len(STATUSES),
                        "Expected independent workflow executions")
            phase("verified")
        finally:
            try:
                if allocated:
                    compose("--profile", "invalid-response", "down", "--timeout", "8")
                report["passed"] = report["phase"] == "verified"
            finally:
                path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("n8n", "smoke"))
    parser.add_argument("--cleanup", action="store_true", help="repeat cleanup on the disposable CI runner")
    args = parser.parse_args()
    try:
        run(args.mode, args.cleanup)
    except Exception as error:
        # Raw child output may contain configuration or entire execution payloads.
        detail = str(error) if type(error).__name__ in {"ValidationError", "RuntimeError"} else type(error).__name__
        sys.exit(f"CI {args.mode} failed: {detail} (see phase above)")
