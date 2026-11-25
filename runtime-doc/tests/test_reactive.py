#!/usr/bin/env python3
"""Execute the independently generated reactive ELF against the frozen oracle."""
import argparse
import os
import random
import re
import subprocess
import tempfile
from pathlib import Path


def run(cmd, cwd, workers=1):
    return subprocess.run(cmd,cwd=cwd,env={**os.environ,'DOC_WORKERS':str(workers)},capture_output=True,text=True,timeout=60)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--native',type=Path);args=ap.parse_args()
    reference=str(args.reference.resolve());commands=[[reference,str(args.source.resolve())]]
    if args.native:commands.append([str(args.native.resolve())])
    diamond=b'source a: int = 1\nderive unchanged: bool (a) = eq(a,a)\nderive down: bool (unchanged) = unchanged\nderive branch: int (a) = add(a,1)\nderive joined: int (down,branch) = if(down,branch,0)\n'
    fault=b'source a: int = 1\nsource b: int = 9223372036854775807\nderive ok: int (a) = add(a,1)\nderive bad: int (b) = add(b,1)\n'
    two=b'source a: int = 3\nsource b: bool = true\nderive c: int (a,b) = if(b,add(a,1),0)\nderive d: int (a) = mul(a,2)\nderive e: bool (c,d) = le(c,d)\n'
    cases=[(diamond,[([],False,[4]),(['--next','a=2','--next','a=2'],False,[4,3,0]),(['--demand=branch','--next','--demand=joined','--next','--demand=branch','a=3','--next','--demand=joined'],False,[1,3,1,2]),(['--demand=a','--next','--demand=unchanged','--next'],False,[0,1,3])]),(fault,[(['--demand=ok'],False,[1]),(['--demand=ok','--next','--demand=bad'],True,[1]),(['--demand=ok','--next','b=1'],False,[1,1]),([],True,[])]),(two,[(['a=4','b=false','--next','a=4','b=false','--next','a=7'],False,[3,0,3]),(['--next','a=8','a=9'],True,[3]),(['--next','a=8','b=0'],True,[3]),(['--next','c=8'],True,[3]),(['--next','unknown=8'],True,[3]),(['--next','a=9223372036854775808'],True,[3]),(['--demand=unknown'],True,[]),(['--backend=gpu'],True,[]),(['--backend=cpu','a= -7 ','b= false '],False,[3])])]
    wide=('source x: int = 2\n'+''.join(f'derive lane_{i}: int (x) = add(x,{i})\n' for i in range(32))+'derive result: int (lane_0,lane_31) = add(lane_0,lane_31)\n').encode()
    wide_fault=('source x: int = 0\n'+''.join(f'derive lane_{i}: int (x) = add(x,{i if i<31 else 9223372036854775807})\n' for i in range(32))+'derive result: int (lane_0,lane_30) = add(lane_0,lane_30)\n').encode()
    cases.extend([(wide,[(['--next','x=3','--next','x=3'],False,[33,33,0])]),(wide_fault,[(['--next','x=1'],True,[33])])])
    rng=random.Random(1107)
    for i in range(12):
        source=f'source x: int = {rng.randrange(-10,10)}\nsource y: int = {rng.randrange(-10,10)}\n'
        names=['x','y']
        for j in range(6):
            a,b=rng.sample(names,2);name=f'd{j}';source+=f'derive {name}: int ({a},{b}) = {rng.choice(["add","sub","mul"])}({a},{b})\n';names.append(name)
        batches=[]
        for epoch in range(5):
            if epoch: batches.append('--next')
            if rng.randrange(2): batches.append('--demand='+rng.choice(names))
            batches.append(f'{rng.choice(["x","y"])}={rng.randrange(-10,10)}')
        cases.append((source.encode(),[(batches,False,None)]))
    with tempfile.TemporaryDirectory(prefix='doc11-reactive-') as tmp:
        cwd=Path(tmp);source=cwd/'input.doc';cfile=cwd/'out.c';exe=cwd/'program';seen={};checks=0
        for command in commands:
            for data,scenarios in cases:
                # Generate native C twice, through different compiler worker settings.
                for workers in (1,4):
                    result=run([*command,'--demand=code','input=['+','.join(map(str,data))+']'],cwd,workers)
                    assert result.returncode==0 and result.stdout.startswith('code: '),(data,result.stderr)
                    code=result.stdout.removeprefix('code: ')
                    assert code==seen.setdefault(data,code),'nondeterministic reactive compiler output'
                cfile.write_text(code)
                cc=run(['cc','-std=c11','-O2','-pthread','-fsanitize=undefined','-fno-sanitize-recover=all',str(cfile),'-o',str(exe)],cwd)
                assert cc.returncode==0,(cc.stderr,code)
                cfile.unlink()
                for argv,failed,counts in scenarios:
                    source.write_bytes(data)
                    if argv==['--backend=gpu']:
                        expected='';ref_failed=True
                    else:
                        ref=run([reference,str(source),*argv],cwd)
                        expected=ref.stdout;ref_failed=bool(ref.returncode)
                    source.unlink()
                    for workers in ((1,4,8) if data in (wide,wide_fault) else (1,4)):
                        actual=run([str(exe),*argv],cwd,workers)
                        assert ref_failed==failed and bool(actual.returncode)==failed,(data,argv,actual.stderr,ref_failed)
                        assert actual.stdout==expected,(data,argv,actual.stdout,expected,actual.stderr)
                        got=list(map(int,re.findall(r'DOC11_REACTIVE_EVALUATIONS: (\d+)',actual.stderr)))
                        if counts is not None:assert got==counts,(data,argv,got,counts)
                        if data in (wide,wide_fault):
                            markers=re.findall(r'DOC11_PARALLEL_FRONTIER: lanes=32 workers=(\d+)',actual.stderr)
                            if workers==1:assert not markers
                            else:
                                assert len(os.sched_getaffinity(0))>=2,'actual parallel evidence requires two effective CPUs'
                                assert len(markers)==2 and all(int(n)>=2 for n in markers),actual.stderr
                        checks+=1
        print(f'DOC11_REACTIVE_PASS: {len(cases)} graphs, {checks} scenarios, {len(commands)} compiler paths, source-free native repair, demand/cutoff/failure, UBSan')

if __name__=='__main__':main()
