#!/usr/bin/env python3
"""Paper 40-leaf trial-division scheduler reproduction, not a DOC-language prime implementation."""
import argparse,csv,hashlib,json,math,os,platform,re,shutil,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=Path(__file__).resolve().parent/'paper_reference'
HIST='27a0139643237bfcaf05c71155fd137f297f6a53'
BASE='431ce65c11e580c76b58cef885fd8f2ed3af1f71'
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def command(args,**kw):
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=240,**kw)
    if p.returncode:raise RuntimeError(str(args)+'\n'+p.stderr.decode(errors='replace')[-4000:])
    return p
def generate(n,pure=False):
    lines=[];cur=[]
    for i in range(n):
        if pure:
            lines += [f'source s{i}:ints=[0,{i+1}]',f'derive leaf{i}:ints(s{i})=recur(s{i},x,eq(get(x,0),25000),append(append(empty(),add(get(x,0),1)),rem(add(mul(get(x,1),48271),1),2147483647)))']
        else:
            lines += [f'source s{i}:int={i}',f'derive leaf{i}:int(s{i})=add(s{i},0)']
        cur.append((f'leaf{i}',pure))
    level=0
    while len(cur)>1:
        nxt=[]
        for j in range(0,len(cur),2):
            if j+1==len(cur):nxt.append(cur[j]);continue
            a,al=cur[j];b,bl=cur[j+1];name=f'r{level}_{j//2}'
            av=f'get({a},1)' if al else a;bv=f'get({b},1)' if bl else b
            lines.append(f'derive {name}:int({a},{b})=add({av},{bv})');nxt.append((name,False))
        cur=nxt;level+=1
    return ('\n'.join(lines)+'\n').encode(),cur[0][0]
