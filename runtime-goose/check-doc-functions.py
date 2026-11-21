#!/usr/bin/env python3
"""Functional DOC-source conformance oracle; Python is never a DOC runtime."""
import random,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
random_gen=random.Random(468529)
cases=0
for kind in ("int","nat"):
    path=f"runtime-rust/examples/functions_{kind}.doc"
    if kind=="int":
        inputs=[(-42,-7,11),(100,-7,11),(0,0,0),(-10,-10,-10),
                (-(2**63),-21,22),(2**63-1,-21,22)]
        inputs += [(random_gen.randrange(-(2**63),2**63),
                    random_gen.randrange(-1000,0),
                    random_gen.randrange(0,1000)) for _ in range(90)]
    else:
        big=10**200
        inputs=[(0,0,0),(1,1,1),(big,big-1,big+1),
                (big*1000,123,big),(10**250-1,1,big)]
        inputs += [(random_gen.randrange(10**random_gen.randrange(1,220)),
                    random_gen.randrange(10**20),
                    big+random_gen.randrange(10**20)) for _ in range(80)]
    for x,lo,hi in inputs:
        clamped=min(max(x,lo),hi)
        expected={
            "clamped":str(clamped),
            "quadruple":str(clamped*4),
            "at_low":str(clamped==lo).lower(),
            "at_high":str(clamped==hi).lower(),
        }
        result_reference=None
        for binary in (rust,goose):
            proc=subprocess.run([binary,path,f"x={x}",f"lo={lo}",f"hi={hi}"],
                                capture_output=True,text=True,timeout=20)
            if proc.returncode!=0:
                raise AssertionError(f"native {kind} function failure: {binary}\n{proc.stderr}")
            values={}
            for line in proc.stdout.splitlines():
                if ":" not in line:continue
                name,value=line.split(":",1)
                if name in expected:values[name]=value.strip()
            if values!=expected:
                raise AssertionError(f"{kind} {binary}: {values} != {expected}")
            if result_reference is not None and values!=result_reference:
                raise AssertionError("function differential mismatch")
            result_reference=values
            cases+=1
invalid=[
    "fn twice(x) = add(x,x)\nsource x: int = 1\nderive bad: int (x) = twice(x,x)\n",
    "fn add(x,y) = mul(x,y)\nsource x: int = 1\n",
    "fn looped(x) = looped(x)\nsource x: int = 1\nderive bad: int (x) = looped(x)\n",
    "fn bad(x,y) = add(x,y)\nsource a: bool = true\nderive badstate: bool (a) = bad(a,a)\n"
]
Path(logs).mkdir(parents=True,exist_ok=True)
for i,program in enumerate(invalid):
    path=Path(logs)/f"fn-bad-{i}.doc"
    path.write_text(program)
    for binary in (rust,goose):
        proc=subprocess.run([binary,str(path)],capture_output=True,text=True,timeout=10)
        if proc.returncode==0:
            raise AssertionError(f"accepted invalid function {i}: {binary}")
        cases+=1
print(f"DOC_NATIVE_FUNCTIONS_PASS: {cases} differential/oracle checks")
(Path(logs)/"doc-native-functions.log").write_text(
    f"DOC_NATIVE_FUNCTIONS_PASS: {cases} differential/oracle checks\n")
