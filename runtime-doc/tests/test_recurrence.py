#!/usr/bin/env python3
"""Native carry/fact recurrence, simultaneous carry and rollback."""
import argparse,os,subprocess,tempfile
from pathlib import Path

def run(cmd,cwd):return subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,timeout=120,env={**os.environ,'DOC_REGION_METRICS':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
def main():
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path);p.add_argument('--reactive-source',required=True,type=Path);p.add_argument('--reactive',type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args();ref=a.reference.resolve();modes=[[ref,a.reactive_source.resolve()]]+([[a.reactive.resolve()]] if a.reactive else []);headers=a.headers.resolve();checks=0
 sources=[('source a:int=1\nsource b:int=2\nsource c:int=10\nderive d:int(a,b,c)=add(add(a,b),c)\nderive done:bool(d)=lt(15,d)\n', [['--through=4','a=b','b=a','--fact=2:c=99'],['--until=done','--max-epochs=4','a=d'],['--until=done','--max-epochs=2'],['--through=0'],['--through=4','a=d','--fact=1:a=0'],['--through=2','a=b','a=d'],['--through=2','a=done'],['--through=2','d=a'],['--through=2','--fact=3:c=1'],['--through=2','--fact=0:c=1'],['--through=2','--fact=1:c=1','--fact=1:c=2'],['--through=2','--fact=1:c=bad']]),('source l:ints=[1]\nsource n:int=2\nsource t:text="hello"\nderive next:ints(l,n)=append(l,n)\nderive msg:text(t)=concat(t,text("!"))\n', [['--through=5','l=next','t=msg','--fact=2:n=8'],['--through=3','l=next','--fact=1:t="x"']]),('source a:int=1\nderive d:int(a)=quot(10,a)\n',[['--through=3','--fact=2:a=0'],['--through=3','a=d']])]
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);source=root/'input.doc';cfile=root/'out.c';exe=root/'app'
  for tool in modes:
   for src,cases in sources:
    source.write_text(src);result=run([*tool,'--demand=code','input=['+','.join(map(str,src.encode()))+']'],root);assert result.returncode==0 and result.stdout.startswith(b'code: '),result.stderr;cfile.write_bytes(result.stdout[len(b'code: '):]);cc=run(['cc','-std=gnu11','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers,cfile,'-o',exe],root);assert cc.returncode==0,cc.stderr
    for args in cases:
     expected=run([ref,source,*args],root);actual=run([exe,*args],root);assert (actual.returncode==0)==(expected.returncode==0) and actual.stdout==expected.stdout,(args,expected.stdout,expected.stderr,actual.stdout,actual.stderr);assert b'DOC11_REGIONS: live=0 ' in actual.stderr and not any(x in actual.stderr for x in (b'AddressSanitizer',b'LeakSanitizer',b'runtime error:')),actual.stderr;checks+=1
 print(f'DOC11_RECURRENCE_PASS: {checks} native comparisons, simultaneous carries, typed facts and authority, halt/cap, managed values, rollback, ASan/UBSan, live=0')
if __name__=='__main__':main()
