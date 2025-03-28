#!/usr/bin/env python3
"""Validate a benchmark campaign emitted by run_all_benchmarks.py."""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: check_benchmark_artifact.py RESULTS_DIR")
root = Path(sys.argv[1])
errors: list[str] = []

required = [
    "raw.csv", "retained.csv", "statistics.csv", "summary.csv",
    "machine.json", "run-config.json", "commands.log",
    "filter-bounds.csv", "outliers.csv", "BENCHMARK-REPORT.md",
]
for name in required:
    p = root / name
    if not p.is_file() or p.stat().st_size == 0:
        errors.append(f"missing or empty {name}")

if not errors:
    machine = json.loads((root / "machine.json").read_text())
    config = json.loads((root / "run-config.json").read_text())
    if not machine:
        errors.append("machine.json is empty")
    if not config:
        errors.append("run-config.json is empty")

    with (root / "raw.csv").open(newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    with (root / "statistics.csv").open(newline="", encoding="utf-8") as fh:
        stats = list(csv.DictReader(fh))

    if len(raw) < 100:
        errors.append(f"raw.csv unexpectedly small: {len(raw)} rows")
    if len(stats) < 50:
        errors.append(f"statistics.csv unexpectedly small: {len(stats)} rows")

    names = {r.get("name", "") for r in raw}
    expected = {
        "cold", "density-1", "density-8", "density-64", "density-512",
        "density-2048", "dense-cheap", "parallel-1", "parallel-2",
        "parallel-3", "parallel-4", "financial-1", "financial-64",
        "financial-1024", "bitonic-1", "bitonic-8", "bitonic-64",
        "bitonic-256", "bitonic-512",
    }
    missing = sorted(expected - names)
    if missing:
        errors.append(f"benchmark rows missing: {missing}")

    # Each process is an oracle-checked run; reject explicit failure indicators.
    bad = [r for r in raw if r.get("ok", "1").lower() in {"0", "false", "no"}]
    if bad:
        errors.append(f"{len(bad)} raw benchmark rows report failed correctness")

if errors:
    print("BENCHMARK ARTIFACT: FAIL")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("BENCHMARK ARTIFACT: PASS")
print(f"- {len(raw)} raw rows")
print(f"- {len(stats)} aggregate-statistics rows")
print("- required workload families and provenance files are present")
