"""One isolated 24-method UI pass with bounded worker diagnostics, no live services.

Run with the already fresh UI environment. Scenario runs first to observe a new
Python process before any other test deserializes the saved scenario models.
This does not clear operating-system caches or claim physical cold-boot timing.
"""
import argparse
import importlib.metadata
import io
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import urllib.request
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
DEVELOPMENT = HERE.parents[2]
V6 = "reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6"


def run(root):
    root = root.resolve()
    if root == DEVELOPMENT or root.is_relative_to(DEVELOPMENT):
        raise ValueError("Use an isolated prepared checkout, not the development tree")
    os.chdir(root)
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
    sys.path = [p for p in sys.path if p and not Path(p).resolve().is_relative_to(DEVELOPMENT)]
    for relative in [V6 + "/tests", V6, "reports/final_project/HEARTTRIALTWIN_INTEGRATED_20261102_v1/src"]:
        sys.path.insert(0, str(root / relative))
    result = {"schema_version": "HTT-V6-PHASE4-HANDOFF-v1", "date": "2026-11-06",
              "workspace": str(root), "remote_clone": False,
              "dependency_installation": "Reused unchanged Phase 3 independently installed fresh venvs; not developer site-packages; no reinstall",
              "public_asset_download": False, "neo4j_calls": 0, "ollama_calls": 0,
              "development_import_paths": [p for p in sys.path if p and Path(p).resolve().is_relative_to(DEVELOPMENT)],
              "commands": [], "worker_observations": []}
    for env in [".venv-full-system", ".venv-vector-rag"]:
        command = [str(root / env / "bin/python"), "-I", "-B", "-m", "pip", "--isolated", "check"]
        p = subprocess.run(command, capture_output=True, text=True, timeout=20)
        result["commands"].append({"argv": command, "returncode": p.returncode,
                                   "outcome": p.stdout.strip() if p.returncode == 0 else "DEPENDENCY_CHECK_FAILED"})
    command = [str(root / ".venv-full-system/bin/python"), "-B", V6 + "/provision.py", "--check-environments"]
    p = subprocess.run(command, capture_output=True, text=True, timeout=30)
    result["commands"].append({"argv": command, "returncode": p.returncode})
    result["preflight"] = json.loads(p.stdout)
    if p.returncode:
        return result
    import client
    import test_app
    import test_integrity
    logging.disable(logging.WARNING)
    original_run, original_request = subprocess.run, client.request

    def measured_run(argv, *args, **kwargs):
        is_worker = isinstance(argv, list) and any(str(v).endswith("/src/worker.py") for v in argv)
        if not is_worker:
            return original_run(argv, *args, **kwargs)
        started = time.perf_counter()
        event = {"kind": "PRODUCTION_WORKER_SUBPROCESS", "timeout_seconds": kwargs.get("timeout")}
        try:
            process = original_run(argv, *args, **kwargs)
            event["returncode"] = process.returncode
            event["stderr_bytes"] = len(process.stderr.encode())
            # Only safe structural fields. Never save stderr, environment or prompts.
            try:
                value = json.loads(process.stdout)
                for key in ["status", "error_code", "diagnostic_type", "worker_elapsed_seconds", "count", "model_fits", "forecasting_release", "source_evidence_written"]:
                    if key in value:
                        event[key] = value[key]
            except ValueError:
                event["response_json_valid"] = False
            return process
        except subprocess.TimeoutExpired:
            event["failure"] = "TIMEOUT"
            raise
        finally:
            event["wall_seconds"] = time.perf_counter() - started
            result["worker_observations"].append(event)

    def measured_request(payload, runner=None):
        value = original_request(payload, runner=runner)
        event = {"kind": "CLIENT_RESULT", "action": payload.get("action"),
                 "fixture_runner": runner is not None}
        for key in ["status", "error_code", "count", "client_elapsed_seconds", "model_fits", "forecasting_release", "source_evidence_written"]:
            if key in value:
                event[key] = value[key]
        result["worker_observations"].append(event)
        return value

    loader = unittest.TestLoader()
    scenario = "test_scenario_acknowledgement_gate"
    tests = [test_app.AppTests(scenario)]
    tests += [test_app.AppTests(n) for n in loader.getTestCaseNames(test_app.AppTests) if n != scenario]
    tests += [test_integrity.IntegrityTests(n) for n in loader.getTestCaseNames(test_integrity.IntegrityTests)]
    output = io.StringIO()
    started = time.perf_counter()
    with patch.object(subprocess, "run", measured_run), patch.object(client, "request", measured_request):
        executed = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.TestSuite(tests))
    result["tests"] = {"run": executed.testsRun, "passed": executed.testsRun - len(executed.failures) - len(executed.errors) - len(executed.skipped),
                       "failures": len(executed.failures), "errors": len(executed.errors), "skipped": len(executed.skipped),
                       "seconds": time.perf_counter() - started, "scenario_executed_first": True,
                       "failed_cases": [{"test": str(t), "last_line": message.strip().splitlines()[-1]} for t, message in executed.failures + executed.errors],
                       "test_names": [t.id() for t in tests]}
    # Actual bounded local HTTP startup, distinct from AppTest workflow checks.
    command = [str(root / ".venv-full-system/bin/python"), "-B", "-m", "streamlit", "run", V6 + "/app.py",
               "--server.address", "127.0.0.1", "--server.port", "8512", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
    server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result["server"] = {"argv": command, "health": "NOT_READY", "stopped_after_test": False}
    try:
        started = time.perf_counter()
        while time.perf_counter() - started < 15 and server.poll() is None:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8512/_stcore/health", timeout=1) as response:
                    if response.read(30) == b"ok":
                        result["server"]["health"] = "ok"
                        break
            except OSError:
                time.sleep(0.2)
    finally:
        if server.poll() is None:
            server.terminate()
        server.wait(timeout=10)
        result["server"]["stopped_after_test"] = True
    result["ui_packages"] = {p: importlib.metadata.version(p) for p in ["streamlit", "numpy", "pandas", "plotly"]}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError("Do not overwrite an earlier execution result")
    value = run(a.root)
    a.output.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({k: value[k] for k in ["preflight", "tests", "server"] if k in value}, indent=2))
