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

# No DOC-specific weekly run cap: spend the actual account quota on distinct
# experiments. A small 7-day duplicate lookback is NOT a quota/run limit.
DUPLICATE_LOOKBACK_DAYS = 7
MAX_SESSION_MINUTES = 30
MIN_QUOTA_RESERVE_HOURS = 0.0
ACCELERATORS = {"NvidiaTeslaT4", "NvidiaL4"}
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

def duplicate_gpu_submission(log, sha, accelerator):
    """A prior remote submission for this exact source and GPU experiment.

    The source revision is the authoritative work identity: changing the DOC
    implementation/tests creates new useful work. Different accelerators are
    distinct hardware experiments. Historical logs without an accelerator
    field (older workflow revisions) match conservatively by source SHA.
    CPU-only failures and quota skips never become GPU submissions.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid DOC source SHA in duplicate check")
    if accelerator not in ACCELERATORS:
        raise ValueError("Unsupported Kaggle GPU experiment")
    for line in log.splitlines():
        if "DOC_KAGGLE_DISPATCH: notebook=" not in line:
            continue
        if not re.search(r"\bsha=" + re.escape(sha) + r"(?:\s|$)", line):
            continue
        match = re.search(r"\baccelerator=([A-Za-z0-9_-]+)(?:\s|$)", line)
        if match is None or match.group(1) == accelerator:
            return True
    return False

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

def gpu_session_attempted(log):
    """Conservatively count a Kaggle notebook push, not just GitHub's CPU preflight.

    A missing/truncated/unreadable historical log counts as an attempt.
    A completed preflight failure with no notebook-dispatch marker does not
    spend GPU time and cannot use up the GPU-session weekly allocation.
    """
    if re.search(r"(?m)^\d{4}-\d{2}-\d{2}T[^\n]*Z DOC_KAGGLE_DISPATCH: notebook=", log):
        return True
    if re.search(r"(?m)^\d{4}-\d{2}-\d{2}T[^\n]*Z DOC_KAGGLE_PHYSICAL_GPU_PARITY_PASS:", log):
        return True
    if re.search(r"(?m)^\d{4}-\d{2}-\d{2}T[^\n]*Z DOC_KAGGLE_QUOTA_SKIP:", log):
        return False
    if re.search(r"(?m)^\d{4}-\d{2}-\d{2}T[^\n]*Z DOC_KAGGLE_DISPATCH_FAILURE:", log):
        return False
    return True

def github_duplicate_work(repo, token, current_run, sha, accelerator):
    """Check only for an already-submitted identical GPU task, not run count.

    Skip preflight-only failures; check completed/failed submissions alike to
    avoid repeat billable hardware work. All pages in the recent seven-day
    lookback are examined; GitHub log/API ambiguity fails closed rather than
    silently authorizing duplicate work.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for safe GPU deduplication")
    base = f"https://api.github.com/repos/{repo}"
    headers = {"Authorization":"Bearer "+token,
               "Accept":"application/vnd.github+json",
               "X-GitHub-Api-Version":"2022-11-28"}
    def get_json(path):
        with urllib.request.urlopen(
                urllib.request.Request(base+path,headers=headers),
                timeout=30) as reply:
            return json.load(reply)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=DUPLICATE_LOOKBACK_DAYS)
    for page in range(1, 51):
        history = get_json(
            f"/actions/workflows/doc-kaggle-gpu.yml/runs?per_page=100&page={page}")
        runs = history.get("workflow_runs")
        if not isinstance(runs,list):
            raise ValueError("Cannot inspect Kaggle GPU run history")
        for run in runs:
            if str(run.get("id")) == str(current_run) or run.get("conclusion") == "skipped":
                continue
            created = run.get("created_at")
            if not created:
                raise ValueError("Unknown date for prior Kaggle GPU attempt")
            if dt.datetime.fromisoformat(created.replace("Z","+00:00")) < cutoff:
                continue
            details = get_json(f"/actions/runs/{run['id']}/jobs?per_page=100")
            jobs = details.get("jobs")
            if not isinstance(jobs,list) or len(jobs)>=100:
                raise ValueError("Incomplete Kaggle GPU job list")
            for job in jobs:
                if ("Kaggle Rust wgpu vs Goose SDL3 physical GPU" not in
                    job.get("name","") or job.get("conclusion")=="skipped"):
                    continue
                job_id=job.get("id")
                if not isinstance(job_id,int):
                    raise ValueError("Unidentified Kaggle GPU job")
                uri=f"{base}/actions/jobs/{job_id}/logs"
                with urllib.request.urlopen(
                        urllib.request.Request(uri,headers=headers),
                        timeout=30) as response:
                    log=response.read(12_000_001)
                if len(log)>12_000_000:
                    raise ValueError("Truncated Kaggle GPU job log")
                if duplicate_gpu_submission(log.decode("utf-8",errors="replace"),
                                            sha,accelerator):
                    return True
        if len(runs)<100:
            return False
    raise ValueError("Kaggle GPU job history too large to deduplicate safely")

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
                "accelerator": spec["accelerator"], "max_gpu_minutes": spec["minutes"],
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
    ap.add_argument("--accelerator", default="NvidiaTeslaT4", choices=sorted(ACCELERATORS))
    ap.add_argument("--minutes", default=30, type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.minutes < 10 or args.minutes > MAX_SESSION_MINUTES:
        ap.error("Session time must be 10-30 minutes")
    spec = {
        "repo": os.environ.get("GITHUB_REPOSITORY", ""),
        "sha": os.environ.get("DOC_TARGET_SHA", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "minutes": args.minutes, "accelerator": args.accelerator}
    if not re.fullmatch(r"[a-f0-9]{40}", spec["sha"]) or not re.fullmatch(r"[0-9]{1,20}", spec["run_id"]) or not re.fullmatch(r"[1-9][0-9]{0,3}", spec["attempt"]):
        raise ValueError("Missing exact trusted GitHub SHA/run provenance")
    if spec["attempt"] != "1" and not args.dry_run:
        # A GitHub rerun is not a free Kaggle retry: a prior notebook may
        # still be running and it could consume a second quota allocation.
        raise RuntimeError("Refusing Kaggle dispatch from a workflow rerun")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temp:
            prepare_kernel(Path(temp) / "kernel", Path(args.template), spec, "test-owner")
        print("DOC_KAGGLE_DRY_RUN_PASS: no credentials, GPU or quota consumed")
        return 0
    duplicate = github_duplicate_work(spec["repo"], os.environ.get("GITHUB_TOKEN", ""),
                                     spec["run_id"], spec["sha"], args.accelerator)
    if duplicate:
        print("DOC_KAGGLE_DUPLICATE_SKIP: identical source and GPU experiment already submitted")
        (out / "doc-kaggle-skipped.json").write_text(json.dumps({
            "sha": spec["sha"], "accelerator":args.accelerator,
            "reason":"identical-hardware-work-already-submitted"}))
        return 0
    with tempfile.TemporaryDirectory(prefix="doc-kaggle-") as temp:
        env, owner = auth_environment(os.environ.get("KAGGLE_DOC_1", ""),
            Path(temp) / "config", os.environ.get("DOC_KAGGLE_USERNAME", ""))
        remaining = gpu_remaining_hours(kaggle(["quota", "--format", "json"], env))
        required = MIN_QUOTA_RESERVE_HOURS + args.minutes / 60
        (out / "doc-kaggle-quota-preflight.json").write_text(json.dumps({
            "sha": spec["sha"], "remaining_gpu_hours": remaining,
            "required_hours": required, "weekly_submission_limit": None,
            "duplicate_lookback_days":DUPLICATE_LOOKBACK_DAYS,
            "duplicate_detected":False,"session_max_minutes":args.minutes}, indent=2))
        if remaining < required:
            print(f"DOC_KAGGLE_QUOTA_SKIP: remaining {remaining:.2f}h, needed {required:.2f}h")
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
        print(f"DOC_KAGGLE_DISPATCH: notebook={name} sha={spec['sha']} accelerator={args.accelerator} minutes={args.minutes} "
              f"dataset={bundle['bundle_dataset']} built-on-github-cpu={bundle['standard_ci_run_id']}")
        kaggle(["kernels", "push", "-p", str(Path(temp) / "kernel"),
                "--accelerator", args.accelerator, "--timeout", str(args.minutes * 60)], env, timeout=180)
        deadline = time.monotonic() + args.minutes * 60 + 1200
        state = "UNKNOWN"
        while time.monotonic() < deadline:
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
