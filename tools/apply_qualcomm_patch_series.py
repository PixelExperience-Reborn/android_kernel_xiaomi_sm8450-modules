#!/usr/bin/env python3
"""Apply the reviewed patch series to one pinned Qualcomm WAIPIO 11900 source.

The source must be the exact gitlink commit recorded in
qualcomm-mondrian-waipio-11900-candidates.json and must be pristine. Every
patch is identified by its SHA-256, the whole series is checked with
`git apply --check` before any file is touched, and only the files named by
the series may change. Compiler warnings are never suppressed here.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "qualcomm-mondrian-waipio-11900-candidates.json"

# project -> ordered (patch path, sha256). An empty series is explicit.
SERIES = {
    "dataipa": (
        ("patches/qualcomm-dataipa/0001-external-module-build-paths.patch",
         "38e0455ad0cecd7485459c2a0bb0af555fc3e3a36edc355e1b7e9a8d8542606f"),
        ("patches/qualcomm-dataipa/0002-llvm23-prototypes-and-explicit-enum-casts.patch",
         "cdefcf3e429405a34656197cf2ca1b6601570131511779021f678cea64d91c78"),
    ),
    "datarmnet": (
        ("patches/qualcomm-datarmnet/0001-external-module-trace-include-path.patch",
         "132d866d2b2748ffc5c44880580295deb104021153580fd6cf250f85d5fdccbd"),
    ),
    "datarmnet-ext": (),
    "eva-kernel": (
        ("patches/qualcomm-eva/0001-llvm23-va-minidump-prototype.patch",
         "cc0982fe3333706311fcec8c8c782cc3593bc66cc33fb9d41cb4413e07a6145a"),
    ),
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patched_paths(text):
    return sorted(set(re.findall(r"(?m)^\+\+\+ b/(\S+)$", text)))


def expected_pin(project):
    lock = json.loads(LOCK.read_text())
    selection = lock["selection"][project]
    if not selection.get("selected"):
        raise ValueError("project is not selected for build: " + project)
    return selection["gitlink"], lock["projects"][project]["commit"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=sorted(SERIES))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--check", action="store_true",
                        help="verify pins, digests and applicability without changing files")
    args = parser.parse_args()
    source = args.source.resolve()
    gitlink, commit = expected_pin(args.project)
    if source != (ROOT / gitlink).resolve():
        raise ValueError(f"{args.project}: source must be the recorded gitlink {gitlink}")
    if git(source, "rev-parse", "HEAD") != commit:
        raise ValueError(f"{args.project}: checkout is not the pinned 11900 commit {commit}")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError(f"{args.project}: checkout is not pristine")
    patches = []
    expected_files = set()
    for relative, digest in SERIES[args.project]:
        path = ROOT / relative
        if sha256(path) != digest:
            raise ValueError("unreviewed patch content: " + relative)
        patches.append(path)
        expected_files.update(patched_paths(path.read_text()))
    # Validate the entire series before changing any file.
    for path in patches:
        subprocess.run(["git", "-C", str(source), "apply", "--check", str(path)], check=True)
    if args.check:
        print(f"[PASS] {args.project}: {len(patches)} reviewed patch(es) apply cleanly to {commit[:12]}")
        return
    if args.evidence is None:
        parser.error("--evidence is required when applying")
    for path in patches:
        subprocess.run(["git", "-C", str(source), "apply", str(path)], check=True)
    changed = set(git(source, "diff", "--name-only").splitlines()) - {""}
    if changed != expected_files:
        raise ValueError(f"{args.project}: unexpected changed paths {sorted(changed ^ expected_files)}")
    if git(source, "diff", "--check"):
        raise ValueError(f"{args.project}: whitespace errors after patching")
    evidence = {
        "project": args.project,
        "gitlink": gitlink,
        "commit": commit,
        "patches": [{"path": rel, "sha256": digest} for rel, digest in SERIES[args.project]],
        "changed_files": sorted(changed),
        "compiler_warnings_suppressed": False,
    }
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"[PASS] {args.project}: {len(patches)} reviewed patch(es) applied to {commit[:12]}")


if __name__ == "__main__":
    main()
