#!/usr/bin/env python3
"""Explicit typed DOC filesystem effect conformance; no Python runtime."""
import subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
doc="runtime-rust/examples/effect_demo.doc"
raw=10**100-1
expected={
    "count":-23, "incremented":-22,
    "amount":raw,"next_amount":raw+1,"selected":raw+3,"enabled":True
}
cases=0
for binary in (rust,goose):
    p=subprocess.run([binary,doc],capture_output=True,text=True,timeout=20)
    if p.returncode:
        raise AssertionError(f"failed native effect read: {binary}\n{p.stderr}")
    actual={}
    for line in p.stdout.splitlines():
        if ":" in line:
            name,value=line.split(":",1)
            if name in expected:
                actual[name]=(value.strip()=="true") if name=="enabled" else int(value.strip())
    if actual!=expected:
        raise AssertionError(f"{binary}: effect source oracle mismatch: {actual}")
    cases+=1
# Commands below must fail before any successful published observation.
tests={
    "missing":"effect a: int = read(\"not-found.txt\")",
    "wrong-op":"effect a: int = write(\"source.txt\")",
    "absolute":"effect a: int = read(\"/tmp/no.txt\")",
    "parent":"effect a: int = read(\"../outside.txt\")",
    "dot":"effect a: int = read(\"./bad-bool.txt\")",
    "drive":"effect a: int = read(\"C:/Windows/secret.txt\")",
    "bad-bool":"effect a: bool = read(\"bad-bool.txt\")",
    "oversize":"effect a: nat = read(\"too-many.txt\")",
}
(root/"bad-bool.txt").write_text("yes\n")
(root/"too-many.txt").write_text("9"*8193+"\n")
for name,decl in tests.items():
    p=root/f"effect-bad-{name}.doc"
    p.write_text(decl+"\nderive answer: bool (a) = eq(a,a)\n")
    for binary in (rust,goose):
        child=subprocess.run([binary,str(p)],capture_output=True,text=True,timeout=15)
        if child.returncode==0:
            raise AssertionError(f"{binary} accepted invalid effect {name}")
        if "answer:" in child.stdout:
            raise AssertionError(f"{binary} published result after effect failure")
        cases+=1
print(f"DOC_NATIVE_TYPED_READ_EFFECT_PASS: {cases} independent source-effect checks")
(root/"doc-typed-effect.log").write_text(f"DOC_NATIVE_TYPED_READ_EFFECT_PASS: {cases}\n")
