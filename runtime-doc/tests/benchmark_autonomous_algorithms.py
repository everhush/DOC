#!/usr/bin/env python3
"""Actual generated algorithm kernels, fixed workload and staged graph families."""
import argparse,csv,hashlib,json,os,re,statistics,subprocess,time,platform
from pathlib import Path
from benchmark_scale_pipeline import cpu_capacity
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--physical',action='store_true');p.add_argument('--samples',type=int,default=3);a=p.parse_args()
 root=a.root.resolve();out=a.out.resolve();out.mkdir();raw=out/'raw';raw.mkdir();build=json.loads((root/'build.json').read_text());mask,cap,quotas=cpu_capacity()
 for k,m in build.items():assert hashlib.sha256((root/k/'bench').read_bytes()).hexdigest()==m['sha256']
 env=dict(os.environ)
 for k in ('DOC_WORKERS','DOC_GPU_ALLOW_SOFTWARE','DOC_REQUIRE_PHYSICAL_GPU','DOC_DIAG_GROUP_CAP','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
 env.update(DOC_REGION_METRICS='1',DOC_REQUIRE_PHYSICAL_GPU='1')
 cases=[]
 for w,ns in [('stress',(4096,65536,262144)),('sort',(1024,16384,65536)),('reduce',(1024,16384,65536))]:
  for n in ns:
   for mode in [str(i) for i in range(1,cap+1)]+['auto']:cases.append((w,n,'cpu',mode,0))
   if a.physical:
    cases.extend([(w,n,'gpu','auto',0),(w,n,'auto','auto',0)])
 rows=[];dispatches=0;physical_sessions=0
 machine=dict(platform=platform.platform(),affinity=mask,capacity=cap,quotas=quotas,physical=a.physical,samples=a.samples,build=build,cases=cases)
 (out/'machine.json').write_text(json.dumps(machine,indent=2)+'\n')
 if a.physical:
  q=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv'],capture_output=True,text=True,check=True);(out/'device.txt').write_text(q.stdout)
 fields=['sample','work','lanes','mode','requested','group_cap','round','epoch_sum_ns','algorithm_ns','checksum','open_ns','process_ns','max_workers','dispatches','stages']
 with (out/'samples.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for s in range(a.samples):
   for w,n,mode,workers,gcap in cases if s%2==0 else reversed(cases):
    e=dict(env)
    if mode=='cpu' and workers!='auto':e['DOC_WORKERS']=workers
    assert not gcap
    rounds=5 if w=='stress' else 2
    t=time.perf_counter_ns();q=subprocess.run([root/w/'bench',mode,str(n),str(rounds)],env=e,capture_output=True,timeout=240);wall=time.perf_counter_ns()-t
    tag=f'{s+1:02d}-{w}-{n}-{mode}-{workers}-{gcap}';(raw/(tag+'.stdout')).write_bytes(q.stdout);(raw/(tag+'.stderr')).write_bytes(q.stderr)
    assert q.returncode==0 and b'live=0' in q.stdout,(tag,q.stderr[-6000:],q.stdout[-1000:])
    header=re.search(rb'open_ns=(\d+) n=(\d+) rounds=(\d+) algorithm=(\d+)',q.stdout);assert header
    opened,size,count,alg=map(int,header.groups());assert(size,count,alg)==(n,rounds,['stress','sort','reduce'].index(w))
    rr=[tuple(map(int,x)) for x in re.findall(rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)',q.stdout)]
    stages=[tuple(map(int,x)) for x in re.findall(rb'stage=(\d+) lanes=(\d+) epoch_ns=(\d+) evaluations=(\d+)',q.stdout)]
    assert [r[0] for r in rr]==list(range(rounds)) and [r[0] for r in stages]==list(range(len(stages)))
    traces=[tuple(map(int,x)) for x in re.findall(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',q.stderr)]
    expected=[(lanes,min((lanes+63)//64,gcap) if gcap else (lanes+63)//64) for _,lanes,_,_ in stages if mode=='gpu' or mode=='auto' and lanes>=64]
    # Repeated identical stage inputs can soundly cut off the map; verify all
    # actual dispatches are in stage order and match the independent oracle.
    if mode=='gpu' and w=='stress':assert traces==expected,(tag,traces,expected)
    else:
     remain=iter(expected);assert all(any(x==t for x in remain) for t in traces),(tag,traces,expected)
    if mode!='cpu':assert b'physical=1 ' in q.stderr and opened>0;physical_sessions+=1
    else:assert not traces and not opened and b'DOC11_GPU_ADAPTER:' not in q.stderr
    dispatches+=len(traces)
    maxworkers=max([1]+[int(v) for v in re.findall(rb'DOC11_CPU_FAMILY: lanes=\d+ workers=(\d+)',q.stderr)])
    assert maxworkers<=cap
    for ordinal,total,algorithm,checksum in rr:
     row=dict(sample=s+1,work=w,lanes=n,mode=mode,requested=workers,group_cap=gcap,round=ordinal,epoch_sum_ns=total,algorithm_ns=algorithm,checksum=checksum,open_ns=opened,process_ns=wall,max_workers=maxworkers,dispatches=len(traces),stages=len(stages));writer.writerow(row);rows.append(row)
    f.flush()
   print('DOC9_AUTONOMOUS_ALGORITHM_BATCH',s+1,'rows',len(rows),flush=True)
 summary=[]
 for w,n,mode,workers,gcap in cases:
  r=[x for x in rows if (x['work'],x['lanes'],x['mode'],x['requested'],x['group_cap'])==(w,n,mode,workers,gcap)]
  warm=[x['epoch_sum_ns']/1e6 for x in r if x['round']>0];wall=[x['algorithm_ns']/1e6 for x in r if x['round']>0]
  summary.append(dict(work=w,lanes=n,mode=mode,requested=workers,group_cap=gcap,samples=len(warm),epoch_median_ms=statistics.median(warm),epoch_mean_ms=statistics.fmean(warm),algorithm_median_ms=statistics.median(wall),actual_workers=sorted({x['max_workers'] for x in r})))
 (out/'summary.json').write_text(json.dumps(dict(machine=machine,rows=len(rows),processes=len(cases)*a.samples,dispatches=dispatches,physical_sessions=physical_sessions,summary=summary),indent=2)+'\n');print('DOC9_AUTONOMOUS_ALGORITHM_PASS',len(rows),len(cases)*a.samples,dispatches,flush=True)
if __name__=='__main__':main()
