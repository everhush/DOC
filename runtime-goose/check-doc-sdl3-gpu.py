#!/usr/bin/env python3
"""Fail-closed SDL3 GPU parity for the native Goose DOC runtime.

This file is a validation oracle, not DOC implementation or shader generator.
The GPU driver and the DOC interpreter are both the native Goose executable.
SDL3's upstream gfx package compiles fixed GLSL to SPIR-V/MSL/HLSL.
"""
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: check-doc-sdl3-gpu.py SDL3_GOOSE_BINARY EVIDENCE_DIR")
binary, evidence_dir = sys.argv[1:]
evidence=Path(evidence_dir)
evidence.mkdir(parents=True, exist_ok=True)
sources={
    "eq":"runtime-rust/examples/integer_equality.doc",
    "lt":"runtime-rust/examples/integer_ordering.doc",
    "le":"runtime-rust/examples/integer_ordering.doc",
    "bool":"runtime-rust/examples/boolean_conditional.doc",
    "staged":"runtime-rust/examples/boolean_staged.doc",
}
pattern=re.compile(
    r"^DOC_GOOSE_SDL3_GPU_PASS: op=(eq|lt|le|bool|staged) "
    r"epoch=([01]) lanes=([0-9]+) count=([0-9]+) backend=([a-zA-Z0-9_]+)$"
)
def inputs(lane,epoch,boolean):
    if boolean:
        a=1 if lane%3==0 else 0
        b=1 if lane%5<2 else 0
        if epoch==1:
            if lane%2==0:a=1-a
            if lane%7==1:b=1-b
        return a,b
    choices=(-(2**31),2**31-1,-1,0,1,5,-934,65536,-19000)
    a=choices[lane%len(choices)]
    if epoch==1:
        if lane%3==0:a=0
        elif lane%3==2:a=2**31-1 if a==-(2**31) else -a
    if lane%4==0:b=a
    elif lane%4==1:b=-1 if a==2**31-1 else a+1
    elif lane%4==2:b=1 if a==-(2**31) else a-1
    else:b=2**31-1 if a==-(2**31) else -a
    assert -(2**31)<=a<=2**31-1 and -(2**31)<=b<=2**31-1
    return a,b
def oracle(mode,epoch,lanes):
    count=0
    for lane in range(lanes):
        a,b=inputs(lane,epoch,mode in ("bool","staged"))
        v=(
            a==b if mode=="eq" else
            a<b if mode=="lt" else
            a<=b if mode=="le" else
            (a==b or a==0)
        )
        if mode=="staged": v=v == (b!=0)
        count+=int(v)
    return count
def run(mode,lanes,extra=(),good=True):
    cmd=[binary,sources[mode],mode,str(lanes),*extra]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    if good and p.returncode:
        raise AssertionError(f"Native Goose SDL3 GPU failed: {cmd}\n{p.stdout}\n{p.stderr}")
    if not good:
        if p.returncode==0 or "DOC_GOOSE_SDL3_GPU_PASS:" in p.stdout:
            raise AssertionError(f"Invalid SDL3 GPU request was accepted: {cmd}")
    return p.stdout,p.stderr
cases=0
for mode in sources:
    for lanes in (1,63,64,65,129,257,1024):
        out,err=run(mode,lanes)
        records=[]
        for line in out.splitlines():
            m=pattern.match(line)
            if m:
                op,epoch,n,count,backend=m.groups()
                records.append((op,int(epoch),int(n),int(count),backend))
        if len(records)!=2:
            raise AssertionError(f"SDL3 did not verify two GPU epochs: {mode}/{lanes}: {out}\n{err}")
        if "DOC_GOOSE_SDL3_DEVICE:" not in out:
            raise AssertionError(f"SDL3 adapter identity was not recorded: {out}")
        for op,epoch,n,count,backend in records:
            if op!=mode or n!=lanes or count!=oracle(mode,epoch,lanes):
                raise AssertionError(f"GPU vs independent Python oracle: {records}")
            if backend not in ("vulkan","metal","direct3d12"):
                raise AssertionError(f"SDL3 reported non-GPU backend: {backend}")
        cases+=2
        (evidence/f"sdl3-{mode}-{lanes}.log").write_text(out+"\n"+err)
for mode,lanes,extra in (
    ("eq",0,()),("lt",4097,()),("bool",-1,()),
    ("eq",65,("--inject-wide",)),
    ("staged",64,("--inject-wide",)),
):
    run(mode,lanes,extra,good=False)
    cases+=1
# Type/definition ineligible: a boolean DOC expression is not silently
# accepted as signed integer eq, and vice versa.
for source,mode in (
    ("runtime-rust/examples/boolean_conditional.doc","eq"),
    ("runtime-rust/examples/integer_equality.doc","bool"),
):
    p=subprocess.run([binary,source,mode,"65"],
                     capture_output=True,text=True,timeout=30)
    if p.returncode==0 or "DOC_GOOSE_SDL3_GPU_PASS:" in p.stdout:
        raise AssertionError(f"Invalid DOC target accepted by SDL3: {source}/{mode}")
    cases+=1
(evidence/"doc-goose-sdl3-summary.log").write_text(
    f"DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: {cases} checks\n"
)
print(f"DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: {cases} checks")
