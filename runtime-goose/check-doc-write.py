#!/usr/bin/env python3
"""Explicit output-effect byte oracle. Python is never a DOC interpreter."""
import subprocess,sys,tempfile
from pathlib import Path
rust,goose,logdir=sys.argv[1:]
cases=0
with tempfile.TemporaryDirectory(prefix="doc_output_") as tmp:
    root=Path(tmp)
    (root/"data").mkdir()
    (root/"read.txt").write_text("-23\n")
    examples=[
        ("int","source a: int = 7\nderive out: int (a) = add(a,1)\n","8\n"),
        ("nat","source a: nat = 9999999999999999999999999999999999999999\n"
               "derive out: nat (a) = add(a,nat(1))\n",
               "10000000000000000000000000000000000000000\n"),
        ("ints","source a: ints = [1,4]\nderive out: ints (a) = append(a,-3)\n",
                "[1,4,-3]\n"),
        ("bool","source a: bool = true\nderive out: bool (a) = eq(a,true)\n",
                "true\n"),
        ("maybe","source a: ints = [8]\n"
                 "derive out: maybe_int (a) = try_get(a,0)\n",
                 "some(8)\n"),
        ("effect","effect a: int = read(\"read.txt\")\n"
                  "derive out: int (a) = mul(a,2)\n","-46\n"),
    ]
    for name,source,expected in examples:
        program=root/f"{name}.doc";program.write_text(source)
        destination=f"data/{name}.txt"
        for runtime in (rust,goose):
            p=subprocess.run([runtime,str(program),f"--emit=out:{destination}"],
                             capture_output=True,text=True,timeout=20)
            if p.returncode:
                raise AssertionError(f"{runtime} output failed: {p.stderr}")
            if "DOC_EFFECT_WRITE_PASS:" not in p.stdout:
                raise AssertionError("DOC success marker missing")
            observed=(root/destination).read_text()
            if observed!=expected:
                raise AssertionError(f"{runtime}/{name}: {observed!r}!={expected!r}")
            cases+=1
    # A failing candidate cannot overwrite an earlier successfully
    # published file. Check both implementations and path policy.
    program=root/"overflow.doc"
    program.write_text("source a: int = 9223372036854775807\n"
                       "derive out: int (a) = add(a,1)\n")
    protected=root/"data"/"protected.txt"
    protected.write_text("OLD\n")
    for runtime in (rust,goose):
        fail=subprocess.run([runtime,str(program),"--emit=out:data/protected.txt"],
                            capture_output=True,text=True,timeout=20)
        if fail.returncode==0 or "DOC_EFFECT_WRITE_PASS:" in fail.stdout:
            raise AssertionError(f"{runtime} published a failed DOC candidate")
        if protected.read_text()!="OLD\n":
            raise AssertionError("output effect unexpectedly changed on computation failure")
        cases+=1
        for invalid in ("../outer.txt","/absolute.txt","data/../out.txt",
                        "C:/drive.txt"):
            p=subprocess.run([runtime,str(program),f"--emit=out:{invalid}"],
                             capture_output=True,text=True,timeout=20)
            if p.returncode==0:
                raise AssertionError(f"{runtime} accepted invalid DOC output {invalid}")
            cases+=1
Path(logdir).mkdir(parents=True,exist_ok=True)
Path(logdir,"doc-output-effects.log").write_text(
    f"DOC_NATIVE_WRITE_EFFECT_PASS: {cases} exact file-output checks\n")
print(f"DOC_NATIVE_WRITE_EFFECT_PASS: {cases} exact file-output checks")
