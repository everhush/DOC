#!/usr/bin/env python3
"""Independent startup effects: compile without assets, read once under authority."""
import argparse, os, subprocess, tempfile
from pathlib import Path


def run(args,cwd):return subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,timeout=120,env={**os.environ,'DOC_REGION_METRICS':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path);p.add_argument('--managed-source',required=True,type=Path);p.add_argument('--reactive-source',required=True,type=Path);p.add_argument('--managed',type=Path);p.add_argument('--reactive',type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args();ref=a.reference.resolve();headers=a.headers.resolve()
    modes=[([ref,a.managed_source.resolve()],False),([ref,a.reactive_source.resolve()],True)]
    if a.managed:modes.extend([([a.managed.resolve()],False),([a.reactive.resolve()],True)])
    src='effect a:int=read("data/i.txt")\neffect b:bool=read("data/b.txt")\neffect c:nat=read("data/n.txt")\neffect d:ints=read("data/l.txt")\neffect e:maybe_int=read("data/m.txt")\neffect f:text=read("data/t.txt")\nderive size:int(d)=len(d)\nderive twice:int(a)=add(a,a)\nderive same:bool(f,b)=if(b,starts_with(f,text("hé")),false)\n'
    invalid=['effect a:int=read("../x")','effect a:int=read("/tmp/x")','effect a:int=read("data//x")','effect a:int=read("data/./x")','effect a:int=read("data/../x")','effect a:int=read("data/")','effect a:int=read("é")','effect a:int=read("")','effect a:int=read(1)','effect a:int=read("x","y")','effect a:int=add(1,2)','derive a:int()=read("x")','fn f(x)=read(x)\nderive a:int()=f(1)']
    checks=0
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);source=root/'program.doc';source.write_text(src);data=root/'data';cfile=root/'generated.c';exe=root/'program';seen={}
        for tool,reactive in modes:
            if data.exists():
                for x in data.iterdir():x.unlink()
                data.rmdir()
            out=run([*tool,'--demand=code','input=['+','.join(map(str,src.encode()))+']'],root);assert out.returncode==0 and out.stdout.startswith(b'code: '),out.stderr
            code=out.stdout[len(b'code: '):];assert code==seen.setdefault(reactive,code);cfile.write_bytes(code)
            flags=['cc','-std=gnu11','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers]
            cc=run([*flags,cfile,'-o',exe],root);assert cc.returncode==0,cc.stderr
            missing=run([exe],root);assert missing.returncode and not missing.stdout,missing
            data.mkdir();values={'i.txt':'17\n','b.txt':'true\n','n.txt':'123456789012345678901234567890\n','l.txt':'[1,2,-7]\n','m.txt':'some(-5)\n','t.txt':'héllo\r\n'}
            for name,value in values.items():(data/name).write_text(value)
            cases=[[],['--demand=twice','a=5']]+([['--next','a=19','--next','a=19']] if reactive else [])
            for args in cases:
                expected=run([ref,source,*args],root);actual=run([exe,'--asset-root='+str(root),*args],root);assert actual.returncode==expected.returncode==0 and actual.stdout==expected.stdout,(actual,expected);assert b'DOC11_REGIONS: live=0 ' in actual.stderr;checks+=1
            # Direct same-process batch: change asset on disk after initial
            # publication, prove the effect is not re-read during repair.
            if reactive:
                harness=root/'harness.c';harness.write_text('#define main generated_main\n#include "generated.c"\n#undef main\n#include <assert.h>\nint main(void){Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));size_t target;epoch_begin(&e);assert(batch(&e,0,NULL,&target));epoch_finish(&e,1);assert(num(S_a)==17);FILE *f=fopen("data/i.txt","w");assert(f);fputs("99",f);fclose(f);epoch_begin(&e);assert(batch(&e,0,NULL,&target));epoch_finish(&e,1);assert(num(S_a)==17);epoch_free(&e);assert(live_bytes==0);return 0;}\n');h=root/'harness';cc=run([*flags,harness,'-o',h],root);assert not cc.returncode,cc.stderr;result=run([h],root);assert not result.returncode,result.stderr
            # Child symlink, FIFO, invalid typed input and missing effect
            # cannot publish even if an override or unrelated demand is given.
            for kind in ('symlink','fifo','malformed','missing'):
                f=data/'i.txt';f.unlink(missing_ok=True)
                if kind=='symlink':f.symlink_to(data/'n.txt')
                elif kind=='fifo':os.mkfifo(f)
                elif kind=='malformed':f.write_text('not an integer')
                result=run([exe,'--asset-root='+str(root),'--demand=twice','a=8'],root);assert result.returncode and not result.stdout and not any(x in result.stderr for x in (b'AddressSanitizer',b'LeakSanitizer',b'runtime error:')),result;checks+=1
            for bad in invalid:
                result=run([*tool,'--demand=code','input=['+','.join(map(str,bad.encode()))+']'],root);assert result.returncode and not result.stdout,result
    print(f'DOC11_EFFECTS_PASS: {checks} native asset checks, {len(invalid)} invalid sources per compiler path, compile without assets, all six kinds, no reread, confined failures, sanitizer clean')
if __name__=='__main__':main()
