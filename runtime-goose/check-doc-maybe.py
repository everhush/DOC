#!/usr/bin/env python3
"""Independent maybe_int / safe-index oracle, never a DOC interpreter."""
import random,subprocess,sys
from pathlib import Path
rust,goose,logs=sys.argv[1:]
root=Path(logs);root.mkdir(parents=True,exist_ok=True)
file="runtime-rust/examples/safe_index.doc"
rng=random.Random(19741)
cases=0
arrays=[[4,-5,9],[],[-2**63,2**63-1],[0]]
arrays += [[rng.randrange(-10000,10001) for _ in range(rng.randrange(0,35))]
           for _ in range(100)]
for xs in arrays:
    indexes={-3,-1,0,1,2,len(xs)-1,len(xs),len(xs)+1,2**63-1}
    for i in indexes:
        v=xs[i] if 0<=i<len(xs) else None
        expected={
            "looked":f"some({v})" if v is not None else "none",
            "value":str(v if v is not None else 42),
            "absent":str(v is None).lower(),
            "preferred":f"some({v})" if v is not None else "none",
            "actual":str(v if v is not None else -1),
        }
        representation="["+",".join(map(str,xs))+"]"
        for binary in (rust,goose):
            cmd=[binary,file,f"xs={representation}",f"index={i}"]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
            if p.returncode:raise AssertionError(f"{cmd}: {p.stderr}")
            actual={}
            for line in p.stdout.splitlines():
                if ":" not in line:continue
                name,raw=line.split(":",1)
                if name in expected:actual[name]=raw.strip()
            if actual!=expected:raise AssertionError(
                f"{binary} xs={xs} index={i}: {actual} != {expected}")
            cases+=1
# Demonstrate option source authority update, not just computed values.
for binary in (rust,goose):
    p=subprocess.run([binary,file,"prior=some(-7)","index=-1"],
                     capture_output=True,text=True,timeout=15)
    if p.returncode or "actual: -7" not in p.stdout:
        raise AssertionError(f"{binary} option source update failed")
    cases+=1
for invalid in (
    "source x: maybe_int = some(9223372036854775808)\n",
    "source x: maybe_int = nil\n",
    "source xs: ints = [1]\nderive bad: int (xs) = unwrap_or(xs,3)\n",
):
    path=root/"maybe-invalid.doc";path.write_text(invalid)
    for binary in (rust,goose):
        p=subprocess.run([binary,str(path)],capture_output=True,timeout=20)
        if p.returncode==0:raise AssertionError(f"{binary} accepted invalid option source")
        cases+=1
print(f"DOC_NATIVE_MAYBE_INT_PASS: {cases} independent safety/result cases")
(root/"doc-maybe-int.log").write_text(
    f"DOC_NATIVE_MAYBE_INT_PASS: {cases} independent safety/result cases\n")
