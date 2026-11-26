#!/usr/bin/env python3
"""Actual WebGPU mesh rendering: original native game snapshots and generated WGSL.
The Rust executable is used only as an independent pixel oracle in this test.
"""
import argparse, dataclasses, hashlib, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from mesh_build import compile_mesh,MeshPlan
from mesh_frame import snapshots,pack,unpack_pixels
from test_mesh_stage import VERTEX,FRAGMENT,CLIP,VARY,COLOR

REPLAY='jedsssxwddddsspr'


def run(cmd,env,*,input=None,timeout=240):
    return subprocess.run([str(x) for x in cmd],env=env,input=input,capture_output=True,timeout=timeout)


def checked(cmd,env,**kw):
    r=run(cmd,env,**kw);assert r.returncode==0,(str(cmd[0]),r.stderr[-6000:]);return r


def proof(raw):
    h=0xcbf29ce484222325
    for x in raw:h=((h^x)*0x100000001b3)&0xffffffffffffffff
    return len(set(raw[i:i+4] for i in range(0,len(raw),4))),f'{h:016x}'


def ppm(raw,w,h):
    return f'P6\n{w} {h}\n255\n'.encode()+b''.join(raw[i:i+3] for i in range(0,len(raw),4))


def covered(raw,clear):return sum(raw[i:i+4]!=bytes(clear) for i in range(0,len(raw),4))


