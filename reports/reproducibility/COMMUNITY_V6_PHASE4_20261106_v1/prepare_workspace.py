"""Export the Phase 4 reviewed source overlay; no assets, secrets or Git writes.

Reuses Phase 3 safe copying primitives, but its historical allowlist is not edited
when the current README and new Phase 4 documents change.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
spec = importlib.util.spec_from_file_location("phase3_workspace", HERE.parent / "COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def prepare(destination, ui_env=None, worker_env=None):
    destination = Path(destination).resolve()
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Use a new isolated directory outside the project")
    destination.mkdir(parents=True, exist_ok=False)
    review = json.loads((HERE / "PUBLICATION_ALLOWLIST.json").read_text())
    process = subprocess.Popen(["git", "archive", "--format=tar", review["base_commit"]], cwd=ROOT, stdout=subprocess.PIPE)
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for member in archive:
            base.safe(destination, member.name)
            if member.issym() or member.islnk():
                raise ValueError("Tracked symlinks not supported")
            archive.extract(member, path=destination, filter="data")
    if process.wait() != 0:
        raise ValueError("Source export failed")
    for entry in review["files"]:
        if entry["path"] in {"README.md", ".gitignore"}:
            src = ROOT / entry["path"]
            if base.sha(src) != entry["sha256"]:
                raise ValueError("Reviewed tracked text changed")
            (destination / entry["path"]).write_bytes(src.read_bytes())
        else:
            base.copy_checked(ROOT, destination, entry)
    for relative in review["review_metadata_paths"]:
        base.copy_checked(ROOT, destination, {"path": relative, "sha256": base.sha(ROOT / relative)})
    for name, environment in [(".venv-full-system", ui_env), (".venv-vector-rag", worker_env)]:
        if environment is None:
            continue
        env = Path(environment).resolve()
        if (env.is_relative_to(ROOT) or not (env / "pyvenv.cfg").is_file()
                or "include-system-site-packages = false" not in (env / "pyvenv.cfg").read_text().lower()):
            raise ValueError("Only separately created fresh environments may be aliased")
        (destination / name).symlink_to(env, target_is_directory=True)
    return {"status": "SOURCE_EXPORTED", "remote_clone": False, "runtime_copies": 0,
            "source_files": len(review["files"]) + len(review["review_metadata_paths"])}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destination", type=Path, required=True)
    p.add_argument("--ui-env", type=Path)
    p.add_argument("--worker-env", type=Path)
    a = p.parse_args()
    print(json.dumps(prepare(a.destination, a.ui_env, a.worker_env), indent=2))
