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
    # Prevent unrelated inherited runner credentials from shadowing the
    # secret the user explicitly selected for this dispatch.
    for credential in ("KAGGLE_DOC_1", "KAGGLE_API_TOKEN",
                       "KAGGLE_USERNAME", "KAGGLE_KEY"):
        env.pop(credential, None)
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
    elif re.fullmatch(r"[a-fA-F0-9]{32}", secret):
        # Kaggle legacy keys are 32 hexadecimal characters. In GitHub, a
        # user may save only the generated key rather than full kaggle.json.
        # Such a key is NOT a modern bearer token; pair it with the
        # already-configured DOC_KAGGLE_USERNAME, never echo either value.
        if not re.fullmatch(r"[a-z0-9_-]{2,60}", username):
            raise ValueError(
                "Bare Kaggle legacy API key requires DOC_KAGGLE_USERNAME")
        path = directory / "kaggle.json"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"username": username, "key": secret}, f)
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

def cli_failure_category(output):
    # Emit only fixed labels, never authenticated output or command arguments.
    match = re.search(r"(?im)\b(?:HTTP(?:Error| status)?[: ]+|status(?:_code| code)?[:= ]+)(401|403|404|429|500|502|503|504)\b", output)
    if match:
        code = int(match.group(1))
        return "http-" + str(code)
    if re.search(r"(?i)\b(?:ConnectionError|ConnectTimeout|ReadTimeout|TimeoutError)\b", output):
        return "network"
    return "unclassified"

def kaggle(command, env, timeout=60):
    operation = tuple(command[:2])
    labels = {("kernels", "push"): "kernels-push",
              ("kernels", "status"): "kernels-status",
              ("kernels", "output"): "kernels-output",
              ("quota", "--format"): "quota"}
    label = labels.get(operation, "other")
    # Never retry an ambiguous write: the remote service may have accepted it.
    attempts = 3 if label in ("kernels-status", "quota") else 1
    for attempt in range(attempts):
        try:
            p = subprocess.run(["kaggle", *command], env=env, capture_output=True,
                               text=True, timeout=timeout)
            if p.returncode == 0:
                return p.stdout
            category = cli_failure_category(p.stdout + "\n" + p.stderr)
        except subprocess.TimeoutExpired:
            category = "network"
        transient = category in ("network", "http-429", "http-500", "http-502", "http-503", "http-504")
        if not transient or attempt + 1 == attempts:
            raise RuntimeError("Kaggle CLI operation failed: " + label + " category=" + category) from None
        time.sleep(2 ** attempt)

def render_kernel_template(template, spec, *, placeholder="__DOC_KAGGLE_RUN_SPEC__"):
    """Render exactly one configuration marker and validate before dispatch."""
    if not re.fullmatch(r"__[A-Z0-9_]+__", placeholder):
        raise ValueError("Invalid notebook template marker")
    code = template.read_text(encoding="utf-8")
    if code.count(placeholder) != 1:
        raise ValueError("GPU test notebook template has changed")
    code = code.replace(placeholder, repr(spec))
    compile(code, str(template), "exec")
    return code

