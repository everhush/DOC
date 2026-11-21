#!/usr/bin/env python3
"""Kaggle native DOC physical-GPU conformance, executed inside a PRIVATE kernel.

This Python file is a test controller, not a DOC runtime. Rust GPU execution
is owned by Rust wgpu; Goose GPU execution is owned by Goose SDL3 gfx.
Neither is dispatched through the other. No secrets are uploaded here.
"""
import csv
import datetime as dt
import json
import os
from pathlib import Path
import re
import random
import statistics
import shutil
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
    "WGPU_BACKEND": "vulkan", "SDL_LOGGING": "*=warn"})

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

def preflight_hardware():
    # A CUDA-visible GPU is NOT proof of usable Vulkan/SDL3/wgpu acceleration.
    output = run("nvidia-smi", ["nvidia-smi", "-L"], max_seconds=20)
    if "GPU" not in output:
        raise RuntimeError("INFRA_BLOCKED: no NVIDIA GPU attached by Kaggle")
    def nvidia_icds():
        return sorted(path for root in (
                "/usr/share/vulkan/icd.d", "/etc/vulkan/icd.d",
                "/usr/local/share/vulkan/icd.d")
            for path in Path(root).glob("*nvidia*.json"))
    nvidia = nvidia_icds()
    if not nvidia:
        # Kaggle often exposes CUDA without a Vulkan ICD. Install only the
        # matching NVIDIA user-space GL/Vulkan ICD; do not replace its running
        # host kernel driver, install DKMS, or fall back to llvmpipe.
        version = run("nvidia-driver-version", [
            "nvidia-smi", "--query-gpu=driver_version",
            "--format=csv,noheader"], max_seconds=15).strip().splitlines()[0]
        match = re.fullmatch(r"(\d{3})\.\d+(?:\.\d+)*", version)
        if not match:
            raise RuntimeError("INFRA_BLOCKED: unrecognized NVIDIA kernel driver version")
        major = match.group(1)
        apt = ["apt-get"] if os.geteuid() == 0 else ["sudo", "-n", "apt-get"]
        try:
            run("install-matching-nvidia-vulkan-icd", [
                *apt, "install", "-y", "-qq", "--no-install-recommends",
                "libnvidia-gl-" + major], max_seconds=220)
        except Exception as err:
            raise RuntimeError(
                "INFRA_BLOCKED: matching NVIDIA Vulkan ICD unavailable in Kaggle APT") from err
        nvidia = nvidia_icds()
    if not nvidia:
        raise RuntimeError(
            "INFRA_BLOCKED: Kaggle exposed CUDA but not the matching NVIDIA Vulkan ICD; "
            "software llvmpipe is not acceptable hardware DOC parity")
    ENV["VK_DRIVER_FILES"] = ":".join(map(str, nvidia))
    ENV["VK_ICD_FILENAMES"] = ENV["VK_DRIVER_FILES"]
    info = run("physical-vulkan", ["vulkaninfo", "--summary"], max_seconds=45)
    if not re.search(r"PHYSICAL_DEVICE_TYPE_(?:DISCRETE|INTEGRATED)_GPU", info):
        raise RuntimeError("INFRA_BLOCKED: no physical Vulkan adapter for SDL3/wgpu")
    print("DOC_KAGGLE_PHYSICAL_VULKAN_FOUND")

def installed_packages(packages):
    # Kaggle notebook images include many development libraries already.
    # Avoid gratuitous apt-get update: its default Ubuntu mirror stalled
    # for 260 seconds in real hardware attempt 44950662134.
    missing = []
    for package in packages:
        completed = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            capture_output=True, text=True, errors="replace", timeout=8)
        if completed.returncode or completed.stdout.strip() != "install ok installed":
            missing.append(package)
    return missing

