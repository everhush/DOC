#!/usr/bin/env python3
"""Test oracle/driver only: DOC performs parsing, typing and C generation."""
import argparse
import os
import random
import subprocess
import tempfile
from pathlib import Path


def run(cmd, cwd, workers=1):
    return subprocess.run(cmd, cwd=cwd, env={**os.environ, 'DOC_WORKERS':str(workers)}, capture_output=True, text=True, timeout=60)


def compile_doc(cmd, data, cwd, workers):
    return run([*cmd,'--demand=code','input=['+','.join(map(str,data))+']'],cwd,workers)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reference',type=Path,required=True); ap.add_argument('--source',type=Path,required=True); ap.add_argument('--native',type=Path); args=ap.parse_args()
    reference=str(args.reference.resolve())
    commands=[[reference,str(args.source.resolve())]]
    if args.native: commands.append([str(args.native.resolve())])
    valid=[(b'source a: int = 2\nsource b: bool = true\nderive x: int (a,b) = if(b,add(a,1),mul(a,7))\nderive ok: bool (x) = eq(x,3)\n','a: 2\nb: true\nx: 3\nok: true\n'),(b'source a: int = -9223372036854775808\nderive b: int (a) = add(a,1)','a: -9223372036854775808\nb: -9223372036854775807\n'),(b'source a: int = +0007\nderive b: int (a) = sub(a,-0008)','a: 7\nb: 15\n'),(b'derive a: int () = if(true,1,add(9223372036854775807,1))','a: 1\n'),(b'derive a: int () = if(false,mul(-9223372036854775808,-1),-1)','a: -1\n'),(b'source a: bool = false\nderive b: bool (a) = if(a,eq(1,2),le(-1,0))','a: false\nb: true\n'),(b'derive a: int () = 1\nderive b: int (a) = a','a: 1\nb: 1\n'),(b'source _Bool: int = 9\nderive main: int (_Bool) = _Bool','_Bool: 9\nmain: 9\n'),(b'source x: int = 3\nderive y: int (x) = add(x,x)\nderive z: bool (y,x) = lt(x,y)','x: 3\ny: 6\nz: true\n')]
    rng=random.Random(11)
    for _ in range(16):
        a,b,c=(rng.randrange(-1000,1000) for _ in range(3)); s=f'source a: int = {a}\nsource b: int = {b}\nderive sum: int (a,b) = add(a,b)\nderive cmp: bool (a,b) = le(a,b)\nderive final: int (sum,cmp) = if(cmp,mul(sum,{c}),sub(sum,{c}))'; out=f'a: {a}\nb: {b}\nsum: {a+b}\ncmp: {str(a<=b).lower()}\nfinal: {(a+b)*c if a<=b else a+b-c}\n'; valid.append((s.encode(),out))
    invalid=[b'derive x: int (x) = x',b'source a: int = - 1',b'source a: int = 3\nderive b: int (a,a) = a',b'source a: int = 3\nsource a: int = 4',b'source a: int = 3\nderive b: int () = a',b'source a: bool = false\nderive b: int (a) = add(a,1)',b'source a: int = 9223372036854775808',b'source a: int = -9223372036854775809',b'derive a: int () = add(1,2,3)',b'derive a: int () = if(true,1,false)',b'derive a: int () = add()',b'derive a: bool () = eq(true,1)',b'derive a: int () = lt(1,2)',b'source a: bool = 0',b'source x: int = add(1,2)',b'derive a: int () = add(1,)',b'derive a: int () = missing(1,2)',b'derive b: int (a) = a\nsource a: int = 1']
    unsupported=[b'',b'source n: nat = 123',b'source xs: ints = [1,2]',b'source t: text = "hi"',b'fn f(a) = add(a,1)\nderive a: int () = f(1)',b'import absent.doc',b'native region a: u8 plain']
    faults=[b'source x: int = 9223372036854775807\nderive y: int (x) = add(x,1)',b'derive x: int () = sub(-9223372036854775808,1)',b'derive x: int () = mul(-9223372036854775808,-1)']
    with tempfile.TemporaryDirectory(prefix='doc11-scalar-') as tmp:
        cwd=Path(tmp); source=cwd/'program.doc'; out=cwd/'out.c'; exe=cwd/'program'; seen={}
        for command in commands:
            for data,expected in valid+[(d,None) for d in faults]:
                source.write_bytes(data)
                ref=run([reference,str(source)],cwd)
                if expected is None: assert ref.returncode and not ref.stdout,(data,ref.stdout,ref.stderr)
                else: assert ref.returncode==0 and ref.stdout==expected,(data,ref.stdout,expected,ref.stderr)
                for workers in (1,4):
                    result=compile_doc(command,data,cwd,workers)
                    assert not result.returncode and result.stdout.startswith('code: '),(data,result.stderr)
                    code=result.stdout.removeprefix('code: ')
                    assert code==seen.setdefault(data,code),'nondeterministic C output'
                    out.write_text(code)
                    cc=run(['cc','-std=c11','-O2','-fsanitize=undefined','-fno-sanitize-recover=all',str(out),'-o',str(exe)],cwd)
                    assert not cc.returncode,(cc.stderr,code)
                    # The target executable requires neither DOC source nor compiler.
                    source.unlink(missing_ok=True); out.unlink()
                    actual=run([str(exe)],cwd)
                    if expected is None: assert actual.returncode and not actual.stdout,(data,actual.stdout,actual.stderr)
                    else: assert not actual.returncode and actual.stdout==expected,(data,actual.stdout,actual.stderr)
            for data in invalid+unsupported:
                result=compile_doc(command,data,cwd,1)
                assert result.returncode and not result.stdout.startswith('code: '),(data,result.stdout,result.stderr)
    print(f'DOC11_SCALAR_PASS: {len(valid)} positive, {len(faults)} runtime-fault, {len(invalid)} invalid, {len(unsupported)} unsupported, {len(commands)} compiler paths, workers=1/4, UBSan')

if __name__=='__main__': main()
