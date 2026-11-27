#!/usr/bin/env python3
"""Actual independent compiler chunked emission and large-name lookup parity."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def main():
    p=argparse.ArgumentParser()
    for name in ('reactive','reference','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');a=p.parse_args()
    out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True)
    src=out/'index-large.doc';src.write_text(''.join(f'source s{i}:int={i}\nderive d{i}:int(s{i})=add(s{i},1)\n' for i in range(150)))
    data=src.read_bytes();reactive=a.reactive.resolve();reference=a.reference.resolve()
    def emit(target,*extra):
        r=subprocess.run([reactive,'--demand='+target,'--input-stdin',*extra],input=data,capture_output=True,timeout=120);prefix=(target+': ').encode();assert r.returncode==0 and r.stdout.startswith(prefix),r.stderr;return r.stdout[len(prefix):]
    count=int(emit('chunk_count'));assert 1<count<=128
    # Independent, bounded compiler processes; every requested chunk must pass.
    with ThreadPoolExecutor(max_workers=min(2,len(os.sched_getaffinity(0)))) as pool:code=b''.join(pool.map(lambda i:emit('code','chunk='+str(i)),range(count)))
    c=out/'index-large.c';c.write_bytes(code);exe=out/'index-large'
    cc=subprocess.run(['cc','-std=gnu11','-O1','-g','-pthread','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',str(a.headers.resolve()),c,'-o',exe],capture_output=True,timeout=180);assert cc.returncode==0,cc.stderr
    cases=[[],['--demand=d149'],['s149=500','--next','s0=-4'],[f's{i}={1000+i}' for i in range(150)],['--demand=d99','s99=100'],['s149x=10'],['s149=1','s149=2'],['s149=notint'],['--demand=d150'],['s149=9223372036854775807']]
    rows=[]
    for i,args in enumerate(cases):
        e=subprocess.run([reference,src,*args],capture_output=True,timeout=30)
        for workers in ('1','4','auto'):
            env=dict(os.environ);env.pop('DOC_WORKERS',None);env.update(DOC_REGION_METRICS='1',ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
            if workers!='auto':env['DOC_WORKERS']=workers
            r=subprocess.run([exe,*args],env=env,capture_output=True,timeout=30)
            assert (r.returncode==0)==(e.returncode==0)==(i<5) and r.stdout==e.stdout and b'DOC11_REGIONS: live=0 ' in r.stderr,(i,workers,r.stderr,e.stderr)
            assert not any(x in r.stderr for x in (b'AddressSanitizer',b'LeakSanitizer',b'runtime error:')),r.stderr
            (out/f'{i}-{workers}.stdout').write_bytes(r.stdout);(out/f'{i}-{workers}.stderr').write_bytes(r.stderr)
            rows.append(dict(case=i,workers=workers,valid=not r.returncode,sha256=hashlib.sha256(r.stdout).hexdigest()))
    (out/'summary.json').write_text(json.dumps({'chunks':count,'cases':rows,'generated_sha256':hashlib.sha256(code).hexdigest()},indent=2)+'\n')
    print('DOC9_GENERATED_INDEX_PASS: 300 states, 150-source batch, 30 oracle/sanitizer cases, exact demand and failure rejection; live=0',flush=True)
if __name__=='__main__':main()
