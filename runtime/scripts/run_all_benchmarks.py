#!/usr/bin/env python3
"""Build, run, analyse, and report the complete DOC benchmark suite.

The default invocation is intentionally sufficient for a publication run:

    python3 scripts/run_all_benchmarks.py

It uses twenty fresh processes per row, alternates scenario order to reduce
monotonic time-drift bias, limits worker capacity outside application graphs,
applies one symmetric Tukey 1.5-IQR policy, and preserves every raw and
excluded measurement.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = ROOT / "build-benchmarks"
DEFAULT_RUNS = ROOT / "results" / "runs"
NUMBER = re.compile(r"-?(?:\d+|\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")
INTEGER = re.compile(r"-?\d+$")


@dataclass(frozen=True)
class Scenario:
    name: str
    command: tuple[str, ...]
    workers: int
    filter_fields: tuple[str, ...]
    group: str
    label: str


BASE_SCENARIOS: tuple[Scenario, ...] = (
    Scenario("cold", ("cold",), 1, ("direct_ms", "doc_ms"), "core", "Cold 2,048-leaf reduction"),
    Scenario("density-1", ("density", "1"), 1, ("direct_ms", "doc_ms"), "core", "1 changed source"),
    Scenario("density-8", ("density", "8"), 1, ("direct_ms", "doc_ms"), "core", "8 changed sources"),
    Scenario("density-64", ("density", "64"), 1, ("direct_ms", "doc_ms"), "core", "64 changed sources"),
    Scenario("density-512", ("density", "512"), 1, ("direct_ms", "doc_ms"), "core", "512 changed sources"),
    Scenario("density-2048", ("density", "2048"), 1, ("direct_ms", "doc_ms"), "core", "2,048 changed sources"),
    Scenario("cutoff", ("cutoff",), 1, ("elapsed_ms",), "core", "Exact equality cutoff"),
    Scenario("dense-cheap", ("dense-cheap",), 1, ("direct_ms", "doc_ms"), "core", "Dense cheap negative control"),
    Scenario("parallel-1", ("parallel",), 1, ("elapsed_ms",), "parallel", "1 participant"),
    Scenario("parallel-2", ("parallel",), 2, ("elapsed_ms",), "parallel", "2 participants"),
    Scenario("parallel-3", ("parallel",), 3, ("elapsed_ms",), "parallel", "3 participants"),
    Scenario("parallel-4", ("parallel",), 4, ("elapsed_ms",), "parallel", "4 participants"),
    Scenario("parallel-5", ("parallel",), 5, ("elapsed_ms",), "parallel", "5 participants"),
    Scenario("financial-1", ("financial", "1"), 1, ("direct_ms", "cached_ms", "doc_ms"), "financial", "1 changed business unit"),
    Scenario("financial-64", ("financial", "64"), 1, ("direct_ms", "cached_ms", "doc_ms"), "financial", "64 changed business units"),
    Scenario("financial-1024", ("financial", "1024"), 1, ("direct_ms", "cached_ms", "doc_ms"), "financial", "1,024 changed business units"),
    Scenario("bitonic-1", ("bitonic", "1"), 1, ("direct_update_ms", "doc_update_ms"), "bitonic", "1 changed input"),
    Scenario("bitonic-8", ("bitonic", "8"), 1, ("direct_update_ms", "doc_update_ms"), "bitonic", "8 changed inputs"),
    Scenario("bitonic-64", ("bitonic", "64"), 1, ("direct_update_ms", "doc_update_ms"), "bitonic", "64 changed inputs"),
    Scenario("bitonic-256", ("bitonic", "256"), 1, ("direct_update_ms", "doc_update_ms"), "bitonic", "256 changed inputs"),
    Scenario("bitonic-512", ("bitonic", "512"), 1, ("direct_update_ms", "doc_update_ms"), "bitonic", "512 changed inputs"),
)


class BenchmarkError(RuntimeError):
    """Raised when a benchmark run is incomplete or inconsistent."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and run all DOC benchmarks, then generate one reproducible report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--samples", type=int, default=20, help="fresh processes per benchmark row")
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD, help="Release build directory")
    parser.add_argument("--results-dir", type=Path, help="output directory; default is a UTC timestamp under results/runs")
    parser.add_argument("--max-participants", type=int, default=5, help="largest ready-frontier worker cap to measure")
    parser.add_argument("--warmups", type=int, default=0, help="unrecorded fresh-process warmups per row")
    parser.add_argument("--no-build", action="store_true", help="reuse an existing doc_benchmark binary")
    parser.add_argument("--skip-tests", action="store_true", help="do not run CTest before benchmarking")
    parser.add_argument("--resume", action="store_true", help="resume an incomplete run in --results-dir")
    parser.add_argument("--cmake-generator", help="override the automatically selected CMake generator")
    return parser.parse_args()


