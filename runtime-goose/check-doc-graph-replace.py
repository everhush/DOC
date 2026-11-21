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
    if "DOC_GRAPH_GENERATION: 1\na: true\nb: false\nsize: true" not in mismatch.stdout:
        raise AssertionError(f"incorrect role/type incompatible source migration: {binary}")
    cases+=1

# Seeded property-style two-generation differential oracles: values and state
# sets are independently calculated from the DOC source rules below, not from
# either runtime. Every candidate is loaded as a separate, real .doc file.
import random
import tempfile

def parse_generations(output):
    groups={}
    current=None
    for line in output.splitlines():
        if line.startswith("DOC_GRAPH_GENERATION: "):
            current=line.rsplit(" ",1)[-1]
            if current in groups:
                raise AssertionError("duplicate published generation")
            groups[current]={}
        elif current is not None and ": " in line:
            name,value=line.split(": ",1)
            if name in groups[current]:
                raise AssertionError("duplicate published state")
            groups[current][name]=value
    return groups

randomizer=random.Random(0xD0C2026)
with tempfile.TemporaryDirectory(prefix="doc-graph-candidates-") as temp:
    folder=Path(temp)
    for index in range(12):
        a=randomizer.randint(1,500)
        b=randomizer.randint(-500,500)
        extra=randomizer.randint(-500,500)
        old_graph=folder/f"source-{index}.doc"
        old_graph.write_text(
            f"source a: int = {a}\n"
            f"source b: int = {b}\n"
            "derive original: int (a,b) = add(a,b)\n"
        )
        old_observation={"a":str(a),"b":str(b),"original":str(a+b)}
        candidates=[
            ("reordered",(
                f"source b: int = {b+123}\n"
                f"source a: int = {a+456}\n"
                "derive merged: int (a,b) = add(a,b)\n"
                "derive doubled: int (merged) = add(merged,merged)\n"
            ),{"b":str(b),"a":str(a),"merged":str(a+b),
               "doubled":str(2*(a+b))}),
            ("new-source",(
                f"source a: int = {a+654}\n"
                f"source extra: int = {extra}\n"
                f"source b: int = {b+321}\n"
                "derive result: int (a,b,extra) = add(add(a,b),extra)\n"
            ),{"a":str(a),"extra":str(extra),"b":str(b),
               "result":str(a+b+extra)}),
            ("incompatible",(
                "source a: bool = true\n"
                f"source b: int = {b+999}\n"
                "derive selected: bool (a) = eq(a,true)\n"
            ),{"a":"true","b":str(b),"selected":"true"}),
            ("failed",(
                "source a: int = 0\n"
                "derive impossible: int (a) = add(a,9223372036854775807)\n"
            ),None),
        ]
        for label,source,expected_next in candidates:
            candidate=folder/f"{label}-{index}.doc"
            candidate.write_text(source)
            expected={"0":old_observation}
            if expected_next is not None:
                expected["1"]=expected_next
            for runtime_name,binary in (("rust",rust),("goose",goose)):
                observed=subprocess.run(
                    [binary,str(old_graph),f"--replace={candidate}"],
                    capture_output=True,text=True,timeout=30)
                generation=parse_generations(observed.stdout)
                if generation!=expected:
                    raise AssertionError(
                        f"{runtime_name} {label} seed={index} graph mismatch:"
                        f" {generation!r} != {expected!r}\n"
                        f"stderr={observed.stderr[-600:]}")
                if (observed.returncode==0)!=(expected_next is not None):
                    raise AssertionError(
                        f"{runtime_name} {label} unexpected exit status:"
                        f" {observed.returncode}")
                cases+=1

root.joinpath("doc-graph-replacements.log").write_text(
    f"DOC_GRAPH_REPLACEMENT_DUAL_RUNTIME_PASS: {cases} checks\n"
)
print(f"DOC_GRAPH_REPLACEMENT_DUAL_RUNTIME_PASS: {cases} checks")
