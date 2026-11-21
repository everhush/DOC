#!/usr/bin/env python3
"""Quota-gated Kaggle GPU dispatcher. Runs only on a trusted GitHub Actions runner.

KAGGLE_DOC_1 is NEVER uploaded to Kaggle. This code is an orchestration tool,
not a DOC runtime, GPU host, shader generator or fallback implementation.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import sys
import tempfile
import time
import urllib.request

# Kaggle itself owns GPU quotas and session limits. DOC imposes none.
# Network I/O timeouts below protect against failed API calls, not GPU use.
DEFAULT_ACCELERATOR = "NvidiaTeslaT4"
STATUS = re.compile(r"\b(?:KERNELWORKERSTATUS[.]|KERNELSTATUS[.])?(COMPLETE|COMPLETED|ERROR|FAILED|CANCELLED|CANCELED|RUNNING|QUEUED|PENDING|INITIALIZING)\b")

def quota_hours(value):
    if isinstance(value, bool):
        raise ValueError("Invalid Kaggle quota value")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:h|hours?)?\s*", str(value), re.I)
        if not match:
            raise ValueError("Unknown Kaggle quota units: refusing GPU dispatch")
        number = float(match.group(1))
    if not (0 <= number < 100000):
        raise ValueError("Invalid Kaggle GPU quota")
    return number

def gpu_remaining_hours(blob):
    data = json.loads(blob)
    if isinstance(data, dict):
        data = data.get("rows", data.get("items", data.get("quotas")))
    if not isinstance(data, list):
        raise ValueError("Unknown Kaggle quota structure")
    rows = [row for row in data if isinstance(row, dict)
            and str(row.get("resource", "")).strip().upper() == "GPU"]
    if len(rows) != 1 or "remaining" not in rows[0]:
        raise ValueError("Missing or ambiguous GPU quota: refusing to submit")
    return quota_hours(rows[0]["remaining"])

def status_from_cli(value):
    hits = STATUS.findall(value.upper())
    if not hits:
        return "UNKNOWN"
    last = hits[-1]
    if last in ("COMPLETE", "COMPLETED"):
        return "COMPLETE"
    if last in ("ERROR", "FAILED", "CANCELLED", "CANCELED"):
        return "FAILED"
    return "RUNNING"

def auth_environment(secret, directory, username_hint):
    secret = secret.strip()
    if not secret:
        raise ValueError("KAGGLE_DOC_1 GitHub secret is not configured")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    env = dict(os.environ)
    env.pop("KAGGLE_DOC_1", None)
    env["KAGGLE_CONFIG_DIR"] = str(directory)
    username = username_hint.strip().lower()
    if secret.startswith("{"):
        obj = json.loads(secret)
        if not isinstance(obj.get("username"), str) or not obj.get("username") or not isinstance(obj.get("key"), str) or not obj.get("key"):
            raise ValueError("KAGGLE_DOC_1 JSON requires username and key")
        username = obj["username"].strip().lower()
        path = directory / "kaggle.json"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"username": obj["username"], "key": obj["key"]}, f)
    else:
        env["KAGGLE_API_TOKEN"] = secret
        if not username:
            # The official Kaggle CLI can resolve the authenticated account
            # from a modern raw API token. Never print config output or token.
            p = subprocess.run(["kaggle", "config", "view"], env=env,
                capture_output=True, text=True, timeout=25)
            if p.returncode == 0:
                match = re.search(r"(?mi)^\s*-?\s*username:\s*([a-z0-9_-]+)\s*$", p.stdout)
                if match:
                    username = match.group(1).lower()
    if not re.fullmatch(r"[a-z0-9_-]{2,60}", username):
        raise ValueError("Kaggle token owner could not be resolved; set DOC_KAGGLE_USERNAME")
    return env, username

def kaggle(command, env, timeout=60):
    p = subprocess.run(["kaggle", *command], env=env, capture_output=True,
                       text=True, timeout=timeout)
    if p.returncode:
        # Do not print authenticated process stdout/stderr, which may include
        # usernames, tokens or other credentials.
        raise RuntimeError("Kaggle CLI operation failed: " + command[0])
    return p.stdout

def prepare_kernel(folder, template, spec, username):
    folder.mkdir(parents=True, exist_ok=False)
    slug = "doc-gpu-{}-{}".format(spec["run_id"], spec["attempt"])
    if not re.fullmatch(r"doc-gpu-[0-9]+-[0-9]+", slug):
        raise ValueError("Invalid unique notebook name")
    code = template.read_text(encoding="utf-8")
    if code.count("__DOC_KAGGLE_RUN_SPEC__") != 1:
        raise ValueError("GPU test notebook template has changed")
    (folder / "doc_kaggle_gpu.py").write_text(
        code.replace("__DOC_KAGGLE_RUN_SPEC__", repr(spec)), encoding="utf-8")
    metadata = {
        "id": username + "/" + slug,
        "title": slug,  # Keep Kaggle title-derived URL slug consistent with kernel id.
        "code_file": "doc_kaggle_gpu.py",
        "language": "python", "kernel_type": "script",
        "is_private": "true", "enable_gpu": "true", "enable_internet": "true",
        "machine_shape": spec["accelerator"],
        "dataset_sources": [spec["bundle_dataset"]] if "bundle_dataset" in spec else [],
        "competition_sources": [],
        "kernel_sources": [], "model_sources": []
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata["id"]

def verify_result(folder, spec):
    result = json.loads((folder / "doc-kaggle-summary.json").read_text())
    expected = {"sha": spec["sha"], "run_id": spec["run_id"],
                "result": "pass", "backend": "vulkan", "hardware": True,
                "accelerator": spec["accelerator"],
                "goose_sdl3_checks": 77, "dual_backend_episodes": 42}
    if "bundle_dataset" in spec:
        expected["bundle_dataset"] = spec["bundle_dataset"]
        expected["native_standard_ci_run_id"] = spec["standard_ci_run_id"]
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError("Missing or stale Kaggle GPU parity evidence: " + key)
    archive_path = folder / "doc-kaggle-logs.tar.gz"
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = {entry.name for entry in archive.getmembers() if entry.isfile()}
            required = {
                "report/native-gpu-equivalence.log":
                    "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes",
                "goose/goose-sdl3/doc-goose-sdl3-summary.log":
                    "DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: 77 checks",
                "physical-vulkan.log": "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
                "nvidia-smi.log": "GPU",
            }
            if not required.keys() <= members:
                raise AssertionError("Incomplete raw physical-GPU evidence archive")
            for name, expected_text in required.items():
                stream = archive.extractfile(name)
                if stream is None:
                    raise AssertionError("Missing GPU evidence: " + name)
                observed = stream.read(262144).decode("utf-8", errors="replace")
                if expected_text not in observed:
                    raise AssertionError("GPU evidence disagrees with result: " + name)
    except (OSError, tarfile.TarError) as error:
        raise AssertionError("Missing or invalid raw physical-GPU evidence archive") from error
    return result

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", default="ci/kaggle/doc_kaggle_gpu.py")
    ap.add_argument("--output", default="kaggle-validation")
    ap.add_argument("--accelerator", default=DEFAULT_ACCELERATOR,
                    help="Kaggle-supported accelerator name; Kaggle validates availability")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.accelerator):
        ap.error("Invalid Kaggle accelerator name")
    spec = {
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "sha": os.environ.get("DOC_TARGET_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "accelerator": args.accelerator}
    if not re.fullmatch(r"[a-f0-9]{40}", spec["sha"]) or not re.fullmatch(r"[0-9]{1,20}", spec["run_id"]) or not re.fullmatch(r"[1-9][0-9]{0,3}", spec["attempt"]):
        raise ValueError("Missing exact trusted GitHub SHA/run provenance")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temp:
            prepare_kernel(Path(temp) / "kernel", Path(args.template), spec, "test-owner")
        print("DOC_KAGGLE_DRY_RUN_PASS: no credentials, GPU or quota consumed")
        return 0
    with tempfile.TemporaryDirectory(prefix="doc-kaggle-") as temp:
        env, owner = auth_environment(os.environ.get("KAGGLE_DOC_1", ""),
            Path(temp) / "config", os.environ.get("DOC_KAGGLE_USERNAME", ""))
        remaining = gpu_remaining_hours(kaggle(["quota", "--format", "json"], env))
        (out / "doc-kaggle-quota-preflight.json").write_text(json.dumps({
            "sha": spec["sha"], "remaining_gpu_hours": remaining,
            "quota_source": "Kaggle account API",
            "doc_gpu_run_cap": None, "doc_gpu_reserve_hours": None,
            "doc_gpu_session_limit": None}, indent=2))
        if remaining <= 0:
            print("DOC_KAGGLE_QUOTA_SKIP: Kaggle account reports no remaining GPU time")
            return 0
        # Native binary compilation is entirely on GitHub's CPU runner.
        # Upload a private SHA-verified input dataset BEFORE the GPU kernel is
        # launched; GPU time is only spent on real native device execution.
        from bundle import prepare_native_gpu_dataset
        bundle = prepare_native_gpu_dataset(
            spec["repo"],os.environ.get("GITHUB_TOKEN",""),spec,
            Path(os.environ.get("GITHUB_WORKSPACE",".")),
            Path(temp),env,owner)
        spec.update(bundle)
        (out/"doc-kaggle-bundle-provenance.json").write_text(
            json.dumps({"sha":spec["sha"],**bundle},indent=2)+"\n")
        name = prepare_kernel(Path(temp) / "kernel", Path(args.template), spec, owner)
        print(f"DOC_KAGGLE_DISPATCH: notebook={name} sha={spec['sha']} accelerator={args.accelerator} "
              f"dataset={bundle['bundle_dataset']} built-on-github-cpu={bundle['standard_ci_run_id']}")
        kaggle(["kernels", "push", "-p", str(Path(temp) / "kernel"),
                "--accelerator", args.accelerator], env, timeout=180)
        state = "UNKNOWN"
        while True:
            state = status_from_cli(kaggle(["kernels", "status", name], env))
            if state in ("COMPLETE", "FAILED"):
                break
            time.sleep(30)
        print("DOC_KAGGLE_REMOTE_STATUS: " + state)
        remote = out / "remote"
        remote.mkdir(exist_ok=True)
        try:
            kaggle(["kernels", "output", name, "-p", str(remote), "--force"], env, timeout=180)
        except (RuntimeError, subprocess.TimeoutExpired):
            print("DOC_KAGGLE_NOTE: remote evidence was not available")
        if state != "COMPLETE":
            raise RuntimeError("Kaggle physical-GPU notebook did not complete: " + state)
        actual = verify_result(remote, spec)
        print("DOC_KAGGLE_PHYSICAL_GPU_PARITY_PASS: {} paired episodes; {} native Goose checks".format(
            actual["dual_backend_episodes"], actual["goose_sdl3_checks"]))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, AssertionError, OSError, subprocess.TimeoutExpired) as error:
        print(f"DOC_KAGGLE_DISPATCH_FAILURE: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