def utc_run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_command(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(shell_quote(part) for part in command)
    print(f"+ {printable}", flush=True)
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture or log_path else None,
        stderr=subprocess.PIPE if capture or log_path else None,
        check=False,
    )
    if log_path is not None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"$ {printable}\n")
            handle.write(completed.stdout or "")
            handle.write(completed.stderr or "")
            handle.write(f"[exit {completed.returncode}]\n\n")
    if completed.returncode != 0:
        detail = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        raise BenchmarkError(f"command failed ({completed.returncode}): {printable}\n{detail}")
    return completed


def shell_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:=+,-]+", value):
        return value
    return "'" + value.replace("'", "'\\''") + "'"


def configure_and_build(args: argparse.Namespace, commands_log: Path) -> Path:
    build_dir = args.build_dir.resolve()
    binary = build_dir / "doc_benchmark"
    if args.no_build:
        if not binary.is_file():
            raise BenchmarkError(f"--no-build requested, but benchmark binary is missing: {binary}")
        commands_log.parent.mkdir(parents=True, exist_ok=True)
        with commands_log.open("a", encoding="utf-8") as handle:
            handle.write(f"[reused benchmark binary] {binary}\n")
            handle.write(f"[sha256] {sha256(binary)}\n\n")
        return binary

    generator = args.cmake_generator
    if generator is None and shutil.which("ninja"):
        generator = "Ninja"

    configure = [
        "cmake",
        "-S",
        str(ROOT),
        "-B",
        str(build_dir),
        "-DCMAKE_BUILD_TYPE=Release",
    ]
    if generator:
        configure.extend(["-G", generator])
    run_command(configure, log_path=commands_log)
    run_command(
        ["cmake", "--build", str(build_dir), "--target", "doc_benchmark", "doc_tests", "doc_benchmark_tests"],
        log_path=commands_log,
    )
    if not args.skip_tests:
        run_command(
            ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
            log_path=commands_log,
        )
    if not binary.is_file():
        raise BenchmarkError(f"build completed without producing {binary}")
    return binary


def available_affinity_cpus() -> int:
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0))
    return os.cpu_count() or 1


def cgroup_cpu_quota() -> float | None:
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    if not cpu_max.exists():
        return None
    fields = cpu_max.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[0] == "max":
        return None
    quota, period = int(fields[0]), int(fields[1])
    return quota / period if period else None


def parse_key_values(line: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for token in line.strip().split():
        if "=" not in token:
            continue
        key, raw = token.split("=", 1)
        if INTEGER.fullmatch(raw):
            row[key] = int(raw)
        elif NUMBER.fullmatch(raw):
            row[key] = float(raw)
        else:
            row[key] = raw
    return row


def benchmark_environment(workers: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DOC_MAX_WORKERS": str(workers),
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
        }
    )
    return env


