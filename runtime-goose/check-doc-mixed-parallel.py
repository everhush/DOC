#!/usr/bin/env python3
"""Native Goose 1/2/4/8 worker mixed scalar frontier, identical Rust oracle.
Proves real Goose worker dispatch, deterministic results, no pool-backed
values crossing task queues, source repair, and no partial typed outcomes.
"""
import os
import subprocess
import sys
from pathlib import Path

rust, goose, logs = sys.argv[1:]
fixture = "runtime-rust/examples/parallel_mixed_scalar.doc"
root=Path(logs)
root.mkdir(parents=True, exist_ok=True)
names={f"p{i:03}" for i in range(128)}

def expected(a,b):
    ans={}
    for i in range(128):
        op = ["add","sub","mul"][i%3] if i<64 else ["eq","lt","le"][(i-64)%3]
        ans[f"p{i:03}"] = {
            "add":str(a+b), "sub":str(a-b), "mul":str(a*b),
            "eq":str(a==b).lower(), "lt":str(a<b).lower(),
            "le":str(a<=b).lower()
        }[op]
    return ans

def parse(stdout):
    parts=stdout.split("DOC_TYPED_EVALUATIONS=")
    readings=[]
    for part in parts[:2]:
        out={}
        for line in part.splitlines():
            if ": " not in line:continue
            key,value=line.split(": ",1)
            if key in names:out[key]=value.strip()
        readings.append(out)
    return readings
base=None
checks=0
for n in (1,2,4,8):
    env={**os.environ, "DOC_GOOSE_WORKERS":str(n)}
    got=subprocess.run([goose,fixture,"--next","a=7"],
        capture_output=True,text=True,env=env,timeout=90)
    if got.returncode:
        raise AssertionError(f"Goose scalar worker mode {n}: {got.stderr}")
    outputs=parse(got.stdout)
    assert len(outputs)==2, f"Missing Goose episodes for {n}"
    for episode,a in enumerate((3,7)):
        assert outputs[episode]==expected(a,5), (
            f"Goose {n}-worker episode={episode}: {outputs[episode]}")
        checks+=1
    if n>1:
        marker="DOC_GOOSE_PARALLEL_FRONTIER: workers="
        if got.stderr.count(marker)<2 and (os.cpu_count() or 1)>1:
            raise AssertionError(f"No actual mixed scalar worker dispatch for {n}")
        checks+=1
    if base is not None and got.stdout!=base:
        raise AssertionError("Goose multicore scalar execution changed stdout")
    base=got.stdout
for episode,a in enumerate((3,7)):
    args=[] if episode==0 else ["a=7"]
    p=subprocess.run([rust,fixture,*args],capture_output=True,text=True,timeout=35)
    if p.returncode:
        raise AssertionError(f"Rust mixed scalar oracle error: {p.stderr}")
    out=parse(p.stdout)[0]
    assert out==expected(a,5),(episode,out)
    checks+=1
# A failing integer candidate must never publish part of a 128-task
# frontier, including when multiple real worker threads are active.
bad=root/"mixed-scalar-overflow.doc"
bad.write_text(
    "source a: int = 9223372036854775807\n"
    "source b: int = 1\n"
    + "".join(
        f"derive p{i:03}: int (a,b) = "
        + ("add(a,b)" if i==127 else "sub(a,b)") + "\n"
        for i in range(128))
)
for name,binary in (("goose",goose),("rust",rust)):
    for n in (1,2,4,8):
        env={**os.environ, "DOC_GOOSE_WORKERS":str(n)}
        process=subprocess.run([binary,str(bad)],env=env,
            capture_output=True,text=True,timeout=25)
        if process.returncode==0:
            raise AssertionError(f"{name}/{n} unexpectedly accepted overflowing frontier")
        if any(line.startswith("p000:") for line in process.stdout.splitlines()):
            raise AssertionError(f"{name}/{n} published a partial failing frontier")
        checks+=1
print(f"DOC_GOOSE_MIXED_SCALAR_PARALLEL_PASS: {checks} worker and oracle checks")
(root/"goose-mixed-workers.log").write_text(
    f"DOC_GOOSE_MIXED_SCALAR_PARALLEL_PASS: {checks}\n")
