#!/usr/bin/env python3
"""Independent state-machine/list oracle for same DOC source in both hosts."""
import ast
import random
import subprocess
import sys
from pathlib import Path

rust,goose,logs=sys.argv[1:]
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
program="runtime-rust/examples/list_fold.doc"
rng=random.Random(94209)
cases=0
def run(binary,filename,*args,valid=True):
    cmd=[binary,filename,*args]
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                     text=True,timeout=30)
    if valid and p.returncode:
        raise AssertionError(f"{cmd} failed: {p.stderr}\n{p.stdout}")
    if not valid and p.returncode==0:
        raise AssertionError(f"{cmd} incorrectly succeeded")
    return p.stdout
def parse_output(output):
    values={}
    for line in output.splitlines():
        if ":" not in line: continue
        k,v=line.split(":",1)
        if k in ("remaining","next_remaining","singleton"):
            values[k]=ast.literal_eval(v.strip())
        elif k in ("total","next_total","count"):
            values[k]=int(v.strip())
        elif k=="done":
            values[k]=v.strip()=="true"
    return values

inputs=[[],[0],[1,-1],[5,-3,9,0],
        [2**63-1],[-2**63],list(range(65))]
inputs.extend([[rng.randint(-1000,1000) for _ in range(rng.randrange(0,30))]
               for _ in range(120)])
for data in inputs:
    source="["+ ",".join(str(v) for v in data)+"]"
    expected={
        "remaining":data,
        "total":0,
        "done":not data,
        "next_remaining":data[1:],
        "next_total":data[0] if data else 0,
        "count":len(data),
        "singleton":[0],
    }
    for binary in (rust,goose):
        got=parse_output(run(binary,program,f"remaining={source}"))
        if got!=expected:
            raise AssertionError(f"{binary} list values mismatch: {got} vs {expected}")
        cases+=1
# Genuine DOC recurrence with a fresh program file per input list:
# not a host-side substitute for repeated forward DOC carry.
for iteration,data in enumerate(([],[1],[-1,0,1],[5,-3,9,0],
                                 list(range(30)),[10,-3,4,-2])):
    initial="["+ ",".join(str(v) for v in data)+"]"
    authored=Path(program).read_text().replace(
        "source remaining: ints = [5,-3,9,0]",
        f"source remaining: ints = {initial}")
    program_path=root/f"list-recurrence-{iteration}.doc"
    program_path.write_text(authored)
    for binary in (rust,goose):
        output=run(binary,str(program_path),"--until=done",
                   f"--max-epochs={len(data)+2}",
                   "remaining=next_remaining","total=next_total")
        if f"DOC_RECURRENCE_HALT: {len(data)}" not in output:
            raise AssertionError(f"{binary} list carry did not halt at {len(data)}")
        totals=[int(line.split(":",1)[1]) for line in output.splitlines()
                if line.startswith("total:")]
        if not totals or totals[-1]!=sum(data):
            raise AssertionError(f"{binary} list sum mismatch: {totals}")
        cases+=1
# Verify an out-of-bounds index produces no stable observation and no success.
for text in (
    "source a: ints = []\nderive bad: int (a) = get(a,0)\n",
    "source a: ints = [1]\nderive bad: int (a) = get(a,-1)\n",
    "source a: ints = [1]\nderive bad: int (a) = len(1)\n",
    "source a: ints = [1]\nderive bad: ints (a) = append(a,false)\n",
    "source a: ints = [1,x]\n",
):
    bad=root/"list-negative.doc"
    bad.write_text(text)
    for binary in (rust,goose):
        run(binary,str(bad),valid=False)
        cases+=1

# Dynamic native collection storage must not impose the old 4096-element cap.
# Both runtimes evaluate the SAME large source and DOC append/length semantics.
large=list(range(4097))
large_source="["+ ",".join(map(str,large))+"]"
large_doc=root/"list-beyond-old-cap.doc"
large_doc.write_text(
    f"source items: ints = {large_source}\n"
    "derive expanded: ints (items) = append(items,777)\n"
    "derive count: int (expanded) = len(expanded)\n"
)
for binary in (rust,goose):
    stdout=run(binary,str(large_doc))
    observed={}
    for line in stdout.splitlines():
        if line.startswith(("items: ","expanded: ","count: ")):
            name,value=line.split(": ",1)
            observed[name]=int(value) if name=="count" else ast.literal_eval(value)
    if observed!={"items":large,"expanded":large+[777],"count":4098}:
        raise AssertionError(f"{binary} large DOC collection result mismatch")
    cases+=1
assert all(isinstance(v,int) for values in inputs for v in values)
root.joinpath("doc-list-conformance.log").write_text(
    f"DOC_NATIVE_DYNAMIC_LIST_PASS: {cases} independent checks\n"
)
print(f"DOC_NATIVE_DYNAMIC_LIST_PASS: {cases} independent checks")
