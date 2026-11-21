#!/usr/bin/env python3
"""Kaggle native DOC physical-GPU conformance, executed inside a PRIVATE kernel.

This Python file is a test controller, not a DOC runtime. Rust GPU execution
is owned by Rust wgpu; Goose GPU execution is owned by Goose SDL3 gfx.
Neither is dispatched through the other. No secrets are uploaded here.
"""
import csv
import hashlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import random
import statistics
import subprocess
import tarfile
import time

SPEC = __DOC_KAGGLE_RUN_SPEC__
GOOSE_SHA = "9412b80f52d833c4697cffdbbf1f4eeb5195cd41"
ROOT = Path("/kaggle/working")
ROOT.mkdir(parents=True, exist_ok=True)
LOGS = ROOT / "doc-kaggle-logs"
LOGS.mkdir(parents=True, exist_ok=True)
START = time.monotonic()
DEADLINE = START + SPEC["minutes"] * 60 - 45
METRICS = []
ENV = dict(os.environ)
ENV.update({
    "DOC_GPU_REQUIRE_HARDWARE": "1", "DOC_GPU_EXECUTION": "gpu",
    "GOOSE_GFX_HEADLESS": "1", "GOOSE_GFX_DEBUG": "0",
    "SDL_VIDEODRIVER": "x11", "SDL_GPU_DRIVER": "vulkan",
    "WGPU_BACKEND": "vulkan", "SDL_LOGGING": "*=warn",
    "DEBIAN_FRONTEND":"noninteractive", "APT_LISTCHANGES_FRONTEND":"none",
    "NEEDRESTART_MODE":"a"})

