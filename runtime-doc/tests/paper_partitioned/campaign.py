#!/usr/bin/env python3
"""Original-size DOC-emitted partitioned CPU benchmark; exact reference counts and oracle."""
import csv, json, os, re, statistics, subprocess, sys, time
from pathlib import Path
H=Path(__file__).resolve().parent
base=H.parent/'paper-scale/final-fullsize-samples.csv'
reference={(r['scenario'],int(r['case'])):(int(r['evaluations']),int(r['value'])) for r in csv.DictReader(base.open()) if r['sample']=='1' and r['variant']=='tuned' and r['requested']=='auto'}
cases=[('reduction','cold',0),*[('reduction','density',n) for n in (1,8,64,512,2048)],('dense','dense-cheap',0),*[('financial','financial',n) for n in (1,64,1024)],*[('sorting','bitonic',n) for n in (1,8,64,256,512)]]
fields=['sample','profile','scenario','changed','requested','states','derived','evaluations','value','cold_ms','update_ms','wall_ms','launched','peak_workers','stdout','stderr']
rounds=int(sys.argv[1]) if len(sys.argv)>1 else 3
cpus=','.join(str(x) for x in sorted(os.sched_getaffinity(0))[:4])
with (H/'samples.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();f.flush()
 for s in range(1,rounds+1):
  ordered=cases if s%2 else list(reversed(cases))
  for tag,scenario,n in ordered:
   for mode in (['1','auto'] if s%2 else ['auto','1']):
    env=os.environ.copy();env.pop('DOC_WORKERS',None)
    if mode!='auto':env['DOC_WORKERS']=mode
    start=time.monotonic_ns();p=subprocess.run(['taskset','-c',cpus,str(H/tag/'native'),scenario,str(n)],env=env,capture_output=True,text=True,timeout=300);elapsed=(time.monotonic_ns()-start)/1e6
    if p.returncode:raise RuntimeError((tag,scenario,n,mode,p.returncode,p.stdout,p.stderr[-2000:]))
    a=dict(re.findall(r'(\w+)=([^\s]+)',p.stdout.splitlines()[0]));assert 'live=0' in p.stdout
    expected=reference[scenario,n];assert (int(a['evaluations']),int(a['value']))==expected,(tag,n,a,expected)
    peak=max([1]+[int(k) for k in re.findall(r'workers=(\d+)',p.stderr)])
    w.writerow(dict(sample=s,profile=tag,scenario=scenario,changed=n,requested=mode,states=a['states'],derived=a['derived'],evaluations=a['evaluations'],value=a['value'],cold_ms=a['cold_ms'],update_ms=a['update_ms'],wall_ms=elapsed,launched=a['launched'],peak_workers=peak,stdout=p.stdout,stderr=p.stderr));f.flush()
    print('PASS',s,tag,scenario,n,mode,a['evaluations'],a['value'],a['cold_ms'],a['update_ms'],peak,flush=True)
rows=list(csv.DictReader((H/'samples.csv').open()));summary=[]
for tag,sc,n in cases:
 for mode in ('1','auto'):
  group=[x for x in rows if x['profile']==tag and x['scenario']==sc and int(x['changed'])==n and x['requested']==mode];assert len(group)==rounds
  vals=[float(x['cold_ms' if sc=='cold' else 'update_ms']) for x in group];summary.append(dict(profile=tag,scenario=sc,changed=n,requested=mode,states=int(group[0]['states']),derived=int(group[0]['derived']),evaluations=int(group[0]['evaluations']),value=int(group[0]['value']),samples=len(vals),mean_ms=statistics.mean(vals),median_ms=statistics.median(vals),min_ms=min(vals),max_ms=max(vals),peak_workers=max(int(x['peak_workers']) for x in group)))
(H/'summary.json').write_text(json.dumps(dict(scope='test-only partitioned compiler-emitted native DAG',affinity=cpus,samples=len(rows),results=summary),indent=2)+'\n')
