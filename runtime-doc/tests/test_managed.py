#!/usr/bin/env python3
"""Differential test driver; all DOC analysis and C emission are in DOC."""
import argparse, os, subprocess, tempfile, pathlib, random, re
from test_general import positive, negative

ROOT=pathlib.Path(__file__).resolve().parent.parent

def run(cmd, cwd, timeout=180):
    return subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,text=True,timeout=timeout,env=dict(os.environ,DOC_REGION_METRICS='1',ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1'))

def emit(cmd,src,cwd):
    r=run([*cmd,'--demand=code','input=['+','.join(map(str,src.encode()))+']'],cwd)
    assert r.returncode==0 and r.stdout.startswith('code: '),(src[:120],r.stderr)
    return r.stdout[len('code: '):]

def build(code,cwd,name,sanitize=True):
    c=cwd/(name+'.c');exe=cwd/name;c.write_text(code)
    flags=['-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie'] if sanitize else ['-fsanitize=undefined','-fno-sanitize-recover=all']
    r=run(['cc','-std=gnu11','-O1',*flags,'-I',ROOT/'runtime',c,'-o',exe],cwd)
    assert r.returncode==0,(name,r.stderr[:4000]);return exe

def compare(ref,exe,args,cwd):
    a=run([*ref,*args],cwd);b=run([exe,*args],cwd)
    assert (a.returncode==0)==(b.returncode==0),(args,a.stderr,b.stderr)
    assert a.stdout==b.stdout,(args,a.stdout,b.stdout)
    assert not any(x in b.stderr for x in ('AddressSanitizer','runtime error:','LeakSanitizer')),b.stderr
    if b.returncode==0:assert 'DOC11_REGIONS: live=0 ' in b.stderr,b.stderr

def bundle(parts):
    # Explicit fixture assembly, not an independent import resolver.
    return '\n'.join('\n'.join(l for l in (ROOT/f).read_text().splitlines() if not l.startswith('import ')) for f in parts)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',required=True,type=pathlib.Path);ap.add_argument('--source',required=True,type=pathlib.Path);ap.add_argument('--native',required=True,type=pathlib.Path);ap.add_argument('--evidence',required=True,type=pathlib.Path);a=ap.parse_args()
    ref=a.reference.resolve();source=a.source.resolve();native=a.native.resolve();evidence=a.evidence.resolve();evidence.mkdir(parents=True,exist_ok=True)
    good=[s for s,_ in positive]+[
      'fn discard(x)=7\nderive a:int()=discard(get(empty(),0))',
      'fn choose(c,x,y)=if(c,x,y)\nderive a:int()=choose(true,3,quot(1,0))',
      'source a:text="héllo??/"\nderive b:text(a)=concat(a,text("é"))',
      'source a:text="a\x00b"\nderive b:ints(a)=utf8_bytes(a)',
      'source xs:ints=[3,7,-1]\nderive a:ints(xs)=remove_at(xs,1)\nderive b:ints(a)=tail(a)\nderive c:maybe_int(b)=try_get(b,1)\nderive d:int(c)=unwrap_or(c,17)',
      'source a:int=-5\nderive b:int(a)=bit_or(a,2)\nderive c:int(b)=bit_xor(b,7)\nderive d:int(c)=bit_not(c)\nderive e:int(d)=shift_right(d,3)\nderive f:int(e)=rem(e,17)',
      'source a:ints=[]\nderive b:ints(a)=recur(a,x,eq(len(x),2000),append(x,1))\nderive c:int(b)=len(b)',
      'source a:int=3\nderive b:int(a)=mul(a,2)\nderive fault:int()=get(empty(),0)',
    ]
    rng=random.Random(1107)
    for i in range(12):
        x=rng.randrange(10**30,10**35);y=rng.randrange(10**10,10**20)
        good.append(f'source a:nat={x}\nsource b:nat={y}\nderive c:nat(a,b)=add(a,b)\nderive d:nat(c,b)=sub(c,b)\nderive e:nat(d,b)=mul(d,b)\nderive f:bool(e,d)=lt(d,e)')
    faults=['derive a:int()=add(9223372036854775807,1)','derive a:int()=quot(-9223372036854775808,-1)','derive a:int()=get(empty(),0)','derive a:nat()=sub(nat(0),nat(1))','derive a:text()=utf8_text(append(empty(),255))','derive a:int()=shift_left(1,64)','source a:ints=[1]\nderive b:ints(a)=slice(a,0,2)']
    specs=[('lexer',['compiler/lexer_core.doc','compiler/lexer.doc'],'tokens'),('parser',['compiler/lexer_core.doc','compiler/parser_core.doc','compiler/parser.doc'],'syntax'),('scalar',['compiler/lexer_core.doc','compiler/parser_core.doc','compiler/common_core.doc','compiler/scalar_core.doc','compiler/scalar.doc'],'code'),('repair',['runtime/repair_core.doc','runtime/repair_plan.doc'],'after_frontier')]
    with tempfile.TemporaryDirectory() as tmp:
        cwd=pathlib.Path(tmp);fixture=cwd/'program.doc';count=0
        for compiler in ([ref,source],[native]):
            for src in good+faults:
                fixture.write_text(src);exe=build(emit(compiler,src,cwd),cwd,'test')
                compare([ref,fixture],exe,[],cwd);count+=1
                if 'derive fault:int()' in src:compare([ref,fixture],exe,['--demand=b','a=19'],cwd);count+=1
            for src in negative:
                r=run([*compiler,'--demand=code','input=['+','.join(map(str,src.encode()))+']'],cwd)
                assert r.returncode!=0 and not r.stdout.strip(),(src,r.stdout,r.stderr)
        for name,parts,target in specs:
            src=bundle(parts);code=emit([native],src,cwd);exe=build(code,cwd,name,False)
            args=['--demand='+target]
            if name!='repair':args+=['input=['+','.join(map(str,b'source x:int=7\nderive y:int(x)=add(x,2)'))+']']
            compare([ref,ROOT/parts[-1]],exe,args,cwd)
            (evidence/(name+'-rebuilt.c')).write_text(code)
            (evidence/(name+'-rebuilt')).write_bytes(exe.read_bytes())
        # Demand proves a failed unrelated derive is not evaluated; bad inputs
        # do not publish; a 2,000-step region carry is reclaimed on success.
    print(f'DOC11_MANAGED_PASS: {count} native comparisons, {len(negative)} invalid sources per compiler path, {len(specs)} rebuilt compiler/runtime fixtures; ASan/UBSan, live=0')
if __name__=='__main__':main()
