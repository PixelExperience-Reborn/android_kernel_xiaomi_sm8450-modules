#!/usr/bin/env python3
"""Read-only CodeLinaro release and source audit for mondrian IPA/RMNET/EVA.

Never build, execute, import or select a driver. The exact public 11900 tags
are checked first; the OEM-specific Xiaomi suffix is not assumed public.
13100 pins are independent comparison candidates from a published mirror of
the WAIPIO manifest, not proof of a match to the Xiaomi 11900 release.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = "https://git.codelinaro.org/clo/la/"
TAGS = (
    "LA.VENDOR.1.0.r1-11900-r1.0.r1_00029.0",
    "LA.VENDOR.1.0.r1-11900-WAIPIO.0",
    "LA.VENDOR.1.0.r1-11900-WAIPIO.QSSI13.0",
)
COMPARISON_MANIFEST = (
    "https://gitlab.com/TadiT7/la_vendor_manifest/-/blob/release/"
    "LA.VENDOR.1.0.r1-13100-WAIPIO.QSSI13.0.xml"
)
PROJECTS = {
    "dataipa": ("platform/vendor/opensource/dataipa",
                "0a4dd67728c8542091df0bf13551a8facabb29aa",
                r"ipa_fmwk_register_ipa|qcom,ipa|qcom,rmnet-ipa3|IPA_HW_v5_1|IPA_HW_v5_0"),
    "datarmnet": ("platform/vendor/qcom/opensource/datarmnet",
                  "be72451f657c2b2f101e318f9c237bdbe73d7d1a",
                  r"rmnet|RMNET"),
    "datarmnet-ext": ("platform/vendor/qcom/opensource/datarmnet-ext",
                      "8f648218b3896d31a39c9d41a0bcba2d7f5fdc53",
                      r"rmnet_shs|rmnet_perf|rmnet_ctl|rmnet_ll|RMNET"),
    "eva-kernel": ("platform/vendor/opensource/eva-kernel",
                   "8613d42b73d64780a62eb4cc5cfdda1e22551c1a",
                   r"qcom,waipio-cvp|waipio|WAIPIO|msm_eva"),
    "cvp-kernel": ("platform/vendor/opensource/cvp-kernel",
                   "b39e254e64b3e46b9602b6c3856af2d9084bf16b",
                   r"qcom,waipio-cvp|waipio|WAIPIO|msm_cvp"),
}


def git(args, cwd=None, timeout=65, allow_no_match=False):
    p = subprocess.run(
        ["git", "-c", "protocol.file.allow=never", *args],
        cwd=cwd, capture_output=True, text=True, errors="replace",
        timeout=timeout,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if p.returncode and not (allow_no_match and p.returncode == 1):
        raise RuntimeError(f"git {args[0]}: {p.stderr.strip()[:400]}")
    return p.stdout


def resolve_tags(output):
    refs = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2:
            sha, ref = parts
            if len(sha) == 40 and all(c in "0123456789abcdef" for c in sha):
                refs[ref] = sha
    return {tag: refs.get(f"refs/tags/{tag}^{{}}") or
            refs.get(f"refs/tags/{tag}") for tag in TAGS}


def survey(name, spec):
    project, comparison, regex = spec
    url = ROOT + project + ".git"
    result = {"url": url, "comparison_manifest": COMPARISON_MANIFEST,
              "comparison_sha": comparison, "source_selected": False,
              "compiled": False, "abi_qualified": False}
    try:
        patterns = [pattern for tag in TAGS for pattern in
                    (f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")]
        tags = resolve_tags(git(["ls-remote", "--tags", url, *patterns]))
        result["official_tags"] = tags
        selected = next((tag for tag in TAGS if tags[tag]), None)
        ref = f"refs/tags/{selected}" if selected else comparison
        expected = tags[selected] if selected else comparison
        result["candidate_basis"] = selected or "13100_manifest_comparison_only"
        with TemporaryDirectory(prefix="mondrian-clo-") as directory:
            git(["init", "-q"], cwd=directory)
            git(["fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
                 url, ref], cwd=directory, timeout=100)
            actual = git(["rev-parse", "FETCH_HEAD^{commit}"], cwd=directory).strip()
            if actual != expected:
                raise RuntimeError("remote commit differs from resolved candidate")
            result["verified_source_commit"] = actual
            paths = git(["ls-tree", "-r", "--name-only", actual], cwd=directory)
            result["kbuild_paths"] = [p for p in paths.splitlines()
                if Path(p).name in ("Kbuild", "Makefile", "Kconfig")][:60]
            evidence = git(["grep", "-n", "-m", "2", "-E", regex, actual, "--",
                            "*.c", "*.h", "Kbuild", "Makefile", "*.mk"],
                           cwd=directory, allow_no_match=True)
            result["source_evidence"] = evidence.splitlines()[:100]
            result["status"] = "official_source_read_candidate_not_qualified"
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        result["status"] = "source_unverified"
        result["error"] = str(error)[:450]
    return name, result


def main():
    with ThreadPoolExecutor(max_workers=5) as pool:
        records = dict(pool.map(lambda item: survey(*item), PROJECTS.items()))
    Path("mondrian-code-linaro-data-survey.json").write_text(
        json.dumps({"device": "mondrian", "soc": "SM8475",
                    "source_imported": False, "projects": records},
                   indent=2) + "\n")
    for name, result in records.items():
        print(name, result["status"], result.get("candidate_basis"),
              result.get("verified_source_commit"))
        if result.get("error"):
            print("  ", result["error"])
    print("[PENDING] source selection, exact OEM ABI, module dependencies and hardware")


if __name__ == "__main__":
    main()