def run(name, argv, cwd=None, env=None, max_seconds=None, path=None):
    remaining = int(DEADLINE - time.monotonic())
    if remaining <= 1:
        raise RuntimeError("Exceeded Kaggle bounded GPU session")
    before = time.perf_counter()
    destination = LOGS / (path or (name + ".log"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(x) for x in argv]
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env or ENV,
            capture_output=True, text=True, errors="replace",
            timeout=min(max_seconds or remaining, remaining), check=False)
    except subprocess.TimeoutExpired as error:
        # Do not discard the diagnostic output for the interrupted step:
        # the first Kaggle T4 attempt was blocked on apt-get update and its
        # 260-second timeout otherwise left no actionable apt diagnostics.
        def output(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""
        diagnostic = (output(error.stdout) + "\n" + output(error.stderr))[-262144:]
        destination.write_text(diagnostic)
        seconds = round(time.perf_counter() - before, 4)
        METRICS.append({"step": name, "wall_seconds": seconds,
                        "exit_code": "timeout"})
        raise RuntimeError("Kaggle bootstrap " + name +
                           " timed out after " + str(round(seconds)) + "s") from error
    seconds = round(time.perf_counter() - before, 4)
    destination.write_text((proc.stdout + "\n" + proc.stderr)[-262144:])
    METRICS.append({"step": name, "wall_seconds": seconds, "exit_code": proc.returncode})
    if proc.returncode:
        raise RuntimeError(name + " failed: " + (proc.stdout + proc.stderr)[-1200:])
    return proc.stdout

def load_verified_native_bundle():
    """Unpack independent GPU binaries compiled by successful GitHub CPU CI."""
    dataset = SPEC.get("bundle_dataset", "")
    expected_hash = SPEC.get("bundle_sha256", "")
    if not re.fullmatch(r"[a-z0-9_-]+/doc-gpu-[0-9]+-[0-9]+-bundle", dataset):
        raise RuntimeError("DOC GPU session has no trusted private binary dataset")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise RuntimeError("DOC GPU binary dataset missing pinned SHA256")
    slug = dataset.split("/")[1]
    bundle = Path("/kaggle/input") / slug / "doc-gpu-bundle.tar.gz"
    if not bundle.is_file() or bundle.stat().st_size > 100_000_000:
        raise RuntimeError("INFRA_BLOCKED: precompiled native GPU dataset not mounted")
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError("DOC GPU artifact integrity check failed")
    with tarfile.open(bundle, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 50:
            raise RuntimeError("Unexpected DOC GPU bundle archive contents")
        for entry in members:
            path=Path(entry.name)
            if entry.name.startswith("/") or ".." in path.parts or \
                    not entry.isfile() or entry.issym() or entry.islnk():
                raise RuntimeError("Unsafe DOC GPU artifact bundle entry")
        archive.extractall(path=ROOT, filter="data")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    if manifest.get("sha") != SPEC["sha"] or \
       str(manifest.get("standard_ci_run_id")) != str(SPEC["standard_ci_run_id"]):
        raise RuntimeError("DOC GPU artifact source SHA/build mismatch")
    for path, digest in manifest.get("files",{}).items():
        destination = ROOT / path
        if not destination.is_file() or \
           hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError("DOC native GPU bundle file hash mismatch: " + path)
    for name in ("webgpu_bool","webgpu_integer_eq","doc-goose-sdl3",
                 "vulkaninfo","Xvfb","xvfb-run","xauth"):
        path=ROOT/"bin"/name
        if not path.is_file():
            raise RuntimeError("Missing preverified GPU binary: " + name)
        path.chmod(0o755)
    ENV["PATH"]=str(ROOT/"bin")+os.pathsep+ENV.get("PATH","")
    ENV["LD_LIBRARY_PATH"]=str(ROOT/"lib")+os.pathsep+ENV.get("LD_LIBRARY_PATH","")
    print("DOC_KAGGLE_CPU_COMPILED_BUNDLE_PASS: sha="+SPEC["sha"]+
          " standard_ci_run="+str(SPEC["standard_ci_run_id"]))
    return (ROOT/"DOC",ROOT/"bin/doc-goose-sdl3",
            ROOT/"bin/webgpu_integer_eq",ROOT/"bin/webgpu_bool")

def preflight_hardware():
    # A CUDA-visible NVIDIA device is not enough: SDL3 and wgpu both require
    # a *physical* Vulkan ICD. Do not use llvmpipe or silently fall back.
    output=run("nvidia-smi",["nvidia-smi","-L"],max_seconds=15)
    if "GPU" not in output:
        raise RuntimeError("INFRA_BLOCKED: Kaggle did not attach NVIDIA GPU")
    roots=("/usr/share/vulkan/icd.d","/etc/vulkan/icd.d",
           "/usr/local/share/vulkan/icd.d")
    drivers=sorted(path for root in roots
                   for path in Path(root).glob("*nvidia*.json"))
    if not drivers:
        # NVIDIA's native Vulkan ICD normally loads libGLX_nvidia.so.0.
        # Some CUDA images include the driver library but omit its JSON
        # registration. Add a local registration only if the shared object
        # actually exists; vulkaninfo must then confirm hardware execution.
        libraries=sorted(path for root in (
                "/usr/lib/x86_64-linux-gnu","/usr/local/nvidia/lib64",
                "/usr/lib/nvidia","/usr/local/cuda/compat")
            for path in Path(root).glob("libGLX_nvidia.so*") if path.is_file())
        if libraries:
            icd=ROOT/"doc-kaggle-nvidia-icd.json"
            icd.write_text(json.dumps({
                "file_format_version":"1.0.0",
                "ICD":{"library_path":str(libraries[0]),
                       "api_version":"1.3.0"}}))
            drivers=[icd]
    if not drivers:
        raise RuntimeError(
            "INFRA_BLOCKED: Kaggle attached CUDA hardware but no NVIDIA Vulkan "
            "driver ICD/library. No APT retries will consume GPU quota.")
    ENV["VK_DRIVER_FILES"]=":".join(map(str,drivers))
    ENV["VK_ICD_FILENAMES"]=ENV["VK_DRIVER_FILES"]
    info=run("physical-vulkan",["vulkaninfo","--summary"],max_seconds=35)
    if not re.search(r"PHYSICAL_DEVICE_TYPE_(?:DISCRETE|INTEGRATED)_GPU",info):
        raise RuntimeError("INFRA_BLOCKED: NVIDIA Vulkan physical GPU not exposed")
    print("DOC_KAGGLE_PHYSICAL_VULKAN_FOUND")

def test_physical_gpu(repo, goose_gpu, rust_signed, rust_bool):
    goose_logs = LOGS / "goose"
    rust_logs = LOGS / "rust"
    goose_logs.mkdir(exist_ok=True)
    rust_logs.mkdir(exist_ok=True)
    run("goose-native-sdl3-oracle", [
        "xvfb-run", "-a", "python3",
        "runtime-goose/check-doc-sdl3-gpu.py", goose_gpu,
        goose_logs / "goose-sdl3"], cwd=repo, max_seconds=500)
    text = (goose_logs / "goose-sdl3/doc-goose-sdl3-summary.log").read_text()
    if "DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: 77 checks" not in text:
        raise RuntimeError("Goose SDL3 CPU/GPU differential oracle failed")
    operations = {"eq": [], "lt": ["--lt"], "le": ["--le"]}
    for mode, flags in operations.items():
        for lanes in (1, 63, 64, 65, 129, 257, 1024):
            env = {**ENV, "DOC_GPU_LANES": str(lanes)}
            run(f"rust-{mode}-{lanes}", [rust_signed, *flags], cwd=repo,
                env=env, max_seconds=80, path=f"rust/rust-{mode}-{lanes}.log")
    run("rust-staged-reduction", [rust_bool, "--staged-repair"], cwd=repo,
        env={**ENV, "DOC_GPU_LANES": "257", "DOC_GPU_REDUCTION": "1"}, max_seconds=90)
    run("independent-doc-gpu-parity", ["python3",
        "runtime-goose/check-dual-gpu-parity.py",
        rust_logs, goose_logs, LOGS / "report"], cwd=repo, max_seconds=50)
    report = (LOGS / "report/native-gpu-equivalence.log").read_text()
    if "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes" not in report:
        raise RuntimeError("Rust wgpu versus Goose SDL3 GPU result parity mismatch")
    return 77, 42

def nearest_rank_p95(values):
    """95th percentile (nearest-rank) of nonempty measured samples."""
    if not values:
        raise ValueError("p95 requires at least one sample")
    ordered = sorted(values)
    return ordered[(95 * len(ordered) + 99) // 100 - 1]

def benchmark_hardware_gpu(repo, goose_gpu, rust_signed):
    """Matched subprocess GPU timings; NOT isolated kernel-time comparisons."""
    if DEADLINE - time.monotonic() < 240:
        print("DOC_KAGGLE_GPU_BENCHMARK_SKIPPED: session reserve <240s")
        return {"status": "skipped_time_budget", "samples": 0}
    source_results = LOGS / "report/native-gpu-equivalence.csv"
    with source_results.open(newline="") as handle:
        reference = {
            (row["operation"], int(row["epoch"])): int(row["equal_or_true_count"])
            for row in csv.DictReader(handle) if int(row["lanes"]) == 1024
        }
    if len(reference) != 6:
        raise RuntimeError("Missing six oracle-verified hardware reference counts")
    cases = {
        "eq": ("runtime-rust/examples/integer_equality.doc", []),
        "lt": ("runtime-rust/examples/integer_ordering.doc", ["--lt"]),
        "le": ("runtime-rust/examples/integer_ordering.doc", ["--le"]),
    }
    rust_pattern = re.compile(
        r"^DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=([01]) lanes=1024 equals=(\d+)$",
        re.M)
    goose_pattern = re.compile(
        r"^DOC_GOOSE_SDL3_GPU_PASS: op=(eq|lt|le) epoch=([01]) lanes=1024 "
        r"count=(\d+) backend=vulkan$", re.M)
    def execute(mode, runtime, repetition):
        source, flags = cases[mode]
        if runtime == "rust":
            cmd = [rust_signed, *flags]
            env = {**ENV, "DOC_GPU_LANES": "1024"}
        else:
            cmd = ["xvfb-run", "-a", goose_gpu, source, mode, "1024"]
            env = ENV
        output = run("gpu-bench-{}-{}-{}".format(mode,runtime,repetition),
                     cmd, cwd=repo, env=env, max_seconds=60,
                     path="benchmark/{}-{}-{}.log".format(mode,runtime,repetition))
        if runtime == "rust":
            observed = {int(epoch):int(count)
                        for epoch,count in rust_pattern.findall(output)}
        else:
            observed = {int(epoch):int(count)
                        for op,epoch,count in goose_pattern.findall(output)
                        if op == mode}
        if observed != {epoch:reference[(mode,epoch)] for epoch in (0,1)}:
            raise RuntimeError("Hardware benchmark returned wrong DOC source values")
        return METRICS[-1]["wall_seconds"] * 1000
    for mode in cases:
        for runtime in ("rust","goose"):
            for i in range(2):
                execute(mode,runtime,"warmup"+str(i))
    samples=[]
    order=[(mode,runtime,index) for mode in cases
           for runtime in ("rust","goose") for index in range(9)]
    random.Random(0xD0C).shuffle(order)
    for mode,runtime,index in order:
        if DEADLINE - time.monotonic() < 90:
            print("DOC_KAGGLE_GPU_BENCHMARK_TRUNCATED: deadline reserve")
            return {"status":"skipped_time_budget","samples":len(samples)}
        elapsed=execute(mode,runtime,index)
        samples.append({"mode":mode,"runtime":runtime,"sample":index,
                        "end_to_end_cli_ms":round(elapsed,4)})
    output=LOGS/"hardware-gpu-benchmark.csv"
    with output.open("w",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    results={}
    for mode in cases:
        for runtime in ("rust","goose"):
            values=sorted(v["end_to_end_cli_ms"] for v in samples
                          if v["mode"]==mode and v["runtime"]==runtime)
            results[mode+"/"+runtime]={
                "count":len(values),
                "median_ms":round(statistics.median(values),4),
                "p95_ms":nearest_rank_p95(values),
                "max_ms":values[-1],
            }
    result={
        "status":"pass", "samples":len(samples), "seed":0xD0C,
        "method":"9 randomized-interleaved CLI process samples per runtime and "
                 "operator; 2 warmups each; includes device initialization, "
                 "pipeline creation, upload, dispatch, readback and subprocess "
                 "startup; Xvfb on Goose, no kernel-only speedup claims",
        "reference":"report/native-gpu-equivalence.csv",
        "results":results,
    }
    (LOGS/"hardware-gpu-benchmark-summary.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("DOC_KAGGLE_HARDWARE_BENCHMARK_PASS:",len(samples),"raw matched samples")
    return result

def save(summary):
    (ROOT / "doc-kaggle-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with tarfile.open(ROOT / "doc-kaggle-logs.tar.gz", "w:gz") as archive:
        for entry in LOGS.rglob("*"):
            if entry.is_file():
                archive.add(entry, arcname=str(entry.relative_to(LOGS)))

def main():
    if not re.fullmatch(r"[a-f0-9]{40}", SPEC["sha"]):
        raise ValueError("Invalid pinned DOC source SHA")
    summary = {
        "sha": SPEC["sha"], "run_id": SPEC["run_id"],
        "accelerator": SPEC["accelerator"], "hardware": False,
        "backend": "unverified", "result": "failed",
        "goose_sdl3_checks": 0, "dual_backend_episodes": 0,
        "max_gpu_minutes": SPEC["minutes"],
        "native_standard_ci_run_id": SPEC.get("standard_ci_run_id"),
        "bundle_dataset": SPEC.get("bundle_dataset"),
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        repo, goose, signed, boolean = load_verified_native_bundle()
        preflight_hardware()
        n_goose, n_dual = test_physical_gpu(repo, goose, signed, boolean)
        summary.update({
            "result": "pass", "hardware": True, "backend": "vulkan",
            "goose_sdl3_checks": n_goose, "dual_backend_episodes": n_dual})
        try:
            summary["hardware_benchmark"] = benchmark_hardware_gpu(repo, goose, signed)
        except Exception as benchmark_error:
            # Correct physical GPU parity remains a valid completed result,
            # even if optional timing evidence fails. Record the limitation.
            summary["hardware_benchmark"] = {
                "status":"failed", "error":str(benchmark_error)[-350:]}
        print(f"DOC_KAGGLE_NATIVE_PHYSICAL_GPU_PASS: {n_dual} paired GPU observations")
    except Exception as err:
        summary["failure"] = str(err)[-1300:]
        print("DOC_KAGGLE_PHYSICAL_GPU_FAILURE: " + type(err).__name__ + ": " + str(err))
        raise
    finally:
        summary["elapsed_seconds"] = round(time.monotonic() - START, 3)
        summary["steps"] = METRICS
        save(summary)

if __name__ == "__main__":
    main()
