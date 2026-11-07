"""Scoped publication inventory/checks; does not read .env or Git secret objects."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ALLOWED_SUFFIXES = {".py", ".mjs", ".html", ".css", ".md", ".json", ".txt", ".example", ".jpg"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "aws_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "embedded_uri_credential": re.compile(r"(?:neo4j|bolt|https?)://[^\s/:]+:[^\s/@]+@", re.I),
    "neo4j_private_endpoint": re.compile(r"(?:neo4j\+s|bolt\+s)://[^\s\"']+", re.I),
    "password_assignment": re.compile(r"(?:PASSWORD|API_KEY|ACCESS_TOKEN)\s*[:=]\s*[\"'][^\"'\n]{8,}[\"']", re.I),
    "private_home_path": re.compile(r"/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/"),
}


def main():
    # The inventory is explicit and restricted; no blanket git staging.
    files = [ROOT / "README.md"] + sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    inventory = HERE / "PUBLICATION_FILES.txt"
    receipt = HERE / "validation/publication_review.json"
    # These two generated files are inventoried too; exclude only receipt's self-hash.
    files = sorted(set(files + [inventory, receipt]))
    for p in files:
        if p == inventory or p == receipt: continue
        if p.suffix not in ALLOWED_SUFFIXES or p.name.startswith(".env") or p.is_symlink():
            raise SystemExit("Unexpected publication file: " + p.name)
        if p.stat().st_size > 1_000_000: raise SystemExit("Oversized demo file: " + p.name)
        if p.suffix == ".jpg":
            if not p.read_bytes().startswith(b"\xff\xd8\xff"): raise SystemExit("Invalid screenshot")
            continue
        content = p.read_text()
        for kind, pattern in PATTERNS.items():
            if pattern.search(content): raise SystemExit("Review required (value suppressed): " + kind + " in " + str(p.relative_to(ROOT)))
    inventory.write_text("\n".join(str(p.relative_to(ROOT)) for p in files) + "\n")
    receipt.parent.mkdir(exist_ok=True)
    receipt.write_text(json.dumps({"status": "PASS", "scope": "Exact new-demo allowlist plus minimal root README",
        "pattern_matches": 0, "files": len(files), "bytes_without_receipt": sum(p.stat().st_size for p in files if p != receipt),
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p != receipt},
        "binary_policy": "Only authentic browser JPEG screenshots; viewed, signature checked; no model/database/archive files",
        "limitations": "Targeted patterns and allowlist, not proof of secret absence; no new exhaustive history/OCR scan. Existing public source traces are independently pinned. Prior Neo4j account rotation remains unconfirmed; credential not read or used.",
        "hosting_enabled": False, "merged": False}, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "files": len(files), "bytes_without_receipt": sum(p.stat().st_size for p in files if p != receipt)}))


if __name__ == "__main__": main()
