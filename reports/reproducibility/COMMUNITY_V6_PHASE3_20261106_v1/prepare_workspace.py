"""Materialize an isolated source candidate, optionally with verified local assets.

No Git writes, downloads, credentials, development packages or research edits.
Fresh-environment aliases are explicit; they never point to development venvs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_COMMIT = "be520bcd40748abfc03e4ff9b64bf244650c5367"
V6 = "reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe(root, name):
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts or any(p.startswith(".env") and p != ".env.example" for p in rel.parts):
        raise ValueError("Unsafe or credential-bearing path")
    path = (Path(root) / rel).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("Path escapes workspace")
    return path


def copy_checked(source_root, target_root, entry):
    src = safe(source_root, entry["path"])
    dst = safe(target_root, entry["path"])
    if not src.is_file() or sha(src) != entry["sha256"]:
        raise ValueError("Source checksum failure: " + entry["path"])
    if dst.exists():
        if sha(dst) != entry["sha256"]:
            raise ValueError("Refusing different existing workspace bytes: " + entry["path"])
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    if sha(dst) != entry["sha256"]:
        raise ValueError("Copy checksum failure")
    return True


def prepare(destination, *, provision=False, ui_env=None, worker_env=None):
    dest = Path(destination).resolve()
    if dest == ROOT or dest.is_relative_to(ROOT):
        raise ValueError("Use a new isolated directory outside the development project")
    dest.mkdir(parents=True, exist_ok=False)
    # A tracked-tree export, NOT a remote clone or a Git-history security claim.
    process = subprocess.Popen(["git", "archive", "--format=tar", BASE_COMMIT], cwd=ROOT, stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            safe(dest, member.name)
            if member.issym() or member.islnk():
                raise ValueError("Unexpected tracked symlink")
            archive.extract(member, path=dest, filter="data")
    if process.wait() != 0:
        raise ValueError("Tracked-tree export failed")
    proposed = json.loads((HERE / "PUBLICATION_ALLOWLIST.json").read_text())
    count = 0
    # Only these two explicitly reviewed tracked files are intentionally updated.
    for entry in proposed["files"]:
        if entry["path"] in {"README.md", ".gitignore"}:
            src = ROOT / entry["path"]
            if sha(src) != entry["sha256"]:
                raise ValueError("Reviewed tracked text changed after allowlist review")
            shutil.copyfile(src, dest / entry["path"])
            count += 1
        else:
            count += copy_checked(ROOT, dest, entry)
    # Review inventories cannot hash themselves; copy those exact declared names
    # with a just-in-time byte check, without treating them as frozen inputs.
    for relative in proposed.get("review_metadata_paths", []):
        count += copy_checked(ROOT, dest, {"path": relative, "sha256": sha(ROOT / relative)})
    external = 0
    if provision:
        inventory = json.loads((HERE / "RUNTIME_ASSETS.json").read_text())
        for entry in inventory["required_assets"]:
            external += copy_checked(ROOT, dest, entry)
    aliases = {}
    for name, environment in [(".venv-full-system", ui_env), (".venv-vector-rag", worker_env)]:
        if environment is None:
            continue
        env = Path(environment).resolve()
        if env.is_relative_to(ROOT) or not (env / "pyvenv.cfg").is_file():
            raise ValueError("Only separately created fresh environments may be aliased")
        if "include-system-site-packages = false" not in (env / "pyvenv.cfg").read_text().lower():
            raise ValueError("System-site-packages must be disabled")
        (dest / name).symlink_to(env, target_is_directory=True)
        aliases[name] = "SEPARATE_FRESH_ENVIRONMENT"
    return {"status": "PREPARED", "base_commit": BASE_COMMIT, "candidate_overlay_copies": count,
            "local_runtime_copies": external, "environment_aliases": aliases,
            "remote_clone": False, "public_runtime_bundle_available": False,
            "credentials_copied": False, "network_calls": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--provision-local-assets", action="store_true")
    parser.add_argument("--ui-env", type=Path)
    parser.add_argument("--worker-env", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination, provision=args.provision_local_assets,
                             ui_env=args.ui_env, worker_env=args.worker_env), indent=2))


if __name__ == "__main__":
    main()