def run_scenario(binary: Path, scenario: Scenario) -> dict[str, Any]:
    completed = run_command(
        [str(binary), *scenario.command],
        env=benchmark_environment(scenario.workers),
        capture=True,
    )
    lines = [line for line in (completed.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise BenchmarkError(f"no output from {scenario.name}; stderr={completed.stderr!r}")
    row = parse_key_values(lines[-1])
    if not row:
        raise BenchmarkError(f"unparseable output from {scenario.name}: {lines[-1]!r}")
    missing = [field for field in scenario.filter_fields if field not in row]
    if missing:
        raise BenchmarkError(f"{scenario.name} omitted required fields {missing}: {row}")
    return row


def csv_fields(rows: Iterable[dict[str, Any]]) -> list[str]:
    preferred = [
        "name",
        "group",
        "label",
        "sample",
        "external_workers",
        "scenario",
        "changed",
        "direct_ms",
        "cached_ms",
        "doc_ms",
        "elapsed_ms",
        "direct_cold_ms",
        "doc_cold_ms",
        "direct_update_ms",
        "doc_update_ms",
        "evaluations",
        "update_evaluations",
        "cutoffs",
        "participants",
        "owner_jobs",
        "worker_jobs",
        "states",
        "comparators",
        "units",
        "periods",
        "value",
    ]
    all_fields = {key for row in rows for key in row}
    return [field for field in preferred if field in all_fields] + sorted(all_fields - set(preferred))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = csv_fields(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw_row in csv.DictReader(handle):
            row: dict[str, Any] = {}
            for key, raw in raw_row.items():
                if raw is None or raw == "":
                    continue
                if INTEGER.fullmatch(raw):
                    row[key] = int(raw)
                elif NUMBER.fullmatch(raw):
                    row[key] = float(raw)
                else:
                    row[key] = raw
            rows.append(row)
    return rows


def tukey_bounds(values: Sequence[float]) -> tuple[float, float]:
    if len(values) < 4:
        return -math.inf, math.inf
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[(len(ordered) + 1) // 2 :]
    q1 = statistics.median(lower)
    q3 = statistics.median(upper)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
    7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
    13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
    19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
    25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def numeric_values(rows: Sequence[dict[str, Any]], key: str) -> list[float]:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return values if len(values) == len(rows) else []


def distribution(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "stdev": None,
                "ci95_low": None, "ci95_high": None, "min": None, "max": None}
    n = len(values)
    mean = statistics.fmean(values)
    median = statistics.median(values)
    minimum, maximum = min(values), max(values)
    if n < 2:
        return {"n": n, "mean": mean, "median": median, "stdev": None,
                "ci95_low": None, "ci95_high": None, "min": minimum, "max": maximum}
    stdev = statistics.stdev(values)
    critical = T95.get(n - 1, 1.96)
    half = critical * stdev / math.sqrt(n)
    return {"n": n, "mean": mean, "median": median, "stdev": stdev,
            "ci95_low": mean - half, "ci95_high": mean + half,
            "min": minimum, "max": maximum}


def analyse(
    rows: list[dict[str, Any]], scenarios: Sequence[Scenario]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
    list[dict[str, Any]], list[dict[str, Any]],
]:
    retained: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    bounds_rows: list[dict[str, Any]] = []
    statistics_rows: list[dict[str, Any]] = []

    metadata = {"name", "group", "label", "sample", "scenario", "external_workers"}
    for scenario in scenarios:
        group = [row for row in rows if row["name"] == scenario.name]
        if not group:
            raise BenchmarkError(f"no measurements for {scenario.name}")

        field_bounds: dict[str, tuple[float, float]] = {}
        for field in scenario.filter_fields:
            values = [float(row[field]) for row in group]
            field_bounds[field] = tukey_bounds(values)
            bounds_rows.append({"name": scenario.name, "field": field,
                                "lower": field_bounds[field][0], "upper": field_bounds[field][1]})

        kept = [row for row in group if all(
            lower <= float(row[field]) <= upper
            for field, (lower, upper) in field_bounds.items()
        )]
        dropped = [row for row in group if row not in kept]
        if not kept:
            raise BenchmarkError(f"outlier policy excluded every row for {scenario.name}")
        retained.extend(kept)
        excluded.extend(dropped)

        summary: dict[str, Any] = {
            "name": scenario.name, "group": scenario.group, "label": scenario.label,
            "external_workers": scenario.workers, "retained": len(kept), "samples": len(group),
        }
        for key in csv_fields(group):
            if key in metadata:
                continue
            raw_values = numeric_values(group, key)
            kept_values = numeric_values(kept, key)
            if not raw_values or not kept_values:
                continue
            raw_stats = distribution(raw_values)
            filtered_stats = distribution(kept_values)
            # Backward-compatible alias: the concise report uses filtered means,
            # while raw and filtered distributions are both preserved explicitly.
            summary[key] = filtered_stats["mean"]
            for prefix, stats in (("raw", raw_stats), ("filtered", filtered_stats)):
                for stat_name, value in stats.items():
                    summary[f"{prefix}_{key}_{stat_name}"] = value
                statistics_rows.append({
                    "name": scenario.name,
                    "group": scenario.group,
                    "label": scenario.label,
                    "external_workers": scenario.workers,
                    "metric": key,
                    "population": prefix,
                    **stats,
                })
            raw_mean = float(raw_stats["mean"])
            filtered_mean = float(filtered_stats["mean"])
            summary[f"filter_sensitivity_{key}_percent"] = (
                100.0 * (filtered_mean - raw_mean) / raw_mean if raw_mean != 0.0 else 0.0
            )
        summaries.append(summary)

    return retained, excluded, summaries, bounds_rows, statistics_rows


def command_output(command: Sequence[str]) -> str:
    try:
        return subprocess.check_output(list(command), text=True, stderr=subprocess.STDOUT).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"unavailable: {exc}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def machine_record(binary: Path, args: argparse.Namespace, scenarios: Sequence[Scenario]) -> dict[str, Any]:
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    return {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "compiler": command_output(["c++", "--version"]).splitlines()[0],
        "build_mode": "Release",
        "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines() if line.startswith("model name")), "unavailable") if Path("/proc/cpuinfo").exists() else "unavailable",
        "kernel": command_output(["uname", "-srvo"]),
        "thread_limit_method": "DOC_MAX_WORKERS environment variable; affinity/cgroup limits are recorded separately",
        "cmake": command_output(["cmake", "--version"]).splitlines()[0],
        "affinity_cpu_count": available_affinity_cpus(),
        "os_cpu_count": os.cpu_count(),
        "cgroup_cpu_quota": cgroup_cpu_quota(),
        "cpu_max": cpu_max.read_text(encoding="utf-8").strip() if cpu_max.exists() else "unavailable",
        "samples_per_row": args.samples,
        "warmups_per_row": args.warmups,
        "max_participants": args.max_participants,
        "benchmark_binary": str(binary),
        "benchmark_binary_sha256": sha256(binary),
        "driver_sha256": sha256(Path(__file__).resolve()),
        "scenario_count": len(scenarios),
        "method": (
            "fresh process for every recorded measurement; deterministic alternating scenario order; "
            "worker limits supplied only through DOC_MAX_WORKERS; LC_ALL/LANG=C and TZ=UTC; "
            "symmetric Tukey 1.5-IQR bounds per declared timing field; a paired row is retained only "
            "when every paired timing remains within its own bounds"
        ),
    }


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]], align: Sequence[str] | None = None) -> list[str]:
    if align is None:
        align = ["---"] * len(headers)
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(align) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def fmt_ms(value: Any) -> str:
    return f"{float(value):.6f} ms"


def generate_report(
    out: Path,
    summaries: list[dict[str, Any]],
    raw: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    machine: dict[str, Any],
) -> str:
    by_name = {row["name"]: row for row in summaries}
    lines: list[str] = [
        "# DOC complete benchmark report",
        "",
        f"Generated at `{machine['generated_at_utc']}` from `{machine['samples_per_row']}` fresh processes per row.",
        "Every benchmark executable checks result equality and exits nonzero on disagreement.",
        "",
        "## Method",
        "",
        "- One fresh process is used for every recorded measurement.",
        "- Scenario order alternates forward and reverse for successive samples to reduce monotonic time-drift bias.",
        "- Processor capacity is imposed externally through `DOC_MAX_WORKERS`; application graphs contain no worker count.",
        "- One symmetric Tukey 1.5-IQR rule is used throughout. For paired direct/DOC rows, both timings must remain within their independently computed bounds.",
        "- Raw, retained, excluded, bounds, summary, machine, and command records are all preserved beside this report.",
        "",
        "## Host and run configuration",
        "",
        *markdown_table(
            ["Property", "Value"],
            [
                ["Platform", str(machine["platform"])],
                ["Compiler", str(machine["compiler"])],
                ["Build mode", str(machine["build_mode"])],
                ["CPU", str(machine["cpu_model"])],
                ["Kernel", str(machine["kernel"])],
                ["External limit", str(machine["thread_limit_method"])],
                ["Affinity CPUs", str(machine["affinity_cpu_count"])],
                ["Cgroup CPU quota", str(machine["cgroup_cpu_quota"])],
                ["Samples per row", str(machine["samples_per_row"])],
                ["Warmups per row", str(machine["warmups_per_row"])],
                ["Benchmark SHA-256", f"`{machine['benchmark_binary_sha256']}`"],
                ["Driver SHA-256", f"`{machine['driver_sha256']}`"],
            ],
        ),
        "",
        "## Initial evaluation, update density, and negative control",
        "",
    ]

    core_rows: list[list[str]] = []
    for name in ("cold", "density-1", "density-8", "density-64", "density-512", "density-2048", "dense-cheap"):
        row = by_name[name]
        core_rows.append(
            [
                str(row["label"]),
                fmt_ms(row["direct_ms"]),
                fmt_ms(row["doc_ms"]),
                f"{int(round(float(row.get('evaluations', 0)))):,}",
                f"{row['retained']}/{row['samples']}",
            ]
        )
    lines.extend(markdown_table(
        ["Scenario", "Direct mean", "DOC mean", "Evaluations", "Retained"],
        core_rows,
        ["---", "---:", "---:", "---:", "---:"],
    ))

    cutoff = by_name["cutoff"]
    lines += [
        "",
        (
            f"Exact cutoff: {fmt_ms(cutoff['elapsed_ms'])}, "
            f"{int(round(float(cutoff.get('evaluations', 0))))} evaluation, "
            f"{int(round(float(cutoff.get('cutoffs', 0))))} equality cutoff, "
            f"retained {cutoff['retained']}/{cutoff['samples']}. "
            "Its sub-millisecond timing is structural evidence, not a stable speed claim."
        ),
        "",
        "## Ready-frontier scaling",
        "",
    ]

    baseline_filtered = float(by_name["parallel-1"]["elapsed_ms"])
    raw_parallel: dict[int, float] = {}
    for workers in range(1, int(machine["max_participants"]) + 1):
        values = [float(row["elapsed_ms"]) for row in raw if row["name"] == f"parallel-{workers}"]
        raw_parallel[workers] = statistics.fmean(values)
    baseline_raw = raw_parallel[1]
    scaling_rows: list[list[str]] = []
    for workers in range(1, int(machine["max_participants"]) + 1):
        row = by_name[f"parallel-{workers}"]
        filtered = float(row["elapsed_ms"])
        scaling_rows.append(
            [
                str(workers),
                fmt_ms(filtered),
                f"{baseline_filtered / filtered:.3f}x",
                fmt_ms(raw_parallel[workers]),
                f"{baseline_raw / raw_parallel[workers]:.3f}x",
                f"{row['retained']}/{row['samples']}",
            ]
        )
    lines.extend(markdown_table(
        ["Participants", "Filtered mean", "Filtered speedup", "Raw mean", "Raw speedup", "Retained"],
        scaling_rows,
        ["---:", "---:", "---:", "---:", "---:", "---:"],
    ))

    lines += [
        "",
        "## Incremental financial projection workload",
        "",
        "This workload models 4,096 business units, each with four input cells and a 360-period fixed-point projection, followed by a balanced consolidation tree. It compares complete serial reevaluation, a conventional serial cached repair using a segment tree, and DOC repair; all three outputs must agree.",
        "",
    ]
    financial_rows: list[list[str]] = []
    for changed in (1, 64, 1024):
        row = by_name[f"financial-{changed}"]
        financial_rows.append([
            f"{changed:,}",
            fmt_ms(row["raw_direct_ms_mean"]),
            fmt_ms(row["raw_cached_ms_mean"]),
            fmt_ms(row["raw_doc_ms_mean"]),
            fmt_ms(row["filtered_doc_ms_mean"]),
            f"{int(round(float(row['evaluations']))):,}",
            f"{row['retained']}/{row['samples']}",
        ])
    lines.extend(markdown_table(
        ["Changed units", "Full raw mean", "Cached raw mean", "DOC raw mean", "DOC filtered mean", "DOC evaluations", "Retained"],
        financial_rows,
        ["---:", "---:", "---:", "---:", "---:", "---:", "---:"],
    ))

    lines += [
        "",
        "## Complete graph-expressed bitonic network",
        "",
    ]
    bitonic_rows: list[list[str]] = []
    for changed in (1, 8, 64, 256, 512):
        row = by_name[f"bitonic-{changed}"]
        bitonic_rows.append(
            [
                f"{changed:,}",
                fmt_ms(row["direct_update_ms"]),
                fmt_ms(row["doc_update_ms"]),
                f"{int(round(float(row['update_evaluations']))):,}",
                f"{int(round(float(row['cutoffs']))):,}",
                f"{row['retained']}/{row['samples']}",
            ]
        )
    lines.extend(markdown_table(
        ["Changed inputs", "Direct mean", "DOC mean", "Evaluations", "Cutoffs", "Retained"],
        bitonic_rows,
        ["---:", "---:", "---:", "---:", "---:", "---:"],
    ))
    bitonic_one = by_name["bitonic-1"]
    lines += [
        "",
        (
            f"The network has {int(round(float(bitonic_one['comparators']))):,} compare-exchanges and "
            f"{int(round(float(bitonic_one['states']))):,} total states. Every run checks DOC output "
            "against both direct execution of the same Batcher network and `std::sort`."
        ),
        "",
        "## Full timing distributions",
        "",
        "The table below reports every timing metric in the matrix. Confidence intervals use a two-sided 95% Student-t interval for up to 31 observations and the normal approximation above that; no interval is reported for a single observation. Filter sensitivity is the percentage change from the raw mean to the filtered mean.",
        "",
    ]
    distribution_rows: list[list[str]] = []
    for row in summaries:
        metrics = sorted(
            key[len("raw_") : -len("_mean")]
            for key in row
            if key.startswith("raw_") and key.endswith("_mean")
            and key[len("raw_") : -len("_mean")].endswith("_ms")
        )
        for metric in metrics:
            stdev = row.get(f"raw_{metric}_stdev")
            ci_low = row.get(f"raw_{metric}_ci95_low")
            ci_high = row.get(f"raw_{metric}_ci95_high")
            distribution_rows.append([
                str(row["label"]),
                metric,
                str(int(row[f"raw_{metric}_n"])),
                f"{float(row[f'raw_{metric}_mean']):.6f}",
                f"{float(row[f'raw_{metric}_median']):.6f}",
                "—" if stdev is None else f"{float(stdev):.6f}",
                "—" if ci_low is None else f"[{float(ci_low):.6f}, {float(ci_high):.6f}]",
                f"{float(row[f'raw_{metric}_min']):.6f}",
                f"{float(row[f'raw_{metric}_max']):.6f}",
                f"{float(row[f'filtered_{metric}_mean']):.6f}",
                f"{float(row[f'filter_sensitivity_{metric}_percent']):+.3f}%",
            ])
    lines.extend(markdown_table(
        ["Scenario", "Metric", "n", "Raw mean", "Median", "SD", "95% CI", "Min", "Max", "Filtered mean", "Sensitivity"],
        distribution_rows,
        ["---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"],
    ))
    lines += [
        "",
        "## Outlier accounting",
        "",
        f"Recorded measurements: **{len(raw):,}**. Excluded measurements: **{len(excluded):,}**. "
        "No result is removed merely for showing a smaller speedup; exclusion depends only on the same declared symmetric timing bounds.",
        "",
        "## Evidence boundary",
        "",
        "The suite supports a cost-shape claim, not universal superiority: sparse repair can avoid work; exact equality can stop propagation; coarse ready frontiers can consume externally granted processors; and dense or fine-grained workloads can lose to direct execution. Exact ratios are host- and workload-specific.",
        "",
        "## Generated files",
        "",
        "- `raw.csv`: every process measurement",
        "- `retained.csv`: measurements used for filtered means",
        "- `outliers.csv`: symmetrically excluded measurements",
        "- `filter-bounds.csv`: the exact bounds used for each timing field",
        "- `summary.csv`: raw and filtered distribution fields plus filter sensitivity",
        "- `statistics.csv`: long-form n, mean, median, standard deviation, 95% confidence interval, minimum, and maximum",
        "- `machine.json`: host, binary hash, and methodology",
        "- `run-config.json`: requested scenarios and command-line settings",
        "- `commands.log`: configure, build, and test commands",
        "",
    ]
    report = "\n".join(lines)
    (out / "BENCHMARK-REPORT.md").write_text(report, encoding="utf-8")
    return report


def scenario_set(max_participants: int) -> tuple[Scenario, ...]:
    if max_participants < 1 or max_participants > 5:
        raise BenchmarkError("--max-participants must be between 1 and 5 for the publication matrix")
    return tuple(
        scenario
        for scenario in BASE_SCENARIOS
        if not scenario.name.startswith("parallel-")
        or scenario.workers <= max_participants
    )


def verify_resume_config(out: Path, config: dict[str, Any]) -> dict[str, Any] | None:
    path = out / "run-config.json"
    if not path.exists():
        return None
    old = json.loads(path.read_text(encoding="utf-8"))
    comparable = ("samples", "warmups", "max_participants", "scenarios")
    differences = [key for key in comparable if old.get(key) != config.get(key)]
    if differences:
        raise BenchmarkError(f"cannot resume with changed configuration fields: {', '.join(differences)}")
    return old


def main() -> int:
    args = parse_args()
    if args.samples < 1:
        raise BenchmarkError("--samples must be positive")
    if args.warmups < 0:
        raise BenchmarkError("--warmups cannot be negative")

    scenarios = scenario_set(args.max_participants)
    out = (args.results_dir or (DEFAULT_RUNS / utc_run_id())).resolve()
    if out.exists() and not args.resume and any(out.iterdir()):
        raise BenchmarkError(f"results directory is not empty; use --resume or another path: {out}")
    out.mkdir(parents=True, exist_ok=True)
    commands_log = out / "commands.log"

    config = {
        "samples": args.samples,
        "warmups": args.warmups,
        "max_participants": args.max_participants,
        "build_dir": str(args.build_dir.resolve()),
        "scenarios": [
            {
                "name": scenario.name,
                "command": list(scenario.command),
                "workers": scenario.workers,
                "filter_fields": list(scenario.filter_fields),
            }
            for scenario in scenarios
        ],
    }
    previous_config = verify_resume_config(out, config) if args.resume else None

    binary = configure_and_build(args, commands_log)
    config["benchmark_binary"] = str(binary)
    config["benchmark_binary_sha256"] = sha256(binary)
    if previous_config is not None:
        previous_hash = previous_config.get("benchmark_binary_sha256")
        if previous_hash is not None and previous_hash != config["benchmark_binary_sha256"]:
            raise BenchmarkError(
                "cannot resume with a different benchmark binary: "
                f"{previous_hash} != {config['benchmark_binary_sha256']}"
            )
    (out / "run-config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    affinity = available_affinity_cpus()
    quota = cgroup_cpu_quota()
    if affinity < args.max_participants:
        print(
            f"warning: requested {args.max_participants} participants but process affinity exposes only {affinity} CPUs",
            file=sys.stderr,
        )
    if quota is not None and quota + 1e-9 < args.max_participants:
        print(
            f"warning: requested {args.max_participants} participants but cgroup quota is approximately {quota:.2f} CPUs",
            file=sys.stderr,
        )

    raw_path = out / "raw.csv"
    raw = read_csv(raw_path) if args.resume else []
    completed = {(str(row["name"]), int(row["sample"])) for row in raw}

    if args.warmups:
        print(f"running {args.warmups} unrecorded warmup process(es) per row", flush=True)
        for scenario in scenarios:
            for _ in range(args.warmups):
                run_scenario(binary, scenario)

    started = time.monotonic()
    total = args.samples * len(scenarios)
    for sample in range(1, args.samples + 1):
        ordered = scenarios if sample % 2 == 1 else tuple(reversed(scenarios))
        for scenario in ordered:
            key = (scenario.name, sample)
            if key in completed:
                continue
            row = run_scenario(binary, scenario)
            row.update(
                {
                    "name": scenario.name,
                    "group": scenario.group,
                    "label": scenario.label,
                    "sample": sample,
                    "external_workers": scenario.workers,
                }
            )
            raw.append(row)
            completed.add(key)
            write_csv(raw_path, raw)
            elapsed = time.monotonic() - started
            print(
                f"[{len(completed)}/{total}] sample={sample}/{args.samples} {scenario.name} "
                f"elapsed={elapsed:.1f}s",
                flush=True,
            )

    expected = {(scenario.name, sample) for scenario in scenarios for sample in range(1, args.samples + 1)}
    missing = expected - completed
    if missing:
        raise BenchmarkError(f"run ended with {len(missing)} missing scenario/sample pairs")

    retained, excluded, summaries, bounds_rows, statistics_rows = analyse(raw, scenarios)
    write_csv(out / "retained.csv", retained)
    write_csv(out / "outliers.csv", excluded)
    write_csv(out / "summary.csv", summaries)
    write_csv(out / "filter-bounds.csv", bounds_rows)
    write_csv(out / "statistics.csv", statistics_rows)

    machine = machine_record(binary, args, scenarios)
    (out / "machine.json").write_text(json.dumps(machine, indent=2) + "\n", encoding="utf-8")
    report = generate_report(out, summaries, raw, excluded, machine)
    print("\n" + report, flush=True)
    print(f"\nComplete report: {out / 'BENCHMARK-REPORT.md'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrupted; raw.csv is resumable with --resume and the same --results-dir", file=sys.stderr)
        raise SystemExit(130)
    except BenchmarkError as exc:
        print(f"benchmark driver failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
