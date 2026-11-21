#!/usr/bin/env python3
"""Independent sorting oracle for *same* user-authored .doc programs.
Neither Python nor the harness is an implementation of the DOC runtime.
"""
import random
import subprocess
import sys
from pathlib import Path

if len(sys.argv)!=4:
    raise SystemExit("usage: check-doc-sorting.py RUST_BINARY GOOSE_BINARY LOGS")
rust,goose,logdir=sys.argv[1:]
root=Path(logdir)
root.mkdir(parents=True,exist_ok=True)
random_gen=random.Random(789541)
cases=0
for kind in ("int","nat"):
    source=f"runtime-rust/examples/sort4_{kind}.doc"
    samples=[
        (0,0,0,0),
        (5,1,3,2),
        (7,7,7,7),
        (4,4,1,1),
        (3,2,1,0),
        (0,1,2,3),
    ]
    if kind=="int":
        samples += [
            (-(2**63),2**63-1,-1,0),
            (2**63-1,2**63-2,-(2**63),-(2**63)+1),
        ]
        for _ in range(150):
            samples.append(tuple(random_gen.randrange(-(2**63),2**63)
                                 for _ in range(4)))
    else:
        for _ in range(150):
            samples.append(tuple(random_gen.randrange(
                10**random_gen.randrange(1,150)) for _ in range(4)))
        samples += [
            (10**250-1,10**250,0,1),
            (10**100+1,10**100,10**100+2,10**100-1),
        ]
    for n,values in enumerate(samples):
        expected=sorted(values)
        docs=[]
        for runtime in (rust,goose):
            cmd=[runtime,source,*[f"{name}={value}" for name,value
                                  in zip("abcd",values)]]
            if kind=="nat" and n%4==0:
                cmd[-1]=cmd[-1].replace("=", "=000")
            p=subprocess.run(cmd,text=True,capture_output=True,timeout=15)
            if p.returncode:
                raise AssertionError(f"{runtime} failed: {cmd}\n{p.stderr}")
            observed={}
            for line in p.stdout.splitlines():
                if ":" not in line:continue
                key,value=line.split(":",1)
                if key in ("first","second","third","fourth"):
                    observed[key]=int(value.strip())
            actual=[observed[name] for name in ("first","second","third","fourth")]
            if actual!=expected:
                raise AssertionError(f"{kind} case={n}: {runtime} gave {actual} not {expected}")
            docs.append(actual)
            cases+=1
        if docs[0]!=docs[1]:
            raise AssertionError(f"cross-runtime sorting parity failed at {n}")
for invalid in [
    "source a: int = 1\nsource b: bool = true\nderive bad: bool (a,b) = lt(a,b)\n",
    "derive bad: bool () = le(true,false)\n",
    "derive bad: bool () = lt(nat(1),1)\n",
]:
    path=root/"sort-negative.doc"
    path.write_text(invalid)
    for runtime in (rust,goose):
        process=subprocess.run([runtime,str(path)],capture_output=True,timeout=10)
        if process.returncode==0:
            raise AssertionError(f"accepted invalid DOC numeric ordering source: {runtime}")
        cases+=1
print(f"DOC_NATIVE_SORTING_PASS: {cases} exact independent sorting oracle cases")
(root/"doc-native-sorting.log").write_text(f"DOC_NATIVE_SORTING_PASS: {cases}\n")
