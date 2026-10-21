import os
import re
import json
import math
import pytest
import yaml
from fastapi.testclient import TestClient

from src.api.main import app

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SANDBOX_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")

def test_req1_docker_compose_and_dockerfile():
    compose_path = os.path.join(REPO_ROOT, "docker-compose.yml")
    dockerfile_path = os.path.join(REPO_ROOT, "Dockerfile")
    assert os.path.isfile(compose_path), "docker-compose.yml must exist at repo root"
    assert os.path.isfile(dockerfile_path), "Dockerfile must exist at repo root"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    assert "api" in services, "api service must exist in docker-compose.yml"
    assert "ledger" in services, "ledger service must exist in docker-compose.yml"

    # API assertions
    api_svc = services["api"]
    assert "healthcheck" in api_svc, "api service must have a healthcheck"
    api_hc = api_svc["healthcheck"]
    for key in ["interval", "timeout", "retries", "start_period"]:
        assert key in api_hc, f"api healthcheck must set {key}"
    assert "depends_on" in api_svc, "api must depend on ledger"
    assert api_svc["depends_on"]["ledger"]["condition"] == "service_healthy"

    # Ledger assertions
    ledger_svc = services["ledger"]
    assert "healthcheck" in ledger_svc, "ledger service must have a healthcheck"
    ledger_hc = ledger_svc["healthcheck"]
    for key in ["interval", "timeout", "retries", "start_period"]:
        assert key in ledger_hc, f"ledger healthcheck must set {key}"

    # Verify seed mount
    volumes = ledger_svc.get("volumes", [])
    has_seed_mount = any("./seeds:" in v or "seeds" in v for v in volumes)
    assert has_seed_mount, "ledger must mount ./seeds to load init SQL"

