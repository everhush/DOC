#!/usr/bin/env python3
"""Kaggle native DOC physical-GPU conformance, executed inside a PRIVATE kernel.

This Python file is a test controller, not a DOC runtime. Only native Rust wgpu executes DOC GPU work. A Python test controller
verifies its independently authored CPU/DOC source oracle. Goose is deprecated;
its runtime and SDL3 dependencies are neither loaded nor dispatched.
No secrets are uploaded here.
"""
import csv
import hashlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import random
import statistics
import subprocess
import tarfile
import time

SPEC = __DOC_KAGGLE_RUN_SPEC__
ROOT = Path("/kaggle/working")
ROOT.mkdir(parents=True, exist_ok=True)
LOGS = ROOT / "doc-kaggle-logs"
LOGS.mkdir(parents=True, exist_ok=True)
START = time.monotonic()
METRICS = []
# The native Rust wgpu provider owns all graphics API and driver choice.
# No application-side native API selection, driver registrations, or tools.
ENV=dict(os.environ)
ENV.pop("DOC_GPU_ALLOW_SOFTWARE",None)
ENV.update({
    "DOC_GPU_REQUIRE_HARDWARE":"1", "DOC_GPU_EXECUTION":"gpu",
    "DEBIAN_FRONTEND":"noninteractive",
    "APT_LISTCHANGES_FRONTEND":"none",
    "NEEDRESTART_MODE":"a",
})

