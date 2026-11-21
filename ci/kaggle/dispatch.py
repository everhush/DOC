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
import sys
import tempfile
import time
import urllib.request

MAX_WEEKLY_RUNS = 2
MAX_SESSION_MINUTES = 30
MIN_QUOTA_RESERVE_HOURS = 2.0
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

def github_recent_attempts(data, current_run, now):
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not isinstance(runs, list) or len(runs) >= 100:
        raise ValueError("Incomplete workflow-run history: refusing to submit")
    since = now - dt.timedelta(days=7)
    count = 0
    for run in runs:
        if str(run.get("id")) == str(current_run):
            continue
        created = run.get("created_at")
        if not created:
            raise ValueError("Missing run timestamp")
        if dt.datetime.fromisoformat(created.replace("Z", "+00:00")) >= since:
            count += 1
    return count

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
    if not re.fullmatch(r"[a-z0-9_-]{2,60}", username):
        raise ValueError("Raw Kaggle API token requires repository variable DOC_KAGGLE_USERNAME")
    return env, username

def kaggle(command, env, timeout=60):
    p = subprocess.run(["kaggle", *command], env=env, capture_output=True,
                       text=True, timeout=timeout)
    if p.returncode:
        # Do not print authenticated process stdout/stderr, which may include
        # usernames, tokens or other credentials.
        raise RuntimeError("Kaggle CLI operation failed: " + command[0])
    return p.stdout

def github_attempts(repo, token, current_run):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository")
    if not token:
        raise ValueError("GITHUB_TOKEN is required for exact weekly dispatch accounting")
    uri = f"https://api.github.com/repos/{repo}/actions/workflows/doc-kaggle-gpu.yml/runs?per_page=100"
    req = urllib.request.Request(uri, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as reply:
        return github_recent_attempts(json.load(reply), current_run, dt.datetime.now(dt.timezone.utc))

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
        "title": "DOC independent native physical GPU parity " + spec["run_id"],
        "code_file": "doc_kaggle_gpu.py",
        "language": "python", "kernel_type": "script",
        "is_private": "true", "enable_gpu": "true", "enable_internet": "true",
        "machine_shape": spec["accelerator"],
        "dataset_sources": [], "competition_sources": [],
        "kernel_sources": [], "model_sources": []
    }
    (folder / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata["id"]

def verify_result(folder, spec):
    result = json.loads((folder / "doc-kaggle-summary.json").read_text())
    expected = {"sha": spec["sha"], "run_id": spec["run_id"],
                "result": "pass", "backend": "vulkan", "hardware": True,
                "goose_sdl3_checks": 77, "dual_backend_episodes": 42}
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError("Missing or stale Kaggle GPU parity evidence: " + key)
    if not (folder / "doc-kaggle-logs.tar.gz").is_file():
        raise AssertionError("Missing raw physical-GPU evidence archive")
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
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        with tempfile.TemporaryDirectory() as temp:
            prepare_kernel(Path(temp) / "kernel", Path(args.template), spec, "test-owner")
        print("DOC_KAGGLE_DRY_RUN_PASS: no credentials, GPU or quota consumed")
        return 0
    previous = github_attempts(spec["repo"], os.environ.get("GITHUB_TOKEN", ""), spec["run_id"])
    if previous >= MAX_WEEKLY_RUNS:
        print(f"DOC_KAGGLE_QUOTA_SKIP: maximum {MAX_WEEKLY_RUNS} attempts in rolling 7 days")
        (out / "doc-kaggle-skipped.json").write_text(json.dumps({
            "sha": spec["sha"], "reason": "weekly-doc-budget", "previous_attempts": previous}))
        return 0
    with tempfile.TemporaryDirectory(prefix="doc-kaggle-") as temp:
        env, owner = auth_environment(os.environ.get("KAGGLE_DOC_1", ""),
            Path(temp) / "config", os.environ.get("DOC_KAGGLE_USERNAME", ""))
        remaining = gpu_remaining_hours(kaggle(["quota", "--format", "json"], env))
        required = MIN_QUOTA_RESERVE_HOURS + args.minutes / 60
        (out / "doc-kaggle-quota-preflight.json").write_text(json.dumps({
            "sha": spec["sha"], "remaining_gpu_hours": remaining,
            "required_hours": required, "rolling_week_prior_runs": previous,
            "weekly_max_runs": MAX_WEEKLY_RUNS, "session_max_minutes": args.minutes}, indent=2))
        if remaining < required:
            print(f"DOC_KAGGLE_QUOTA_SKIP: remaining {remaining:.2f}h, needed {required:.2f}h")
            return 0
        name = prepare_kernel(Path(temp) / "kernel", Path(args.template), spec, owner)
        print(f"DOC_KAGGLE_DISPATCH: notebook={name} sha={spec['sha']} minutes={args.minutes}")
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