def test_req2_env_example():
    env_example_path = os.path.join(REPO_ROOT, ".env.example")
    env_path = os.path.join(REPO_ROOT, ".env")
    assert os.path.isfile(env_example_path), ".env.example must exist at root"
    assert not os.path.exists(env_path), ".env must NOT be present at repository root"

    with open(env_example_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_keys = [
        "CELESTO_PROVIDER",
        "CELESTO_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "API_PORT"
    ]
    for key in required_keys:
        assert f"{key}=" in content, f".env.example must contain key {key}"
        assert "replace" in content or "example" in content, "Keys should contain placeholders"

def test_req3_problem_statement():
    path = os.path.join(REPO_ROOT, "reports", "problem.json")
    assert os.path.isfile(path), "reports/problem.json must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for field in ["who", "agent_work", "proof_output", "idea_source"]:
        assert field in data, f"problem.json must contain {field}"

    assert data["idea_source"] in ["idea_bank", "original"], "idea_source must be idea_bank or original"
    assert len(data["who"]) >= 40, "who must be at least 40 chars"
    assert len(data["agent_work"]) >= 40, "agent_work must be at least 40 chars"
    assert len(data["proof_output"]) >= 20, "proof_output must be at least 20 chars"

def test_req4_commands_audit_log():
    path = os.path.join(REPO_ROOT, "logs", "commands.jsonl")
    assert os.path.isfile(path), "logs/commands.jsonl must exist"

    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line_str = line.strip()
            if line_str:
                rec = json.loads(line_str)
                lines.append(rec)
                assert "ts" in rec, f"Line {idx} missing ts"
                assert "sandbox_name" in rec, f"Line {idx} missing sandbox_name"
                assert SANDBOX_REGEX.match(rec["sandbox_name"]), f"Invalid sandbox_name {rec['sandbox_name']}"
                assert "command" in rec and rec["command"], f"Line {idx} empty command"
                assert rec["decision"] in ["allow", "block"], f"Invalid decision {rec['decision']}"
                assert rec["execution_target"] == "celesto_sandbox", "execution_target must be exactly celesto_sandbox"

    assert len(lines) >= 1, "logs/commands.jsonl must contain at least one line"

def test_req5_capabilities():
    path = os.path.join(REPO_ROOT, "reports", "capabilities.json")
    assert os.path.isfile(path), "reports/capabilities.json must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "capabilities" in data, "capabilities key must exist"
    caps = data["capabilities"]
    assert len(caps) >= 2, "Must include at least two capabilities"

    allowed_ids = {
        "persistence", "snapshots", "celestofs", "browser", "published_ports",
        "network_policy", "safety_hooks", "host_mounts", "coding_agent_preset",
        "agentor_durable"
    }
    seen_ids = set()
    for cap in caps:
        cap_id = cap.get("id")
        assert cap_id in allowed_ids, f"Unknown capability id {cap_id}"
        assert cap_id not in seen_ids, f"Duplicate capability id {cap_id}"
        seen_ids.add(cap_id)

        why = cap.get("why", "")
        assert len(why) >= 80, f"Capability {cap_id} why must be at least 80 chars (got {len(why)})"

        evidence_path = cap.get("evidence_path", "")
        full_evidence = os.path.join(REPO_ROOT, evidence_path)
        assert os.path.exists(full_evidence), f"Evidence path {evidence_path} does not exist in repo"

def test_req6_lifecycle():
    lifecycle_path = os.path.join(REPO_ROOT, "reports", "lifecycle.json")
    assert os.path.isfile(lifecycle_path), "reports/lifecycle.json must exist"

    with open(lifecycle_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("cleanup_on_success") is True, "cleanup_on_success must be true"
    assert data.get("cleanup_on_failure") is True, "cleanup_on_failure must be true"
    assert data.get("cleanup_on_interrupt") is True, "cleanup_on_interrupt must be true"

    sbx_names = data.get("sandbox_names", [])
    assert len(sbx_names) > 0, "sandbox_names must not be empty"
    assert len(sbx_names) == len(set(sbx_names)), "sandbox_names must be unique"

    # Cross-reference with commands log or reliability
    with open(os.path.join(REPO_ROOT, "logs", "commands.jsonl"), "r", encoding="utf-8") as f:
        log_sbx = {json.loads(line)["sandbox_name"] for line in f if line.strip()}

    with open(os.path.join(REPO_ROOT, "reports", "reliability.json"), "r", encoding="utf-8") as f:
        rel_sbx = {r["sandbox_name"] for r in json.load(f)["runs"]}

    for name in sbx_names:
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox_name {name}"
        assert name in log_sbx or name in rel_sbx, f"{name} must appear in commands.jsonl or reliability.json"

def test_req7_reliability():
    rel_path = os.path.join(REPO_ROOT, "reports", "reliability.json")
    postmortem_path = os.path.join(REPO_ROOT, "reports", "postmortem.md")
    assert os.path.isfile(rel_path), "reports/reliability.json must exist"
    assert os.path.isfile(postmortem_path), "reports/postmortem.md must exist"

    with open(postmortem_path, "r", encoding="utf-8") as f:
        postmortem_text = f.read()
    assert len(postmortem_text) >= 200, "reports/postmortem.md must be at least 200 characters"

    with open(rel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    runs = data.get("runs", [])
    run_count = data.get("run_count")
    assert len(runs) >= 20, "runs must have at least 20 rows"
    assert run_count == len(runs), "run_count must equal length of runs"

    unique_names = set()
    for r in runs:
        name = r["sandbox_name"]
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox_name {name}"
        assert name not in unique_names, f"Duplicate sandbox_name {name}"
        unique_names.add(name)
        assert r["fresh"] is True, "fresh must be true"
        assert isinstance(r["success"], bool), "success must be boolean"
        assert r["wall_clock_s"] >= 0, "wall_clock_s must be >= 0"
        assert r["boot_to_ready_s"] >= 0, "boot_to_ready_s must be >= 0"
        assert r["cost_usd"] >= 0, "cost_usd must be >= 0"

    # Math validations
    n = len(runs)
    successes = sum(1 for r in runs if r["success"])
    expected_sr = successes / n
    assert abs(data["success_rate"] - expected_sr) <= 0.001, "success_rate mismatch"

    sorted_wc = sorted(r["wall_clock_s"] for r in runs)
    if n % 2 == 0:
        expected_median_wc = (sorted_wc[n // 2 - 1] + sorted_wc[n // 2]) / 2.0
    else:
        expected_median_wc = sorted_wc[n // 2]
    assert abs(data["median_wall_clock_s"] - expected_median_wc) <= 0.001, "median_wall_clock_s mismatch"

    p90_idx = math.ceil(0.90 * n) - 1
    expected_p90 = sorted_wc[p90_idx]
    assert abs(data["p90_wall_clock_s"] - expected_p90) <= 0.001, "p90_wall_clock_s mismatch"

    sorted_boot = sorted(r["boot_to_ready_s"] for r in runs)
    if n % 2 == 0:
        expected_median_boot = (sorted_boot[n // 2 - 1] + sorted_boot[n // 2]) / 2.0
    else:
        expected_median_boot = sorted_boot[n // 2]
    assert abs(data["median_boot_to_ready_s"] - expected_median_boot) <= 0.001, "median_boot_to_ready_s mismatch"

    expected_cost = sum(r["cost_usd"] for r in runs)
    assert abs(data["total_cost_usd"] - expected_cost) <= 0.01, "total_cost_usd mismatch"
    assert data["postmortem_path"] == "reports/postmortem.md"

def test_req8_containment():
    path = os.path.join(REPO_ROOT, "reports", "containment.json")
    assert os.path.isfile(path), "reports/containment.json must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("attack") in ["prompt_injection_exfil", "destructive_command", "suspicious_package"]
    assert data.get("blocked") is True, "blocked must be true"
    assert data.get("host_untouched") is True, "host_untouched must be true"

    evidence_paths = data.get("evidence_paths", [])
    assert len(evidence_paths) >= 1, "evidence_paths must have at least one entry"
    for p in evidence_paths:
        full_p = os.path.join(REPO_ROOT, p)
        assert os.path.isfile(full_p), f"Evidence path {p} must exist"

def test_req9_failure_policy_and_trace():
    policy_path = os.path.join(REPO_ROOT, "reports", "failure_policy.json")
    trace_path = os.path.join(REPO_ROOT, "reports", "failure_trace.jsonl")
    assert os.path.isfile(policy_path), "reports/failure_policy.json must exist"
    assert os.path.isfile(trace_path), "reports/failure_trace.jsonl must exist"

    with open(policy_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("failed_step") == 7, "failed_step must be 7"
    assert data.get("total_steps") == 10, "total_steps must be 10"
    policy = data.get("policy")
    assert policy in ["resume", "rollback", "fresh"], "policy must be resume, rollback, or fresh"
    assert len(data.get("rationale", "")) >= 200, "rationale must be at least 200 chars"
    assert data.get("trace_path") == "reports/failure_trace.jsonl"

    found_policy_applied = False
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line.strip())
                if item.get("event") == "policy_applied" and item.get("policy") == policy:
                    found_policy_applied = True
                    break

    assert found_policy_applied, f"failure_trace.jsonl must contain an event 'policy_applied' with policy '{policy}'"

def test_req10_concurrency():
    path = os.path.join(REPO_ROOT, "reports", "concurrency.json")
    assert os.path.isfile(path), "reports/concurrency.json must exist"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    assert len(jobs) >= 5, "jobs must have at least 5 objects"

    job_names = set()
    for job in jobs:
        name = job.get("sandbox_name", "")
        assert SANDBOX_REGEX.match(name), f"Invalid sandbox_name {name}"
        assert name not in job_names, f"Duplicate sandbox_name {name}"
        job_names.add(name)
        assert job.get("started_at"), "started_at must be non-empty string"

    assert len(data.get("breakage_notes", "")) >= 40, "breakage_notes must be at least 40 chars"

def test_req11_ledger_api_endpoints():
    client = TestClient(app)

    # 1. GET /health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    # 2. GET /api/runs
    r_runs = client.get("/api/runs")
    assert r_runs.status_code == 200
    runs = r_runs.json()
    assert isinstance(runs, list)
    assert any(item.get("sandbox_name") == "sbx-seeddemo1" for item in runs), "Runs must contain sbx-seeddemo1"

    # 3. POST /api/runs (Valid row -> 201)
    valid_payload = {
        "run_id": "test-run-valid-99",
        "sandbox_name": "sbx-testrun99a",
        "problem_id": "prob-detonation-99",
        "state": "running",
        "execution_target": "celesto_sandbox"
    }
    r_post_valid = client.post("/api/runs", json=valid_payload)
    assert r_post_valid.status_code == 201
    stored = r_post_valid.json()
    assert stored["sandbox_name"] == "sbx-testrun99a"

    # 4. POST /api/runs (Invalid execution_target 'host' -> 400)
    invalid_target = dict(valid_payload, execution_target="host", sandbox_name="sbx-testrun99b")
    r_bad_target = client.post("/api/runs", json=invalid_target)
    assert r_bad_target.status_code == 400

    # 5. POST /api/runs (Invalid state -> 400)
    invalid_state = dict(valid_payload, state="unknown_status", sandbox_name="sbx-testrun99c")
    r_bad_state = client.post("/api/runs", json=invalid_state)
    assert r_bad_state.status_code == 400

    # 6. POST /api/runs (Invalid sandbox_name -> 400)
    invalid_name = dict(valid_payload, sandbox_name="bad-name")
    r_bad_name = client.post("/api/runs", json=invalid_name)
    assert r_bad_name.status_code == 400

def test_req12_readme_and_demo():
    readme_path = os.path.join(REPO_ROOT, "README.md")
    demo_path = os.path.join(REPO_ROOT, "demo", "walkthrough.mp4")

    assert os.path.isfile(readme_path), "README.md must exist at root"
    assert os.path.isfile(demo_path), "demo/walkthrough.mp4 must exist"
    assert os.path.getsize(demo_path) > 1000, "demo/walkthrough.mp4 must not be empty"

    with open(readme_path, "r", encoding="utf-8") as f:
        readme_text = f.read()

    required_phrases = [
        "Problem statement",
        "How I used Celesto",
        "Eval report",
        "Containment test",
        "State and failure design",
        "Setup"
    ]
    for phrase in required_phrases:
        assert phrase in readme_text, f"README.md must contain exact phrase: '{phrase}'"
