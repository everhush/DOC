#!/usr/bin/env python3
"""Native Goose isolated-worker signed scalar-ready-frontier conformance."""
import os,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
fixture="runtime-rust/examples/parallel_signed_frontier.doc"
Path(logs).mkdir(parents=True,exist_ok=True)
expected={}
for i in range(128):
    op=i%3
    expected[f"p{i:03}"]=(False,True) if op==0 else (
        (True,False) if op==1 else (True,True))
expected["folded"]=(False,False)
def parse(stdout):
    epochs=[]
    for block in stdout.split("DOC_TYPED_EVALUATIONS=")[:2]:
        v={}
        for line in block.splitlines():
            if ":" not in line:continue
            name,val=line.split(":",1)
            if name in expected:v[name]=val.strip()=="true"
        epochs.append(v)
    return epochs
def goose_run(workers):
    p=subprocess.run([goose,fixture,"--next","a=7"],
                     env={**os.environ,"DOC_GOOSE_WORKERS":str(workers)},
                     capture_output=True,text=True,timeout=60)
    if p.returncode:raise AssertionError(p.stderr)
    values=parse(p.stdout)
    for name,(first,second) in expected.items():
        if values[0].get(name)!=first or values[1].get(name)!=second:
            raise AssertionError(f"{workers}-worker result incorrect: {name}")
    if workers>1 and "DOC_GOOSE_PARALLEL_FRONTIER:" not in p.stderr and (os.cpu_count() or 1)>1:
        raise AssertionError(f"{workers} worker request did not dispatch")
    return p.stdout
serial=goose_run(1)
for n in (2,4):
    if goose_run(n)!=serial:
        raise AssertionError("Goose signed worker schedule changed observations")
for episode,changed in enumerate(([],["a=7"])):
    p=subprocess.run([rust,fixture,*changed],capture_output=True,text=True,timeout=30)
    if p.returncode:raise AssertionError(p.stderr)
    values={}
    for line in p.stdout.splitlines():
        if ":" not in line:continue
        name,value=line.split(":",1)
        if name in expected:values[name]=value.strip()=="true"
    for name,outputs in expected.items():
        if values.get(name)!=outputs[episode]:
            raise AssertionError(f"Rust signed comparison mismatch {name}")
print("DOC_GOOSE_SIGNED_PARALLEL_PASS: 128 int comparison tasks, 1/2/4 workers")
Path(logs,"goose-signed-workers.log").write_text(
    "DOC_GOOSE_SIGNED_PARALLEL_PASS: 128 tasks, 1/2/4 workers\n")
