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
import re
for run_result,requested in ((parallel2,2),(parallel4,4)):
    matches=re.findall(r"DOC_GOOSE_PARALLEL_FRONTIER: workers=([0-9]+) candidates=128 hardware=([0-9]+)",run_result.stderr)
    if not matches and (os.cpu_count() or 1)>1:
        raise AssertionError("native Goose never dispatched isolated workers")
    for count,hardware in matches:
        if int(count)!=min(requested,int(hardware),4):
            raise AssertionError("Goose oversubscribed physical thread budget")
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
# Requests over the removed 16-worker cap are valid; actual concurrency
# is still constrained by hardware and profitable frontier granularity.
wide=run(goose,17)
if wide.stdout!=serial.stdout:
    raise AssertionError("Goose worker request above 16 changed output")
for invalid in ("0","bogus"):
    bad=subprocess.run([goose,fixture],
        env={**os.environ,"DOC_GOOSE_WORKERS":invalid},
        capture_output=True,timeout=30)
    if bad.returncode==0:
        raise AssertionError("Goose accepted invalid worker budget")
# Check lexical names which used to trigger the obsolete substring
# exclusion despite being pure Boolean/Int scalar work.
named="runtime-rust/examples/parallel_named_scalar.doc"
env={**os.environ,"DOC_GOOSE_WORKERS":"17"}
named_goose=subprocess.run([goose,named],capture_output=True,text=True,env=env,timeout=60)
named_rust=subprocess.run([rust,named],capture_output=True,text=True,timeout=60)
if named_goose.returncode or named_rust.returncode:
    raise AssertionError(f"named pure scalar frontier failed: {named_goose.stderr} / {named_rust.stderr}")
if "p127: false" not in named_goose.stdout or "folded: true" not in named_goose.stdout:
    raise AssertionError("named scalar frontier gave wrong Boolean observations")
if "p127: false" not in named_rust.stdout or "folded: true" not in named_rust.stdout:
    raise AssertionError("Rust independent named scalar oracle disagrees")
if (os.cpu_count() or 1)>1 and "DOC_GOOSE_PARALLEL_FRONTIER:" not in named_goose.stderr:
    raise AssertionError("Goose incorrectly classified a pool-free 'national' identifier")
print("DOC_GOOSE_PARALLEL_READY_FRONTIER_PASS: 1/2/4 native worker paths, 128 tasks, 2 updates")
(root/"goose-parallel-frontier.log").write_text(
    "DOC_GOOSE_PARALLEL_READY_FRONTIER_PASS: 1/2/4 native worker paths\n"
    +parallel4.stderr)
