"""Validate the portable DM-009 export and its example reports (stdlib only)."""

import json
import re
from datetime import datetime, timedelta
from graphlib import TopologicalSorter
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1] / "automations" / "n8n"
STATUSES = ("operational", "degraded", "unavailable", "unknown")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_workflow(workflow):
    require(workflow["name"] == "DealMind — System Health Check", "Unexpected name")
    require(not workflow["active"] and not workflow.get("pinData"), "Expected an inactive, unpinned export")
    require("id" not in workflow and "shared" not in workflow, "Remove instance-specific ownership")
    raw = json.dumps(workflow)
    require(not re.search(r'"(?:credentials|password|authorization|cookie|apiKey)"\s*:|Bearer\s+\S+', raw, re.I), "Review sensitive fields")
    nodes = {node["name"]: node for node in workflow["nodes"]}
    require(len(nodes) == len(workflow["nodes"]), "Duplicate node name")
    require(len({n["id"] for n in nodes.values()}) == len(nodes), "Duplicate node ID")
    allowed = {"manualTrigger", "set", "switch", "httpRequest", "code", "noOp", "stickyNote"}
    for node in nodes.values():
        require(node["type"] in {"n8n-nodes-base." + kind for kind in allowed}, "Unexpected node type")
        require(not node.get("disabled"), "Disabled node")
    triggers = [n["name"] for n in nodes.values() if n["type"] == "n8n-nodes-base.manualTrigger"]
    require(len(triggers) == 1, "Expected one Manual Trigger")
    probes = [n for n in nodes.values() if n["type"] == "n8n-nodes-base.httpRequest"]
    require(len(probes) == 2, "Expected two read-only probes")
    for name, path in (("Check API Health", "health"), ("Check API Readiness", "ready")):
        node = nodes[name]
        params = node["parameters"]
        require(params["method"] == "GET", "Only GET is supported")
        require(params["url"] == "={{ $('Initialize Context').first().json.api_base_url + '/api/v1/" + path + "' }}", "Unexpected destination")
        require(node["retryOnFail"] and (node["maxTries"], node["waitBetweenTries"]) == (2, 1000), "Retry policy changed")
        options = params["options"]
        response = options["response"]["response"]
        require(options["timeout"] == 8000 and not options["redirect"]["redirect"]["followRedirects"], "Unexpected HTTP options")
        require(response["fullResponse"] and response["neverError"] and response["responseFormat"] == "text", "Missing HTTP diagnostic envelope")
    context = nodes["Initialize Context"]["parameters"]["assignments"]["assignments"]
    require(next(a["value"] for a in context if a["name"] == "api_base_url") == "http://api:8000", "Unexpected origin")
    require(workflow["settings"]["executionTimeout"] == 60, "Unexpected workflow deadline")
    graph = TopologicalSorter()
    visited = {triggers[0]}
    links = {}
    for source, outputs in workflow["connections"].items():
        require(source in nodes, "Unknown connection source")
        links[source] = []
        for output in outputs["main"]:
            for link in output:
                target = link["node"]
                require(target in nodes and link["type"] == "main", "Invalid connection")
                graph.add(target, source)
                links[source].append(target)
    for name in graph.static_order():
        if name in visited:
            visited.update(links.get(name, []))
    require(visited == {k for k, n in nodes.items() if not n["type"].endswith(".stickyNote")}, "Unreachable node")
    leaves = visited - set(links)
    require(leaves == {s.title() + " Result" for s in STATUSES}, "Unexpected terminal branches")


def validate_report(report, expected):
    keys = {"schema_version", "workflow", "workflow_version", "execution_id", "started_at",
            "finished_at", "duration_ms", "overall_status", "services", "errors"}
    require(set(report) == keys and report["schema_version"] == "1.0", "Invalid report envelope")
    require(report["workflow"] == "system-health-check" and report["workflow_version"] == "1.0.0", "Wrong workflow")
    require(isinstance(report["execution_id"], str) and report["execution_id"], "Missing execution ID")
    start, end = (datetime.fromisoformat(report[k].replace("Z", "+00:00")) for k in ("started_at", "finished_at"))
    require(start.utcoffset() == end.utcoffset() == timedelta(0), "Expected UTC")
    require(end >= start and end - start == timedelta(milliseconds=report["duration_ms"]), "Invalid duration")
    require(report["overall_status"] == expected, "Incorrect example status")
    services = report["services"]
    require(set(services) == {"backend", "readiness", "database"}, "Unexpected services")
    for key in ("backend", "readiness"):
        probe = services[key]
        require(set(probe) == {"status", "http_status", "request_id"} and probe["status"] in STATUSES, "Invalid probe")
        status = probe["http_status"]
        require(status is None or isinstance(status, int) and 100 <= status <= 599, "Invalid HTTP status")
        if probe["request_id"] is not None:
            require(status is not None and UUID(probe["request_id"]).version == 4, "Invalid request correlation")
    require(services["database"] in [{"status": s} for s in ("operational", "not_ready", "unknown")], "Invalid database status")
    require(isinstance(report["errors"], list), "Expected error array")
    require(bool(report["errors"]) == (expected != "operational"), "Invalid diagnostic outcome")
    for error in report["errors"]:
        require(set(error) == {"code", "message", "source"} and error["source"] in ("health", "readiness"), "Invalid diagnostic error")
        require(error["code"] in {"TIMEOUT", "NETWORK_ERROR", "HTTP_ERROR", "INVALID_RESPONSE", "DATABASE_NOT_READY", "APPLICATION_NOT_READY", "CONFIGURATION_ERROR"}, "Unknown error code")


if __name__ == "__main__":
    validate_workflow(read(ROOT / "workflows/system-health-check.json"))
    for status in STATUSES:
        validate_report(read(ROOT / "examples" / "system-health-check" / (status + ".json")), status)
    print("PASS: portable workflow, graph, transport settings and four report examples")