def install_dependencies():
    # Preflight GPU first to avoid spending minutes of quota apt-installing
    # non-GPU Kaggle containers. A CUDA-visible GPU does not yet prove Vulkan.
    output = run("nvidia-smi", ["nvidia-smi", "-L"], max_seconds=15)
    if "GPU" not in output:
        raise RuntimeError("INFRA_BLOCKED: Kaggle did not attach NVIDIA CUDA hardware")
    packages = [
        "cmake", "ninja-build", "pkg-config", "git", "curl", "ca-certificates",
        "build-essential", "libx11-dev", "libxext-dev", "libxrandr-dev",
        "libxinerama-dev", "libxcursor-dev", "libxi-dev",
        "libxkbcommon-dev", "libxss-dev", "libxfixes-dev",
        "libx11-xcb-dev", "libxtst-dev", "libxdamage-dev",
        "libxshmfence-dev", "libxrender-dev", "libasound2-dev",
        "xvfb", "xauth", "libvulkan-dev", "libvulkan1", "vulkan-tools"]
    missing = installed_packages(packages)
    (LOGS/"kaggle-packages-required.json").write_text(
        json.dumps({"requested":packages,"missing":missing},indent=2)+"\n")
    apt = ["apt-get"] if os.geteuid() == 0 else ["sudo", "-n", "apt-get"]
    options = [
        "-o", "Acquire::Retries=0",
        "-o", "Acquire::http::Timeout=12",
        "-o", "Acquire::https::Timeout=12",
        "-o", "Acquire::ForceIPv4=true",
        "-o", "Dpkg::Use-Pty=0"]
    if missing:
        # Use the image's existing APT metadata first. Update only when the
        # first install attempt fails and cap ALL attempted network work.
        def install():
            return run("apt-install-missing",[
                *apt,*options,"install","-y","-qq","--no-install-recommends",
                *missing],max_seconds=105)
        try:
            install()
        except (RuntimeError,subprocess.TimeoutExpired):
            try:
                run("apt-update-bounded",[*apt,*options,"update","-qq"],
                    max_seconds=50)
                install()
            except (RuntimeError,subprocess.TimeoutExpired) as error:
                raise RuntimeError(
                    "INFRA_BLOCKED: Kaggle APT bootstrap failed under bounded "
                    "network timeouts; see retained apt diagnostics") from error
        unresolved=installed_packages(missing)
        if unresolved:
            raise RuntimeError("INFRA_BLOCKED: missing native SDL3/Vulkan build dependencies: "+
                               ",".join(unresolved))
    else:
        print("DOC_KAGGLE_APT_CACHE_HIT: required build libraries already installed")
    if not shutil.which("cargo"):
        install = ROOT / "rustup-init.sh"
        run("rustup-fetch", ["curl", "-fsSL", "https://sh.rustup.rs", "-o", install], max_seconds=90)
        run("rustup-install", ["sh", install, "-y", "--profile", "minimal"], max_seconds=170)
        ENV["PATH"] = str(Path.home() / ".cargo/bin") + os.pathsep + ENV.get("PATH", "")
    preflight_hardware()

def checkout_exact(folder, url, sha, label):
    folder.mkdir(exist_ok=True, parents=True)
    run(label + "-init", ["git", "-C", folder, "init", "-q"], max_seconds=20)
    run(label + "-fetch", ["git", "-C", folder, "fetch", "--depth", "1", url, sha], max_seconds=125)
    run(label + "-checkout", ["git", "-C", folder, "checkout", "--detach", "-q", "FETCH_HEAD"], max_seconds=25)
    got = run(label + "-sha", ["git", "-C", folder, "rev-parse", "HEAD"], max_seconds=15).strip()
    if got != sha:
        raise RuntimeError("Repository SHA mismatch, refusing untrusted GPU result")

def build():
    repo = ROOT / "DOC"
    checkout_exact(repo, "https://github.com/" + SPEC["repo"] + ".git", SPEC["sha"], "doc")
    goose = ROOT / "goose-src"
    checkout_exact(goose, "https://github.com/aardappel/goose.git", GOOSE_SHA, "goose")
    builddir = ROOT / "goose-build"
    run("goose-cmake", ["cmake", "-S", goose, "-B", builddir,
        "-DCMAKE_BUILD_TYPE=Release", "-DGOOSE_BUILTIN_LIBS=gfx"], max_seconds=160)
    run("goose-compiler", ["cmake", "--build", builddir, "--parallel", "2"], max_seconds=750)
    compiler = builddir / "goose"
    goose_gpu = ROOT / "doc-goose-sdl3"
    run("goose-doc-check", [compiler, "check", "runtime-goose/doc_sdl3_gpu.goose"],
        cwd=repo, max_seconds=120)
    run("goose-doc-build", [compiler, "build", "runtime-goose/doc_sdl3_gpu.goose",
        "--offline", "-o", goose_gpu], cwd=repo, max_seconds=200)
    run("rust-wgpu-build", ["cargo", "build", "--release",
        "--manifest-path", "runtime-rust/Cargo.toml",
        "--features", "webgpu", "--examples"], cwd=repo, max_seconds=850)
    signed = repo / "runtime-rust/target/release/examples/webgpu_integer_eq"
    boolean = repo / "runtime-rust/target/release/examples/webgpu_bool"
    for exe in (goose_gpu, signed, boolean):
        if not exe.is_file():
            raise RuntimeError("Native DOC GPU binary missing: " + str(exe))
    return repo, goose_gpu, signed, boolean

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
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        install_dependencies()
        repo, goose, signed, boolean = build()
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
