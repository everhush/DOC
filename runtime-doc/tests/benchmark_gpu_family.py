#!/usr/bin/env python3
"""Exact emitted DOC family code, bounded host timings and independent lane checks."""
import argparse,csv,hashlib,json,math,os,re,statistics,subprocess,time,platform
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--physical',action='store_true');p.add_argument('--samples',type=int,default=10);p.add_argument('--epochs',type=int,default=17);p.add_argument('--widths',default='1,31,32,63,64,128,256,512,1024,2048,4096');a=p.parse_args();root=a.root.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);raw=out/'raw';raw.mkdir(exist_ok=True);widths=list(map(int,a.widths.split(',')));assert all(0<n<=4096 for n in widths) and a.samples>0 and 2<=a.epochs<=128
 env=dict(os.environ)
 for k in ('DOC_WORKERS','DOC_GPU_ALLOW_SOFTWARE','DOC_REQUIRE_PHYSICAL_GPU','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
 env.update(DOC_REGION_METRICS='1');env['DOC_REQUIRE_PHYSICAL_GPU' if a.physical else 'DOC_GPU_ALLOW_SOFTWARE']='1'
 scenarios=[(work,n,mode) for work in ('add','poly') for n in widths for mode in ('cpu1','cpu-auto','auto','gpu')];rows=[];dispatch=[]
 def oracle(work,n,epoch):
  bias=epoch%7-3
  if work=='add':return sum(i+epoch+bias for i in range(n))
  total=0
  for i in range(n):
   x=(i+epoch)%9-4;v=bias
   for _ in range(5):v=v*x+bias
   total+=v
  return total
 for sample in range(a.samples):
  for work,n,mode in scenarios if sample%2==0 else reversed(scenarios):
   e=dict(env)
   if mode=='cpu1':e['DOC_WORKERS']='1'
   backend='cpu' if mode.startswith('cpu') else mode
   exe=root/work/'bench';t=time.perf_counter_ns();r=subprocess.run([exe,backend,str(n),str(a.epochs)],env=e,capture_output=True,timeout=120);wall=time.perf_counter_ns()-t;tag=f'{sample+1:02d}-{work}-{n}-{mode}'
   (raw/(tag+'.stdout')).write_bytes(r.stdout);(raw/(tag+'.stderr')).write_bytes(r.stderr)
   assert r.returncode==0 and b'live=0 ' in r.stdout,(tag,r.stdout,r.stderr[-4000:]);head=re.search(rb'open_ns=(\d+) lanes=(\d+) epochs=(\d+) complex=(\d+)',r.stdout);assert head
   opened,lanes,epochs,complexity=map(int,head.groups());assert (lanes,epochs,complexity)==(n,a.epochs,int(work=='poly'))
   epoch_rows=[tuple(map(int,x)) for x in re.findall(rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)',r.stdout)];assert [x[0] for x in epoch_rows]==list(range(a.epochs));assert all(ms>0 and ev==1 and value==oracle(work,n,i) for i,ms,ev,value in epoch_rows),(tag,epoch_rows)
   gpu_expected=mode=='gpu' or (mode=='auto' and n>=64);adapters=[x for x in r.stderr.splitlines() if x.startswith(b'DOC11_GPU_ADAPTER:')]
   assert len(adapters)==int(backend!='cpu') and (opened>0)==(backend!='cpu')
   if adapters:assert (b'physical=1 ' in adapters[0])==a.physical,(tag,adapters)
   traces=[tuple(map(int,x)) for x in re.findall(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',r.stderr)];assert traces==([(n,math.ceil(n/64))]*a.epochs if gpu_expected else []),(tag,traces)
   times=[tuple(map(int,x)) for x in re.findall(rb'DOC11_GPU_DISPATCH_TIMING: dispatch=(\d+) wall_ns=(\d+) upload_bytes=(\d+) readback_bytes=(\d+) capacity=(\d+)',r.stderr)];assert len(times)==len(traces) and all(d==i+1 and ns>0 and up>0 and down>0 and cap>=n for i,(d,ns,up,down,cap) in enumerate(times))
   cpu=[tuple(map(int,x)) for x in re.findall(rb'DOC11_CPU_FAMILY: lanes=(\d+) workers=(\d+)',r.stderr)];assert len(cpu)==(0 if gpu_expected else a.epochs) and all(k==n and w>=1 for k,w in cpu)
   if mode=='cpu1':assert all(w==1 for _,w in cpu)
   rss=re.search(rb'DOC11_PROCESS_METRICS: max_rss_kib=(\d+)',r.stderr);region=re.search(rb'live=0 peak=(\d+) allocations=(\d+)',r.stdout);assert rss and region
   for i,ns,ev,checksum in epoch_rows:rows.append(dict(sample=sample+1,workload=work,lanes=n,mode=mode,epoch=i,epoch_ns=ns,process_ns=wall,device_open_ns=opened,workers=max([w for _,w in cpu],default=0),workgroups=math.ceil(n/64) if gpu_expected else 0,checksum=checksum,rss_kib=int(rss[1]),region_peak_bytes=int(region[1]),region_allocations=int(region[2])))
   for d,ns,up,down,cap in times:dispatch.append(dict(sample=sample+1,workload=work,lanes=n,mode=mode,dispatch=d,wall_ns=ns,upload_bytes=up,readback_bytes=down,capacity=cap))
  for name,data in [('epochs.csv',rows),('dispatches.csv',dispatch)]:
   if data:
    with (out/name).open('w') as f:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
  print('completed physical' if a.physical else 'completed software',sample+1,'epochs',len(rows),'dispatches',len(dispatch),flush=True)
 summary=[]
 for work,n,mode in scenarios:
  arows=[x for x in rows if (x['workload'],x['lanes'],x['mode'])==(work,n,mode)];warm=[x['epoch_ns']/1e6 for x in arows if x['epoch']>0];cold=[x['epoch_ns']/1e6 for x in arows if x['epoch']==0];opens=[x['device_open_ns']/1e6 for x in arows if x['epoch']==0];dt=[x['wall_ns']/1e6 for x in dispatch if (x['workload'],x['lanes'],x['mode'])==(work,n,mode) and x['dispatch']>1]
  def stats(x):return dict(n=len(x),mean=statistics.fmean(x),median=statistics.median(x),p95=sorted(x)[math.ceil(.95*len(x))-1],min=min(x),max=max(x))
  summary.append(dict(workload=work,lanes=n,mode=mode,warm_ms=stats(warm),cold_ms=stats(cold),device_open_ms=stats(opens),warm_dispatch_ms=stats(dt) if dt else None,workers=sorted(set(x['workers'] for x in arows)),groups=arows[0]['workgroups']))
 (out/'summary.json').write_text(json.dumps(dict(physical=a.physical,platform=platform.platform(),affinity=sorted(os.sched_getaffinity(0)),samples=a.samples,epochs_per_process=a.epochs,widths=widths,summary=summary,epoch_count=len(rows),dispatch_count=len(dispatch),binaries={w:hashlib.sha256((root/w/'bench').read_bytes()).hexdigest() for w in ('add','poly')}),indent=2)+'\n');print('DOC9_GPU_SCALE_PASS:',len(rows),'verified epochs',len(dispatch),'actual dispatches physical='+str(a.physical),flush=True)
if __name__=='__main__':main()
