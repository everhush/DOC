#!/usr/bin/env python3
"""Independent graph successor oracle for DOC-authored forward list traversal."""
import random,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
root=Path(logs)
root.mkdir(parents=True,exist_ok=True)
template=Path("runtime-rust/examples/graph_walk.doc").read_text()
seed=random.Random(197507)
cases=0
for length in list(range(1,50))+[64,65,99,128]:
    path=list(range(length))
    seed.shuffle(path)
    links=[-1]*length
    for i,node in enumerate(path):
        links[node]=path[i+1] if i+1<len(path) else -1
    fixture=template.replace("[2,4,-1,1,3]",
        "["+",".join(str(v) for v in links)+"]").replace(
        "source node: int = 0",f"source node: int = {path[0]}")
    doc=root/f"walk-{length}.doc"
    doc.write_text(fixture)
    for binary in (rust,goose):
        p=subprocess.run([binary,str(doc),"--until=halt",
                          f"--max-epochs={length+2}",
                          "node=next_node","hops=next_hops"],
                         capture_output=True,text=True,timeout=30)
        if p.returncode:
            raise AssertionError(f"{binary} graph walk failed: {p.stderr}")
        if f"DOC_RECURRENCE_HALT: {length}" not in p.stdout:
            raise AssertionError(f"{binary} incorrect graph path length {length}")
        hops=[int(line.split(":",1)[1]) for line in p.stdout.splitlines()
              if line.startswith("hops:")]
        node=[int(line.split(":",1)[1]) for line in p.stdout.splitlines()
              if line.startswith("node:")]
        if hops[-1]!=length or node[-1]!=-1:
            raise AssertionError(f"{binary} wrong final DOC graph valuation")
        cases+=1
for mode,links in (("cycle","[0]"),("bad-index","[1]")):
    path=root/f"walk-{mode}.doc"
    path.write_text(template.replace("[2,4,-1,1,3]",links))
    for binary in (rust,goose):
        p=subprocess.run([binary,str(path),"--until=halt","--max-epochs=4",
                          "node=next_node","hops=next_hops"],
                         capture_output=True,timeout=20)
        if p.returncode==0 or b"DOC_RECURRENCE_HALT:" in p.stdout:
            raise AssertionError(f"{binary} accepted invalid/nonhalting graph {mode}")
        cases+=1
print(f"DOC_NATIVE_GRAPH_TRAVERSAL_PASS: {cases} graph/source oracle checks")
(root/"doc-graph-traversal.log").write_text(
    f"DOC_NATIVE_GRAPH_TRAVERSAL_PASS: {cases} graph/source oracle checks\n")
