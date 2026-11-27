#!/usr/bin/env python3
"""Matched actual CPU/physical GPU measurements; all raw process pairs in one archive."""
import argparse,csv,hashlib,json,math,os,re,statistics,subprocess,tarfile,time,platform
from pathlib import Path
def cpu_capacity():
 mask=sorted(os.sched_getaffinity(0));cap=len(mask);quotas={}
 root=Path('/sys/fs/cgroup');paths=[root]
 for l in Path('/proc/self/cgroup').read_text().splitlines():
  if l.startswith('0::/'):
   d=(root/l[4:]).resolve()
   if d.is_relative_to(root):paths.extend([d,*[p for p in d.parents if p.is_relative_to(root)]])
 for p in set(paths):
  try:
   q,t=(p/'cpu.max').read_text().split();quotas[str(p)]=q+' '+t
   if q!='max':cap=min(cap,max(1,int(q)//int(t)))
  except OSError:pass
 return mask,cap,quotas
def oracle(work,n,e):
 b=e%7-3
 if work=='add':return n*(n-1)//2+n*(e+b)
 vals=[]
 for x in range(-4,5):
  v=b
  for _ in range(5):v=v*x+b
  vals.append(v)
 q,r=divmod(n,9);return q*sum(vals)+sum(vals[(e+i)%9] for i in range(r))
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--physical',action='store_true');p.add_argument('--samples',type=int,default=5);p.add_argument('--epochs',type=int,default=9);a=p.parse_args()
 root=a.root.resolve();out=a.out.resolve();out.mkdir();raw=out/'raw';raw.mkdir();build=json.loads((root/'build.json').read_text());mask,cap,quotas=cpu_capacity()
 for k,m in build.items():assert hashlib.sha256((root/k/'bench').read_bytes()).hexdigest()==m['sha256']
 env=dict(os.environ)
 for k in ('DOC_WORKERS','DOC_GPU_ALLOW_SOFTWARE','DOC_REQUIRE_PHYSICAL_GPU','DOC_DIAG_GROUP_CAP','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
 env.update(DOC_REGION_METRICS='1',DOC_REQUIRE_PHYSICAL_GPU='1')
 # Actual admitted CPU capacity only. Every mode uses identical lane arithmetic.
 cases=[]
 for w in ('add','poly'):
  for n in (64,4096,16384,65536):
   for mode in [str(i) for i in range(1,cap+1)]+['auto']:
    cases.append((w,'wide64',n,'cpu',mode,0))
   if a.physical:
    for v in ('wide32','wide64','wide128','wide256','poll64'):
     cases.append((w,v,n,'gpu','auto',0))
    if n<=4096:cases.append((w,'base',n,'gpu','auto',0))
  if a.physical:
   for n in (4096,65536):
    for groups in (1,4,16,64,256,1024):
     if groups<=n//64:cases.append((w,'stride64',n,'gpu','auto',groups))
   for n in (64,4096,16384,65536):cases.append((w,'wide64',n,'auto','auto',0))
 assert len(cases)==len(set(cases))
 machine=dict(platform=platform.platform(),affinity=mask,capacity=cap,quotas=quotas,physical=a.physical,samples=a.samples,epochs=a.epochs,build=build,cases=cases)
 (out/'machine.json').write_text(json.dumps(machine,indent=2)+'\n')
 if a.physical:
  q=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total,multiprocessor_count','--format=csv'],capture_output=True,text=True)
  if q.returncode:q=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv'],capture_output=True,text=True)
  assert q.returncode==0
  (out/'device.txt').write_text(q.stdout)
 fields=['sample','work','variant','lanes','mode','requested','group_cap','epoch','epoch_ns','dispatch_ns','groups','wg','workers','open_ns','process_ns','checksum','rss_kib','peak_bytes']
 rows=[]
 with (out/'samples.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for s in range(a.samples):
   for j,(w,v,n,mode,workers,gcap) in enumerate(cases if s%2==0 else reversed(cases)):
    m=build[v+'/'+w];e=dict(env)
    if mode=='cpu' and workers!='auto':e['DOC_WORKERS']=workers
    if gcap:e['DOC_DIAG_GROUP_CAP']=str(gcap)
    start=time.perf_counter_ns();r=subprocess.run([root/v/w/'bench',mode,str(n),str(a.epochs)],env=e,capture_output=True,timeout=120);wall=time.perf_counter_ns()-start
    tag=f'{s+1:02d}-{w}-{v}-{n}-{mode}-{workers}-{gcap}';(raw/(tag+'.stdout')).write_bytes(r.stdout);(raw/(tag+'.stderr')).write_bytes(r.stderr)
    assert r.returncode==0 and b'live=0 ' in r.stdout,(tag,r.stderr[-3000:],r.stdout[-1000:])
    head=re.search(rb'open_ns=(\d+) lanes=(\d+) epochs=(\d+) complex=(\d+)',r.stdout);assert head
    opened,lanes,epochs,complexity=map(int,head.groups());assert (lanes,epochs,complexity)==(n,a.epochs,int(w=='poly'))
    ep=[tuple(map(int,x)) for x in re.findall(rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)',r.stdout)];assert [x[0] for x in ep]==list(range(a.epochs));assert all(ns>0 and ev==1 and ck==oracle(w,n,i) for i,ns,ev,ck in ep),(tag,ep)
    gpu=mode!='cpu';traces=[tuple(map(int,x)) for x in re.findall(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',r.stderr)]
    groups=min(math.ceil(n/m['wg']),gcap) if gcap else math.ceil(n/m['wg'])
    if gpu:
     assert b'physical=1 ' in r.stderr and b'DOC9_LIMITS:' in r.stderr and opened>0
     assert traces==[(n,groups)]*a.epochs,(tag,traces)
     assert b'event=closed' in r.stderr
    else:assert not traces and not opened and b'DOC11_GPU_ADAPTER:' not in r.stderr
    dt=[int(x) for x in re.findall(rb'DOC11_GPU_DISPATCH_TIMING: dispatch=\d+ wall_ns=(\d+)',r.stderr)];assert len(dt)==(a.epochs if gpu else 0)
    ct=[(int(n),int(k)) for n,k in re.findall(rb'DOC11_CPU_FAMILY: lanes=(\d+) workers=(\d+)',r.stderr)];assert len(ct)==(0 if gpu else a.epochs)
    assert all(x==n and 1<=k<=cap for x,k in ct)
    if workers!='auto':assert all(k<=int(workers) for x,k in ct)
    rss=int(re.search(rb'DOC11_PROCESS_METRICS: max_rss_kib=(\d+)',r.stderr)[1]);peak=int(re.search(rb'live=0 peak=(\d+)',r.stdout)[1])
    for i,ns,ev,ck in ep:
     row=dict(sample=s+1,work=w,variant=v,lanes=n,mode=mode,requested=workers,group_cap=gcap,epoch=i,epoch_ns=ns,dispatch_ns=dt[i] if gpu else 0,groups=groups if gpu else 0,wg=m['wg'],workers=ct[i][1] if ct else 0,open_ns=opened,process_ns=wall,checksum=ck,rss_kib=rss,peak_bytes=peak);writer.writerow(row);rows.append(row)
    f.flush()
   print('DOC9_GEOMETRY_BATCH',s+1,'rows',len(rows),flush=True)
 summary=[]
 for w,v,n,mode,workers,gcap in cases:
  rr=[r for r in rows if (r['work'],r['variant'],r['lanes'],r['mode'],r['requested'],r['group_cap'])==(w,v,n,mode,workers,gcap)]
  assert len(rr)==a.samples*a.epochs
  warm=[r['epoch_ns']/1e6 for r in rr if r['epoch']];disp=[r['dispatch_ns']/1e6 for r in rr if r['epoch'] and r['dispatch_ns']]
  summary.append(dict(work=w,variant=v,lanes=n,mode=mode,requested=workers,group_cap=gcap,workers=sorted({r['workers'] for r in rr}),groups=rr[0]['groups'],samples=len(warm),mean_ms=statistics.fmean(warm),median_ms=statistics.median(warm),p95_ms=sorted(warm)[math.ceil(.95*len(warm))-1],dispatch_median_ms=statistics.median(disp) if disp else None,cold_median_ms=statistics.median(r['epoch_ns']/1e6 for r in rr if not r['epoch']),open_median_ms=statistics.median(r['open_ns']/1e6 for r in rr if not r['epoch'])))
 (out/'summary.json').write_text(json.dumps(dict(machine=machine,rows=len(rows),processes=len(cases)*a.samples,dispatches=sum(bool(r['dispatch_ns']) for r in rows),summary=summary),indent=2)+'\n')
 assert len(list(raw.glob('*.stderr')))==len(cases)*a.samples
 print('DOC9_GEOMETRY_PASS',len(rows),'epochs',len(cases)*a.samples,'processes',flush=True)
if __name__=='__main__':main()
