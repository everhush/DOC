#!/usr/bin/env python3
"""Build actual generated scene, exercise native GPU rendering and X11 input.
Only compiler/tool orchestration and typed observation comparison live here.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'compiler'))
from doc_build import bundle, gpu_artifacts, compile_c
REPLAY='jedsssxwddddsspr'

def checked(argv,**kwargs):
    return subprocess.run([str(x) for x in argv],check=True,timeout=240,**kwargs)

def write_shader_header(render,out):
    shader=(render/'mesh.wgsl').read_bytes()
    assert 0<len(shader)<=65536 and all(c in (9,10,13) or 32<=c<=126 for c in shader)
    plan=json.loads((render/'plan-meta.json').read_text())['original']
    assert len(plan['vertex'])==12 and len(plan['draw'])==8
    domains=[]
    for bounds in plan['vertex']+plan['draw']:
        if bounds is None:domains.append('{0,0,0}')
        else:
            assert len(bounds)==2 and all(type(x) is int for x in bounds)
            lo,hi=bounds;assert -(2**31)<=lo<=hi<2**31
            domains.append('{1,%d,%d}'%(lo,hi))
    (out/'scene_shader.h').write_text('static char scene_shader[]={'+','.join(map(str,shader))+',0};\nstatic const MeshDomain scene_domains[20]={'+','.join(domains)+'};\n')

def capture(argv,out,name,env):
    r=subprocess.run([str(x) for x in argv],cwd=out,env=env,capture_output=True,timeout=180)
    (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
    assert r.returncode==0,(name,r.returncode,r.stderr[-4000:])
    return r.stdout,r.stderr

def wait_log(proc,path,pattern):
    end=time.monotonic()+60
    while time.monotonic()<end:
        raw=path.read_bytes();match=re.search(pattern,raw,re.M)
        if match:return match
        if proc.poll() is not None:raise AssertionError((proc.returncode,raw[-4000:]))
        time.sleep(.05)
    raise TimeoutError((pattern,path.read_bytes()[-4000:]))

def check_window(stdout,stderr,expected,oracle,interactive=False):
    assert stdout==expected
    assert b'DOC11_WINDOW_PASS:' in stderr and b'DOC11_MESH_ADAPTER: physical=0' in stderr
    assert re.search(rb'DOC11_GPU_ADAPTER:.*physical=0',stderr)
    assert re.search(rb'DOC11_GPU_FRONTIER: cpu=[1-9]\d* gpu=[1-9]\d* concurrent=1',stderr)
    frames=re.findall(rb'DOC11_WINDOW_FRAME: epoch=(\d+) width=(\d+) height=(\d+) rgba=([a-f0-9]{16}) rgb=[a-f0-9]{16} kind=commit$',stderr,re.M)
    assert [(int(ep),digest.decode()) for ep,w,h,digest in frames]==[(ep,digest) for ep,_,digest in oracle]
    assert all((w,h)==(b'640',b'480') for _,w,h,_ in frames)
    if interactive:
        assert re.findall(rb'DOC11_WINDOW_INPUT: key=(.)$',stderr,re.M)==[c.encode() for c in REPLAY]
        assert b'DOC11_WINDOW_RESIZE: 800x600' in stderr and b'DOC11_WINDOW_RESIZE: 640x480' in stderr
        assert re.search(rb'DOC11_WINDOW_FRAME: epoch=0 width=800 height=600 .*kind=resize$',stderr,re.M)
    return len(frames)

def main():
    p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--wgpu-root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--cc',default='clang-18');a=p.parse_args()
    root=Path(__file__).resolve().parents[2];runtime=root/'runtime-doc/runtime';tests=root/'runtime-doc/tests'
    games=a.games.resolve();render=a.render.resolve();wgpu=a.wgpu_root.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True)
    assets=out/'assets';shutil.copytree(root/'engine/levels',assets/'levels',dirs_exist_ok=True)
    assert not list(assets.rglob('*.doc'))
    expected=(games/'radar_chase_3d-reference.txt').read_bytes()
    data=bundle([games/'scanner2'],root/'engine/radar_chase_3d.doc',stream=True)
    shader,gpu_header=gpu_artifacts([games/'gpu_plan2'],data,stream=True)
    (out/'compute.wgsl').write_bytes(shader);(out/'gpu_generated.h').write_bytes(gpu_header)
    shutil.copyfile(games/'radar_chase_3d.c',out/'scene_generated.c')
    write_shader_header(render,out)
    schema=hashlib.sha256(data).hexdigest()
    common=[a.cc,'-std=gnu11','-pthread','-I',runtime,'-I',out,'-DDOC_SOURCE_SHA256="'+schema+'"']
    san=['-O0','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie']
    compile_c(common+san+[tests/'scene_session_host.c','-lm','-o',out/'scene-session'],timeout=300,evidence=out/'compile-session.json')
    compile_c(common+san+[tests/'scene_x11_host.c','-lX11','-o',out/'scene-x11-host'],timeout=120,evidence=out/'compile-x11.json')
    env=os.environ.copy();env['DOC_GPU_ALLOW_SOFTWARE']='1';env.pop('DOC_REQUIRE_PHYSICAL_GPU',None);env['DOC_WORKERS']='4'
    assert env.get('DISPLAY')
    stdout,stderr=capture([out/'scene-session',assets,REPLAY],out,'session',env)
    assert stdout==expected and b'DOC11_SCENE_SESSION_PASS:' in stderr
    stdout,_=capture([out/'scene-x11-host'],out,'x11',env);assert b'DOC11_X11_PRESENT_PASS:' in stdout
    exe=out/'doc-scene-window'
    compile_c(common+['-O1','-DDOC_ENABLE_GPU','-DDOC_MESH_LIBRARY','-I',wgpu/'include',runtime/'scene_window.c',runtime/'mesh_render.c','-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-lX11','-lm','-o',exe],timeout=300,evidence=out/'compile-window.json')
    linkage=checked(['ldd',exe],capture_output=True).stdout;(out/'linkage.txt').write_bytes(linkage)
    assert b'libwgpu_native.so' in linkage and b'libX11.so' in linkage and b'libdoc' not in linkage and b'not found' not in linkage
    args=[exe,'--asset-root='+str(assets),'--output-root='+str(out),'--backend=auto','--verify-window']
    oracle=json.loads((render/'render-summary.json').read_text())['oracle']
    assert len(oracle)==len(REPLAY)+1
    (out/'window-wav').mkdir();(out/'cli-wav').mkdir()
    stdout,stderr=capture(args+['--replay='+REPLAY,'--save=window.chk','--audio-dir=window-wav'],out,'replay',env)
    frames=check_window(stdout,stderr,expected,oracle)
    carries=re.search(rb'^render_carries: (.+)$',expected,re.M).group(1).decode().split(',')
    actions=dict(x.split(':') for x in re.search(rb'^render_actions: (.+)$',expected,re.M).group(1).decode().split(','))
    cli=[games/'radar_chase_3d','--asset-root='+str(assets),'--output-root='+str(out),'--backend=cpu']
    carryargs=[x.replace(':','=') for x in carries]
    stdout,_=capture(cli+['--through='+str(len(REPLAY)),*carryargs,*[f'--fact={i}:action={actions[k]}' for i,k in enumerate(REPLAY,1)],'--save=cli.chk','--audio-dir=cli-wav'],out,'cli',env)
    assert stdout==expected and (out/'window.chk').read_bytes()==(out/'cli.chk').read_bytes()
    assert {x.name:x.read_bytes() for x in (out/'window-wav').glob('*.wav')}=={x.name:x.read_bytes() for x in (out/'cli-wav').glob('*.wav')}
    stdout,_=capture(args+['--load=window.chk','--replay=.'],out,'restore',env)
    compare,_=capture(cli+['--through=1',*carryargs,'--fact=1:action='+actions['.'],'--load=cli.chk'],out,'restore-cli',env)
    assert stdout==compare
    bad=bytearray((out/'window.chk').read_bytes());bad[-1]^=1;(out/'bad.chk').write_bytes(bad)
    rejected=subprocess.run([str(x) for x in args+['--load=bad.chk','--replay=.']],env=env,cwd=out,capture_output=True,timeout=60)
    (out/'rejected.stderr').write_bytes(rejected.stderr)
    assert rejected.returncode and not rejected.stdout and b'DOC11_WINDOW_PRESENTED:' not in rejected.stderr
    log=out/'interactive.stderr';typed=out/'interactive.stdout'
    with log.open('wb') as err,typed.open('wb') as std:
        proc=subprocess.Popen([str(x) for x in args+['--input-only']],cwd=out,env=env,stdout=std,stderr=err)
        try:
            win=wait_log(proc,log,rb'^DOC11_WINDOW_READY: window=(\d+)$').group(1).decode()
            checked(['xdotool','windowsize',win,'800','600'],env=env)
            wait_log(proc,log,rb'^DOC11_WINDOW_RESIZE: 800x600$')
            checked(['xdotool','windowsize',win,'640','480'],env=env)
            wait_log(proc,log,rb'^DOC11_WINDOW_RESIZE: 640x480$')
            for ep,key in enumerate(REPLAY,1):
                checked(['xdotool','key','--window',win,'space' if key=='j' else key],env=env)
                wait_log(proc,log,rb'^DOC11_WINDOW_PRESENTED: epoch='+str(ep).encode()+rb'$')
            checked(['xdotool','key','--window',win,'Escape'],env=env)
            assert proc.wait(timeout=30)==0
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
    check_window(typed.read_bytes(),log.read_bytes(),expected,oracle,interactive=True)
    (out/'window-summary.json').write_text(json.dumps({'schema':schema,'frames':frames,'interactive_frames':frames,'resize':[800,600,640,480],'actual_x11_readback':True,'physical_gpu':False,'window_transport':'validated WebGPU readback presented through X11 XPutImage','checkpoint_equal':True,'restored_typed_equal':True,'audio_equal':True,'generated_c_sha256':hashlib.sha256((out/'scene_generated.c').read_bytes()).hexdigest()},indent=2)+'\n')
    print(f'DOC11_NATIVE_WINDOW_PASS: {frames} exact replay and {frames} keyboard-triggered frames, actual X11 readback, resize, mixed software GPU, source-only checkpoint, restore, malformed checkpoint rejection and WAV parity')
if __name__=='__main__':main()
