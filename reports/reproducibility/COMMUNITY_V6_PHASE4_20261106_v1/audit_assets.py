"""Read only the 190 enumerated assets; save metadata, never matched secret text.

No .env reads, pickle loading, OCR, historical Git rescan or network requests.
Run with the bundled PDF/Pillow runtime for PDF text and PNG metadata inspection.
"""
from collections import Counter
import gzip
import json
from pathlib import Path
import re

from runtime_bundle import HERE, ROOT, inventory, sha

RULES = {
    "SECRET_ASSIGNMENT": re.compile(r'''(?im)["']?(?:NEO4J_PASSWORD|FULL_GRAPHRAG_NEO4J_PASSWORD|OPENAI_API_KEY|api_key|access_token|password)["']?\s*[:=]\s*["']([^"'\r\n]{6,})["']'''),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "TOKEN_SHAPE": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{35,})"),
    "AUTHENTICATED_URI": re.compile(r"(?:bolt|neo4j|https?)(?:\+s)?://[^\s/\"']+:[^\s/@\"']+@"),
}


def group(path):
    if path.endswith(".joblib"):
        return "FROZEN_EXECUTABLE_MODELS"
    if path.endswith("/train_exploratory.py"):
        return "PRIVATE_PATH_RUNTIME_HELPER"
    if path.startswith("artifacts/cohort_scaling/"):
        return "PINNED_GRAPH_AND_SOURCE_CACHE"
    if "archive_extracts/" in path:
        return "HISTORICAL_REGISTRY_CACHES"
    if "historical_snapshot_eligibility_audit" in path:
        return "HISTORICAL_ELIGIBILITY_LEDGER"
    if "community_sensitivity" in path or "community_exploration" in path:
        return "FROZEN_COMMUNITY_OUTPUT"
    if "HEARTTRIALTWIN_FINAL_20261102/" in path:
        return "FROZEN_BASE_PACKAGE_GUARD"
    if "HEARTTRIALTWIN_INTEGRATED_20261102_v1/" in path:
        return "INTEGRATED_DASHBOARD_AND_SCENARIO"
    if "independent_evaluation_2021_2024" in path:
        return "BLOCKED_EVALUATION_SUMMARY"
    return "SOURCE_AND_BOOTSTRAP"


