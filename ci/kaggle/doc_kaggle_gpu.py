#!/usr/bin/env python3
"""Kaggle native DOC physical-GPU conformance, executed inside a PRIVATE kernel.

This Python file is a test controller, not a DOC runtime. Rust GPU execution
is owned by Rust wgpu; Goose GPU execution is owned by Goose SDL3 gfx.
Neither is dispatched through the other. No secrets are uploaded here.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
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
    proc = subprocess.run([str(x) for x in argv], cwd=cwd,
        env=env or ENV, capture_output=True, text=True, errors="replace",
        timeout=min(max_seconds or remaining, remaining), check=False)
    seconds = round(time.perf_counter() - before, 4)
    destination = LOGS / (path or (name + ".log"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(proc.stdout + "\n" + proc.stderr)
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

def install_dependencies():
    apt = ["apt-get"] if os.geteuid() == 0 else ["sudo", "-n", "apt-get"]
    run("apt-update", [*apt, "update", "-qq"], max_seconds=260)
    packages = [
        "cmake", "ninja-build", "pkg-config", "git", "curl", "ca-certificates",
        "build-essential", "libx11-dev", "libxext-dev", "libxrandr-dev",
        "libxinerama-dev", "libxcursor-dev", "libxi-dev",
        "libxkbcommon-dev", "libxss-dev", "libxfixes-dev",
        "libx11-xcb-dev", "libxtst-dev", "libxdamage-dev",
        "libxshmfence-dev", "libxrender-dev", "libasound2-dev",
        "xvfb", "xauth", "libvulkan-dev", "libvulkan1", "vulkan-tools"]
    run("apt-graphics", [*apt, "install", "-y", "-qq", *packages], max_seconds=460)
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