def prepare_kernel(folder, template, spec, username, *, placeholder="__DOC_KAGGLE_RUN_SPEC__"):
    slug = "doc-gpu-{}-{}".format(spec["run_id"], spec["attempt"])
    if not re.fullmatch(r"doc-gpu-[0-9]+-[0-9]+", slug):
        raise ValueError("Invalid unique notebook name")
    code = render_kernel_template(template, spec, placeholder=placeholder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "doc_kaggle_gpu.py").write_text(code, encoding="utf-8")
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
                "result": "pass", "backend": "webgpu", "hardware": True,
                "accelerator": spec["accelerator"],
                "rust_gpu_episodes": 42,
                "selected_rust_doc_gpu_cases": 62}
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
                "report/rust-gpu-conformance.log":
                    "DOC_RUST_NATIVE_PHYSICAL_GPU_PASS: 42 signed GPU episodes",
                "report/webgpu-device-admission.log":
                    "DOC_WEBGPU_HARDWARE_ADMISSION_PASS: 62 executed DOC source cases",
                "report/doc-selected-gpu-equivalence.log":
                    "DOC_SELECTED_RUST_DOC_GPU_PARITY_PASS: 62 real GPU-selected executions",
                "report/radar-auto-result.log":"DOC_RADAR_PHYSICAL_AUTO_PASS:",
                "report/radar-auto-physical.log":"DOC_AUTO_SUMMARY: gpu_kind=physical",
                "report/radar-auto-cpu.log":"DOC_AUTO_SUMMARY: gpu_kind=none",
                "report/radar-auto-fault.log":"DOC_GPU_INJECTED_STAGE_FAILURE: stage=0",
                "report/scene3d-physical.log":"DOC_SCENE_REPLAY_PASS: mode=offscreen actions=16 frames=17",
                "report/scene3d-cpu.log":"DOC_SCENE_REPLAY_PASS: mode=headless actions=16 frames=17",
                "report/scene3d-result.log":"DOC_SCENE3D_PHYSICAL_PASS:",
                "report/scene3d-pixel-proof.log":"DOC_SCENE_GPU_PROOF_PASS:",
                "report/scene3d-fault.log":"DOC_GPU_INJECTED_STAGE_FAILURE: stage=0",
                "report/dependency-family.log":"DOC_FAMILY_PROOF_PASS: device=physical gpu_lanes=512 episodes=5 rollback=true",
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
                if name == "report/webgpu-device-admission.log":
                    devices = re.findall(
                        r"(?m)^DOC_GPU_SELECTED_DEVICE: name=([^\n]+?) "
                        r"type=(DiscreteGpu|IntegratedGpu) vendor=([0-9]+) device=([0-9]+)$",
                        observed)
                    if len(devices)!=62 or "DOC_GPU_SOFTWARE_TEST_ONLY" in observed:
                        raise AssertionError(
                            "WebGPU evidence lacks 62 physical adapter admissions")

            # Require raw same-game compute provenance, not a summary alone.
            def read_log(name):
                return archive.extractfile(name).read(262144).decode("utf-8",errors="replace")
            raw=read_log("report/radar-auto-physical.log")
            cpu=read_log("report/radar-auto-cpu.log")
            fault=read_log("report/radar-auto-fault.log")
            radar=result.get("radar_auto_physical",{})
            devices=re.findall(r"(?m)^DOC_GPU_SELECTED_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu) vendor=\d+ device=\d+$",raw)
            physical_records=re.findall(r"(?m)^DOC_GPU_SELECTED_DEVICE: [^\n]*$",raw)
            mixed=re.findall(r"(?m)^DOC_AUTO_FRONTIER: cpu=(\d+) gpu=(\d+) gpu_kind=physical placement=typed-independent$",raw)
            dispatch=re.findall(r"(?m)^DOC_RUST_GPU_FRONTIER_DISPATCH: states=(\d+) workgroups=\d+ workgroup_size=\d+$",raw)
            stats=re.findall(r"(?m)^DOC_AUTO_SUMMARY: gpu_kind=physical cpu_nodes=(\d+) gpu_nodes=(\d+) cpu_parallel_frontiers=\d+ cpu_only_frontiers=\d+ gpu_frontiers=(\d+) mixed_frontiers=(\d+)$",raw)
            game_lines=lambda log:[x for x in log.splitlines() if x.startswith(("DOC_GAME_FRAME:","DOC_GAME_ENTITIES:","DOC_GAME_RADAR:"))]
            if not (len(physical_records)==len(devices)==1 and "DOC_GPU_SOFTWARE_TEST_ONLY" not in raw
                and radar.get("adapter")==devices[0][0] and radar.get("device_type")==devices[0][1]
                and len(mixed)==15 and all(int(c)>0 and int(g)>=128 for c,g in mixed)
                and len(dispatch)>=15 and sum(map(int,dispatch))==sum(int(g) for _,g in mixed)==radar.get("gpu_nodes")
                and isinstance(radar.get("cpu_nodes"),int) and radar["cpu_nodes"]>0
                and radar["cpu_nodes"]+radar["gpu_nodes"]==2940
                and radar.get("mixed_frontiers")==radar.get("gpu_frontiers")==15
                and stats==[(str(radar["cpu_nodes"]),str(radar["gpu_nodes"]),"15","15")]
                and radar.get("complete_replay_parity") is True and radar.get("failure_rollback") is True
                and raw.count("DOC_AUTO_GPU_SESSION_CREATED: gpu_kind=physical")==1
                and raw.count("DOC_AUTO_GPU_SESSION_REUSED: gpu_kind=physical")==14
                and game_lines(raw)==game_lines(cpu)
                and "DOC_GAME_FRAME: tick=13 player=(6,4) score=2 paused=false won=true coin=(6,4)" in game_lines(raw)
                and len([x for x in game_lines(raw) if x.startswith("DOC_GAME_FRAME:")])==16
                and fault.count("DOC_GAME_FRAME:")==1):
                raise AssertionError("Physical automatic Radar Chase raw evidence is incomplete or inconsistent")
            # Independently check raw physical 3D render AND actual mixed compute.
            sraw=read_log("report/scene3d-physical.log")
            scpu=read_log("report/scene3d-cpu.log")
            proof=read_log("report/scene3d-pixel-proof.log")
            sfault=read_log("report/scene3d-fault.log")
            sresult=result.get("scene3d_physical",{})
            sdev=re.findall(r"(?m)^DOC_SCENE_RENDER_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu)$",sraw)
            spix=re.findall(r"(?m)^DOC_SCENE_PIXELS: epoch=(\d+) distinct=(\d+) digest=([0-9a-f]{16})$",sraw)
            smix=re.findall(r"(?m)^DOC_AUTO_FRONTIER: cpu=(\d+) gpu=(\d+) gpu_kind=physical placement=typed-independent$",sraw)
            sdispatch=re.findall(r"(?m)^DOC_RUST_GPU_FRONTIER_DISPATCH: states=(\d+) workgroups=\d+ workgroup_size=\d+$",sraw)
            frames=lambda s:[x for x in s.splitlines() if x.startswith("DOC_SCENE_FRAME:")]
            if not (len(sdev)==1 and sresult.get("adapter")==sdev[0][0] and sresult.get("device_type")==sdev[0][1]
                and "DOC_SCENE_RENDER_SOFTWARE_TEST_ONLY" not in sraw and "DOC_GPU_SOFTWARE_TEST_ONLY" not in sraw
                and len(frames(sraw))==17 and frames(sraw)==frames(scpu)
                and any("next_won=true" in x for x in frames(sraw))
                and any("next_elevation=24" in x for x in frames(sraw))
                and len(spix)==17 and [int(x[0]) for x in spix]==list(range(17))
                and all(int(x[1])>=3 for x in spix) and len({x[2] for x in spix})>3
                and len(smix)==16 and all(int(c)>0 and int(g)>=128 for c,g in smix)
                and sum(map(int,sdispatch))==sum(int(g) for _,g in smix)
                and "DOC_GPU_GENERATED_PIPELINE_CREATED:" in sraw and "DOC_GPU_GENERATED_PIPELINE_REUSED:" in sraw
                and "DOC_SCENE_GENERATED_PIPELINE:" in sraw
                and re.findall(r"(?m)^DOC_SCENE_RENDER_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu)$",proof)==sdev
                and "DOC_SCENE_RENDER_SOFTWARE_TEST_ONLY" not in proof
                and re.search(r"(?m)^DOC_SCENE_GPU_PROOF_PASS: covered=[1-9][0-9]+ mutated=[1-9][0-9]+ lighting=3 depth_orders=2 jump=24 landed=0 repeats=16 rejected=2$",proof)
                and sfault.count("DOC_SCENE_FRAME:")==1 and "DOC_GPU_INJECTED_STAGE_FAILURE: stage=0" in sfault
                and sresult.get("frames")==17 and sresult.get("mixed_frontiers")==16
                and sresult.get("complete_replay_parity") is True):
                raise AssertionError("Physical 3D rendering/compute raw evidence incomplete")
            family=read_log("report/dependency-family.log")
            family_episodes=re.findall(r"(?m)^DOC_FAMILY_EPISODE: lanes=(\d+) gpu_lanes=(\d+)$",family)
            family_dispatch=re.findall(r"(?m)^DOC_RUST_GPU_FRONTIER_DISPATCH: states=(\d+) workgroups=\d+ workgroup_size=\d+$",family)
            fdev=re.findall(r"(?m)^DOC_GPU_SELECTED_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu) vendor=\d+ device=\d+$",family)
            if not (family_episodes==[("128","128"),("0","0"),("256","256"),("3","0"),("128","128")]
                and fdev==sdev and "DOC_GPU_SOFTWARE_TEST_ONLY" not in family
                and sum(map(int,family_dispatch))==512
                and "DOC_GPU_GENERATED_PIPELINE_REUSED:" in family):
                raise AssertionError("Physical runtime-sized dependency family evidence incomplete")
    except (OSError, tarfile.TarError) as error:
        raise AssertionError("Missing or invalid raw physical-GPU evidence archive") from error
    return result

