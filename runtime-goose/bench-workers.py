#!/usr/bin/env python3
"""Same-source, same-host 1/2/4 native DOC ready-frontier worker measurements.
Records raw measurements, correctness and negative speedups. No acceleration
claims or GPU claims; processes start fresh for every sample.
"""
import csv,json,math,os,platform,random,statistics,subprocess,sys,time
from pathlib import Path
rust,goose,folder=sys.argv[1:]
out=Path(folder)
out.mkdir(parents=True,exist_ok=True)
file="runtime-rust/examples/parallel_frontier.doc"
binaries={"rust":rust,"goose":goose}
samples=[]
reference=None
def invoke(runtime,workers):
    env=os.environ.copy()
    env["DOC_WORKERS"]=str(workers)
    env["DOC_GOOSE_WORKERS"]=str(workers)
    started=time.perf_counter_ns()
    p=subprocess.run([binaries[runtime],file],capture_output=True,text=True,
                     env=env,timeout=30)
    elapsed=(time.perf_counter_ns()-started)/1_000_000
    if p.returncode:
        raise AssertionError(f"{runtime}/{workers} failed: {p.stderr}")
    normalized="\n".join(line for line in p.stdout.splitlines()
                         if not line.startswith("DOC_TYPED_EVALUATIONS="))+"\n"
    if "p127: false" not in normalized or "folded: true" not in normalized:
        raise AssertionError("invalid wide ready-frontier result")
    if runtime=="goose" and workers>1 and (
        f"DOC_GOOSE_PARALLEL_FRONTIER: workers={workers} candidates=128"
        not in p.stderr):
        raise AssertionError("Goose worker implementation did not dispatch typed-queue jobs")
    return normalized,elapsed
for runtime in binaries:
    for w in (1,2,4):
        for _ in range(3):
            text,_=invoke(runtime,w)
            if reference is None: reference=text
            if text!=reference:raise AssertionError("worker count changed DOC semantics")
jobs=[(runtime,w,i) for runtime in binaries for w in (1,2,4) for i in range(31)]
random.Random(97413).shuffle(jobs)
for runtime,w,i in jobs:
    text,ms=invoke(runtime,w)
    if text!=reference:raise AssertionError("nondeterministic DOC result")
    samples.append({"runtime":runtime,"workers":w,"rep":i,
                    "wall_ms":round(ms,6),
                    "sha":os.environ.get("GITHUB_SHA","unversioned"),
                    "host":platform.node()})
with (out/"doc-ready-frontier-workers.csv").open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(samples[0]))
    writer.writeheader();writer.writerows(samples)
summary={}
for runtime in binaries:
    for w in (1,2,4):
        values=sorted(s["wall_ms"] for s in samples
                      if s["runtime"]==runtime and s["workers"]==w)
        summary[f"{runtime}/{w}"]={
            "n":len(values),
            "median_ms":statistics.median(values),
            "p95_ms":values[math.ceil(.95*len(values))-1],
            "min_ms":values[0],
            "max_ms":values[-1],
        }
(out/"doc-ready-frontier-workers.json").write_text(json.dumps({
    "revision":os.environ.get("GITHUB_SHA","unversioned"),
    "hardware_threads":os.cpu_count(),
    "method":"31 randomized interleaved native per-process repetitions per worker count;",
    "caveat":"Includes CLI startup and IPC overhead; negative speedups must be retained.",
    "results":summary},indent=2)+"\n")
print("DOC_WORKER_BENCHMARK_PASS:",len(samples),"raw samples")
for key,result in summary.items():
    print(f"{key}: n={result['n']} median_ms={result['median_ms']:.3f}"
          f" p95_ms={result['p95_ms']:.3f}")
