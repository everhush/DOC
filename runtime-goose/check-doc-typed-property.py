#!/usr/bin/env python3
"""Seeded all-types native DOC property/differential conformance, Python oracle."""
import random,subprocess,sys
from pathlib import Path

rust,goose,logdir=sys.argv[1:]
rng=random.Random(220277)
file="runtime-rust/examples/typed_property.doc"
chars=["a","B"," ","ñ","🙂","ह","世界","0","字","ー"]
names=("sum","ordered","extended","result","selected","count",
       "increment","is_zero","prefix","newmsg","bytes","choice")
def normalize(output):
    result={}
    for line in output.splitlines():
        if ": " not in line:continue
        key,value=line.split(": ",1)
        if key in names:result[key]=value
    return result
def verify_case(case):
    x,y,index,seq,n,flag,msg=case
    summed=x+y
    xs=seq+[summed]
    selected=xs[index] if 0<=index<len(xs) else None
    expected={
        "sum":str(summed),
        "ordered":str(x<=y).lower(),
        "extended":"["+",".join(map(str,xs))+"]",
        "result":f"some({selected})" if selected is not None else "none",
        "selected":str(selected if selected is not None else x),
        "count":str(len(xs)),
        "increment":str(n+1),
        "is_zero":str(n==0).lower(),
        "prefix":str(msg.startswith("Hi")).lower(),
        "newmsg":msg+"!",
        "bytes":str(len((msg+"!").encode("utf8"))),
        "choice":str(flag and x<=y).lower(),
    }
    assignments=[f"x={x}",f"y={y}",f"index={index}",
                 "seq=["+",".join(map(str,seq))+"]",
                 f"n={n}",f"flag={str(flag).lower()}",
                 f'msg="{msg}"']
    for binary,env_workers in ((rust,1),(goose,1)):
        p=subprocess.run([binary,file,*assignments],capture_output=True,
                         text=True,encoding="utf8",timeout=20)
        if p.returncode:
            raise AssertionError(f"{binary} typed oracle failed: {p.stderr}")
        observed=normalize(p.stdout)
        if observed!=expected:
            raise AssertionError(f"Typed DOC mismatch {binary}: {observed} != {expected}")
    return 2
cases=0
for case in [
    (-3,5,0,[4,7],10**35-1,True,"Hi 世界"),
    (0,0,-1,[],0,False,""),
    (20,-30,3,[1,2,3],10**250-1,True,"🙂🙂"),
    (-100,100,100,[0],123,False,"हिंदी"),
]:
    cases+=verify_case(case)
for _ in range(900):
    case=(rng.randint(-10**9,10**9),rng.randint(-10**9,10**9),
          rng.randrange(-10,45),
          [rng.randint(-999,999) for _ in range(rng.randrange(0,30))],
          rng.randrange(10**rng.randrange(1,150)),
          bool(rng.randrange(2)),
          "".join(rng.choice(chars) for _ in range(rng.randrange(0,30))))
    cases+=verify_case(case)
for invalid in ("x=true","y=hello","seq=[1,nope]","n=-1",
                "flag=0","msg=no_quotes","index=some(2)"):
    for binary in (rust,goose):
        p=subprocess.run([binary,file,invalid],capture_output=True,text=True,
                         timeout=20)
        if p.returncode==0:
            raise AssertionError(f"{binary} accepted invalid assignment {invalid}")
        if normalize(p.stdout):
            raise AssertionError(f"{binary} published derived values after bad update")
        cases+=1
Path(logdir).mkdir(parents=True,exist_ok=True)
Path(logdir,"doc-typed-property.log").write_text(
    f"DOC_TYPED_PROPERTY_DIFFERENTIAL_PASS: {cases} all-type oracle cases\n"
)
print(f"DOC_TYPED_PROPERTY_DIFFERENTIAL_PASS: {cases} all-type oracle cases")
