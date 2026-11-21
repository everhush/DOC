#!/usr/bin/env python3
"""Matched native Rust/Goose DOC benchmark. Python is a test harness only.

Every sample runs an already-built native executable on the EXACT same .doc
source and inputs. We check output equivalence first and on every repetition.
Separate process launch, parsing and runtime cost are intentionally INCLUDED;
these are end-to-end CLI samples, not scheduler-only speedup measurements.
No cross-CPU claim or fake confidence interval is made.
"""
import csv
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: benchmark-matched.py RUST_DOC GOOSE_DOC OUTPUT_DIR")
rust, goose, output_dir = sys.argv[1:]
out = Path(output_dir)
out.mkdir(parents=True, exist_ok=True)
runs = {
    "finite_bool": (
        "runtime-rust/examples/boolean_conditional.doc",
        ["a=true", "b=false"],
        "chosen: false",
    ),
    "signed_equality": (
        "runtime-rust/examples/integer_equality.doc",
        ["a=-2147483648", "b=-2147483648"],
        "equal: true",
    ),
    "ancestor_demand": (
        "runtime-rust/examples/demand_lazy.doc",
        ["--demand=copy", "a=19"],
        "copy: 22",
    ),
    "natural_factorial_30": (
        "runtime-rust/examples/factorial_nat.doc",
        ["--through=30", "n=next_n", "product=next_product"],
        "product: 265252859812191058636308480000000",
    ),
    "natural_two_counter_20": (
        "runtime-rust/examples/nat_counter_machine.doc",
        ["--through=20", "pc=pc_next", "a=a_next", "b=b_next"],
        "b: 3",
    ),
}
binaries = {"rust": rust, "goose": goose}
sha = os.environ.get("GITHUB_SHA", "local-unversioned")
rng = random.Random(0xD0C)
repetitions = 21

def run_native(command):
    # wait4 returns the resource usage for this ONE native child, unlike
    # RUSAGE_CHILDREN which only exposes a cumulative peak resident set.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        start = time.perf_counter_ns()
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        pid, wait_status, usage = os.wait4(proc.pid, 0)
        elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
        if pid != proc.pid:
            raise RuntimeError("unexpected child process")
        proc.returncode = os.waitstatus_to_exitcode(wait_status)
        stdout.seek(0)
        stderr.seek(0)
        output = stdout.read().decode("utf-8", errors="replace")
        failure = stderr.read().decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"native DOC execution failed: {command}\n{failure}\n{output}"
        )
    clean = "\n".join(
        line for line in output.splitlines()
        if not line.startswith("DOC_TYPED_EVALUATIONS=")
    ) + "\n"
    return clean, elapsed_ms, usage

def nearest_rank(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction)-1)]

samples = []
for name, (source, arguments, checkpoint) in runs.items():
    command_map = {
        runtime: [binary, source, *arguments] for runtime, binary in binaries.items()
    }
    references = {}
    for runtime, cmd in command_map.items():
        result, _, _ = run_native(cmd)
        if checkpoint not in result:
            raise AssertionError(f"{name} {runtime} missing expected oracle checkpoint")
        references[runtime] = result
    if references["rust"] != references["goose"]:
        raise AssertionError(f"{name}: Rust/Goose results differ:\n{references}")
    # Warm up each already-built executable. We still measure per-process
    # startup and interpreter work in subsequent runs.
    for cmd in command_map.values():
        for _ in range(3):
            output, _, _ = run_native(cmd)
            if output != references["rust"]:
                raise AssertionError(f"{name}: nondeterministic warmup result")
    order = [(runtime, idx)
             for idx in range(repetitions) for runtime in binaries]
    rng.shuffle(order)
    for runtime, idx in order:
        result, wall, usage = run_native(command_map[runtime])
        if result != references["rust"]:
            raise AssertionError(
                f"{name} {runtime} iteration {idx}: nondeterministic output"
            )
        samples.append({
            "workload": name, "runtime": runtime, "rep": idx,
            "wall_ms": round(wall, 6),
            "cpu_user_ms": round(usage.ru_utime*1000, 6),
            "cpu_sys_ms": round(usage.ru_stime*1000, 6),
            # Linux ru_maxrss is KiB, the metric is per-execution.
            "rss_kib": usage.ru_maxrss, "exit_code": 0,
            "binary_bytes": Path(binaries[runtime]).stat().st_size,
            "commit_sha": sha,
            "command": json.dumps(command_map[runtime]),
        })

columns = list(samples[0])
with (out/"doc-matched-samples.csv").open("w", newline="") as f:
    writer=csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(samples)

summary = {
    "revision": sha,
    "host": {
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "logical_cores": os.cpu_count(),
        "cpu_model": next(
            (line.split(":",1)[1].strip()
             for line in Path("/proc/cpuinfo").read_text().splitlines()
             if line.lower().startswith("model name")), "unknown"),
        "mem_total": next(
            (line for line in Path("/proc/meminfo").read_text().splitlines()
             if line.startswith("MemTotal:")), "unknown"),
    },
    "method": (
        "Native release binaries, same input/source/semantics, 3 warmups per "
        "runtime/workload, 21 randomized-interleaved child-process samples; "
        "end-to-end CLI startup+parse+evaluate; Linux wait4 per-child RSS; "
        "not a pure-runtime/steady-state/multicore or hardware-GPU benchmark."
    ),
    "workloads": {},
}
for name in runs:
    for runtime in binaries:
        subset=[s for s in samples
                if s["workload"]==name and s["runtime"]==runtime]
        walls=[s["wall_ms"] for s in subset]
        rss=[s["rss_kib"] for s in subset]
        summary["workloads"][f"{name}/{runtime}"] = {
            "samples": len(subset),
            "median_wall_ms": round(statistics.median(walls), 6),
            "p95_wall_ms": round(nearest_rank(walls, .95), 6),
            "max_wall_ms": round(max(walls), 6),
            "median_rss_kib": statistics.median(rss),
            "max_rss_kib": max(rss),
            "binary_bytes": subset[0]["binary_bytes"],
            "result_hash_sha256": __import__("hashlib").sha256(
                run_native([binaries[runtime],runs[name][0],*runs[name][1]])[0]
                    .encode()
            ).hexdigest(),
        }
(out/"doc-matched-summary.json").write_text(
    json.dumps(summary, sort_keys=True, indent=2)+"\n"
)
print("DOC_MATCHED_DUAL_RUNTIME_BENCHMARK_PASS:", len(samples), "raw samples")
for key, stats in summary["workloads"].items():
    print(f"{key}: median={stats['median_wall_ms']:.3f}ms "
          f"p95={stats['p95_wall_ms']:.3f}ms "
          f"max_rss={stats['max_rss_kib']}KiB")
