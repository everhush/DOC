#!/usr/bin/env python3
"""Same-source Stage-2 native CPU and frozen-reference whole-process replay evidence.

Each sample starts a new process; repeated samples do not imply a warmed GPU
or in-process steady-state measurement. No speedup threshold is asserted.
"""
import argparse,csv,hashlib,json,math,os,platform,re,statistics,subprocess,tempfile,time
from pathlib import Path

CARRIES='frame:next_frame,player_x:next_x,player_y:next_y,coin_x:next_coin_x,coin_y:next_coin_y,score:next_score,paused:next_paused,won:next_won,animation_phase:next_animation_phase,entity_ids:next_entity_ids,entity_xs:next_entity_xs,entity_ys:next_entity_ys,next_entity_id:next_next_entity_id,issued_high_water:next_issued_high_water,prefab_template_xs:template_next_xs,prefab_template_ys:template_next_ys'
ACTIONS=dict(x.split(':') for x in '.:0,w:1,s:2,a:3,d:4,p:5,r:6,e:7,x:8,j:9'.split(','))
GAMES=[('radar_chase','edsssxwddddsspr',CARRIES),('radar_chase_3d','jedsssxwddddsspr',CARRIES+',elevation:next_elevation,vertical_velocity:next_vertical_velocity')]

def sha(data):return hashlib.sha256(data).hexdigest()
def digest(p):return sha(p.read_bytes())
def p95(seq):return sorted(seq)[math.ceil(0.95*len(seq))-1]
def sample(cmd,cwd,workers,report):
    env={**os.environ,'DOC_REGION_METRICS':'1'};env.pop('DOC_WORKERS',None)
    if workers!='auto':env['DOC_WORKERS']=workers
    t=time.perf_counter_ns();p=subprocess.run(['/usr/bin/time','-f','%M','-o',str(report),*map(str,cmd)],cwd=cwd,env=env,capture_output=True,timeout=120);elapsed=time.perf_counter_ns()-t
    assert p.returncode==0,(cmd[0],p.stderr[-4000:]);return elapsed,int(report.read_text().strip()),p.stdout,p.stderr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--engine',required=True,type=Path);ap.add_argument('--evidence',required=True,type=Path);ap.add_argument('--reference',required=True,type=Path);ap.add_argument('--assets',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--source-sha',required=True);ap.add_argument('--provenance',choices=['exact-ci','local-archived-bootstrap'],required=True);ap.add_argument('--samples',type=int,default=9);a=ap.parse_args();assert a.samples>=5;a.out.mkdir(parents=True,exist_ok=True)
    root=a.engine.resolve();evidence=a.evidence.resolve();assets=a.assets.resolve();reference=a.reference.resolve();rows=[];summary=[]
    meta={'source_sha':a.source_sha,'provenance':a.provenance,'reference_sha256':digest(reference),'host':platform.platform(),'logical_affinity':sorted(os.sched_getaffinity(0)),'cpu':next((x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),None),'compiler':subprocess.check_output(['cc','--version'],text=True).splitlines()[0],'samples':a.samples,'measurement':'fresh process wall including launch, typed stdout and GNU time wrapper; RSS KiB per child; no GPU or steady-state claim','games':{}}
    with tempfile.TemporaryDirectory() as tmp:
        report=Path(tmp)/'rss'
        for name,replay,carries in GAMES:
            exe=evidence/name;source=root/(name+'.doc');expected_file=evidence/(name+'-reference.txt');expected=expected_file.read_bytes();args=['--through='+str(len(replay))]+[x.replace(':','=') for x in carries.split(',')]+[f'--fact={i}:action={ACTIONS[ch]}' for i,ch in enumerate(replay,1)]
            meta['games'][name]={'source_sha256':digest(source),'binary_sha256':digest(exe),'binary_bytes':exe.stat().st_size,'generated_c_sha256':digest(evidence/(name+'.c')),'generated_c_bytes':(evidence/(name+'.c')).stat().st_size,'typed_output_sha256':sha(expected),'args':args,'assets':{str(x.relative_to(assets)):digest(x) for x in sorted(assets.rglob('*')) if x.is_file()}}
            for mode,workers in [('reference','auto')]+[('native',str(x)) for x in (1,2,4,8)]+[('native','auto')]:
                cmd=[reference,source,*args] if mode=='reference' else [exe,'--asset-root='+str(assets),'--backend=cpu',*args];subset=[]
                for trial in range(a.samples):
                    elapsed,rss,out,err=sample(cmd,assets,workers,report);assert out==expected,(name,mode,workers,sha(out),sha(expected));actual=[int(n) for n in re.findall(rb'DOC11_MANAGED_PARALLEL: lanes=\d+ workers=(\d+)',err)]
                    if mode=='native':assert b'DOC11_REGIONS: live=0 ' in err
                    row={'game':name,'mode':mode,'requested_workers':workers,'trial':trial,'wall_ns':elapsed,'rss_kib':rss,'max_reported_workers':max(actual,default=1) if mode=='native' else '', 'parallel_frontiers':len(actual) if mode=='native' else '', 'output_sha256':sha(out)};rows.append(row);subset.append(row)
                times=[r['wall_ns']/1e6 for r in subset];mem=[r['rss_kib'] for r in subset];result={'game':name,'mode':mode,'workers':workers,'p50_ms':statistics.median(times),'p95_ms':p95(times),'max_rss_kib':max(mem),'max_reported_workers':max((r['max_reported_workers'] for r in subset),default='')};summary.append(result);print('DOC11_CPU_BENCH:',json.dumps(result),flush=True)
    with (a.out/'samples.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (a.out/'summary.json').write_text(json.dumps({'metadata':meta,'results':summary},indent=2)+'\n');print(f'DOC11_CPU_BENCH_PASS: {len(rows)} complete replay samples, exact typed output parity; no GPU claim',flush=True)
if __name__=='__main__':main()
