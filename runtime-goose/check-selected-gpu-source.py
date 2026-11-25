#!/usr/bin/env python3
"""Linux SDL3 Vulkan: real selected Goose DOC-source GPU vs CPU and independent oracle.

No GPU stage is emulated by this Python verifier. The native Goose executable
parses the identical authored .doc source, owns SDL3 compute, and does its own
readback. This script checks external results and rejects missing GPU markers.
Mesa results prove software Vulkan correctness, not physical acceleration.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: check-selected-gpu-source.py NATIVE_GOOSE_SDL3 OUTPUT_DIRECTORY")

binary = str(Path(sys.argv[1]).resolve())
root = Path(sys.argv[2])
root.mkdir(parents=True, exist_ok=True)
sources = Path("runtime-rust/examples")
pattern = re.compile(r"^([a-zA-Z_][a-zA-Z_0-9]*): (true|false|-?[0-9]+)$")


def results(stdout):
    return dict(m.groups() for line in stdout.splitlines()
                if (m := pattern.fullmatch(line)))


def stable_epochs(stdout):
    epochs = []
    current = None
    for line in stdout.splitlines():
        if line.startswith("epoch: "):
            current = {}
            epochs.append((int(line.split(": ", 1)[1]), current))
        elif current is not None:
            match = pattern.fullmatch(line)
            if match and not match.group(1).startswith("DOC_"):
                current[match.group(1)] = match.group(2)
    return epochs


def invoke(index, side, fixture, args, ok=True):
    cmd = [binary, str(fixture), f"--backend={side}", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          errors="replace", env=os.environ.copy())
    stem = root / f"{index:03}-{side}"
    stem.with_suffix(".stdout").write_text(proc.stdout)
    stem.with_suffix(".stderr").write_text(proc.stderr)
    if ok and proc.returncode:
        raise AssertionError(f"{fixture.name}: selected {side} failed (case {index})")
    if not ok and proc.returncode == 0:
        raise AssertionError(f"{fixture.name}: invalid {side} case unexpectedly succeeded")
    return proc.stdout


cases = []
for name in ("boolean_conditional.doc", "boolean_staged.doc"):
    for a in (False, True):
        for b in (False, True):
            chosen = (a == b or not a)
            expected = {"chosen": str(chosen).lower()}
            if name == "boolean_staged.doc":
                expected["verified"] = str(chosen == b).lower()
            cases.append((name, [f"a={str(a).lower()}", f"b={str(b).lower()}"],
                          expected))
for gate in (False, True):
    for a in (-2147483648, -1, 0, 1, 2147483647):
        for b in (-2147483648, -1, 0, 1, 2147483647):
            cases.append(("mixed_comparison.doc",
                          [f"gate={str(gate).lower()}", f"a={a}", f"b={b}"],
                          {"chosen": str(a == b if gate else a < b).lower()}))
if len(cases) != 58:
    raise AssertionError("selected Goose DOC scalar boundary matrix is wrong")

for index, (source, args, expected) in enumerate(cases):
    fixture = sources / source
    cpu = invoke(index, "cpu", fixture, args)
    gpu = invoke(index, "gpu", fixture, args)
    observed = results(gpu)
    if not observed or observed != results(cpu):
        raise AssertionError(f"GPU/CPU DOC result mismatch in case {index}")
    if any(observed.get(key) != value for key, value in expected.items()):
        raise AssertionError(f"Independent DOC Boolean oracle mismatch in case {index}")
    if "DOC_GOOSE_SELECTED_GPU_DEVICE: backend=vulkan" not in gpu or \
       "DOC_GOOSE_SELECTED_DOC_GPU_PASS:" not in gpu:
        raise AssertionError(f"no native SDL3 GPU execution proof for case {index}")

for n, source in enumerate(("boolean_diamond.doc", "boolean_network.doc",
                            "integer_equality.doc", "integer_ordering.doc",
                            "gpu_arithmetic_chain.doc",
                            "typed_arithmetic.doc",
                            "gpu_nested_arithmetic.doc",
                            "parallel_frontier.doc"), start=58):
    fixture = sources / source
    cpu = invoke(n, "cpu", fixture, [])
    gpu = invoke(n, "gpu", fixture, [])
    if not results(cpu) or results(cpu) != results(gpu):
        raise AssertionError(f"multi-node or ordering DOC GPU mismatch {source}")
    if "DOC_GOOSE_SELECTED_DOC_GPU_PASS:" not in gpu:
        raise AssertionError(f"source-driven GPU stages missing in {source}")
    if source == "gpu_arithmetic_chain.doc":
        expected={"sum":"11","twice":"22","diff":"18","chosen":"true"}
        if any(results(gpu).get(key)!=value for key,value in expected.items()):
            raise AssertionError("derived arithmetic disagrees with independent oracle")
    if source == "typed_arithmetic.doc":
        expected={"sum":"5","delta":"-1","product":"-5",
                  "equal":"false","chosen":"-5","confirm":"false"}
        if any(results(gpu).get(key)!=value for key,value in expected.items()):
            raise AssertionError("full typed arithmetic DAG disagrees with oracle")
    if source == "parallel_frontier.doc":
        expected={"p000":"false","p127":"false","folded":"true"}
        if any(results(gpu).get(key)!=value for key,value in expected.items()):
            raise AssertionError("independent wide DOC GPU frontier oracle mismatch")
        if "DOC_GOOSE_GPU_FRONTIER_DISPATCH: states=128 workgroups=2" not in gpu:
            raise AssertionError("wide Goose source GPU did not launch two workgroups")
    if source == "gpu_nested_arithmetic.doc":
        expected={"sum":"8","chosen":"true","branched":"4","ok":"false"}
        if any(results(gpu).get(key)!=value for key,value in expected.items()):
            raise AssertionError("nested arithmetic disagrees with independent oracle")

# Host-orchestrated finite recurrence still GPU-computes every derived
# state on every epoch. Compare the identical authored DOC source to native
# Goose CPU recurrence and an independent epoch-by-epoch state oracle.
recurrent=sources/"recurrence_halt.doc"
for offset,mode in enumerate((["--through=3","index=successor"],
                              ["--until=halt","--max-epochs=5","index=successor"],
                              ["--through=3","index=successor","--fact=1:step=2"])):
    cpu=invoke(120+offset*2,"cpu",recurrent,mode)
    gpu=invoke(121+offset*2,"gpu",recurrent,mode)
    a=stable_epochs(cpu)
    b=stable_epochs(gpu)
    if len(a)!=4 or a!=b:
        raise AssertionError("GPU recurrence epochs differ from native Goose CPU")
    if gpu.count("DOC_GOOSE_SELECTED_DOC_GPU_PASS: 2 GPU-dispatched states")!=4:
        raise AssertionError("Missing exactly four GPU recurrence epoch dispatches")
    expected_indices=[0,1,3,4] if offset==2 else [0,1,2,3]
    for epoch,values in b:
        if values.get("index")!=str(expected_indices[epoch]):
            raise AssertionError("Independent DOC recurrent index oracle mismatch")
        step=2 if offset==2 and epoch==1 else 1
        if values.get("step")!=str(step):
            raise AssertionError("DOC recurrence fact/default authority mismatch")
        if values.get("successor")!=str(expected_indices[epoch]+step):
            raise AssertionError("GPU derived recurrence successor is wrong")
        if values.get("halt")!=str(expected_indices[epoch]==3).lower():
            raise AssertionError("GPU derived recurrence halt is wrong")
    if offset==1 and "DOC_RECURRENCE_HALT: 3" not in gpu:
        raise AssertionError("GPU requested halt was not observed")
for case,args in enumerate((
    ["--through=2","index=successor","--fact=1:index=7"],
    ["--through=2","step=halt"],
),start=128):
    bad=invoke(case,"gpu",recurrent,args,ok=False)
    if "DOC_GOOSE_SELECTED_GPU_DEVICE:" in bad or stable_epochs(bad):
        raise AssertionError("Invalid GPU recurrence published a state")

# Normal DOC invocations must default to CPU on the same SDL3-enabled
# executable; merely omitting --backend=gpu must never select the GPU or the
# legacy static operator catalog. The source language is unchanged.
for n,(source,args) in enumerate([
    ("boolean_staged.doc", []),
    ("mixed_comparison.doc", ["gate=true","a=-1","b=0"]),
    ("typed_arithmetic.doc", []),
],start=80):
    fixture=sources/source
    actual=subprocess.run([binary,str(fixture),*args],capture_output=True,
                          text=True,errors="replace",env=os.environ.copy())
    explicit=invoke(n,"cpu",fixture,args)
    (root/f"{n:03}-default.stdout").write_text(actual.stdout)
    (root/f"{n:03}-default.stderr").write_text(actual.stderr)
    if actual.returncode or results(actual.stdout)!=results(explicit) or not results(actual.stdout):
        raise AssertionError("Goose selected-runtime CPU default broken for "+source)
    if "DOC_GOOSE_SELECTED_GPU_DEVICE:" in actual.stdout or \
       "DOC_GOOSE_SELECTED_DOC_GPU_PASS:" in actual.stdout:
        raise AssertionError("GPU incorrectly admitted when CPU was selected by default")
print("DOC_GOOSE_SOURCE_CPU_DEFAULT_PASS: 3 authored source executions")

nested = root / "unproved-deep-arithmetic.doc"
deep="a"
for _ in range(13):
    deep=f"add(a,{deep})"
nested.write_text("source a: int = 2\n"
                  f"derive total: int (a) = {deep}\n")
wide_literal = root / "unproved-nested-literal.doc"
wide_literal.write_text("source a: int = 2\n"
                        "derive total: int (a) = add(a,mul(a,5))\n")
invalid = [
    ("too-many-arithmetic-ops", nested, []),
    ("nested-input-too-wide", sources / "gpu_nested_arithmetic.doc", ["a=5"]),
    ("nested-literal-too-wide", wide_literal, []),
    ("wide-i64", sources / "mixed_comparison.doc", ["a=2147483648"]),
    ("duplicate-batch", sources / "boolean_staged.doc", ["a=true", "a=false"]),
    ("invalid-recurrence-epoch-cap", sources / "boolean_conditional.doc", ["--through=-1"]),
    ("wide-arithmetic-input", sources / "gpu_arithmetic_chain.doc", ["a=32768"]),
    ("intermediate-too-wide", sources / "gpu_arithmetic_chain.doc",
     ["a=32767","b=32767"]),
]
for n, (label, fixture, args) in enumerate(invalid, start=90):
    gpu = invoke(n, "gpu", fixture, args, ok=False)
    if "DOC_GOOSE_SELECTED_DOC_GPU_PASS:" in gpu:
        raise AssertionError(f"unsupported {label} falsely claimed GPU execution")
    if results(gpu):
        raise AssertionError(f"unsupported {label} leaked a partial DOC published state")

empty = root / "only-source.doc"
empty.write_text("source a: bool = true\n")
if results(invoke(100,"gpu",empty,[],ok=False)):
    raise AssertionError("empty GPU graph leaked published state")
effect = root / "blocked-effect.doc"
effect.write_text('effect a: int = read("missing.txt")\nderive ok: bool (a) = eq(a,0)\n')
if results(invoke(101,"gpu",effect,[],ok=False)):
    raise AssertionError("GPU effect rejection leaked published state")
auto=subprocess.run([binary,str(sources/"boolean_staged.doc"),"--backend=auto"],
                    capture_output=True,text=True,errors="replace")
if auto.returncode==0 or results(auto.stdout) or \
   "DOC_GOOSE_SELECTED_DOC_GPU_PASS:" in auto.stdout:
    raise AssertionError("Goose accepted automatic backend or published invalid result")

summary = {
    "matrix_oracle_gpu_cases": 58,
    "other_source_graphs": 8,
    "strict_rejection_cases": 11,
    "source_cpu_default_cases": 3,
    "atomic_negative_publications": 10,
    "recurrent_gpu_stable_epochs": 12,
    "recurrent_gpu_strict_rejections": 2,
    "software_gpu_backend": "SDL3 Vulkan (Mesa; not physical hardware proof)",
    "source_runtime": "Goose independently implemented compute, not Rust",
}
(root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print("DOC_GOOSE_SELECTED_SOURCE_GPU_MATRIX_PASS: 58 oracle cases, 8 DAG/arithmetic fixtures, 11 strict rejections, 3 CPU defaults")
print("DOC_GOOSE_SELECTED_GPU_RECURRENCE_PASS: 12 GPU-derived stable epochs")
