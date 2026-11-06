"""Private, exact-byte handoff only. No downloads, publishing or model loading.

An archive hash obtained through a trusted owner channel is required at install.
Checksums establish identity, not a license, signature or pickle safety guarantee.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INVENTORY = ROOT / "reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/RUNTIME_ASSETS.json"
INVENTORY_SHA256 = "5a06766aa1188ebb5d69397b1e0684b67da102e59f53d5dc57cc0297286844e6"
MAX_ARCHIVE_BYTES = 60_000_000


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe(root, relative):
    p = Path(relative)
    if (p.is_absolute() or ".." in p.parts or not p.parts or "\\" in relative
            or any(v.startswith(".") for v in p.parts)):
        raise ValueError("Unsafe asset path")
    root = Path(root).resolve()
    dest = root / p
    # Even an in-root symlink would make the received layout ambiguous.
    if any(v.is_symlink() for v in [dest, *dest.parents] if v != root.parent):
        raise ValueError("Symlinks are not runtime assets")
    if not dest.resolve().is_relative_to(root):
        raise ValueError("Asset escapes destination")
    return dest


def inventory():
    if sha(INVENTORY) != INVENTORY_SHA256:
        raise ValueError("Pinned Phase 3 inventory changed")
    entries = json.loads(INVENTORY.read_text())["required_assets"]
    if len(entries) != 190 or len({e["path"] for e in entries}) != 190:
        raise ValueError("Runtime inventory identity mismatch")
    for e in entries:
        safe(ROOT, e["path"])
    return entries


def check(root, entries):
    missing, mismatched = [], []
    for e in entries:
        p = safe(root, e["path"])
        if not p.is_file():
            missing.append(e["path"])
        elif p.stat().st_size != e["bytes"] or sha(p) != e["sha256"]:
            mismatched.append(e["path"])
    return {"required": len(entries), "missing": missing, "mismatched": mismatched}


def create(source, candidate, archive, *, trusted_local_assets=False):
    if not trusted_local_assets:
        raise ValueError("Explicit trust in owner-supplied local assets is required")
    entries = inventory()
    source_check, target_check = check(source, entries), check(candidate, entries)
    if source_check["missing"] or source_check["mismatched"] or target_check["mismatched"]:
        raise ValueError("Source/candidate integrity failure; no archive created")
    missing = set(target_check["missing"])
    selected = sorted((e for e in entries if e["path"] in missing), key=lambda e: e["path"])
    archive = Path(archive)
    if archive.resolve().is_relative_to(ROOT) or archive.exists():
        raise ValueError("Use a new private archive outside the repository")
    archive.parent.mkdir(parents=True, exist_ok=True)
    # No embedded manifest/self hash; the pinned source inventory is already in source.
    with open(archive, "xb", opener=lambda p, flags: os.open(p, flags, 0o600)) as out, tarfile.open(fileobj=out, mode="w") as tar:
        for e in selected:
            data = safe(source, e["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != e["sha256"]:
                raise ValueError("Asset changed during packaging")
            info = tarfile.TarInfo("payload/" + e["path"])
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    archive.chmod(0o600)
    return {"schema_version": "HTT-COMMUNITY-V6-PRIVATE-RUNTIME-v1",
            "distribution": "PRIVATE_LOCAL_TEST_ONLY_PUBLIC_DISTRIBUTION_NOT_APPROVED",
            "inventory_sha256": INVENTORY_SHA256, "archive_sha256": sha(archive),
            "archive_bytes": archive.stat().st_size,
            "payload_files": len(selected), "payload_bytes": sum(e["bytes"] for e in selected),
            "files": selected, "credentials_included": False,
            "note": "No .env paths allowed; content review is separately recorded. Includes trusted executable joblib files."}


def install(archive, destination, *, trusted_archive_sha256):
    archive, destination = Path(archive), Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Handoff test must not write into the development project")
    if not destination.is_dir():
        raise ValueError("Prepare the reviewed source checkout first")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES or sha(archive) != trusted_archive_sha256:
        raise ValueError("Archive identity failure")
    entries = inventory()
    allowed = {"payload/" + e["path"]: e for e in entries}
    verified, seen = [], set()
    # Validate ALL members before copying ANY bytes. Never use extractall.
    with tarfile.open(archive, mode="r:") as tar:
        for member in tar:
            if member.name not in allowed or member.name in seen or not member.isfile():
                raise ValueError("Unexpected, duplicate or non-regular archive member")
            seen.add(member.name)
            e = allowed[member.name]
            dest = safe(destination, e["path"])
            if member.size != e["bytes"]:
                raise ValueError("Member size mismatch")
            data = tar.extractfile(member).read(e["bytes"] + 1)
            if hashlib.sha256(data).hexdigest() != e["sha256"]:
                raise ValueError("Member checksum mismatch")
            if dest.exists() and (not dest.is_file() or sha(dest) != e["sha256"]):
                raise ValueError("Refusing to overwrite existing different bytes")
            verified.append((e, dest))
        present = check(destination, entries)
        if present["mismatched"] or not set(present["missing"]).issubset(e["path"] for e, _ in verified):
            raise ValueError("Archive cannot complete this source checkout")
        copied = 0
        for e, dest in verified:
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as out:
                out.write(tar.extractfile("payload/" + e["path"]).read())
            copied += 1
    result = check(destination, entries)
    if result["missing"] or result["mismatched"]:
        raise ValueError("Post-install verification failed; no automatic repair/delete")
    return {"status": "VERIFIED_LOCAL_HANDOFF", "copied": copied, "verified_assets": 190,
            "downloads": 0, "public_reproduction_established": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check"); c.add_argument("--root", type=Path, required=True)
    c = sub.add_parser("create-private")
    c.add_argument("--source", type=Path, required=True)
    c.add_argument("--candidate", type=Path, required=True)
    c.add_argument("--archive", type=Path, required=True)
    c.add_argument("--trusted-local-assets", action="store_true")
    c = sub.add_parser("install")
    c.add_argument("--archive", type=Path, required=True)
    c.add_argument("--destination", type=Path, required=True)
    c.add_argument("--trusted-archive-sha256", required=True)
    a = p.parse_args()
    if a.action == "check":
        result = check(a.root, inventory())
    elif a.action == "create-private":
        result = create(a.source, a.candidate, a.archive, trusted_local_assets=a.trusted_local_assets)
    else:
        result = install(a.archive, a.destination, trusted_archive_sha256=a.trusted_archive_sha256)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