def missing_private_mount(folder, spec):
    """Retry only a failed, same-SHA, same-dataset input attachment."""
    try:
        result=json.loads((folder/"doc-kaggle-summary.json").read_text())
    except (OSError,ValueError):
        return False
    return (result.get("sha")==spec["sha"]
        and result.get("run_id")==spec["run_id"]
        and result.get("bundle_dataset")==spec.get("bundle_dataset")
        and result.get("result")=="failed"
        and result.get("hardware") is False
        and result.get("failure")==
            "INFRA_BLOCKED: precompiled native GPU dataset not mounted")


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
            print("DOC_KAGGLE_INFRA_BLOCKED: Kaggle account reports no remaining GPU time")
            raise RuntimeError("INFRA_BLOCKED: Kaggle GPU quota unavailable; no physical test")
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
        kernel_folder=Path(temp)/"kernel"
        name=prepare_kernel(kernel_folder,Path(args.template),spec,owner)
        print(f"DOC_KAGGLE_DISPATCH: notebook={name} sha={spec['sha']} accelerator={args.accelerator} "
              f"dataset={bundle['bundle_dataset']} built-on-github-cpu={bundle['standard_ci_run_id']}")
        remote_root=out/"remote"
        remote_root.mkdir(exist_ok=True)
        for submission in (1,2):
            if submission==2:
                print("DOC_KAGGLE_PRIVATE_MOUNT_REATTACH: re-push identical notebook source and dataset")
            kaggle(["kernels","push","-p",str(kernel_folder),
                    "--accelerator",args.accelerator],env,timeout=180)
            state="UNKNOWN"
            while True:
                state=status_from_cli(kaggle(["kernels","status",name],env))
                if state in ("COMPLETE","FAILED"):
                    break
                time.sleep(30)
            print("DOC_KAGGLE_REMOTE_STATUS: "+state+" submission="+str(submission))
            remote=remote_root/("submission-"+str(submission))
            remote.mkdir()
            try:
                kaggle(["kernels","output",name,"-p",str(remote),"--force"],
                       env,timeout=180)
            except (RuntimeError,subprocess.TimeoutExpired):
                print("DOC_KAGGLE_NOTE: remote evidence unavailable submission="+str(submission))
            if state=="COMPLETE":
                actual=verify_result(remote,spec)
                print("DOC_KAGGLE_RUST_PHYSICAL_GPU_PASS: {} native signed GPU episodes and {} DOC source cases".format(
                    actual["rust_gpu_episodes"],actual["selected_rust_doc_gpu_cases"]))
                return 0
            if submission==1 and state=="FAILED" and missing_private_mount(remote,spec):
                # Kaggle may attach a newly added source only on the next
                # identical kernel version. No other failure can trigger
                # a GPU rerun or be mistaken for a GPU pass.
                continue
            raise RuntimeError("Kaggle physical-GPU notebook did not complete: "+state)
        raise RuntimeError("Kaggle private input mount missing after exact-source reattachment")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, AssertionError, OSError, subprocess.TimeoutExpired) as error:
        print(f"DOC_KAGGLE_DISPATCH_FAILURE: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
