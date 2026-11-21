#!/usr/bin/env python3
"""Independent arbitrary-size integer oracle; CI only, not DOC runtime."""
import random,subprocess,sys,time
from pathlib import Path
rust,goose,logdir=sys.argv[1:]
files=[f"runtime-rust/examples/counter_{x}.machine" for x in ("transfer","loop","branch")]
def expected(file,prefix,a,b):
    code=[]
    for line in Path(file).read_text().splitlines():
        t=line.split("#")[0].split()
        if t:
            assert int(t[0])==len(code)
            code.append(t[1:])
    vals={"a":int(a),"b":int(b)};pc=0;lines=[]
    for epoch in range(prefix+1):
        lines+= [f"epoch: {epoch}",f"pc: {pc}",f"a: {vals['a']}",f"b: {vals['b']}"]
        op=code[pc]
        if op[0]=="halt":
            lines.append(f"DOC_COUNTER_HALT: {epoch}");break
        if epoch==prefix:break
        if op[0]=="inc":
            vals[op[1]]+=1;pc=int(op[2])
        elif vals[op[1]]:
            vals[op[1]]-=1;pc=int(op[2])
        else:pc=int(op[3])
    return "\n".join(lines)+"\n"
def invoke(binary,file,prefix,a,b):
    cmd=[binary,file,f"--prefix={prefix}",f"--a={a}",f"--b={b}"]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
    assert p.returncode==0,(cmd,p.stdout,p.stderr)
    return p.stdout
cases=0
for f in files:
    for prefix in (0,1,2,3,5,13,30):
        for a,b in ((0,0),(1,0),(4,5),(10,13),(10**20+9,10**30+1),
                    (10**100-1,10**90+7)):
            result=expected(f,prefix,a,b)
            for executable in (rust,goose):
                assert invoke(executable,f,prefix,a,b)==result,(f,prefix,a,b,executable)
            cases+=1
rand=random.Random(23347)
for _ in range(50):
    f=rand.choice(files);prefix=rand.randrange(30)
    a=rand.randrange(10**rand.randrange(1,100))
    b=rand.randrange(10**rand.randrange(1,100))
    result=expected(f,prefix,a,b)
    for executable in (rust,goose):
        assert invoke(executable,f,prefix,a,b)==result
    cases+=1
for executable in (rust,goose):
    for args in (("--prefix=-1","--a=1","--b=0"),
                 ("--prefix=bad","--a=1","--b=0"),
                 ("--prefix=2","--a=-1","--b=0"),
                 ("--prefix=2","--a=1","--b=0x1")):
        p=subprocess.run([executable,files[0],*args],capture_output=True,timeout=30)
        assert p.returncode!=0,(executable,args)
huge=10**250-1;timings=[]
for executable in (rust,goose):
    t=time.perf_counter()
    assert invoke(executable,files[1],150,huge,0)==expected(files[1],150,huge,0)
    timings.append(f"{Path(executable).name} 250_digit_prefix=150 wall_ms="
                   f"{(time.perf_counter()-t)*1000:.3f}")
Path(logdir).mkdir(parents=True,exist_ok=True)
result=f"DOC_COUNTER_ARBITRARY_NAT_WITNESS_PASS: {cases} cases\n"+"\n".join(timings)+"\n"
(Path(logdir)/"counter-machine-evidence.log").write_text(result)
print(result,end="")
