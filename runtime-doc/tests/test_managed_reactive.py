#!/usr/bin/env python3
"""Native managed epochs, exact cutoff, worker parity and rollback proof."""
import argparse, os, re, subprocess, tempfile
from pathlib import Path


def run(cmd, cwd, workers=1):
    return subprocess.run([str(x) for x in cmd],cwd=cwd,env={**os.environ,'DOC_WORKERS':str(workers),'DOC_REGION_METRICS':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'},capture_output=True,text=True,timeout=120)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--native',type=Path);ap.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');args=ap.parse_args()
    ref=args.reference.resolve();source=args.source.resolve();commands=[[ref,source]]+([[args.native.resolve()]] if args.native else [])
    lists='source xs:ints=[1,2]\nderive ys:ints(xs)=map_ints(xs,x,add(x,1))\nderive n:int(ys)=len(ys)\nderive first:maybe_int(ys)=try_get(ys,0)\nderive final:int(first,n)=add(unwrap_or(first,0),n)\n'
    strings='source t:text="hi"\nsource n:nat=12345678901234567890\nderive bytes:ints(t)=utf8_bytes(t)\nderive txt:text(bytes)=utf8_text(bytes)\nderive a:nat(n)=mul(n,nat(99))\nderive same:bool(txt,t)=eq(txt,t)\n'
    fault='source xs:ints=[1,2]\nsource x:int=1\nderive vals:ints(xs)=append(xs,5)\nderive first:int(vals,x)=get(vals,x)\n'
    recurrence='source start:ints=[]\nsource n:int=10\nderive result:ints(start,n)=recur(start,x,eq(len(x),n),append(x,1))\nderive size:int(result)=len(result)\n'
    wide='source xs:ints=[1,2]\n'+''.join(f'derive l{i}:ints(xs)=append(xs,{i})\n' for i in range(32))+'derive sum:int(l0,l31)=add(len(l0),len(l31))\n'
    wide_fault='source xs:ints=[0,1]\nsource n:int=0\n'+''.join(f'derive l{i}:ints(xs)=append(xs,{i})\n' for i in range(31))+'derive bad:int(xs,n)=get(xs,n)\n'
    cases=[(lists,[([], [4]),(['--next','xs=[1,2,3]','--next','xs=[1,2,3]'],[4,4,0]),(['--demand=ys','--next','--demand=final','--next','xs=[]'],[1,3,4])]),(strings,[(['--next','t="日本語"','n=999999999999999999999','--next','t="日本語"'],[4,4,0]),(['--demand=a','--next','--demand=same','t="hello"'],[1,3])]),(fault,[(['--next','xs=[]','x=9'],[2]),(['--next','xs=[]','x=0'],[2,2]),(['--next','xs=[7]','xs=[9]'],[2])]),(recurrence,[(['--next','n=15','--next','n=15'],[2,2,0])]),(wide,[(['--next','xs=[7]','--next','xs=[7]'],[33,33,0])]),(wide_fault,[(['--next','xs=[]','n=0'],[32])])]
    checks=0;seen={}
    with tempfile.TemporaryDirectory() as tmp:
        cwd=Path(tmp);fixture=cwd/'program.doc';cfile=cwd/'generated.c';exe=cwd/'program';flags=['cc','-std=gnu11','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',args.headers.resolve()]
        for compiler in commands:
            for src,scenarios in cases:
                out=run([*compiler,'--demand=code','input=['+','.join(map(str,src.encode()))+']'],cwd);assert out.returncode==0 and out.stdout.startswith('code: '),out.stderr
                code=out.stdout.removeprefix('code: ');assert code==seen.setdefault(src,code);cfile.write_text(code)
                cc=run([*flags,cfile,'-o',exe],cwd);assert cc.returncode==0,cc.stderr
                for argv,counts in scenarios:
                    fixture.write_text(src);expected=run([ref,fixture,*argv],cwd);fixture.unlink()
                    for workers in (1,4):
                        actual=run([exe,*argv],cwd,workers);assert (actual.returncode==0)==(expected.returncode==0),(argv,actual.stderr,expected.stderr)
                        assert actual.stdout==expected.stdout,(argv,actual.stdout,expected.stdout)
                        assert 'DOC11_REGIONS: live=0 ' in actual.stderr and not any(x in actual.stderr for x in ('AddressSanitizer','LeakSanitizer','runtime error:')),actual.stderr
                        assert list(map(int,re.findall(r'DOC11_MANAGED_EVALUATIONS: (\d+)',actual.stderr)))==counts,(argv,actual.stderr,counts)
                        if src in (wide,wide_fault) and workers==4:assert 'DOC11_MANAGED_PARALLEL: lanes=32 workers=2' in actual.stderr,actual.stderr
                        checks+=1
                if src==fault:
                    # Call the generated graph API directly, proving recovery
                    # inside one process after rejecting an updated later frontier.
                    harness=cwd/'harness.c';harness.write_text('#define main generated_main\n#include "generated.c"\n#undef main\n#include <assert.h>\nint main(void){Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));size_t t;epoch_begin(&e);assert(batch(&e,0,NULL,&t));epoch_finish(&e,1);assert(num(S_first)==2);char *bad[]={"xs=[]","x=9"};epoch_begin(&e);assert(!batch(&e,2,bad,&t));epoch_finish(&e,0);assert(num(S_x)==1&&S_xs.n==2&&S_vals.n==3&&num(S_first)==2);char *good[]={"xs=[9]","x=0"};epoch_begin(&e);assert(batch(&e,2,good,&t));epoch_finish(&e,1);assert(num(S_first)==9);epoch_free(&e);assert(live_bytes==0);puts("DOC11_MANAGED_ROLLBACK: recovery passed");return 0;}\n');cc=run([*flags,harness,'-o',exe],cwd);assert cc.returncode==0,cc.stderr;result=run([exe],cwd,4);assert result.returncode==0 and 'DOC11_MANAGED_ROLLBACK' in result.stdout,result.stderr
    print(f'DOC11_MANAGED_REACTIVE_PASS: {checks} source-free native epoch comparisons, {len(commands)} compiler paths, ASan/UBSan, exact cutoff, actual workers, in-process rollback and recovery, live=0')
if __name__=='__main__':main()
