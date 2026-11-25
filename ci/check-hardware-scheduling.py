#!/usr/bin/env python3
"""Linux-only dynamic ready-frontier scaling/conformance evidence.

The 512 independent DOC computations run on native Rust and native Goose CPU.
No benchmark result implies a universal speedup or any GPU execution.
"""
import csv
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit("usage: check-hardware-scheduling.py RUST_DOC GOOSE_DOC OUTPUT_DIR")
rust, goose = (str(Path(x).resolve()) for x in sys.argv[1:3])
folder = Path(sys.argv[3])
folder.mkdir(parents=True, exist_ok=True)
width = 512
fixture = folder / "parallel-512.doc"
fixture.write_text(
    "source a: bool = true\nsource b: bool = false\n"
    + "".join(
        f"derive p{i:03}: bool (a,b) = eq(a,b)\n"
        for i in range(width)
    )
    + "derive folded: bool (p000,p001) = eq(p000,p001)\n"
)
expected = {"a": "true", "b": "false", "folded": "true"}
expected.update({f"p{i:03}": "false" for i in range(width)})
pattern = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*): (true|false)$")
marker = re.compile(
    r"DOC_(?:GOOSE|RUST)_PARALLEL_FRONTIER: "
    r"workers=(\d+) candidates=512 hardware=(\d+)"
)
goose_auto = re.compile(
    r"DOC_GOOSE_AUTO_FRONTIER_SEQUENTIAL: "
    r"estimate=(\d+) candidates=512 hardware=(\d+)"
)
budgets = [1, 2, 4, 8, 17, "auto"]
results = []
reference = None
for runtime, executable in (("rust", rust), ("goose", goose)):
    for requested in budgets:
        for trial in range(3):
            env = os.environ.copy()
            env.pop("DOC_WORKERS", None)
            env.pop("DOC_GOOSE_WORKERS", None)
            if requested != "auto":
                env["DOC_WORKERS"] = str(requested)
                env["DOC_GOOSE_WORKERS"] = str(requested)
            start = time.perf_counter_ns()
            p = subprocess.run(
                [executable, str(fixture), "--backend=cpu"],
                env=env, capture_output=True, text=True, timeout=90
            )
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            if p.returncode:
                raise AssertionError(
                    f"{runtime} requested={requested} trial={trial}: "
                    f"{p.stderr[-1200:]}"
                )
            actual = dict(match.groups() for line in p.stdout.splitlines()
                          if (match := pattern.fullmatch(line)))
            if actual != expected:
                raise AssertionError(
                    f"{runtime} requested={requested}: incorrect 512-node "
                    "frontier publication"
                )
            if reference is None:
                reference = actual
            if actual != reference:
                raise AssertionError("worker count changed DOC semantics")
            matches = [(int(w), int(h)) for w,h in marker.findall(p.stderr)]
            if len(matches) > 1:
                raise AssertionError("wide source scheduled duplicate frontiers")
            auto_match=goose_auto.search(p.stderr) if runtime=="goose" else None
            effective, hardware = (
                matches[0] if matches else (1,int(auto_match.group(2)))
                if auto_match else (1,1)
            )
            if matches:
                admission = min(
                    width // 32, hardware,
                    requested if requested != "auto" else hardware
                )
                if effective != admission or effective < 2:
                    raise AssertionError(
                        f"{runtime}: incorrect hardware/grain scheduling "
                        f"{effective}/{hardware}/{requested}"
                    )
            elif requested == 1:
                pass
            elif requested == "auto" and runtime == "goose" and auto_match:
                # Auto grain control is allowed to avoid a measured
                # pathological slowdown on tiny pure scalar expressions.
                if int(auto_match.group(1)) >= 2048:
                    raise AssertionError("Goose auto skipped profitable work")
            elif len(os.sched_getaffinity(0)) > 1:
                raise AssertionError(
                    f"{runtime}: available Linux CPUs but no concurrent "
                    "512-wide DOC execution"
                )
            results.append({
                "runtime": runtime,
                "requested_workers": requested,
                "effective_workers": effective,
                "hardware_reported": hardware,
                "frontier_width": width,
                "trial": trial,
                "wall_ms": round(elapsed, 6),
                "sha": os.environ.get("GITHUB_SHA", "unversioned"),
            })

with (folder / "hardware-frontier-scale.csv").open(
    "w", newline="", encoding="utf-8"
) as out:
    writer = csv.DictWriter(out, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

summary = {}
for runtime in ("rust", "goose"):
    for budget in budgets:
        cohort = [row["wall_ms"] for row in results
                  if row["runtime"] == runtime
                  and row["requested_workers"] == budget]
        summary[f"{runtime}/{budget}"] = {
            "median_ms": statistics.median(cohort),
            "min_ms": min(cohort),
            "max_ms": max(cohort),
            "observations": len(cohort),
        }
(folder / "hardware-frontier-scale.json").write_text(
    json.dumps({
        "revision": os.environ.get("GITHUB_SHA", "unversioned"),
        "linux_affinity_cpus": len(os.sched_getaffinity(0)),
        "frontier_width": width,
        "note": "Whole CLI wall-clock; no guaranteed speedup; zero GPU claims.",
        "results": summary,
    }, indent=2) + "\n", encoding="utf-8"
)
print(
    f"DOC_LINUX_HARDWARE_SCHEDULER_PASS: {len(results)} executions "
    f"across {len(budgets)} scheduler budgets and both native runtimes"
)
