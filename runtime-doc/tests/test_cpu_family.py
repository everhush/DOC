#!/usr/bin/env python3
"""Native runtime-sized family execution, hardware cap and rollback."""
import argparse,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser()
    for name in ('reactive','reference','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sanitizer',choices=('address,undefined','thread'),default='address,undefined');p.add_argument('--headers',type=Path,default=ROOT/'runtime-doc/runtime');p.add_argument('--fixture',type=Path,default=ROOT/'runtime-rust/examples/dependency_family.doc');a=p.parse_args()
    out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True);headers=a.headers.resolve();fixture=a.fixture.resolve();source=fixture.read_bytes()
    env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','TSAN_OPTIONS':'halt_on_error=1','DOC_REGION_METRICS':'1'}
    def run(cmd,workers=4,**kw):return subprocess.run([str(x) for x in cmd],cwd=out,env={**env,'DOC_WORKERS':str(workers)},capture_output=True,timeout=180,**kw)
    def build(name,data):
        e=run([a.reactive.resolve(),'--demand=code','--input-stdin'],input=data);assert e.returncode==0 and e.stdout.startswith(b'code: '),e.stderr
        c=out/(name+'.c');c.write_bytes(e.stdout[6:]);exe=out/name
        cc=run(['cc','-std=gnu11','-O1','-g','-pthread','-fsanitize='+a.sanitizer,'-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',headers,c,'-lm','-o',exe]);assert cc.returncode==0,cc.stderr
        assert b'doc_map_family(' in c.read_bytes(),c.read_bytes()[:2000]
        return exe
    def compare(exe,src,args,workers=4,valid=True,label=None):
        expected=run([a.reference.resolve(),src,*args],workers);actual=run([exe,'--backend=cpu',*args],workers)
        assert (actual.returncode==0)==valid==(expected.returncode==0) and actual.stdout==expected.stdout,(args,actual.stderr,expected.stderr)
        assert b'DOC11_REGIONS: live=0 ' in actual.stderr and not any(x in actual.stderr for x in (b'AddressSanitizer',b'LeakSanitizer',b'ThreadSanitizer',b'runtime error:')),actual.stderr
        if label:
            (out/(label+'.stdout')).write_bytes(actual.stdout);(out/(label+'.stderr')).write_bytes(actual.stderr)
        return actual
    def xs(n):return 'xs=['+','.join(map(str,range(n)))+']'
    exe=build('family',source);hw=len(os.sched_getaffinity(0));rows=[];args=[]
    for n,b in [(128,5),(0,5),(256,6),(3,7),(128,8)]:
        if args:args.append('--next')
        args.extend([xs(n),'bias='+str(b)])
    for workers in (1,2,4,8):
        actual=compare(exe,fixture,args,workers,label='workers-'+str(workers))
        observed=[tuple(map(int,x)) for x in re.findall(rb'DOC11_CPU_FAMILY: lanes=(\d+) workers=(\d+)',actual.stderr)]
        expected=[(n,min(workers,hw,n//16) if n>=32 else 1) for n in (128,256,3,128)]
        assert observed==expected,(observed,expected,actual.stderr)
        rows.append({'requested':workers,'hardware':hw,'actual':observed,'sha256':hashlib.sha256(actual.stdout).hexdigest()})
    compare(exe,fixture,['--demand=ys',xs(4096)],label='capacity')
    compare(exe,fixture,['--demand=ys',xs(4097)],valid=False,label='overcapacity')
    bad=compare(exe,fixture,[*args,'--next','xs=[9223372036854775807]','flag=true'],valid=False,label='overflow')
    assert b'epoch: 4\n' in bad.stdout and b'epoch: 5\n' not in bad.stdout
    # A large parent frontier already owns a CPU pool. Inner family work is
    # serial on its assigned worker rather than multiplying the thread cap.
    mixed=source+b'\n'+b''.join(f'derive extra{i}:int(bias)=add(bias,{i})\n'.encode() for i in range(32));mixed_source=out/'mixed.doc';mixed_source.write_bytes(mixed);mixed_exe=build('mixed',mixed)
    result=compare(mixed_exe,mixed_source,[xs(128)],label='mixed')
    if hw>=2:
        assert b'DOC11_CPU_FAMILY: lanes=128 workers=1' in result.stderr and b'DOC11_MANAGED_PARALLEL:' in result.stderr,result.stderr
    (out/'summary.json').write_text(json.dumps({'cases':rows,'capacity':4096,'rollback':True,'nested_pool_suppressed':True},indent=2)+'\n')
    print('DOC11_CPU_FAMILY_PASS: actual worker scaling, frozen 4096-lane cap, overflow rollback and no nested CPU pool',flush=True)
if __name__=='__main__':main()
