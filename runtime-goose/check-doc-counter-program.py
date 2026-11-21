#!/usr/bin/env python3
"""Independent machine execution oracle for the actual DOC two-counter program."""
import subprocess,sys,random
from pathlib import Path
goose,rust,logdir=sys.argv[1:]
path="runtime-rust/examples/nat_counter_machine.doc"
def invoke(binary,path,*args,good=True):
    p=subprocess.run([binary,path,*args],capture_output=True,text=True,timeout=25)
    if good and p.returncode:
        raise AssertionError(f"{binary}: {p.stdout} {p.stderr}")
    if not good and p.returncode==0:
        raise AssertionError(f"Invalid test unexpectedly succeeded: {binary} {args}")
    return p.stdout
def expected(n,a=3,b=0,halt=False):
    pc=0;out=[]
    for epoch in range(n+1):
        next_a=a if pc!=0 or a==0 else a-1
        next_b=b+1 if pc==1 else b
        next_pc=(2 if a==0 else 1) if pc==0 else 0
        stopped=pc==2
        out.extend((f"epoch: {epoch}",f"pc: {pc}",f"a: {a}",
                    f"b: {b}",f"a_next: {next_a}",f"b_next: {next_b}",
                    f"pc_next: {next_pc}",f"halt: {str(stopped).lower()}"))
        if halt and stopped:
            out.append(f"DOC_RECURRENCE_HALT: {epoch}")
            break
        if epoch==n:break
        pc,a,b=next_pc,next_a,next_b
    return "\n".join(out)+"\n"
cases=0
for n in (0,1,2,3,5,6,7,8,12):
    oracle=expected(n)
    for binary in (rust,goose):
        actual=invoke(binary,path,f"--through={n}",
                      "pc=pc_next","a=a_next","b=b_next")
        assert actual==oracle,(binary,n,actual,oracle)
        cases+=1
for binary in (rust,goose):
    actual=invoke(binary,path,"--until=halt","--max-epochs=20",
                  "pc=pc_next","a=a_next","b=b_next")
    assert actual==expected(20,halt=True),(binary,actual)
    invoke(binary,path,"--until=halt","--max-epochs=5",
           "pc=pc_next","a=a_next","b=b_next",good=False)
    cases+=2
# Demand a finite prefix with a much larger than i64 natural input.
huge="9"*100
with_source=Path(logdir)/"counter-machine-large.doc"
with_source.write_text(Path(path).read_text().replace(
    "source a: nat = 3",f"source a: nat = {huge}"))
for n in (0,1,2,3,10,20,40):
    oracle=expected(n,int(huge))
    for binary in (rust,goose):
        actual=invoke(binary,str(with_source),f"--through={n}",
                      "pc=pc_next","a=a_next","b=b_next")
        assert actual==oracle,(binary,n,actual,oracle)
        cases+=1
out=f"DOC_NATIVE_TWO_COUNTER_PROGRAM_PASS: {cases} cross-runtime oracle checks\n"
Path(logdir,"doc-native-counter-machine.log").write_text(out)
print(out,end="")
