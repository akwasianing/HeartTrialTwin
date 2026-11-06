"""Check an allowlisted v6 runtime; never copy, download, install or repair files."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

from integrity import ROOT, IntegrityError, check_files, load_receipt, verify_runtime

UI_PACKAGES = {"streamlit": "1.64.0", "pandas": "2.2.3", "numpy": "2.1.3",
               "pyarrow": "24.0.0", "altair": "6.3.0", "pillow": "12.3.0", "plotly": "7.1.0"}
WORKER_PACKAGES = {"numpy": "1.26.4", "scipy": "1.17.1", "scikit-learn": "1.9.1",
                   "joblib": "1.6.0", "pillow": "12.3.0"}


def check_environment(root=ROOT, runner=subprocess.run):
    errors = []
    if sys.version_info[:2] != (3, 12):
        errors.append("UI requires the verified Python 3.12 environment")
    for package, expected in UI_PACKAGES.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = "MISSING"
        if actual != expected:
            errors.append(f"UI dependency {package}: expected {expected}; found {actual}")
    python = Path(root) / ".venv-vector-rag/bin/python"
    if not python.is_file():
        return errors + ["Missing dedicated .venv-vector-rag worker environment"]
    code = ("import importlib.metadata as m,json,sys;print(json.dumps({'python':list(sys.version_info[:2]),"
            "'packages':{p:m.version(p) for p in " + repr(list(WORKER_PACKAGES)) + "}}))")
    try:
        result = runner([str(python), "-I", "-B", "-c", code], capture_output=True,
                        text=True, timeout=15, check=False)
        value = json.loads(result.stdout) if result.returncode == 0 else {}
        if value != {"python": [3, 12], "packages": WORKER_PACKAGES}:
            errors.append("Worker Python/dependency versions do not match the verified runtime")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        errors.append("Worker environment check failed; no raw configuration or exception published")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="store_true", help="Print paths/hashes/distribution policy only")
    parser.add_argument("--assets-root", type=Path, default=ROOT,
                        help="Validate a separately provisioned mirror layout without copying it")
    parser.add_argument("--check-environments", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipt = load_receipt()
        if args.inventory:
            print(json.dumps({"schema_version": receipt["schema_version"], "assets": receipt["assets"]}, indent=2))
            return 0
        failures = check_files(args.assets_root, receipt)
        env_errors = check_environment(args.assets_root) if args.check_environments else []
        if not failures:
            verify_runtime(args.assets_root)
        print(json.dumps({"status": "READY_LOCAL" if not failures and not env_errors else "NOT_READY",
                          "asset_failures": failures, "environment_errors": env_errors,
                          "clean_clone_reproduction_established": False,
                          "copies": 0, "downloads": 0, "network_calls": False}, indent=2))
        return int(bool(failures or env_errors))
    except (IntegrityError, OSError, KeyError, TypeError, ValueError):
        print(json.dumps({"status": "NOT_READY", "error": "Integrity inventory or identity check failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