def run(name, argv, cwd=None, env=None, path=None):
    """Execute a native check without DOC-imposed session or per-step caps.

    Kaggle and the GitHub runner own their actual execution lifetimes. Native
    errors retain raw diagnostic logs; wall-clock data is still measured.
    """
    before = time.perf_counter()
    destination = LOGS / (path or (name + ".log"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(x) for x in argv]
    proc = subprocess.run(argv, cwd=cwd, env=env or ENV,
                          capture_output=True, text=True, errors="replace",
                          check=False)
    seconds = round(time.perf_counter() - before, 4)
    destination.write_text((proc.stdout + "\n" + proc.stderr)[-262144:])
    METRICS.append({"step": name, "wall_seconds": seconds, "exit_code": proc.returncode})
    if proc.returncode:
        raise RuntimeError(name + " failed: " + (proc.stdout + proc.stderr)[-1200:])
    return proc.stdout

def load_verified_native_bundle():
    """Unpack SHA-pinned Rust GPU binaries from successful Rust-only CI."""
    dataset = SPEC.get("bundle_dataset", "")
    expected_hash = SPEC.get("bundle_sha256", "")
    if not re.fullmatch(r"[a-z0-9_-]+/doc-gpu-[0-9]+-[0-9]+-bundle", dataset):
        raise RuntimeError("DOC GPU session has no trusted private binary dataset")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise RuntimeError("DOC GPU binary dataset missing pinned SHA256")
    slug=dataset.split("/")[1]
    root=Path("/kaggle/input")
    # Kaggle may place attached sources under multiple root layouts.
    # Mount candidates are accepted ONLY if their complete archive
    # SHA-256 equals the exact successful GitHub CI artifact provenance.
    candidates=(sorted(p for p in root.rglob("doc-gpu-bundle.bin")
                       if p.is_file() and not p.is_symlink())
                if root.is_dir() else [])
    print("DOC_KAGGLE_INPUT_MOUNT_SCAN: root="+str(root.is_dir())+
          " candidates="+str(len(candidates))+
          " slug_visible="+str(any(slug in p.parts for p in candidates)),
          flush=True)
    if not candidates:
        raise RuntimeError("INFRA_BLOCKED: precompiled native GPU dataset not mounted")
    bundle=None
    for candidate in candidates:
        if candidate.stat().st_size>100_000_000:
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest()==expected_hash:
            bundle=candidate
            break
    if bundle is None:
        raise RuntimeError("DOC GPU artifact integrity check failed")
    print("DOC_KAGGLE_PRIVATE_BUNDLE_MOUNT_SHA_PASS",flush=True)
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
    for name in ("webgpu_bool","webgpu_integer_eq","doc-rust-gpu","doc-game","doc-scene3d","scene3d_gpu_proof","dependency_family_proof"):
        path=ROOT/"bin"/name
        if not path.is_file():
            raise RuntimeError("Missing preverified GPU binary: " + name)
        path.chmod(0o755)
    ENV["PATH"]=str(ROOT/"bin")+os.pathsep+ENV.get("PATH","")
    print("DOC_KAGGLE_CPU_COMPILED_BUNDLE_PASS: sha="+SPEC["sha"]+
          " standard_ci_run="+str(SPEC["standard_ci_run_id"]))
    return (ROOT/"DOC",ROOT/"bin/webgpu_integer_eq",ROOT/"bin/webgpu_bool")

def experiment_provision_host_graphics():
    """One isolated Kaggle notebook HOST graphics-library trial, never DOC API selection.

    Logs host hardware and NVIDIA package provenance; installs the matching
    userspace package only when Kaggle's actual driver branch is known.
    Physical acceptance still depends on DOC wgpu dispatch and typed readback.
    """
    report={"schema":1,"scope":"ephemeral_kaggle_host",
            "status":"INFRA_BLOCKED","driver_branch":None,"package":None,
            "diagnostics":{}}
    destination=LOGS/"kaggle-host-graphics-experiment.json"
    def probe(label,argv,timeout=120):
        before=time.perf_counter()
        try:
            p=subprocess.run(argv,capture_output=True,text=True,check=False,
                             timeout=timeout,env=ENV)
            result={"exit_code":p.returncode,
                    "seconds":round(time.perf_counter()-before,3),
                    "stdout_tail":p.stdout[-1000:],"stderr_tail":p.stderr[-1000:]}
        except (OSError,subprocess.TimeoutExpired) as error:
            result={"exit_code":-1,"error":(type(error).__name__+": "+str(error))[:350]}
        report["diagnostics"][label]=result
        return result
    try:
        report["euid"]=os.geteuid()
        report["nvidia_nodes"]=sorted(p.name for p in Path("/dev").glob("nvidia*"))[:12]
        smi=probe("gpu_driver",["nvidia-smi","--query-gpu=name,driver_version",
                                "--format=csv,noheader"],timeout=20)
        if smi["exit_code"]!=0:
            raise RuntimeError("INFRA_BLOCKED: Kaggle session has no NVIDIA GPU")
        branches=re.findall(r"\b(\d{3})\.\d+(?:\.\d+)?\b",smi["stdout_tail"])
        if not branches or len(set(branches))!=1:
            raise RuntimeError("INFRA_BLOCKED: missing or conflicting NVIDIA driver branch")
        report["driver_branch"]=branches[0]
        package="libnvidia-gl-"+branches[0]
        report["package"]=package
        probe("graphics_package_before",["dpkg-query","-W",package,"libvulkan1"],timeout=20)
        probe("nvidia_libraries_before",["ldconfig","-p"],timeout=20)
        if os.geteuid()!=0:
            raise RuntimeError("INFRA_BLOCKED: no root for Kaggle host graphics setup")
        update=probe("apt_update",["apt-get","update","-qq"],timeout=180)
        if update["exit_code"]!=0:
            raise RuntimeError("INFRA_BLOCKED: Kaggle APT repository unavailable")
        probe("matching_package_candidate",["apt-cache","policy",package],timeout=20)
        install=probe("host_graphics_install",
            ["apt-get","install","-y","--no-install-recommends",
             package,"libvulkan1"],timeout=360)
        if install["exit_code"]!=0:
            raise RuntimeError("INFRA_BLOCKED: matching NVIDIA graphics package not installable")
        after=probe("graphics_package_after",["dpkg-query","-W",package,"libvulkan1"],timeout=20)
        if after["exit_code"]!=0:
            raise RuntimeError("INFRA_BLOCKED: host graphics package still missing")
        report["status"]="HOST_GRAPHICS_INSTALLED"
    except Exception as error:
        report["error"]=str(error)[:500]
        print("DOC_KAGGLE_HOST_GRAPHICS_BLOCKED: "+str(error)[:500],flush=True)
    finally:
        destination.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print("DOC_KAGGLE_HOST_GRAPHICS_STATUS: "+report["status"]+
              " package="+str(report["package"]),flush=True)
    if report["status"]!="HOST_GRAPHICS_INSTALLED":
        raise RuntimeError(report.get("error","INFRA_BLOCKED: Kaggle host setup failed"))

def preflight_hardware():
    """The *selected WebGPU adapter*, not driver utilities, is the gate.

    A visible accelerator or successful setup alone proves nothing. Every
    actual DOC GPU invocation must separately report physical adapter class,
    execute shader work, and match independent same-source CPU observations.
    """
    print("DOC_WEBGPU_HARDWARE_PROBE_REQUIRED: actual compute and typed readback",
          flush=True)

def selected_physical_webgpu_adapter(log):
    """Require exactly one actual native Rust wgpu selected-device record.

    Never infer physical GPU from a vendor ID, platform driver name, API,
    CUDA installation, or GPU allocation request. A reported CPU adapter,
    conflicting device admission or explicit software-test marker rejects.
    """
    if "DOC_GPU_SOFTWARE_TEST_ONLY" in log:
        raise RuntimeError("Software WebGPU adapter is not physical hardware")
    # Count *every* selected-device declaration, not only eligible classes.
    # Otherwise a CPU admission followed by a physical-looking record could
    # accidentally satisfy the evidence gate.
    records=re.findall(r"(?m)^DOC_GPU_SELECTED_DEVICE: [^\n]*$",log)
    if len(records)!=1:
        raise RuntimeError("Expected exactly one Rust WebGPU selected-device record")
    devices=re.fullmatch(
        r"DOC_GPU_SELECTED_DEVICE: name=(.+?) "
        r"type=(DiscreteGpu|IntegratedGpu) vendor=([0-9]+) device=([0-9]+)",
        records[0])
    if devices is None:
        raise RuntimeError("Selected Rust WebGPU adapter is not a physical GPU")
    return devices.groups()

def test_physical_gpu(repo, rust_signed, rust_bool):
    """Run actual signed Rust wgpu kernels, including multi-workgroup loads.

    Native Rust owns all GPU computation. This controller checks real dispatch
    markers and retains the raw stdout/stderr, never substitutes CPU work.
    """
    rust_logs=LOGS/"rust"
    rust_logs.mkdir(exist_ok=True)
    operations={"eq":[],"lt":["--lt"],"le":["--le"]}
    episodes=0
    for mode,flags in operations.items():
        for lanes in (1,63,64,65,129,257,1024):
            output=run("rust-{}-{}".format(mode,lanes),
                [rust_signed,*flags],cwd=repo,
                env={**ENV,"DOC_GPU_LANES":str(lanes)},
                path="rust/rust-{}-{}.log".format(mode,lanes))
            if output.count("DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=")!=2:
                raise RuntimeError("Rust native signed compute did not dispatch two epochs")
            episodes+=2
    output=run("rust-staged-reduction",
        [rust_bool,"--staged-repair"],cwd=repo,
        env={**ENV,"DOC_GPU_LANES":"257","DOC_GPU_REDUCTION":"1"},
        path="rust/rust-staged-reduction.log")
    if output.count("DOC_WEBGPU_REDUCTION_PASS:")<2:
        raise RuntimeError("Native Rust GPU reduction did not execute two stages")
    report=LOGS/"report/rust-gpu-conformance.log"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(
        "DOC_RUST_NATIVE_PHYSICAL_GPU_PASS: {} signed GPU episodes\n".format(episodes))
    if episodes!=42:
        raise RuntimeError("Rust hardware signed compute case count changed")
    return episodes

def check_selected_rust_doc_gpu(repo, doc):
    """Require physically selected GPU execution of directly authored DOC DAGs.

    The same native binary's CPU evaluator and an independent Python Boolean
    oracle must agree with every stage's GPU-published values. This does not
    certify host effects or unsupported DOC operations inside a WGSL shader;
    only admitted selected-DOC source computations are counted.
    """
    cases = []
    for source in ("boolean_conditional.doc", "boolean_staged.doc"):
        for a in (False, True):
            for b in (False, True):
                chosen = (a == b or not a)
                expected = {"chosen": str(chosen).lower()}
                if source == "boolean_staged.doc":
                    expected["verified"] = str(chosen == b).lower()
                cases.append((
                    source,
                    ["a="+str(a).lower(), "b="+str(b).lower()],
                    expected))
    for gate in (False, True):
        for a in (-2147483648, -1, 0, 1, 2147483647):
            for b in (-2147483648, -1, 0, 1, 2147483647):
                cases.append((
                    "mixed_comparison.doc",
                    ["gate="+str(gate).lower(), "a="+str(a), "b="+str(b)],
                    {"chosen": str(a == b if gate else a < b).lower()}))
    cases.extend([
        ("gpu_arithmetic_chain.doc", [],
         {"sum":"11","twice":"22","diff":"18","chosen":"true"}),
        ("typed_arithmetic.doc", [],
         {"sum":"5","delta":"-1","product":"-5","equal":"false",
          "chosen":"-5","confirm":"false"}),
        ("gpu_nested_arithmetic.doc", [],
         {"sum":"8","chosen":"true","branched":"4","ok":"false"}),
        ("parallel_frontier.doc", [],
         {"p000":"false","p127":"false","folded":"true"}),
    ])
    if len(cases) != 62:
        raise AssertionError("Incorrect GPU DAG and arithmetic source matrix")
    detail=[]
    device_lines=[]
    for index,(source,assignments,expected) in enumerate(cases):
        fixture="runtime-rust/examples/"+source
        prefix="selected-rust-gpu/case-{:03d}".format(index)
        actual=run("selected-rust-gpu-{:03d}".format(index),
            [doc,fixture,"--backend=gpu",*assignments],cwd=repo,
            path=prefix+"-gpu.log")
        reference=run("selected-rust-cpu-{:03d}".format(index),
            [doc,fixture,"--backend=cpu",*assignments],cwd=repo,
            path=prefix+"-cpu.log")
        if actual != reference:
            raise RuntimeError(
                "Selected real GPU differs from same-source CPU evaluator: "+str(index))
        fields=dict(line.split(": ",1) for line in actual.splitlines()
                    if ": " in line)
        if any(fields.get(name) != value for name,value in expected.items()):
            raise RuntimeError("Independent DOC GPU Boolean oracle mismatch: "+str(index))
        gpu_log=(LOGS/(prefix+"-gpu.log")).read_text()
        physical=selected_physical_webgpu_adapter(gpu_log)
        device_lines.append(
            "DOC_GPU_SELECTED_DEVICE: name={} type={} vendor={} device={}".format(
                *physical))
        if gpu_log.count("DOC_GPU_GENERATED_SESSION_CREATED: cache_capacity=32")!=1:
            raise RuntimeError("Missing generated WGSL session")
        if "DOC_GPU_GENERATED_PIPELINE_CREATED:" not in gpu_log:
            raise RuntimeError("No DOC-derived compute shader was compiled")
        if source=="parallel_frontier.doc":
            # The fixture contains 128 independent derives followed by folded.
            created=re.findall(r"(?m)^DOC_GPU_GENERATED_PIPELINE_CREATED: lanes=(\d+) source_bytes=\d+$",gpu_log)
            dispatched=re.findall(r"(?m)^DOC_RUST_GPU_FRONTIER_DISPATCH: states=(\d+) workgroups=\d+ workgroup_size=\d+$",gpu_log)
            if created!=["128","1"] or dispatched!=["128","1"]:
                raise RuntimeError("Expected specialized independent and dependent GPU pipelines")
        if "DOC_GPU_SOFTWARE_TEST_ONLY" in gpu_log:
            raise RuntimeError("Software WebGPU adapter cannot certify physical GPU")
        if source=="parallel_frontier.doc" and (
            not re.search(
                r"DOC_RUST_GPU_FRONTIER_DISPATCH: states=128 "
                r"workgroups=([2-9]|[1-9][0-9]+) workgroup_size=[0-9]+",
                gpu_log)):
            raise RuntimeError("128 independent DOC states did not execute across GPU workgroups")
        detail.append("case={:03d} fixture={} args={} pass".format(
            index,source," ".join(assignments)))
    report=LOGS/"report/doc-selected-gpu-equivalence.log"
    report.parent.mkdir(parents=True,exist_ok=True)
    hardware=LOGS/"report/webgpu-device-admission.log"
    hardware.write_text(
        "DOC_WEBGPU_HARDWARE_ADMISSION_PASS: 62 executed DOC source cases\n"+
        "\n".join(device_lines)+"\n")
    if len(device_lines)!=62:
        raise RuntimeError("Incomplete native WebGPU adapter device evidence")
    report.write_text("\n".join(detail)+
        "\nDOC_SELECTED_RUST_DOC_GPU_PARITY_PASS: 62 real GPU-selected executions\n")
    print("DOC_SELECTED_RUST_DOC_GPU_PARITY_PASS: 62 real GPU-selected executions")
    return len(cases)

def nearest_rank_p95(values):
    """95th percentile (nearest-rank) of nonempty measured samples."""
    if not values:
        raise ValueError("p95 requires at least one sample")
    ordered = sorted(values)
    return ordered[(95 * len(ordered) + 99) // 100 - 1]

def benchmark_hardware_gpu(repo,rust_signed):
    """Rust-only physical GPU whole-process measurements, not shader-only speedup.

    Validate every sample against the independently verified same binary
    reference from the physical Rust signed GPU conformance sweep.
    """
    operations={"eq":[],"lt":["--lt"],"le":["--le"]}
    pattern=re.compile(
        r"^DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=([01]) lanes=1024 equals=(\d+)$",
        re.M)
    reference={}
    for mode in operations:
        raw=(LOGS/"rust/rust-{}-1024.log".format(mode)).read_text()
        reference[mode]={int(epoch):int(count)
                          for epoch,count in pattern.findall(raw)}
        if set(reference[mode])!={0,1}:
            raise RuntimeError("Missing verified Rust physical GPU baseline")
    def execute(mode,repetition):
        output=run("gpu-bench-rust-{}-{}".format(mode,repetition),
            [rust_signed,*operations[mode]],cwd=repo,
            env={**ENV,"DOC_GPU_LANES":"1024"},
            path="benchmark/rust-{}-{}.log".format(mode,repetition))
        counts={int(epoch):int(count) for epoch,count in pattern.findall(output)}
        if counts!=reference[mode]:
            raise RuntimeError("Physical Rust GPU benchmark changed source result")
        return METRICS[-1]["wall_seconds"]*1000
    for mode in operations:
        for index in range(2): execute(mode,"warmup"+str(index))
    sequence=[(mode,index) for mode in operations for index in range(9)]
    random.Random(0xD0C).shuffle(sequence)
    samples=[{"mode":mode,"runtime":"rust","sample":index,
              "end_to_end_cli_ms":round(execute(mode,index),4)}
             for mode,index in sequence]
    path=LOGS/"hardware-gpu-benchmark.csv"
    with path.open("w",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=list(samples[0]))
        writer.writeheader();writer.writerows(samples)
    stats={}
    for mode in operations:
        values=sorted(row["end_to_end_cli_ms"] for row in samples
                      if row["mode"]==mode)
        stats[mode]={"count":len(values),
                     "median_ms":round(statistics.median(values),4),
                     "p95_ms":nearest_rank_p95(values),"max_ms":values[-1]}
    summary={"status":"pass","samples":len(samples),"seed":0xD0C,
             "method":"9 shuffled process-level samples and 2 warmups per mode; "
                      "includes setup, compile, upload, dispatch, readback and "
                      "process startup; no kernel-only speedup claim",
             "baseline":"rust/rust-{mode}-1024.log","results":stats}
    (LOGS/"hardware-gpu-benchmark-summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print("DOC_KAGGLE_RUST_HARDWARE_BENCHMARK_PASS:",len(samples))
    return summary


def check_physical_radar_game(repo, game):
    """Real same-source automatic game execution; no authored placement hints."""
    replay="edsssxwddddsspr"
    argv=[game,repo/"engine/radar_chase.doc","--headless","--measure",
          "--replay="+replay]
    auto_env=dict(ENV)
    for key in ("DOC_GPU_ALLOW_SOFTWARE","DOC_AUTO_DISABLE_GPU",
                "DOC_GPU_INJECT_FAILURE_STAGE"):
        auto_env.pop(key,None)
    cpu_env={**auto_env,"DOC_AUTO_DISABLE_GPU":"1"}
    cpu=run("radar-cpu",argv,cwd=repo,env=cpu_env,path="report/radar-auto-cpu.log")
    auto=run("radar-physical",argv,cwd=repo,env=auto_env,
             path="report/radar-auto-physical.log")
    def frames(output):
        return [line for line in output.splitlines()
                if line.startswith(("DOC_GAME_FRAME:","DOC_GAME_ENTITIES:","DOC_GAME_RADAR:"))]
    assert frames(cpu)==frames(auto), "Physical auto replay differs from CPU"
    victory="DOC_GAME_FRAME: tick=13 player=(6,4) score=2 paused=false won=true coin=(6,4)"
    assert victory in frames(auto) and len([x for x in frames(auto)
        if x.startswith("DOC_GAME_FRAME:")])==16, "Incomplete winning replay"
    raw=(LOGS/"report/radar-auto-physical.log").read_text()
    cpu_raw=(LOGS/"report/radar-auto-cpu.log").read_text()
    device=selected_physical_webgpu_adapter(raw)
    assert re.search(r"(?m)^DOC_AUTO_SUMMARY: gpu_kind=none cpu_nodes=2940 gpu_nodes=0 ",cpu_raw)
    frontiers=re.findall(r"(?m)^DOC_AUTO_FRONTIER: cpu=(\d+) gpu=(\d+) gpu_kind=physical placement=typed-independent$",raw)
    mixed=[(int(cpu),int(gpu)) for cpu,gpu in frontiers if int(cpu)>0 and int(gpu)>=128]
    dispatch=re.findall(r"(?m)^DOC_RUST_GPU_FRONTIER_DISPATCH: states=(\d+) workgroups=(\d+) workgroup_size=(\d+)$",raw)
    assert len(mixed)==15 and len(dispatch)>=15, "Missing real mixed physical frontiers"
    assert sum(int(n) for n,_,_ in dispatch)==sum(g for _,g in mixed), "GPU readback and placement counts differ"
    summary=re.search(r"(?m)^DOC_AUTO_SUMMARY: gpu_kind=physical cpu_nodes=(\d+) gpu_nodes=(\d+) cpu_parallel_frontiers=\d+ cpu_only_frontiers=\d+ gpu_frontiers=(\d+) mixed_frontiers=(\d+)$",raw)
    assert summary, "Missing actual physical scheduler summary"
    cpu_nodes,gpu_nodes,gpu_frontiers,mixed_frontiers=map(int,summary.groups())
    assert cpu_nodes>0 and cpu_nodes+gpu_nodes==2940
    assert gpu_nodes==sum(g for _,g in mixed) and gpu_frontiers==mixed_frontiers==15
    assert raw.count("DOC_AUTO_GPU_SESSION_CREATED: gpu_kind=physical")==1
    assert raw.count("DOC_AUTO_GPU_SESSION_REUSED: gpu_kind=physical")==14
    def measurement(output, label):
        matched=re.search(r"(?m)^"+label+r": steps=(\d+) p50_us=(\d+) p95_us=(\d+) process_peak_rss_kib=(\d+) measurement=DOC_recurrence_advance_only$",output)
        assert matched and int(matched.group(1))==15,"Missing comparable game measurement"
        return dict(zip(("steps","p50_us","p95_us","process_peak_rss_kib"),map(int,matched.groups())))
    cpu_timing=measurement(cpu,"DOC_GAME_CPU_MEASURED")
    auto_timing=measurement(auto,"DOC_GAME_AUTO_MIXED_MEASURED")
    fault=subprocess.run([str(game),str(repo/"engine/radar_chase.doc"),
        "--headless","--replay=e"],cwd=repo,
        env={**auto_env,"DOC_GPU_INJECT_FAILURE_STAGE":"0"},
        capture_output=True,text=True,check=False)
    fault_raw=fault.stdout+"\n"+fault.stderr
    (LOGS/"report/radar-auto-fault.log").write_text(fault_raw)
    assert fault.returncode!=0 and fault.stdout.count("DOC_GAME_FRAME:")==1
    selected_physical_webgpu_adapter(fault_raw)
    assert "DOC_GPU_INJECTED_STAGE_FAILURE: stage=0" in fault_raw
    result={"adapter":device[0],"device_type":device[1],"cpu_nodes":cpu_nodes,
            "gpu_nodes":gpu_nodes,"mixed_frontiers":mixed_frontiers,
            "gpu_frontiers":gpu_frontiers,"cpu_measurement":cpu_timing,
            "mixed_measurement":auto_timing,"complete_replay_parity":True,
            "failure_rollback":True}
    marker="DOC_RADAR_PHYSICAL_AUTO_PASS: "+json.dumps(result,sort_keys=True)
    (LOGS/"report/radar-auto-result.log").write_text(marker+"\n")
    print(marker,flush=True)
    return result

def save(summary):
    (ROOT / "doc-kaggle-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    with tarfile.open(ROOT / "doc-kaggle-logs.tar.gz", "w:gz") as archive:
        for entry in LOGS.rglob("*"):
            if entry.is_file():
                archive.add(entry, arcname=str(entry.relative_to(LOGS)))

def check_physical_scene3d(repo,scene):
    env=dict(ENV)
    for key in ("DOC_GPU_ALLOW_SOFTWARE","DOC_AUTO_DISABLE_GPU","DOC_GPU_INJECT_FAILURE_STAGE"):
        env.pop(key,None)
    argv=[scene,"engine/radar_chase_3d.doc","--replay=jedsssxwddddsspr"]
    cpu=run("scene3d-cpu",argv+["--headless"],cwd=repo,env=env,path="report/scene3d-cpu.log")
    output=run("scene3d-physical",argv+["--offscreen","--snapshot="+str(LOGS/"report/scene3d-physical.ppm")],cwd=repo,env=env,path="report/scene3d-physical.log")
    raw=(LOGS/"report/scene3d-physical.log").read_text()
    records=lambda s:[x for x in s.splitlines() if x.startswith("DOC_SCENE_FRAME:")]
    devices=re.findall(r"(?m)^DOC_SCENE_RENDER_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu)$",raw)
    pixels=re.findall(r"(?m)^DOC_SCENE_PIXELS: epoch=(\d+) distinct=(\d+) digest=([0-9a-f]{16})$",raw)
    mixed=re.findall(r"(?m)^DOC_AUTO_FRONTIER: cpu=(\d+) gpu=(\d+) gpu_kind=physical placement=typed-independent$",raw)
    if not (len(devices)==1 and "DOC_SCENE_RENDER_SOFTWARE_TEST_ONLY" not in raw and
            "DOC_GPU_SOFTWARE_TEST_ONLY" not in raw and records(cpu)==records(output) and
            len(records(output))==17 and any("next_won=true" in x for x in records(output)) and
            any("next_elevation=24" in x for x in records(output)) and
            len(pixels)==17 and [int(x[0]) for x in pixels]==list(range(17)) and
            all(int(x[1])>=3 for x in pixels) and len({x[2] for x in pixels})>3 and
            len(mixed)==16 and all(int(c)>0 and int(g)>=128 for c,g in mixed) and
            "DOC_GPU_GENERATED_PIPELINE_CREATED:" in raw and "DOC_GPU_GENERATED_PIPELINE_REUSED:" in raw and
            "DOC_SCENE_GENERATED_PIPELINE:" in raw and
            "DOC_SCENE_REPLAY_PASS: mode=offscreen actions=16 frames=17" in output):
        raise RuntimeError("3D physical rendering/compute evidence failed")
    proof=run("scene3d-pixel-proof",[ROOT/"bin/scene3d_gpu_proof","engine/radar_chase_3d.doc"],cwd=repo,env=env,path="report/scene3d-pixel-proof.log")
    proof_raw=(LOGS/"report/scene3d-pixel-proof.log").read_text()
    proof_devices=re.findall(r"(?m)^DOC_SCENE_RENDER_DEVICE: name=([^\n]+?) type=(DiscreteGpu|IntegratedGpu)$",proof_raw)
    if proof_devices!=devices or "DOC_SCENE_RENDER_SOFTWARE_TEST_ONLY" in proof_raw or not re.search(
        r"(?m)^DOC_SCENE_GPU_PROOF_PASS: covered=[1-9][0-9]+ mutated=[1-9][0-9]+ lighting=3 depth_orders=2 jump=24 landed=0 repeats=16 rejected=2$",proof):
        raise RuntimeError("3D mesh depth, source mutation, light or resource proof failed")
    failure=subprocess.run([str(scene),"engine/radar_chase_3d.doc","--offscreen","--replay=j"],cwd=repo,
        env={**env,"DOC_GPU_INJECT_FAILURE_STAGE":"0"},capture_output=True,text=True,check=False)
    fault=failure.stdout+"\n"+failure.stderr
    (LOGS/"report/scene3d-fault.log").write_text(fault)
    if failure.returncode==0 or fault.count("DOC_SCENE_FRAME:")!=1 or "DOC_GPU_INJECTED_STAGE_FAILURE: stage=0" not in fault:
        raise RuntimeError("3D GPU failure published a successor")
    marker="DOC_SCENE3D_PHYSICAL_PASS: frames=17 mixed_frontiers=16 adapter="+devices[0][0]
    (LOGS/"report/scene3d-result.log").write_text(marker+"\n")
    print(marker)
    return {"frames":17,"mixed_frontiers":16,"adapter":devices[0][0],"device_type":devices[0][1],"complete_replay_parity":True}

def main():
    if not re.fullmatch(r"[a-f0-9]{40}", SPEC["sha"]):
        raise ValueError("Invalid pinned DOC source SHA")
    summary = {
        "sha": SPEC["sha"], "run_id": SPEC["run_id"],
        "accelerator": SPEC["accelerator"], "hardware": False,
        "backend": "unverified", "result": "failed",
        "rust_gpu_episodes": 0,
        "native_standard_ci_run_id": SPEC.get("standard_ci_run_id"),
        "bundle_dataset": SPEC.get("bundle_dataset"),
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        repo,signed,boolean=load_verified_native_bundle()
        experiment_provision_host_graphics()
        preflight_hardware()
        episodes=test_physical_gpu(repo,signed,boolean)
        selected_rust=check_selected_rust_doc_gpu(repo,ROOT/"bin/doc-rust-gpu")
        radar=check_physical_radar_game(repo,ROOT/"bin/doc-game")
        scene3d=check_physical_scene3d(repo,ROOT/"bin/doc-scene3d")
        family_env=dict(ENV)
        for key in ("DOC_GPU_ALLOW_SOFTWARE","DOC_AUTO_DISABLE_GPU","DOC_GPU_INJECT_FAILURE_STAGE"):
            family_env.pop(key,None)
        family=run("dependency-family",[ROOT/"bin/dependency_family_proof","runtime-rust/examples/dependency_family.doc","physical"],cwd=repo,env=family_env,path="report/dependency-family.log")
        if "DOC_FAMILY_PROOF_PASS: device=physical gpu_lanes=512 episodes=5 rollback=true" not in family:
            raise RuntimeError("Missing physical dependency family proof")
        summary.update({
            "radar_auto_physical":radar,
            "scene3d_physical":scene3d,
            "result":"pass","hardware":True,"backend":"webgpu",
            "rust_gpu_episodes":episodes,
            "selected_rust_doc_gpu_cases":selected_rust})
        try:
            summary["hardware_benchmark"]=benchmark_hardware_gpu(repo,signed)
        except Exception as benchmark_error:
            # Correct physical GPU parity remains a valid completed result,
            # even if optional timing evidence fails. Record the limitation.
            summary["hardware_benchmark"] = {
                "status":"failed", "error":str(benchmark_error)[-350:]}
        print(f"DOC_KAGGLE_RUST_NATIVE_PHYSICAL_GPU_PASS: {episodes} GPU episodes, {selected_rust} authored DOC cases")
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
