#!/usr/bin/env python3
"""Wide exact same-source Goose worker conformance, with independent oracle."""
import os,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
fixture="runtime-rust/examples/parallel_frontier.doc"
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
expected={f"p{i:03}":(False,True) for i in range(128)}
expected["folded"]=(True,True)
def run(binary,workers):
    env=os.environ.copy()
    env["DOC_GOOSE_WORKERS"]=str(workers)
    p=subprocess.run([binary,fixture,"--next","a=false"],
                     capture_output=True,text=True,env=env,timeout=60)
    if p.returncode:
        raise AssertionError(f"{binary}/{workers}: {p.stderr}\n{p.stdout}")
    chunks=p.stdout.split("DOC_TYPED_EVALUATIONS=")
    states=[]
    for block in chunks[:2]:
        values={}
        for line in block.splitlines():
            if ":" not in line: continue
            name,value=line.split(":",1)
            if name in expected: values[name]=value.strip()=="true"
        states.append(values)
    for name,epochs in expected.items():
        for episode in (0,1):
            if states[episode].get(name) != epochs[episode]:
                raise AssertionError(f"{binary}/{workers}: {name} episode={episode} unexpected")
    return p
serial=run(goose,1)
parallel2=run(goose,2)
parallel4=run(goose,4)
if serial.stdout!=parallel2.stdout or serial.stdout!=parallel4.stdout:
    raise AssertionError("Goose parallel scheduling changed DOC observations")
if "DOC_GOOSE_PARALLEL_FRONTIER:" in serial.stderr:
    raise AssertionError("single-worker Goose incorrectly claimed parallel work")
for run_result,n in ((parallel2,2),(parallel4,4)):
    if f"DOC_GOOSE_PARALLEL_FRONTIER: workers={n} candidates=128" not in run_result.stderr:
        raise AssertionError(f"native Goose never dispatched {n} isolated workers")
# Rust uses one source-episode invocation per process rather than
# Goose's --next. Both must still compute the identical DOC graph valuation.
for episode,assignments in enumerate(([],["a=false"])):
    reference=subprocess.run([rust,fixture,*assignments],
                             capture_output=True,text=True,timeout=60)
    if reference.returncode:
        raise AssertionError(f"Rust reference failed: {reference.stderr}")
    parsed={}
    for line in reference.stdout.splitlines():
        if ":" in line:
            name,value=line.split(":",1)
            if name in expected: parsed[name]=value.strip()=="true"
    for name,epochs in expected.items():
        if parsed.get(name) != epochs[episode]:
            raise AssertionError(f"Rust Boolean oracle mismatch {name} episode={episode}")
# Resource cap, safe fail-stop rather than silently applying an invalid budget.
bad=subprocess.run([goose,fixture],env={**os.environ,"DOC_GOOSE_WORKERS":"17"},
                   capture_output=True,timeout=30)
if bad.returncode==0:
    raise AssertionError("Goose accepted invalid worker limit")
print("DOC_GOOSE_PARALLEL_READY_FRONTIER_PASS: 1/2/4 native worker paths, 128 tasks, 2 updates")
(root/"goose-parallel-frontier.log").write_text(
    "DOC_GOOSE_PARALLEL_READY_FRONTIER_PASS: 1/2/4 native worker paths\n"
    +parallel4.stderr)