def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',type=Path);p.add_argument('--prebuilt',type=Path);p.add_argument('--game-output',type=Path,required=True);p.add_argument('--scene-reference',type=Path,required=True);p.add_argument('--engine',type=Path,default=ROOT.parent/'engine');p.add_argument('--wgpu-root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--physical',action='store_true');a=p.parse_args()
    out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True);wgpu=a.wgpu_root.resolve();tool=a.compiler.resolve() if a.compiler else None;env=dict(os.environ)
    if a.physical:env['DOC_REQUIRE_PHYSICAL_GPU']='1';env['DOC_GPU_REQUIRE_HARDWARE']='1';env.pop('DOC_GPU_ALLOW_SOFTWARE',None)
    else:env.pop('DOC_REQUIRE_PHYSICAL_GPU',None);env['DOC_GPU_ALLOW_SOFTWARE']='1'
    frames=snapshots(a.game_output.read_bytes());assert len(frames)==len(REPLAY)+1 and frames[0].draws!=frames[1].draws
    if a.prebuilt:
        base=a.prebuilt.resolve()
        metadata=json.loads((base/'plan-meta.json').read_text())
        def restore(key,shader):
            row=metadata[key]
            assert set(row)=={'vertex','draw','varying','colors'}
            return MeshPlan((base/shader).read_bytes(),*(tuple(tuple(d) if d is not None else None for d in row[k]) for k in ('vertex','draw','varying','colors')))
        plan=restore('original','mesh.wgsl');mutated=restore('mutated','mesh-mutated.wgsl')
        exe=base/'mesh-render'
    else:
        assert tool is not None
        vertex=(a.engine/'graphics/arena_vertex.doc').read_bytes();fragment=(a.engine/'graphics/mesh_fragment.doc').read_bytes()
        plan=compile_mesh(tool,vertex,fragment,VERTEX,FRAGMENT,CLIP,VARY,COLOR);mutated=compile_mesh(tool,vertex,fragment.replace(b'= light_r',b'= if(eq(light_r,0),0,0)'),VERTEX,FRAGMENT,CLIP,VARY,COLOR)
        exe=out/'mesh-render';checked(['cc','-std=c11','-O2','-Wall','-Wextra','-I',wgpu/'include',ROOT/'runtime/mesh_render.c','-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',exe],env)
        (out/'plan-meta.json').write_text(json.dumps({key:{k:getattr(obj,k) for k in ('vertex','draw','varying','colors')} for key,obj in [('original',plan),('mutated',mutated)]},indent=2)+'\n')
    assert plan.wgsl!=mutated.wgsl
    records={}
    def render(plan,frames,label):
        packet=pack(plan,frames);t=time.perf_counter_ns();r=run([exe],env,input=packet);elapsed=time.perf_counter_ns()-t
        (out/(label+'.log')).write_bytes(r.stderr)
        if r.returncode:
            (out/(label+'.failed-packet')).write_bytes(packet);(out/(label+'.failed.wgsl')).write_bytes(plan.wgsl)
            (out/(label+'.failure.json')).write_text(json.dumps({'returncode':r.returncode,'stdout_bytes':len(r.stdout),'packet_sha256':hashlib.sha256(packet).hexdigest(),'shader_sha256':hashlib.sha256(plan.wgsl).hexdigest()},indent=2)+'\n')
            assert not r.stdout, 'failed render published partial pixels'
            raise AssertionError((str(exe),r.returncode,r.stderr[-6000:]))
        assert b'DOC11_MESH_RENDER:' in r.stderr and b'DOC11_MESH_ADAPTER:' in r.stderr,r.stderr
        if a.physical:assert b'physical=1' in r.stderr,r.stderr
        images=unpack_pixels(r.stdout,frames);records[label]={'frames':len(images),'wall_ns':elapsed,'packet_sha256':hashlib.sha256(packet).hexdigest(),'shader_sha256':hashlib.sha256(plan.wgsl).hexdigest(),'image_sha256':[hashlib.sha256(x).hexdigest() for x in images]};(out/(label+'.log')).write_bytes(r.stderr);return images
    images=render(plan,frames,'replay');assert len(set(images[0][i:i+4] for i in range(0,len(images[0]),4)))>=7 and images[0]!=images[1]
    with tempfile.TemporaryDirectory() as td:
        snap=Path(td)/'reference.ppm';r=checked([a.scene_reference.resolve(),(a.engine/'radar_chase_3d.doc').resolve(),'--offscreen','--replay='+REPLAY,'--verify-pixels','--snapshot='+str(snap)],env)
        oracle=[(int(e),int(n),h.decode()) for e,n,h in re.findall(rb'DOC_SCENE_PIXELS: epoch=(\d+) distinct=(\d+) digest=([0-9a-f]{16})',r.stdout)]
        assert oracle==[(i,*proof(x)) for i,x in enumerate(images)],(oracle,[(i,*proof(x)) for i,x in enumerate(images)])
        assert snap.read_bytes()==ppm(images[-1],frames[-1].width,frames[-1].height),'final pixel bytes differ from frozen reference'
        (out/'reference.log').write_bytes(r.stdout+r.stderr);(out/'reference-final.ppm').write_bytes(snap.read_bytes())
    first=frames[0];far=first.draws[-1];near=(*far[:2],far[2]+12,far[3]+8,far[4]+12,100,130,160,*far[8:]);only=lambda draws:dataclasses.replace(first,draws=tuple(draws))
    near_img,far_img,near_first,near_last,*repeats=render(plan,[only([near]),only([far]),only([near,far]),only([far,near])]+[first]*16,'depth-and-repeat')
    assert covered(near_img,first.clear)>200 and covered(near_img,first.clear)==covered(far_img,first.clear) and near_img!=far_img
    for color in [(100,130,160,255),(70,100,130,255),(40,70,100,255)]:assert bytes(color) in set(near_img[i:i+4] for i in range(0,len(near_img),4)),color
    assert near_first==near_last==near_img and all(x==images[0] for x in repeats)
    changed,=render(mutated,[first],'source-mutation');changed_count=0
    for i in range(0,len(changed),4):
        original=images[0][i:i+4];new=changed[i:i+4]
        if original==bytes(first.clear):assert new==original
        else:assert new[0]==0 and new[1:]==original[1:];changed_count+=original[0]!=0
    assert changed_count>1000
    packet=pack(plan,[first,first]);bad=run([exe],env,input=packet[:-1]);assert bad.returncode and not bad.stdout and b'DOC11_MESH_REJECT:' in bad.stderr
    loss=run([exe,'--test-device-loss'],env,input=packet);assert loss.returncode and not loss.stdout and b'DOC11_MESH_DEVICE_LOSS:' in loss.stderr,loss.stderr
    (out/'device-loss.stderr').write_bytes(loss.stderr);(out/'device-loss.stdout').write_bytes(loss.stdout)
    assert b'DOC11_WGPU_DESTROY_CONFIRMED:' in loss.stderr and b'DOC11_WGPU_QUEUE_RETIRED:' in loss.stderr and b'DOC11_MESH_LOST_CALLBACK:' in loss.stderr, loss.stderr
    for name,raw in [('initial',images[0]),('jump',images[1]),('final',images[-1]),('mutated',changed)]: (out/(name+'.ppm')).write_bytes(ppm(raw,first.width,first.height))
    (out/'mesh.wgsl').write_bytes(plan.wgsl);(out/'mesh-mutated.wgsl').write_bytes(mutated.wgsl);(out/'render-summary.json').write_text(json.dumps({'physical_required':a.physical,'oracle':oracle,'changed_pixels':changed_count,'batches':records},indent=2)+'\n')
    print(f'DOC11_MESH_RENDER_PASS: {len(images)} exact replay pixel proofs and final RGB bytes, depth order, 3 lit faces, {changed_count} source-mutated pixels, 16 repeated frames, malformed and device-loss rejection; physical_required={a.physical}')
if __name__=='__main__':main()
