"""Create only a small static projection of verified, already-published facts."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("public_replay", HERE / "replay.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify determinism; do not write files")
    args = parser.parse_args()
    evidence = r.load_evidence()
    raw = (json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    pins = {"payload_sha256": r.sha(raw), "source_trace_sha256": r.FILES,
            "source_manifest_sha256": r.MANIFEST_SHA256, "source_commit": r.PUBLIC_COMMIT,
            "graph_manifest_sha256": r.GRAPH_MANIFEST}
    integrity = ("// Generated from verified published traces. Not a digital signature.\nexport const PINS = "
                 + json.dumps(pins, indent=2, sort_keys=True) + ";\n").encode()
    outputs = {"evidence.json": raw, "integrity.mjs": integrity}
    for name, content in outputs.items():
        target = HERE / "site" / name
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                raise SystemExit("Static evidence is missing or differs: " + name)
        else:
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(content)
    print(json.dumps({"status": "VERIFIED" if args.check else "BUILT", "bytes": len(raw),
                      "payload_sha256": pins["payload_sha256"], "records": {k: len(v) for k, v in evidence["records"].items()}}))


if __name__ == "__main__": main()
