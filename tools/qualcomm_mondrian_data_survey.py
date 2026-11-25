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
import xml.etree.ElementTree as ET

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


def is_sha(value):
    return value is not None and len(value) == 40 and all(
        c in "0123456789abcdef" for c in value)


def parse_pins(xmls):
    """Collect only exact project names and immutable revisions."""
    project_names = {spec[0] for spec in PROJECTS.values()}
    pins = {}
    for raw in xmls:
        root = ET.fromstring(raw)
        default = root.find("default")
        default_rev = default.get("revision") if default is not None else None
        for entry in root.iter("project"):
            name = entry.get("name")
            revision = entry.get("revision", default_rev)
            if name not in project_names or not is_sha(revision):
                continue
            if name in pins and pins[name] != revision:
                raise ValueError(f"conflicting release manifest pins for {name}")
            pins[name] = revision
    return pins


def read_tagged_manifest():
    """The public release manifest may pin projects without per-repo tags."""
    url = ROOT + "la/vendor/manifest.git"
    patterns = [pattern for tag in TAGS for pattern in
                (f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")]
    tags = resolve_tags(git(["ls-remote", "--tags", url, *patterns]))
    for tag in TAGS:
        if not tags[tag]:
            continue
        with TemporaryDirectory(prefix="mondrian-clo-manifest-") as directory:
            git(["init", "-q"], cwd=directory)
            git(["fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
                 url, f"refs/tags/{tag}"], cwd=directory, timeout=90)
            actual = git(["rev-parse", "FETCH_HEAD^{commit}"], cwd=directory).strip()
            if actual != tags[tag]:
                raise RuntimeError("manifest commit differs from official tag")
            paths = git(["ls-tree", "-r", "--name-only", actual], cwd=directory).splitlines()
            roots = [p for p in (tag + ".xml", "default.xml", "vendor.xml") if p in paths]
            if not roots:
                continue
            todo = roots[:]
            visited = set()
            documents = []
            while todo:
                path = todo.pop()
                if path in visited or path not in paths or len(visited) >= 100:
                    continue
                visited.add(path)
                raw = git(["show", f"{actual}:{path}"], cwd=directory)
                documents.append(raw)
                for inc in ET.fromstring(raw).iter("include"):
                    name = inc.get("name")
                    if name and name in paths:
                        todo.append(name)
            pins = parse_pins(documents)
            if pins:
                return {"url": url, "tag": tag, "commit": actual,
                        "status": "official_manifest_read",
                        "files": sorted(visited), "pins": pins}
    return {"url": url, "status": "official_manifest_tag_or_pins_not_found",
            "official_tags": tags, "pins": {}}


def read_mirror_manifest():
    """Fallback metadata only: every project SHA is still fetched from CLO."""
    url = "https://gitlab.com/TadiT7/la_vendor_manifest.git"
    with TemporaryDirectory(prefix="mondrian-manifest-mirror-") as directory:
        git(["init", "-q"], cwd=directory)
        git(["fetch", "--depth=1", "--no-tags", "--no-recurse-submodules",
             url, "refs/heads/release"], cwd=directory, timeout=90)
        actual = git(["rev-parse", "FETCH_HEAD^{commit}"], cwd=directory).strip()
        for tag in TAGS:
            path = tag + ".xml"
            try:
                raw = git(["show", f"{actual}:{path}"], cwd=directory)
            except RuntimeError:
                continue
            pins = parse_pins([raw])
            if pins:
                return {"url": url, "tag": tag, "commit": actual,
                        "file": path, "status": "mirror_manifest_metadata_only",
                        "pins": pins}
    return {"url": url, "status": "mirror_manifest_pins_not_found", "pins": {}}


def release_manifest():
    attempts = []
    for reader in (read_tagged_manifest, read_mirror_manifest):
        try:
            result = reader()
            attempts.append({k: v for k, v in result.items() if k != "pins"})
            if result["pins"]:
                return {**result, "attempts": attempts}
        except (OSError, RuntimeError, ValueError, ET.ParseError,
                subprocess.SubprocessError) as error:
            attempts.append({"reader": reader.__name__, "error": str(error)[:450]})
    return {"status": "manifest_unverified", "pins": {}, "attempts": attempts}


def survey(name, spec, manifest):
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
        manifest_sha = manifest["pins"].get(project)
        if manifest_sha:
            ref = expected = manifest_sha
            result["candidate_basis"] = manifest["tag"] + "_manifest_pin"
            result["manifest_provenance"] = manifest["status"]
        elif selected:
            ref, expected = f"refs/tags/{selected}", tags[selected]
            result["candidate_basis"] = selected
        else:
            ref = expected = comparison
            result["candidate_basis"] = "13100_manifest_comparison_only"
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
    manifest = release_manifest()
    print("WAIPIO release manifest:", manifest["status"], manifest.get("tag"),
          manifest.get("commit"), "exact project pins:", len(manifest["pins"]))
    for attempt in manifest.get("attempts", []):
        print("manifest attempt:", json.dumps(attempt, sort_keys=True))
    with ThreadPoolExecutor(max_workers=5) as pool:
        records = dict(pool.map(lambda item: survey(*item, manifest), PROJECTS.items()))
    Path("mondrian-code-linaro-data-survey.json").write_text(
        json.dumps({"device": "mondrian", "soc": "SM8475",
                    "source_imported": False, "manifest": manifest, "projects": records},
                   indent=2) + "\n")
    for name, result in records.items():
        print(name, result["status"], result.get("candidate_basis"),
              result.get("verified_source_commit"))
        if result.get("error"):
            print("  ", result["error"])
    print("[PENDING] source selection, exact OEM ABI, module dependencies and hardware")


if __name__ == "__main__":
    main()
