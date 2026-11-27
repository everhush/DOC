#!/usr/bin/env python3
"""Original 40-leaf paper interval reduction, integrated DOC source, no native callback."""
import argparse,csv,hashlib,json,math,os,re,statistics,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'compiler'))
from doc_build import emit
def source():
 # Packed positive int64: candidate high bits; count 15 bits; odd divisor low 10 bits.
 # For these fixed paper intervals candidate<2^20, count<2^15, divisor<2^10.
 # 26 ordered odd-divisor checks per causal step keep this source within
 # admitted inference and recurrence budgets. No change to trial-division order.
 block=26
 lines=['fn candidate(s)=shift_right(s,25)','fn pcount(s)=bit_and(shift_right(s,10),32767)','fn divisor(s)=bit_and(s,1023)',f'fn c{block}(n,d)=add(d,{2*block})']
 for j in range(block-1,-1,-1):
  d='d' if j==0 else f'add(d,{2*j})'
  lines.append(f'fn c{j}(n,d)=if(le({d},quot(n,{d})),if(eq(rem(n,{d}),0),33554435,c{j+1}(n,d)),33555459)')
 lines+=['fn phase(s)=add(bit_and(s,-1024),if(eq(bit_and(candidate(s),1),0),33554435,c0(candidate(s),divisor(s))))']
 cur=[]
 for i in range(40):
  lines.extend([f'source s{i}:int={(500000+i)*33554432+3}',f'derive leaf{i}:int(s{i})=recur(s{i},x,eq(candidate(x),add(candidate(s{i}),25000)),phase(x))']);cur.append((f'leaf{i}',True))
 level=0
 while len(cur)>1:
  nxt=[]
  for j in range(0,len(cur),2):
   if j+1==len(cur):nxt.append(cur[j]);continue
   a,al=cur[j];b,bl=cur[j+1];name=f'r{level}_{j//2}';av=f'pcount({a})' if al else a;bv=f'pcount({b})' if bl else b;lines.append(f'derive {name}:int({a},{b})=add({av},{bv})');nxt.append((name,False))
  cur=nxt;level+=1
 assert cur[0][0]=='r5_0'
 return ('\n'.join(lines)+'\n').encode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--reactive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--headers',type=Path,default=HERE.parent/'runtime');p.add_argument('--cc',default='clang');p.add_argument('--samples',type=int,default=10);a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=source();(out/'prime40.doc').write_bytes(src)
 t=time.perf_counter_ns();c=emit([a.reactive.resolve()],src,True,stream=True);emit_ns=time.perf_counter_ns()-t;(out/'prime40.c').write_bytes(c)
 exe=out/'prime40';t=time.perf_counter_ns();subprocess.run([a.cc,'-std=gnu11','-O1','-pthread','-fmacro-backtrace-limit=1','-I',str(a.headers.resolve()),out/'prime40.c','-o',exe],check=True,timeout=600);build_ns=time.perf_counter_ns()-t
 # Independent sieve, not a repeated implementation of the same trial division.
 limit=525040;prime=bytearray(b'\1')*limit;prime[:2]=b'\0\0'
 for i in range(2,math.isqrt(limit-1)+1):
  if prime[i]:prime[i*i:limit:i]=b'\0'*(((limit-1-i*i)//i)+1)
 expected=sum(sum(prime[500000+i:525000+i]) for i in range(40));assert expected==76216
 mask=sorted(os.sched_getaffinity(0));cap=min(4,len(mask));q=Path('/sys/fs/cgroup/cpu.max')
 if q.exists():
  quota,period=q.read_text().split()
  if quota!='max':cap=min(cap,max(1,int(quota)//int(period)))
 modes=[str(i) for i in range(1,cap+1)]+['auto'];rows=[]
 for i in range(a.samples):
  for mode in modes if i%2==0 else reversed(modes):
   env=dict(os.environ);env.pop('DOC_WORKERS',None);env['DOC_REGION_METRICS']='1'
   if mode!='auto':env['DOC_WORKERS']=mode
   t=time.perf_counter_ns();r=subprocess.run(['taskset','-c',','.join(map(str,mask[:cap])),exe,'--demand=r5_0'],env=env,capture_output=True,timeout=120);elapsed=time.perf_counter_ns()-t
   assert r.returncode==0 and r.stdout==f'r5_0: {expected}\n'.encode() and b'DOC11_MANAGED_EVALUATIONS: 79 frontiers=7' in r.stderr and b'DOC11_REGIONS: live=0 peak=0 allocations=0' in r.stderr,(mode,r.stderr,r.stdout)
   workers=max([1]+[int(x) for x in re.findall(rb'DOC11_MANAGED_PARALLEL: lanes=\d+ workers=(\d+)',r.stderr)])
   assert workers==(cap if mode=='auto' else int(mode)),(mode,workers,r.stderr)
   rows.append(dict(sample=i+1,mode=mode,actual_workers=workers,wall_ns=elapsed,stdout=r.stdout.decode(),stderr=r.stderr.decode()))
   with (out/'samples.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
  print('integrated prime batch',i+1,flush=True)
 summary=[]
 for mode in modes:
  vals=[r['wall_ns']/1e6 for r in rows if r['mode']==mode];summary.append(dict(mode=mode,n=len(vals),mean_ms=statistics.fmean(vals),median_ms=statistics.median(vals),p95_ms=sorted(vals)[math.ceil(.95*len(vals))-1],min_ms=min(vals),max_ms=max(vals)))
 (out/'summary.json').write_text(json.dumps(dict(oracle=expected,states=119,evaluations=79,frontiers=7,affinity=mask[:cap],emit_ns=emit_ns,build_ns=build_ns,source_sha256=hashlib.sha256(src).hexdigest(),generated_sha256=hashlib.sha256(c).hexdigest(),summary=summary),indent=2)+'\n')
 print('DOC9_INTEGRATED_PRIME_PASS:',len(rows),'native runs; actual complete DOC source, no external leaf',flush=True)
if __name__=='__main__':main()
