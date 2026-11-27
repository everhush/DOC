#!/usr/bin/env python3
"""Real software WebGPU poll latency A/B on the unchanged original game replays."""
import argparse,csv,hashlib,json,math,os,re,shutil,statistics,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(args,**kwargs):
    p=subprocess.run([str(x) for x in args],capture_output=True,timeout=240,**kwargs)
    if p.returncode:raise RuntimeError(str(args)+'\n'+p.stderr.decode(errors='replace')[-4000:])
    return p
def main():
    p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True);p.add_argument('--gpu',type=Path,required=True);p.add_argument('--wgpu',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--samples',type=int,default=30);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);games=a.games.resolve();gpu=a.gpu.resolve();wgpu=a.wgpu.resolve()
    base=ROOT/'runtime';candidate=out/'poll-diagnostic-headers';shutil.copytree(base,candidate)
    path=candidate/'gpu_values.h';code=path.read_text()
    old='struct timespec interval={0,1000000},start,now;'
    new='struct timespec interval={0,50000},start,now;'
    assert code.count(old)==1;code=code.replace(old,new)
    old='wgpuInstanceProcessEvents(gpu_instance);nanosleep(&interval,NULL);'
    new='wgpuInstanceProcessEvents(gpu_instance);if(!atomic_load(done)){nanosleep(&interval,NULL);if(interval.tv_nsec<1000000){interval.tv_nsec*=2;if(interval.tv_nsec>1000000)interval.tv_nsec=1000000;}}'
    assert code.count(old)==1;path.write_text(code.replace(old,new))
    metadata=json.loads((games/'cpu-benchmark/summary.json').read_text())['metadata']['games']
    scenarios=[]
    for name in metadata:
        hdr=out/name;hdr.mkdir();shutil.copy2(gpu/'games'/(name+'-gpu.h'),hdr/'gpu_generated.h')
        src=games/(name+'.c');assert src.read_bytes()==(gpu/'games'/(name+'.c')).read_bytes()
        for version,headers in [('baseline',base),('poll-diagnostic',candidate)]:
            exe=out/(name+'-'+version)
            run(['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-I',headers,'-I',hdr,'-I',wgpu/'include',src,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-lm','-o',exe])
            scenarios.append((name,version))
    xdg=out/'xdg';xdg.mkdir(mode=0o700)
    assets=out/'assets';shutil.copytree(ROOT.parent/'engine/levels',assets/'levels')
    for name,m in metadata.items():
        for f,h in m['assets'].items():assert hashlib.sha256((assets/f).read_bytes()).hexdigest()==h
    rows=[];dispatch=[];raw=out/'raw';raw.mkdir()
    for sample in range(-3,a.samples):
        order=scenarios if sample%2==0 else list(reversed(scenarios))
        for name,version in order:
            m=metadata[name];env={**os.environ,'DOC_GPU_ALLOW_SOFTWARE':'1','DOC_REGION_METRICS':'1','DOC_WORKERS':'4','XDG_RUNTIME_DIR':str(xdg)}
            env.pop('DOC_REQUIRE_PHYSICAL_GPU',None);env.pop('DOC_GPU_TEST_FAIL_DISPATCH',None)
            cmd=[out/(name+'-'+version),'--asset-root='+str(assets),'--backend=auto',*m['args']]
            t=time.perf_counter_ns();q=run(cmd,env=env);wall=time.perf_counter_ns()-t
            assert hashlib.sha256(q.stdout).hexdigest()==m['typed_output_sha256'],(name,version)
            assert b'DOC11_REGIONS: live=0 ' in q.stderr and re.search(rb'DOC11_GPU_ADAPTER: .* physical=0 ',q.stderr),q.stderr
            opens=re.findall(rb'DOC11_GPU_OPEN_TIMING: wall_ns=(\d+)',q.stderr)
            times=[tuple(map(int,r)) for r in re.findall(rb'DOC11_GPU_DISPATCH_TIMING: dispatch=(\d+) wall_ns=(\d+) upload_bytes=(\d+) readback_bytes=(\d+) capacity=(\d+)',q.stderr)]
            assert len(opens)==1 and len(times)==11 and [t[0] for t in times]==list(range(1,12))
            assert b'DOC11_GPU_POOL_METRICS: event=closed' in q.stderr
            if sample>=0:
                rows.append(dict(sample=sample+1,game=name,variant=version,wall_ms=wall/1e6,open_ms=int(opens[0])/1e6,warm_median_ms=statistics.median(r[1] for r in times[1:])/1e6,sha256=hashlib.sha256(q.stdout).hexdigest()))
                for ordinal,ns,up,down,cap in times:dispatch.append(dict(sample=sample+1,game=name,variant=version,dispatch=ordinal,wall_ns=ns,upload_bytes=up,readback_bytes=down,capacity=cap))
                (raw/f'{sample+1:03d}-{name}-{version}.stderr').write_bytes(q.stderr)
        if sample>=0:print('completed',sample+1,flush=True)
    for file,data in [('samples.csv',rows),('dispatch.csv',dispatch)]:
        with (out/file).open('w') as f:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)
    results=[]
    for name,version in scenarios:
        vals=[r for r in rows if r['game']==name and r['variant']==version];d={'game':name,'variant':version,'samples':len(vals)}
        for key in ['wall_ms','open_ms','warm_median_ms']:
            values=[r[key] for r in vals];d[key]={'mean':statistics.fmean(values),'median':statistics.median(values),'p95':sorted(values)[math.ceil(.95*len(values))-1],'min':min(values),'max':max(values)}
        results.append(d)
    (out/'summary.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
if __name__=='__main__':main()
