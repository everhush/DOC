#!/usr/bin/env python3
"""Original-size paper runtime-substrate witness, not an integrated DOC compiler benchmark."""
import argparse,csv,hashlib,json,math,os,platform,re,shutil,statistics,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
REF=HERE/'paper_reference'
REF_FILES={
 'src/runtime.cpp':'23e97434c0f88bb0ad7e65090e04c63a14b2331b',
 'include/doc/runtime.hpp':'8d8cea8c80bf6660c97901af95ce69debc606b86',
 'benchmarks/benchmark.cpp':'c3d9d67746c6086f7afc7a4b3f50f432a04ce424',
 'benchmarks/workload_generator.cpp':'12d1f3f4f5477fa43a342727364f25078a461d2e',
 'benchmarks/workload_generator.hpp':'abd92a8903d5ab78dd9ab19c00b84437a7f2a70b'}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git_blob(p):
    data=Path(p).read_bytes();return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
def run(args,**kw):
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=180,**kw)
    if p.returncode:raise RuntimeError(str(args)+'\n'+p.stderr.decode(errors='replace')[-4000:])
    return p
def capacity(maximum):
    affinity=sorted(os.sched_getaffinity(0));cap=min(maximum,len(affinity));root=Path('/sys/fs/cgroup')
    paths=[root]
    try:
        for line in Path('/proc/self/cgroup').read_text().splitlines():
            if line.startswith('0::/'):
                child=root/line[4:];child=child.resolve()
                if child.is_relative_to(root):
                    paths.extend([child,*[p for p in child.parents if p.is_relative_to(root)]])
    except OSError:pass
    quotas={}
    for p in set(paths):
        try:
            s=(p/'cpu.max').read_text().strip();quotas[str(p)]=s;q,t=s.split()
            if q!='max':cap=min(cap,max(1,int(q)//int(t)))
        except (OSError,ValueError,ZeroDivisionError):pass
    return affinity[:cap],quotas
def build(out,headers):
    for f,h in REF_FILES.items():assert git_blob(REF/f)==h,('historical source drift',f)
    cc=os.environ.get('CC','gcc');cxx=os.environ.get('CXX','g++')
    flags=['-std=c++20','-O3','-DNDEBUG','-pthread','-I',REF/'include','-I',REF/'benchmarks']
    runtime=out/'reference-runtime.o';workload=out/'reference-workload.o'
    run([cxx,*flags,'-c',REF/'src/runtime.cpp','-o',runtime])
    run([cxx,*flags,'-c',REF/'benchmarks/workload_generator.cpp','-o',workload])
    run([cxx,*flags,REF/'benchmarks/benchmark.cpp',runtime,workload,'-o',out/'paper-original'])
    run([cxx,'-std=c++20','-O3','-c',HERE/'paper_fullsize_bridge.cpp','-o',out/'bridge.o'])
    # Never change the runtime source. This isolated copy binds the callback's
    # test state identity; the independently built test graph supplies CSR metadata.
    h=out/'test-only-headers';shutil.copytree(headers,h)
    p=h/'reactive_values.h';s=p.read_text();needle='V result=input?input_value(s->kind,input):s->eval();'
    assert s.count(needle)==1;p.write_text(s.replace(needle,'paper_test_id=i;'+needle))
    run([cc,'-std=gnu11','-O3','-pthread','-I',h,'-c',HERE/'paper_fullsize_host.c','-o',out/'native.o'])
    run([cxx,'-pthread',out/'native.o',out/'bridge.o',runtime,workload,'-lm','-o',out/'native'])
    return {'cc':run([cc,'--version']).stdout.decode(),'cxx':run([cxx,'--version']).stdout.decode(),'reference_blobs':REF_FILES,'production_headers':{p.name:git_blob(p) for p in headers.iterdir() if p.is_file()},'host_sha256':digest(HERE/'paper_fullsize_host.c'),'bridge_sha256':digest(HERE/'paper_fullsize_bridge.cpp'),'binaries':{x:digest(out/x) for x in ('paper-original','native')}}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--headers',type=Path,default=HERE.parent/'runtime');p.add_argument('--out',type=Path,required=True);p.add_argument('--samples',type=int,default=30);p.add_argument('--warmups',type=int,default=3);p.add_argument('--max-participants',type=int,default=4);a=p.parse_args()
    assert a.samples>0 and a.warmups>=0 and 1<=a.max_participants<=4
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);mask,quota=capacity(a.max_participants);cap=len(mask);assert cap>0
    meta=build(out,a.headers.resolve());meta.update(platform=platform.platform(),affinity=mask,cgroup_quotas=quota,samples=a.samples,warmups=a.warmups,scope='original graph sizes and historical numerical callbacks in test-only host; not integrated DOC compiler; all original paper evaluator-count comparisons')
    (out/'machine.json').write_text(json.dumps(meta,indent=2)+'\n')
    cases=[('cold',0),*[('density',i) for i in (1,8,64,512,2048)],('cutoff',0),('dense-cheap',0),*[('parallel',i) for i in range(1,cap+1)],*[('financial',i) for i in (1,64,1024)],*[('bitonic',i) for i in (1,8,64,256,512)]]
    scenarios=[]
    for tag,k in cases:
        w=str(k) if tag=='parallel' else '1'
        scenarios.extend([(tag,k,'paper-original',w),(tag,k,'native',w)])
        if tag!='parallel':scenarios.append((tag,k,'native','auto'))
    rows=[]
    with (out/'samples.csv').open('w') as f:
        writer=None
        for i in range(-a.warmups,a.samples):
            batch=[]
            for tag,k,v,w in scenarios if i%2==0 else reversed(scenarios):
                env=dict(os.environ);env.pop('DOC_WORKERS',None);env.pop('DOC_MAX_WORKERS',None)
                if w!='auto':env['DOC_WORKERS']=env['DOC_MAX_WORKERS']=w
                args=[tag]+([str(k)] if tag in ('density','financial','bitonic') else [])
                t=time.perf_counter_ns();q=run(['taskset','-c',','.join(map(str,mask)),out/v,*args],env=env);wall=(time.perf_counter_ns()-t)/1e6
                line=q.stdout.decode().strip();d=dict(re.findall(r'(\w+)=([\w.+-]+)',line))
                if v=='paper-original':
                    ms=float(d['elapsed_ms'] if tag in ('parallel','cutoff') else d['doc_update_ms'] if tag=='bitonic' else d['doc_ms']);ev=int(d['update_evaluations'] if tag=='bitonic' else d['evaluations']);peak=int(d.get('participants',w))
                else:
                    ms=float(d['cold_ms'] if tag in ('cold','parallel') else d['update_ms']);ev=int(d['evaluations']);peak=max([1]+[int(x) for x in re.findall(rb'DOC11_MANAGED_PARALLEL: lanes=\d+ workers=(\d+)',q.stderr)])
                row=dict(phase='warmup' if i<0 else 'measured',sample=i+1,scenario=tag,case=k,variant=v,requested=w,peak_workers=peak,timed_ms=ms,process_ms=wall,evaluations=ev,value=d.get('value',''),stdout=line,stderr=q.stderr.decode())
                if writer is None:writer=csv.DictWriter(f,fieldnames=row);writer.writeheader()
                writer.writerow(row);f.flush();batch.append(row)
            for tag,k in cases:
                sub=[x for x in batch if (x['scenario'],x['case'])==(tag,k)];assert len({x['evaluations'] for x in sub})==1,sub;assert len({x['value'] for x in sub if x['value']})<=1,sub
            if i>=0:rows.extend(batch);print('completed batch',i+1,'observations',len(rows),flush=True)
    result=[]
    for tag,k,v,w in scenarios:
        sub=[x for x in rows if (x['scenario'],x['case'],x['variant'],x['requested'])==(tag,k,v,w)];x=[z['timed_ms'] for z in sub];assert len(x)==a.samples
        result.append(dict(scenario=tag,case=k,variant=v,requested=w,n=len(x),mean_ms=statistics.fmean(x),median_ms=statistics.median(x),p95_ms=sorted(x)[math.ceil(.95*len(x))-1],min_ms=min(x),max_ms=max(x),stdev_ms=statistics.stdev(x) if len(x)>1 else 0,evaluations=sub[0]['evaluations'],peak_workers=sorted({z['peak_workers'] for z in sub})))
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print('DOC9_FULLSIZE_RUNTIME_PASS:',len(rows),'measured observations; test-only graph, no integrated compiler claim',flush=True)
if __name__=='__main__':main()