def audit(candidate):
    from PIL import Image
    from pypdf import PdfReader
    records, scans = [], []
    for e in inventory():
        path, rel = ROOT / e["path"], e["path"]
        if sha(path) != e["sha256"] or path.stat().st_size != e["bytes"]:
            raise ValueError("Pinned runtime source changed")
        raw = path.read_bytes()
        method = "UTF8_OR_PRINTABLE_BINARY_STRINGS"
        text = raw.decode("utf-8", errors="replace")
        detail = {}
        if path.suffix == ".gz":
            text = gzip.decompress(raw).decode("utf-8")
            obj = json.loads(text)
            detail["top_level_fields"] = sorted(obj) if isinstance(obj, dict) else []
            detail["tables"] = sorted(obj.get("tables", {})) if isinstance(obj, dict) else []
            method = "DECOMPRESSED_JSON_TEXT"
        elif path.suffix == ".png":
            with Image.open(path) as im:
                text = json.dumps(im.info, default=str)
                detail["image_size"] = list(im.size)
            method = "PNG_METADATA_ONLY_NO_OCR"
        elif path.suffix == ".pdf":
            reader = PdfReader(path)
            text = str(reader.metadata) + "\n" + "\n".join(p.extract_text() or "" for p in reader.pages)
            detail["pages"] = len(reader.pages)
            method = "PDF_TEXT_AND_METADATA_NO_IMAGE_OCR"
        hits = [{"rule": name, "line": text.count("\n", 0, m.start()) + 1}
                for name, rule in RULES.items() for m in rule.finditer(text)]
        private_paths = sorted(set(re.findall(r"/(?:Users|home)/[^\s\"'<>]+", text)))
        emails = len(re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text))
        scans.append({"path": rel, "method": method, "credential_pattern_findings": hits,
                      "private_home_path_count": len(private_paths), "email_pattern_count": emails,
                      "over_50_mb": len(raw) > 50_000_000, **detail})
        g = group(rel)
        missing = not (candidate / rel).is_file()
        caution = []
        if private_paths:
            caution.append("PRIVATE_HOME_PATH_METADATA_OWNER_REVIEW_REQUIRED")
        if emails:
            caution.append("POSSIBLE_PUBLIC_REGISTRY_CONTACT_OR_REPORT_EMAIL_REVIEW_REQUIRED")
        if hits:
            caution.append("SECRET_PATTERN_REVIEW_REQUIRED")
        if g == "FROZEN_EXECUTABLE_MODELS":
            caution.append("EXECUTABLE_PICKLE_TRUSTED_OWNER_SOURCE_ONLY")
        original = g != "SOURCE_AND_BOOTSTRAP"
        records.append({**e, "missing_in_source_only": missing, "asset_group": g,
            "essential_for_current_full_app": True,
            "essentiality_reason": "Direct runtime/bootstrap dependency or required by unchanged whole-package/source hash guards; not all are directly rendered",
            "preserve_original_bytes": True, "frozen_scientific_or_source_artifact": original,
            "upstream_public_reference": "https://aact.ctti-clinicaltrials.org/" if g in {"PINNED_GRAPH_AND_SOURCE_CACHE", "HISTORICAL_REGISTRY_CACHES"} else None,
            "exact_direct_public_download_verified": False,
            "exact_public_url_documented": bool(e.get("public_source_url")),
            "public_download_note": "Existing base-commit link documented; not freshly downloaded" if e.get("public_source_url") else "No authoritative public URL established for these exact derived bytes; current registry is not a substitute",
            "redistribution_decision": "HOLD_PUBLIC_DISTRIBUTION_PENDING_OWNER_RIGHTS_TERMS_AND_CONTENT_REVIEW" if missing else "EXISTING_TRACKED_OR_REVIEWED_SOURCE_NOT_NEW_CLEARANCE",
            "security_and_privacy_notes": caution,
            "approved_alternative": "Trusted owner-to-team private provision of identical bytes after permission; otherwise full five-page demo remains blocked. No source/guard rewriting authorized." if missing else "Existing source candidate",
        })
    missing = [e for e in records if e["missing_in_source_only"]]
    return {"schema_version": "HTT-V6-PHASE4-ASSET-REVIEW-v1", "date": "2026-11-06",
            "required_files": len(records), "required_bytes": sum(e["bytes"] for e in records),
            "missing_files": len(missing), "missing_bytes": sum(e["bytes"] for e in missing),
            "missing_by_group": dict(Counter(e["asset_group"] for e in missing)),
            "public_bundle_approved": False, "assets": records}, {
            "schema_version": "HTT-V6-PHASE4-SCOPED-SCAN-v1", "files": scans,
            "scope": "190 exact runtime assets, not Git history; no secret value printed or retained",
            "limitations": ["Regex inspection cannot certify absence of secrets", "No fresh OCR of raster figures or PDF image layers", "Joblib printable strings inspected without deserializing", "No credential validity or rotation test", "Private source paths and possible public contact emails require owner review"],
            "credential_pattern_findings": sum(len(e["credential_pattern_findings"]) for e in scans)}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate", type=Path, required=True)
    a = p.parse_args()
    review, scan = audit(a.candidate)
    for name, value in [("ASSET_DISTRIBUTION_REVIEW.json", review), ("RUNTIME_SECURITY_SCAN.json", scan)]:
        (HERE / name).write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({k: v for k, v in review.items() if k != "assets"}, indent=2))
    print(json.dumps({"scanned": len(scan["files"]), "credential_pattern_findings": scan["credential_pattern_findings"]}))
