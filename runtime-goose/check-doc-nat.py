#!/usr/bin/env python3
"""Same directly-authored nat DOC source under Rust and Goose, Python oracle only."""
import random
import subprocess
import sys
import time
from pathlib import Path

goose,rust,logs=sys.argv[1:]
source="runtime-rust/examples/nat_recurrence.doc"
initial=10**50-1
target=10**50+2

def invoke(binary,*args,expect_failure=False):
    cmd=[binary,source,*args]
    result=subprocess.run(cmd,text=True,capture_output=True,timeout=20)
    if expect_failure:
        if result.returncode==0:
            raise AssertionError(f"bad DOC source succeeded: {cmd}\n{result.stdout}")
    else:
        if result.returncode:
            raise AssertionError(f"DOC native failed: {cmd}\n{result.stderr}\n{result.stdout}")
    return result.stdout

def oracle(epoch,first):
    c=first+epoch
    return (f"epoch: {epoch}\ncounter: {c}\nnext: {c+1}\n"
            f"previous: {max(0,c-1)}\nhalt: {str(c==target).lower()}\n")

def prefix(limit,first=initial,halt=False):
    output=""
    for epoch in range(limit+1):
        output+=oracle(epoch,first)
        if halt and first+epoch==target:
            output+=f"DOC_RECURRENCE_HALT: {epoch}\n"
            break
    return output

def checked(*args,expected=None,negative=False):
    for binary in (rust,goose):
        stdout=invoke(binary,*args,expect_failure=negative)
        if expected is not None and stdout!=expected:
            raise AssertionError(f"{binary} {args}: expected:\n{expected}\nobserved:\n{stdout}")
    return 2

Path(logs).mkdir(parents=True,exist_ok=True)
cases=0
# Long-running recurrence must preserve results across repeated arena compaction.
# The retention policy roots only current values, defaults and future facts.
for epoch in (250, 500):
    cases+=checked(f"--through={epoch}","counter=next",expected=prefix(epoch))
for epoch in (0,1,2,3,4,5):
    cases+=checked(f"--through={epoch}","counter=next",expected=prefix(epoch))
cases+=checked("--until=halt","--max-epochs=8","counter=next",
               expected=prefix(8,halt=True))
cases+=checked("--until=halt","--max-epochs=2","counter=next",negative=True)
# Canonicalization, independent nat arithmetic and guarded subtraction.
rand=random.Random(33809)
for _ in range(48):
    n=rand.randrange(10**150)
    raw="0"*rand.randrange(4)+str(n)
    for target_name,expected in (
        ("counter",n),("next",n+1),("previous",max(0,n-1)),("halt",n==target)
    ):
        value=str(expected).lower() if isinstance(expected,bool) else str(expected)
        cases+=checked(f"--demand={target_name}",f"counter={raw}",
                       expected=f"{target_name}: {value}\n")
for invalid in ("counter=-1","counter=abc","counter=0x17","counter=true"):
    cases+=checked("--demand=next",invalid,negative=True)
cases+=checked("--demand=unknown","counter=0",negative=True)
# Failure is dynamic, not a source type-checking error.
failure=Path(logs)/"nat-negative-underflow.doc"
failure.write_text("source a: nat = 0\n"
                   "derive bad: nat (a) = sub(a,nat(1))\n")
for binary in (rust,goose):
    p=subprocess.run([binary,str(failure)],capture_output=True,timeout=15)
    assert p.returncode!=0,(binary,p.stdout,p.stderr)
cases+=1
# Record a small same-workload sample with warmups; no speedup claim.
timings=[]
for binary in (rust,goose):
    invoke(binary, "--through=4", "counter=next")
    for rep in range(5):
        t=time.perf_counter()
        invoke(binary,"--through=4","counter=next")
        timings.append((Path(binary).name,rep,(time.perf_counter()-t)*1000))
log=Path(logs)/"doc-nat-conformance.log"
log.write_text("DOC_NATIVE_NAT_CONFORMANCE_PASS: "+str(cases)+" cases\n"+
              "\n".join(f"runtime={b} rep={i} wall_ms={ms:.3f}"
                        for b,i,ms in timings)+"\n")
print(log.read_text(),end="")
