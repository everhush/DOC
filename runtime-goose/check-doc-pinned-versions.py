#!/usr/bin/env python3
"""Prove Goose graph version reader pinning and pool reclamation against
a separately evaluated Rust DOC source oracle. No Python DOC runtime.
"""
from pathlib import Path
import subprocess,sys
rust,goose,logs=sys.argv[1:]
root=Path(logs);root.mkdir(parents=True,exist_ok=True)
base="runtime-rust/examples/versions"
old=f"{base}/pinned_old.doc"
new=f"{base}/pinned_new.doc"
bad=f"{base}/pinned_invalid.doc"
p=subprocess.run([goose,old,f"--replace-pinned={new}"],
                 capture_output=True,text=True,timeout=45)
if p.returncode:
    raise AssertionError(
        "Goose pinned graph replacement failed\nstdout:\n"
        +p.stdout+"\nstderr:\n"+p.stderr)
marker="DOC_GOOSE_GRAPH_PINNED_REPLACE_PASS: 4 readers, full pool compaction"
assert p.stdout.count(marker)==1,p.stdout
assert p.stdout.count("DOC_GRAPH_GENERATION: 0")==1,p.stdout
assert p.stdout.count("DOC_GRAPH_GENERATION: 1")==1,p.stdout
blocks=p.stdout.split("DOC_GRAPH_GENERATION: ")
old_block=blocks[1].split("DOC_GOOSE_GRAPH_PINNED_REPLACE_PASS:")[0]
new_block=blocks[2]
want_old={"n":"9"*50,"items":"[3,5,8]","msg":"Hello 世界",
          "next":"1"+"0"*50,"size":"3","joined":"Hello 世界?"}
want_new={"n":"9"*50,"items":"[3,5,8]","msg":"Hello 世界",
          "next":"1"+"0"*49+"1","size":"4","joined":"Hello 世界!"}
def expected_lines(block,expect):
    for k,v in expect.items():
        if f"{k}: {v}" not in block:
            raise AssertionError(f"missing {k}={v!r} in {block!r}")
expected_lines(old_block,want_old)
expected_lines(new_block,want_new)
# Rust's native finite graph replacement must produce identical observations.
r=subprocess.run([rust,old,f"--replace={new}"],capture_output=True,text=True,
                 timeout=30)
if r.returncode:
    raise AssertionError("Rust graph replacement invalid: "+r.stderr)
rb=r.stdout.split("DOC_GRAPH_GENERATION: ")
expected_lines(rb[1],want_old)
expected_lines(rb[2],want_new)
for binary,flag in ((goose,"--replace-pinned="),(rust,"--replace=")):
    bad_run=subprocess.run([binary,old,flag+bad],capture_output=True,text=True,
                           timeout=30)
    if bad_run.returncode==0:
        raise AssertionError("failed candidate incorrectly accepted")
    if "DOC_GRAPH_GENERATION: 1" in bad_run.stdout:
        raise AssertionError("failed graph generation was published")
    if "DOC_GRAPH_GENERATION: 0" not in bad_run.stdout:
        raise AssertionError("prior stable graph observation absent")
print("DOC_GOOSE_PINNED_GRAPH_VERSION_PASS: four live readers and all data pools")
(root/"goose-pinned-versions.log").write_text(
    "DOC_GOOSE_PINNED_GRAPH_VERSION_PASS: 4 readers across version retirement\n")
