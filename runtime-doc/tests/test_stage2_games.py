#!/usr/bin/env python3
"""Stage-2 compiler/tool rebuild and unchanged game graph CPU replay.
No host implementation of DOC expressions or gameplay rules. This gate
does not claim window/graphics, save/audio or physical GPU acceptance.
"""
import argparse,hashlib,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'compiler'))
from doc_build import bundle,emit,build

CARRIES=('frame:next_frame,player_x:next_x,player_y:next_y,coin_x:next_coin_x,coin_y:next_coin_y,score:next_score,paused:next_paused,won:next_won,animation_phase:next_animation_phase,entity_ids:next_entity_ids,entity_xs:next_entity_xs,entity_ys:next_entity_ys,next_entity_id:next_next_entity_id,issued_high_water:next_issued_high_water,prefab_template_xs:template_next_xs,prefab_template_ys:template_next_ys')
ACTIONS='.:0,w:1,s:2,a:3,d:4,p:5,r:6,e:7,x:8'

def execute(cmd,cwd,workers=1,timeout=240,isolated=False):
    env={**os.environ,'DOC_WORKERS':str(workers),'DOC_REGION_METRICS':'1'}
    if isolated:env['PATH']=''
    p=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,capture_output=True,timeout=timeout)
    assert p.returncode==0,(str(cmd[0]),p.stderr[-8000:])
    return p.stdout,p.stderr

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def rebuild(stage2,scanner,source,out,evidence,stream_scanner):
    start=time.monotonic()
    data=bundle([scanner],source,stream=stream_scanner)
    code=emit([stage2],data,stream=True)
    c=evidence/(out.name+'.c');c.write_bytes(code)
    execute(['cc','-std=gnu11','-O1','-pthread','-I',ROOT/'runtime',c,'-o',out],evidence,timeout=300)
    print(f'DOC11_STAGE2_TOOL: {out.name} source_bytes={len(data)} c_bytes={len(code)} elf_bytes={out.stat().st_size} seconds={time.monotonic()-start:.3f} sha256={digest(out)}',flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage2',required=True,type=Path);p.add_argument('--scanner',required=True,type=Path);p.add_argument('--reference',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path);a=p.parse_args()
    stage2=a.stage2.resolve();stage1_scan=a.scanner.resolve();reference=a.reference.resolve();evidence=a.evidence.resolve();evidence.mkdir(parents=True,exist_ok=True)
    scanner=evidence/'scanner2';compiler=evidence/'reactive2';planner=evidence/'gpu_plan2'
    rebuild(stage2,stage1_scan,ROOT/'compiler/module_scan.doc',scanner,evidence,False)
    rebuild(stage2,scanner,ROOT/'compiler/managed_reactive.doc',compiler,evidence,True)
    rebuild(stage2,scanner,ROOT/'compiler/gpu_plan.doc',planner,evidence,True)
    checks=0
    with tempfile.TemporaryDirectory() as tmp:
        cwd=Path(tmp);assets=cwd/'assets';shutil.copytree(REPO/'engine/levels',assets/'levels')
        for name,replay,carries,actions in [('radar_chase','edsssxwddddsspr',CARRIES,ACTIONS),('radar_chase_3d','jedsssxwddddsspr',CARRIES+',elevation:next_elevation,vertical_velocity:next_vertical_velocity',ACTIONS+',j:9')]:
            source=REPO/'engine'/(name+'.doc');exe=evidence/name;c=evidence/(name+'.c')
            start=time.monotonic();code=build([scanner],[compiler],source,exe,ROOT/'runtime',True,c,stream=True)
            print(f'DOC11_STAGE2_GAME_BUILD: {name} c_bytes={len(code)} elf_bytes={exe.stat().st_size} seconds={time.monotonic()-start:.3f} sha256={digest(exe)}',flush=True)
            linkage,_=execute(['readelf','-d',exe],cwd);assert b'libdoc' not in linkage and b'librust' not in linkage
            (evidence/(name+'-linkage.txt')).write_bytes(linkage)
            action_map=dict(x.split(':') for x in actions.split(','))
            args=['--through='+str(len(replay))]+[x.replace(':','=') for x in carries.split(',')]+[f'--fact={i}:action={action_map[ch]}' for i,ch in enumerate(replay,1)]
            expected,_=execute([reference,source,*args],cwd)
            assert expected.count(b'epoch: ')==len(replay)+1 and b'next_won: true\n' in expected
            if name=='radar_chase_3d':assert b'next_elevation: 24\n' in expected and b'render_draws: [' in expected
            (evidence/(name+'-reference.txt')).write_bytes(expected)
            assert not list(assets.rglob('*.doc'))
            for workers in (1,2,4,8):
                start=time.monotonic()
                actual,err=execute([exe,'--asset-root='+str(assets),'--backend=cpu',*args],assets,workers,isolated=True)
                assert actual==expected,(name,workers,len(actual),len(expected),err[-3000:])
                assert b'DOC11_REGIONS: live=0 ' in err
                if workers==1:assert b'DOC11_MANAGED_PARALLEL:' not in err
                else:assert b'DOC11_MANAGED_PARALLEL:' in err,(name,workers,err[-3000:])
                (evidence/(name+f'-workers-{workers}.log')).write_bytes(err)
                (evidence/(name+f'-workers-{workers}.txt')).write_bytes(actual)
                print(f'DOC11_STAGE2_REPLAY: {name} workers={workers} epochs={len(replay)+1} bytes={len(actual)} elapsed={time.monotonic()-start:.6f}s sha256={hashlib.sha256(actual).hexdigest()}',flush=True)
                checks+=1
    print(f'DOC11_STAGE2_GAMES_PASS: {checks} source-free typed CPU replays; original 2D and 3D source; Stage2 rebuilt scanner and reactive compiler; graphics and platform effects not covered',flush=True)
if __name__=='__main__':main()
