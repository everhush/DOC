#!/usr/bin/env python3
"""Independent two-generation DOC graph CLI oracle for both native runtimes."""
import subprocess,sys
from pathlib import Path
rust,goose,logdir=sys.argv[1:]
root=Path(logdir)
root.mkdir(parents=True,exist_ok=True)
base="runtime-rust/examples/versions"
original=f"{base}/old.doc"
expected={
    "0":{"a":"2","b":"[1,2]","sum":"3","size":"2"},
    "1":{"a":"2","b":"[1,2]","sum":"7","size":"2","double":"14"},
}
cases=0
for binary in (rust,goose):
    p=subprocess.run([binary,original,
                      f"--replace={base}/compatible.doc"],capture_output=True,
                     text=True,timeout=30)
    if p.returncode:
        raise AssertionError(f"{binary} failed valid replacement:\n{p.stderr}")
    generations={}
    which=None
    for line in p.stdout.splitlines():
        if line.startswith("DOC_GRAPH_GENERATION: "):
            which=line.rsplit(" ",1)[1]
            generations[which]={}
        elif which is not None and ": " in line:
            name,v=line.split(": ",1)
            generations[which][name]=v
    if generations != expected:
        raise AssertionError(f"{binary} graph versions: {generations} != {expected}")
    cases+=1
    bad=subprocess.run([binary,original,
                        f"--replace={base}/invalid.doc"],
                       capture_output=True,text=True,timeout=30)
    if bad.returncode==0:
        raise AssertionError("overflowing new graph unexpectedly published")
    if "DOC_GRAPH_GENERATION: 1" in bad.stdout:
        raise AssertionError("partial graph generation was published")
    if "DOC_GRAPH_GENERATION: 0" not in bad.stdout:
        raise AssertionError("old graph observation was missing")
    cases+=1
    mismatch=subprocess.run([binary,original,
                             f"--replace={base}/incompatible.doc"],
                            capture_output=True,text=True,timeout=30)
    if mismatch.returncode:
        raise AssertionError(f"incompatible authority should use new default: {binary}")
    if "DOC_GRAPH_GENERATION: 1\na: true\nb: []\nsize: 0" not in mismatch.stdout:
        raise AssertionError(f"incorrect role/type incompatible source migration: {binary}")
    cases+=1
root.joinpath("doc-graph-replacements.log").write_text(
    f"DOC_GRAPH_REPLACEMENT_DUAL_RUNTIME_PASS: {cases} checks\n"
)
print(f"DOC_GRAPH_REPLACEMENT_DUAL_RUNTIME_PASS: {cases} checks")
