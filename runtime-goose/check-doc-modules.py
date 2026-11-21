#!/usr/bin/env python3
"""Independent pure module and source-level import oracle for both hosts."""
import random,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
gen=random.Random(8927)
cases=0
for kind in ("int","nat"):
    path=f"runtime-rust/examples/module_clamp{'' if kind=='int' else '_nat'}.doc"
    values=[(0,0,0),(3,2,7),(17,2,7)]
    if kind=="int":
        values.extend((gen.randrange(-(2**63),2**63),
                       gen.randrange(-1000,0),
                       gen.randrange(0,1000)) for _ in range(80))
    else:
        values.extend((gen.randrange(10**200),
                       gen.randrange(10**30),
                       10**100+gen.randrange(10**20)) for _ in range(80))
    for x,lo,hi in values:
        if hi<lo:lo,hi=hi,lo
        expected=min(max(x,lo),hi)
        for runtime in (rust,goose):
            p=subprocess.run([runtime,path,f"x={x}",f"lo={lo}",f"hi={hi}"],
                             capture_output=True,text=True,timeout=15)
            if p.returncode:
                raise AssertionError(f"{runtime} module source failed: {p.stderr}")
            vals={}
            for line in p.stdout.splitlines():
                if ":" in line:
                    name,value=line.split(":",1)
                    if name in ("bounded","amplified"):vals[name]=int(value.strip())
            if vals!={"bounded":expected,"amplified":expected*4}:
                raise AssertionError(f"{runtime}: module oracle mismatch {vals}")
            cases+=1
# Fail closed: only pure fn declarations in imported source, no imports in
# the module, no duplicate name authorities, and no missing module.
bad_entries={
    "missing":"import missing_module.doc",
    "absolute":"import /tmp/private.doc",
    "parent":"import ../secret.doc",
    "dot":"import ./lib/ordering.doc",
    "drive":"import C:/Windows/secret.doc",
    "backslash":"import lib\\ordering.doc",
    "duplicate":"import lib/ordering.doc\nimport lib/ordering.doc",
}
for name,head in bad_entries.items():
    bad=root/f"module-bad-{name}.doc"
    bad.write_text(head+"\nsource a: int = 1\n")
    for runtime in (rust,goose):
        p=subprocess.run([runtime,str(bad)],capture_output=True,timeout=15)
        if p.returncode==0:
            raise AssertionError(f"{runtime} accepted invalid module {name}")
        cases+=1
# A module containing source declarations must never be imported.
evil=root/"module-eager.doc"
evil.write_text("source secret: int = 1\n")
bad=root/"module-bad-eager.doc"
bad.write_text("import module-eager.doc\nsource a: int = 1\n")
for runtime in (rust,goose):
    p=subprocess.run([runtime,str(bad)],capture_output=True,timeout=15)
    if p.returncode==0:
        raise AssertionError(f"{runtime} imported effectful/data-bearing module")
    cases+=1
print(f"DOC_NATIVE_MODULES_PASS: {cases} source-level module oracle checks")
(root/"doc-native-modules.log").write_text(f"DOC_NATIVE_MODULES_PASS: {cases}\n")
