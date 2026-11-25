#!/usr/bin/env python3
"""Unchanged Stage-2 game source, real mixed compute, failed epoch rollback.

The native GPU binary and CPU-only binary use identical compiler-emitted C;
the GPU build adds the independently generated WGSL and narrow WebGPU ABI.
The reference output is the same exact-checkout frozen-oracle replay already
verified in stage2-games, not an alternative Python game implementation.
"""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from doc_build import build_bundled,bundle
from test_stage2_games import CARRIES,ACTIONS
from gpu_game_trace import trace,first_successor_dispatch,self_test

GAMES=[('radar_chase','edsssxwddddsspr',CARRIES,ACTIONS),
       ('radar_chase_3d','jedsssxwddddsspr',CARRIES+',elevation:next_elevation,vertical_velocity:next_vertical_velocity',ACTIONS+',j:9')]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def execute(exe,assets,args,backend,physical=False,fail_at=None):
    env=dict(os.environ)
    for k in ('DOC_REQUIRE_PHYSICAL_GPU','DOC_GPU_ALLOW_SOFTWARE','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
    env.update(PATH='',DOC_WORKERS='4',DOC_REGION_METRICS='1')
    if physical:env['DOC_REQUIRE_PHYSICAL_GPU']='1'
    else:env['DOC_GPU_ALLOW_SOFTWARE']='1'
    if fail_at is not None:env['DOC_GPU_TEST_FAIL_DISPATCH']=str(fail_at)
    start=time.perf_counter_ns()
    r=subprocess.run([str(exe),'--asset-root='+str(assets),'--backend='+backend,*args],cwd=assets,env=env,capture_output=True,timeout=240)
    return r,time.perf_counter_ns()-start

def record(out,name,r):
    (out/(name+'.stdout')).write_bytes(r.stdout)
    (out/(name+'.stderr')).write_bytes(r.stderr)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--games',required=True,type=Path);p.add_argument('--wgpu-root',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path)
    p.add_argument('--engine',type=Path,default=ROOT.parent/'engine');p.add_argument('--physical',action='store_true')
    a=p.parse_args();games=a.games.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True)
    scanner=games/'scanner2';compiler=games/'reactive2';planner=games/'gpu_plan2';engine=a.engine.resolve()
    self_test();summary={}
    with tempfile.TemporaryDirectory() as tmp:
        assets=Path(tmp)/'assets';shutil.copytree(engine/'levels',assets/'levels');assert not list(assets.rglob('*.doc'))
        for name,replay,carries,actions in GAMES:
            action_map=dict(x.split(':') for x in actions.split(','))
            args=['--through='+str(len(replay))]+[x.replace(':','=') for x in carries.split(',')]+[f'--fact={i}:action={action_map[ch]}' for i,ch in enumerate(replay,1)]
            expected=(games/(name+'-reference.txt')).read_bytes()
            starts=[m.start() for m in re.finditer(rb'(?m)^epoch: \d+\n',expected)]
            assert len(starts)==len(replay)+1 and starts[0]==0
            source=engine/(name+'.doc');snapshot=bundle([scanner],source,stream=True)
            exe=out/(name+'-gpu');c=out/(name+'.c');wgsl=out/(name+'.wgsl')
            start=time.perf_counter_ns()
            code=build_bundled([compiler],snapshot,exe,ROOT/'runtime',True,c,stream=True,gpu_plan=[planner],wgpu_root=a.wgpu_root,emit_wgsl=wgsl,emit_gpu_header=out/(name+'-gpu.h'))
            build_ns=time.perf_counter_ns()-start
            assert code==(games/(name+'.c')).read_bytes(),'CPU/GPU generated C differs'
            # CPU-only ELF is a deterministic absent-WebGPU case, regardless of
            # installed driver. Auto may fall back before starting an epoch.
            fallback,_=execute(games/name,assets,args,'auto')
            record(out,name+'-absent-auto',fallback)
            assert fallback.returncode==0 and fallback.stdout==expected and b'DOC11_GPU_DISPATCH:' not in fallback.stderr and b'DOC11_REGIONS: live=0 ' in fallback.stderr
            strict,_=execute(games/name,assets,args,'gpu')
            record(out,name+'-absent-explicit',strict)
            assert strict.returncode and not strict.stdout and b'DOC_GPU_UNAVAILABLE' in strict.stderr
            actual,elapsed=execute(exe,assets,args,'auto',a.physical);record(out,name+'-auto',actual)
            assert actual.returncode==0 and actual.stdout==expected,(name,actual.returncode,actual.stderr[-8000:])
            assert b'DOC11_GPU_ADAPTER:' in actual.stderr and b'DOC11_REGIONS: live=0 ' in actual.stderr
            if a.physical:assert re.search(rb'(?m)^DOC11_GPU_ADAPTER: .* physical=1 ',actual.stderr)
            epochs=trace(actual.stderr)
            assert len(epochs)==len(starts) and sum(e['mixed_frontiers'] for e in epochs[1:])>0 and sum(e['concurrent_frontiers'] for e in epochs[1:])>0,'no actual concurrent mixed successor frontier'
            epoch,ordinal=first_successor_dispatch(epochs)
            # Select a real successor dispatch from the successful trace, not a
            # hardcoded dispatch count. No byte of that failed successor may
            # be printed; all earlier committed epochs must match the oracle.
            failed,_=execute(exe,assets,args,'auto',a.physical,ordinal);record(out,name+'-fault',failed)
            assert failed.returncode and failed.stdout==expected[:starts[epoch]],(name,epoch,failed.stderr[-8000:])
            assert f'DOC11_GPU_INJECTED_FAILURE: dispatch={ordinal}\n'.encode() in failed.stderr and b'DOC11_REGIONS: live=0 ' in failed.stderr
            strict,_=execute(exe,assets,args,'gpu',a.physical);record(out,name+'-explicit',strict)
            assert strict.returncode and not strict.stdout and b'DOC_GPU_UNSUPPORTED' in strict.stderr
            linkage=subprocess.check_output(['readelf','-d',exe]);(out/(name+'-linkage.txt')).write_bytes(linkage)
            assert b'libwgpu_native' in linkage and b'librust' not in linkage and b'libdoc' not in linkage
            summary[name]={'source_sha256':sha(source),'c_sha256':sha(c),'wgsl_sha256':sha(wgsl),'binary_sha256':sha(exe),'binary_bytes':exe.stat().st_size,'reference_sha256':hashlib.sha256(expected).hexdigest(),'build_ns':build_ns,'replay_ns':elapsed,'epochs':epochs,'fault_epoch':epoch,'fault_dispatch':ordinal}
            print(f'DOC11_GAME_GPU_PASS: {name} epochs={len(epochs)} gpu_lanes={sum(e["gpu_lanes"] for e in epochs)} mixed_frontiers={sum(e["mixed_frontiers"] for e in epochs)} rejected_epoch={epoch} physical_required={a.physical}',flush=True)
    (out/'summary.json').write_text(json.dumps({'physical_required':a.physical,'games':summary},indent=2)+'\n')
if __name__=='__main__':main()
