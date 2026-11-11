#!/usr/bin/env python3
"""Discover Qualcomm CodeLinaro releases; do not select/import automatically."""
import json
from pathlib import Path
import subprocess

CANDIDATES = {
    "mmrm": ("mmrm-driver", "VIDEO.LA.2.0.r1-10200-WAIPIO.0"),
    "display": ("display-drivers", "DISPLAY.LA.2.0.r1-13000-WAIPIO.0"),
    "camera": ("camera-kernel", "CAMERA.LA.2.0.r1-11800-WAIPIO.0"),
    "video": ("video-driver", "VIDEO.LA.2.0.r1-10200-WAIPIO.0"),
}

def main():
    results = {}
    for name, (project, tag) in CANDIDATES.items():
        url = f"https://git.codelinaro.org/clo/la/platform/vendor/opensource/{project}.git"
        try:
            p = subprocess.run(["timeout", "45", "git", "ls-remote", "--tags", url,
                                f"refs/tags/{tag}*"],
                               capture_output=True, text=True, check=True, timeout=50)
            entries = [l.split() for l in p.stdout.splitlines() if l.strip()]
            peeled = [sha for sha, ref in entries if ref.endswith("^{}")]
            direct = [sha for sha, ref in entries if ref.endswith("/" + tag)]
            commit = (peeled or direct or [None])[0]
            results[name] = {"url": url, "tag": tag, "resolved_commit": commit,
                             "status": "candidate_not_qualified" if commit else "tag_not_found"}
        except (OSError, subprocess.SubprocessError) as error:
            results[name] = {"url": url, "tag": tag, "resolved_commit": None,
                             "status": "source_temporarily_inaccessible",
                             "error": str(error)[:200]}
    destination = Path("qualcomm-release-survey.json")
    destination.write_text(json.dumps(results, indent=2) + "\n")
    for name, result in results.items():
        print(name, result["status"], result["tag"], result["resolved_commit"])
    print("[PENDING] No Qualcomm module imported; KMI and source ABI not qualified")

if __name__ == "__main__":
    main()
