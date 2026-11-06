"""Exact allowlist and staged-byte review. Never stage, commit, push or read .env.

No exhaustive history/OCR claim. Previously reviewed frozen source is retained;
runtime payloads and unresolved private paths are never added by directory glob.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

from runtime_bundle import HERE, ROOT, sha
from audit_assets import RULES

POSTER = "figures and charts /HeartTrialTwin_V20.pptx"
METADATA = [str((HERE / n).relative_to(ROOT)) for n in ["PUBLICATION_ALLOWLIST.json", "PUBLICATION_FILES.txt", "PUBLICATION_CHECKS.json"]]


def poster_review():
    p = ROOT / POSTER
    with zipfile.ZipFile(p) as archive:
        if archive.testzip() is not None:
            raise ValueError("Poster archive integrity failure")
        names = archive.namelist()
        text = "\n".join(archive.read(n).decode("utf-8") for n in names if n.endswith((".xml", ".rels")))
        flags = [name for name, pattern in RULES.items() if pattern.search(text)]
        if re.search(r"/(?:Users|home)/", text):
            flags.append("PRIVATE_PATH")
        if any("/embeddings/" in n or "vbaProject" in n for n in names):
            flags.append("EMBEDDED_EXECUTABLE_OR_OBJECT")
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        size = ET.fromstring(archive.read("ppt/presentation.xml")).find("p:sldSz", ns)
        external = sum(e.get("TargetMode") == "External" for n in names if n.endswith(".rels") for e in ET.fromstring(archive.read(n)))
        result = {"path": POSTER, "sha256": sha(p), "bytes": p.stat().st_size,
                  "slides": sum(bool(re.fullmatch(r"ppt/slides/slide\d+.xml", n)) for n in names),
                  "inches": [int(size.get(k)) / 914400 for k in ["cx", "cy"]],
                  "external_relationships": external, "security_flags": flags,
                  "review": "Original V20; ZIP/XML readable; key cohort, graph, community, ranking and V1 metrics agree with saved findings. No modification or new rendering.",
                  "visual_qa_rerun": False, "temporary_office_lockfile_excluded": True}
        if flags or external:
            raise ValueError("Poster needs manual publication review; no values disclosed")
        return result


def build():
    previous = json.loads((HERE.parent / "COMMUNITY_V6_PHASE3_20261106_v1/PUBLICATION_ALLOWLIST.json").read_text())
    old = {e["path"]: e for e in previous["files"]}
    # Only README is deliberately revised; other historical hashes must still match.
    bad = [p for p, e in old.items() if p != "README.md" and sha(ROOT / p) != e["sha256"]]
    if bad:
        raise ValueError("Prior reviewed source changed: " + ", ".join(bad))
    (HERE / "POSTER_REVIEW.json").write_text(json.dumps(poster_review(), indent=2) + "\n")
    paths = set(old) | set(previous["review_metadata_paths"]) | {POSTER}
    paths |= {str(p.relative_to(ROOT)) for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    paths -= set(METADATA)
    for name in paths:
        p = Path(name)
        if p.suffix in {".tar", ".gz", ".zip", ".joblib", ".pkl", ".pt", ".npy", ".parquet"} or any(v.startswith(".env") or v in {"backups", "__pycache__"} for v in p.parts):
            raise ValueError("Restricted publication path")
        if name.endswith("/train_exploratory.py"):
            raise ValueError("Private-path helper must remain external")
    files = [{"path": n, "bytes": (ROOT / n).stat().st_size, "sha256": sha(ROOT / n)} for n in sorted(paths)]
    review = {"schema_version": "HTT-V6-FINAL-SOURCE-PUBLICATION-v1",
              "base_commit": previous["base_commit"], "branch": "codex/v6-submission-readiness",
              "authorization": "Owner final-submission prompt November 6 2026: exact cleared source/docs only; private runtime not authorized for publication",
              "status": "SOURCE_CONTENT_REVIEW_ONLY_ACCOUNT_AND_RUNTIME_CLEARANCE_NOT_IMPLIED",
              "credentials_rotated_or_revoked": "UNCONFIRMED_NO_USE",
              "files": files, "review_metadata_paths": METADATA,
              "runtime_bundle_included": False,
              "excluded": previous["excluded"], "publication_holds": previous["publication_holds"] + [
                  {"path": "reports/final_project/HEARTTRIALTWIN_FINAL_20261102/reports/REPRODUCIBILITY.md", "reason": "Preserved external-only historical private path"}],
              "review_metadata_note": "Self-referential metadata are not self-hashed; exact staged bytes and final Git commit bind them."}
    (HERE / "PUBLICATION_ALLOWLIST.json").write_text(json.dumps(review, indent=2) + "\n")
    (HERE / "PUBLICATION_FILES.txt").write_text("\n".join(sorted(paths | set(METADATA))) + "\n")
    return review


def validate(review, staged=False):
    expected = {e["path"] for e in review["files"]} | set(review["review_metadata_paths"])
    issues, scans, missing_links = [], [], []
    tracked = set(subprocess.check_output(["git", "ls-tree", "-r", "--name-only", review["base_commit"]], cwd=ROOT, text=True).splitlines())
    for e in review["files"]:
        p = ROOT / e["path"]
        data = subprocess.check_output(["git", "show", ":" + e["path"]], cwd=ROOT) if staged else p.read_bytes()
        if hashlib.sha256(data).hexdigest() != e["sha256"]:
            issues.append({"path": e["path"], "reason": "HASH_MISMATCH"})
        if e["path"] == POSTER:
            continue
        text = data.decode("utf-8")
        flags = [name for name, pattern in RULES.items() if pattern.search(text)]
        if re.search(r"/(?:Users|home)/[A-Za-z0-9]", text):
            flags.append("PRIVATE_HOME_PATH")
        if len(data) > 10_000_000:
            flags.append("OVERSIZED")
        if flags:
            scans.append({"path": e["path"], "flags": flags})
        if p.suffix == ".py":
            ast.parse(text, filename=e["path"])
        if p.suffix == ".json":
            json.loads(text)
        if p.suffix == ".md":
            for match in re.finditer(r"\]\(([^)]+)\)", text):
                target = match.group(1).strip("<>").split("#")[0]
                if not target or re.match(r"[a-zA-Z]+:", target):
                    continue
                resolved = (p.parent / urllib.parse.unquote(target)).resolve()
                if not resolved.is_relative_to(ROOT) or str(resolved.relative_to(ROOT)) not in expected | tracked:
                    missing_links.append({"path": e["path"], "target": target})
    whitespace_findings = []
    if staged:
        actual = set(subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"], cwd=ROOT).decode().strip("\0").split("\0"))
        # The allowlist includes unchanged already-published files; only deltas stage.
        expected_delta = set()
        for path in expected:
            old = subprocess.run(["git", "show", review["base_commit"] + ":" + path], cwd=ROOT, capture_output=True)
            if old.returncode or old.stdout != (ROOT / path).read_bytes():
                expected_delta.add(path)
        if actual != expected_delta:
            issues.append({"reason": "STAGED_SET_MISMATCH", "unexpected": sorted(actual - expected_delta), "missing": sorted(expected_delta - actual)})
        for path in review["review_metadata_paths"]:
            if subprocess.check_output(["git", "show", ":" + path], cwd=ROOT) != (ROOT / path).read_bytes():
                issues.append({"path": path, "reason": "STAGED_METADATA_MISMATCH"})
        whitespace = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True, text=True)
        whitespace_findings = [tuple(m.groups()) for m in re.finditer(r"^(.+):(\d+): (.+)$", whitespace.stdout, re.M)]
        allowed = {
            ("V1_INDEPENDENT_EVALUATION_REPORT.md", "3", "trailing whitespace."),
            ("V1_INDEPENDENT_EVALUATION_REPORT.md", "4", "trailing whitespace."),
            ("reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/trial_intelligence_v5.py", "209", "new blank line at EOF."),
        }
        if (set(whitespace_findings) - allowed or whitespace.returncode not in {0, 2}
                or (whitespace.returncode and not whitespace_findings)):
            issues.append({"reason": "UNREVIEWED_WHITESPACE_OR_DIFF_ERROR"})
    result = {"schema_version": "HTT-V6-FINAL-PUBLICATION-CHECK-v1", "staged": staged,
              "allowlisted_paths": len(expected), "hashed_files": len(review["files"]),
              "bytes": sum(e["bytes"] for e in review["files"]),
              "integrity_issues": issues, "secret_pattern_candidates": scans,
              "missing_or_excluded_documentation_links": missing_links,
              "immutable_whitespace_exceptions": whitespace_findings,
              "limitations": ["Scoped patterns and previously recorded history findings, not credential validity or exhaustive secret absence", "No private .env or exposed credential read", "Runtime redistribution is not cleared"],
              "status": "PASS" if not issues and not scans and not missing_links else "REVIEW_REQUIRED"}
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", action="store_true")
    p.add_argument("--staged", action="store_true")
    a = p.parse_args()
    review = build() if a.build else json.loads((HERE / "PUBLICATION_ALLOWLIST.json").read_text())
    result = validate(review, a.staged)
    if not a.staged:
        (HERE / "PUBLICATION_CHECKS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(result["status"] != "PASS")