def oracle_prime(n):
    high=500000+n-1+25000
    prime=bytearray(b'\x01')*high;prime[:2]=b'\x00\x00'
    for i in range(2,math.isqrt(high-1)+1):
        if prime[i]:prime[i*i:high:i]=b'\x00'*(((high-1-i*i)//i)+1)
    return sum(sum(prime[500000+i:525000+i]) for i in range(n))
def oracle_pure(n):
    total=0
    for i in range(n):
        x=i+1
        for _ in range(25000):x=(x*48271+1)%2147483647
        total+=x
    return total
def emit(reactive,source,out):
    p=command([reactive,'--demand=code','--input-stdin'],input=source)
    if not p.stdout.startswith(b'code: '):raise ValueError('missing independent compiler output')
    out.write_bytes(p.stdout[6:]);return p.stdout[6:].decode()
def build(reactive,headers,out):
    out.mkdir(parents=True,exist_ok=True)
    cc=os.environ.get('CC','gcc');cxx=os.environ.get('CXX','g++')
    rflags=['-std=c++20','-O3','-DNDEBUG','-pthread','-I',REF/'include','-I',REF/'benchmarks']
    runtime=out/'reference-runtime.o';workload=out/'reference-workload.o'
    command([cxx,*rflags,'-c',REF/'src/runtime.cpp','-o',runtime])
    command([cxx,*rflags,'-c',REF/'benchmarks/workload_generator.cpp','-o',workload])
    command([cxx,*rflags,REF/'benchmarks/benchmark.cpp',runtime,workload,'-o',out/'paper-original'])
    # Wrapper links the actual historical count_primes, no reimplementation or sieve substitution.
    adapter=out/'prime-adapter.cpp'
    adapter.write_text('#include "workload_generator.hpp"\nextern "C" int64_t paper_leaf(int64_t x){return (int64_t)doc::bench::count_primes(500000+(uint64_t)(x<0?-x:x),25000);}\n')
    command([cxx,*rflags,'-c',adapter,'-o',out/'prime-adapter.o'])
    candidate=out/'full-capacity-test-only-headers'
    shutil.copytree(headers,candidate,dirs_exist_ok=True)
    policy=candidate/'placement_policy_generated.h'
    original=policy.read_text()
    lines=original.splitlines()
    # This isolated diagnostic override is intentionally not a production policy.
    replacements={'F_place_parallel':'#define F_place_parallel(P_tasks) (v_le(vi(2),P_tasks))',
                  'F_place_workers':'#define F_place_workers(P_tasks,P_capacity) (v_if(v_le(P_tasks,vi(1)),vi(1),v_if(v_lt(P_capacity,P_tasks),P_capacity,P_tasks)))'}
    for name,repl in replacements.items():
        ids=[i for i,l in enumerate(lines) if l.startswith('#define '+name+'(')]
        assert len(ids)==1,(name,ids)
        lines[ids[0]]=repl
    policy.write_text('\n'.join(lines)+'\n')
    (out/'baseline-policy.h').write_text(original)
    (out/'diagnostic-policy.h').write_bytes(policy.read_bytes())
    manifest={'base':BASE,'historical':HIST,'reactive_sha256':digest(reactive),'compiler':command([cc,'--version']).stdout.decode(),'cxx':command([cxx,'--version']).stdout.decode(),'cases':{}}
    for n,pure in [(40,False),(40,True),(128,True)]:
        tag=('pure' if pure else 'prime')+str(n)
        src,root=generate(n,pure);(out/(tag+'.doc')).write_bytes(src)
        code=emit(reactive,src,out/(tag+'.generated.c'))
        if not pure:
            for i in range(n):
                pat=r'(static V E_leaf'+str(i)+r'\(void\)\{return )[^\n]+?;\}'
                code,count=re.subn(pat,lambda m:m[1]+f'vi(paper_leaf(num(S_s{i})));'+'}',code)
                assert count==1,(i,count)
            code='#include <stdint.h>\nextern int64_t paper_leaf(int64_t);\n'+code
        # Preserve generated source graph, epoch publication and actual scheduler.
        # Only replace CLI entry with timing/verification around one full stabilization.
        marker='int main(int argc,char **argv){return run_reactive(states,sizeof(states)/sizeof(states[0]),argc,argv);}'
        assert code.count(marker)==1
        code=code.replace(marker,'')
        code+='\n#include <time.h>\nint main(void){Epoch e;epoch_init(&e,states,sizeof(states)/sizeof(states[0]));size_t target=0;struct timespec a,b;clock_gettime(CLOCK_MONOTONIC,&a);int ok=epoch_begin(&e)&&batch(&e,0,NULL,&target);ok=epoch_finish(&e,ok);clock_gettime(CLOCK_MONOTONIC,&b);if(!ok)return 1;printf("elapsed_ms=%.9f value=%lld evaluations=%zu frontiers=%zu launched=%zu\\n",(b.tv_sec-a.tv_sec)*1000.0+(b.tv_nsec-a.tv_nsec)/1e6,(long long)num(S_'+root+'),e.evaluations,e.frontiers,e.launched);epoch_free(&e);if(live_bytes)return 2;return 0;}\n'
        path=out/(tag+'.harness.c');path.write_text(code)
        for variant,h in [('current',headers),('full-capacity-diagnostic',candidate)]:
            exe=out/(tag+'-'+variant)
            obj=out/(tag+'-'+variant+'.o')
            command([cc,'-std=gnu11','-O3','-DNDEBUG','-pthread','-I',h,'-c',path,'-o',obj])
            if pure:command([cc,'-pthread',obj,'-lm','-o',exe])
            else:command([cxx,'-pthread',obj,out/'prime-adapter.o',runtime,workload,'-lm','-o',exe])
        manifest['cases'][tag]={'n':n,'pure':pure,'expected':oracle_pure(n) if pure else oracle_prime(n),'source_sha256':digest(out/(tag+'.doc')),'generated_sha256':digest(out/(tag+'.generated.c'))}
    (out/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
def measure(out,samples,warmups,max_workers):
    info=json.loads((out/'build.json').read_text());aff=sorted(os.sched_getaffinity(0))
    quota=Path('/sys/fs/cgroup/cpu.max')
    rawquota=quota.read_text().strip() if quota.exists() else None
    effective=len(aff)
    if rawquota and rawquota.split()[0]!='max':
        q,p=map(int,rawquota.split());effective=min(effective,max(1,q//p))
    cap=min(max_workers,effective)
    scenarios=[('paper-original',k) for k in range(1,cap+1)]
    for tag in info['cases']:
        for mode in ('current','full-capacity-diagnostic'):
            scenarios.extend((tag+'-'+mode,k) for k in range(1,cap+1))
            scenarios.append((tag+'-'+mode,'auto'))
    rows=[]
    # Bound affinity to effective capacity for comparable trials; auto gets no worker environment setting.
    for i in range(-warmups,samples):
        order=scenarios if i%2==0 else list(reversed(scenarios))
        for name,k in order:
            env={**os.environ};env.pop('DOC_WORKERS',None);env.pop('DOC_MAX_WORKERS',None)
            if k!='auto':env['DOC_WORKERS']=env['DOC_MAX_WORKERS']=str(k)
            args=['taskset','-c',','.join(map(str,aff[:cap])),out/name]
            if name=='paper-original':args.append('parallel')
            t=time.perf_counter_ns();p=command(args,env=env);wall=(time.perf_counter_ns()-t)/1e6
            line=p.stdout.decode().strip()
            data=dict(re.findall(r'(\w+)=([\w.+-]+)',line))
            if name!='paper-original':
                tag=name.split('-')[0]
                expected=info['cases'][tag]
                assert int(data['value'])==expected['expected'] and int(data['evaluations'])==2*expected['n']-1,(name,k,line)
            else:assert int(data['evaluations'])==79,(name,k,line)
            traces=[int(x) for x in re.findall(rb'DOC11_MANAGED_PARALLEL: lanes=\d+ workers=(\d+)',p.stderr)]
            observed=max(traces,default=1) if name!='paper-original' else int(data['participants'])
            if name!='paper-original':
                n=info['cases'][tag]['n'];want=min(cap if k=='auto' else k,n)
                if '-current' in name:want=max(1,min(want,n//16)) if n>=32 else 1
                assert observed==want,(name,k,observed,want,p.stderr)
            if i>=0:
                rows.append({'sample':i+1,'scenario':name,'requested':k,'observed':observed,'elapsed_ms':float(data['elapsed_ms']),'process_wall_ms':wall,'evaluations':data['evaluations'],'raw_stdout':line,'raw_stderr':p.stderr.decode()})
        if i>=0:
            with (out/'samples.csv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
            print('completed sample',i+1,'of',samples,flush=True)
    result=[]
    for name,k in scenarios:
        selected=[r for r in rows if r['scenario']==name and r['requested']==k]
        vals=[r['elapsed_ms'] for r in selected];mean=statistics.fmean(vals)
        base=statistics.fmean(r['elapsed_ms'] for r in rows if r['scenario']==name and r['requested']==1)
        result.append(dict(scenario=name,requested=k,observed=selected[0]['observed'],n=len(vals),mean_ms=mean,median_ms=statistics.median(vals),p95_ms=sorted(vals)[math.ceil(.95*len(vals))-1],min_ms=min(vals),max_ms=max(vals),stdev_ms=statistics.stdev(vals) if len(vals)>1 else 0,speedup=base/mean))
    (out/'results.json').write_text(json.dumps({'platform':platform.platform(),'affinity':aff,'cpu_max':rawquota,'tested_capacity':cap,'results':result},indent=2)+'\n')
    print(json.dumps(result,indent=2))
def main():
    p=argparse.ArgumentParser();p.add_argument('--reactive',type=Path);p.add_argument('--headers',type=Path,default=ROOT/'runtime');p.add_argument('--out',type=Path,required=True);p.add_argument('--samples',type=int,default=100);p.add_argument('--warmups',type=int,default=3);p.add_argument('--max-workers',type=int,default=4);p.add_argument('--measure-only',action='store_true');p.add_argument('--build-only',action='store_true');a=p.parse_args()
    out=a.out.resolve()
    if not a.measure_only:
        if a.reactive is None:raise ValueError('--reactive required for build')
        build(a.reactive.resolve(),a.headers.resolve(),out)
    if not a.build_only:measure(out,a.samples,a.warmups,a.max_workers)
if __name__=='__main__':main()
