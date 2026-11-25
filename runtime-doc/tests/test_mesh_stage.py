#!/usr/bin/env python3
"""Self-hosted DOC vertex/fragment source, interval admission and host ABI checks."""
import argparse
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from mesh_build import compile_mesh, stage

# Immutable scene ABI facts in the original Radar Chase 3D graph, NOT shader code.
VERTEX='x:vertex:0:-220:220,y:vertex:1:-3:32,z:vertex:2:-220:220,nx:vertex:3:-1:1,ny:vertex:4:-1:1,shift_x:draw:0:-220:220,shift_y:draw:1:-20:150,shift_z:draw:2:-220:220,red:draw:3:64:255,green:draw:4:64:255,blue:draw:5:64:255,scale:draw:6:1:3,camera_w:draw:7:1024:1024'
FRAGMENT='light_r:varying:0:0:255,light_g:varying:1:0:255,light_b:varying:2:0:255'
CLIP='clip_x,clip_y,clip_z,clip_w';VARY='lit_r,lit_g,lit_b';COLOR='color_r,color_g,color_b'


def rejects(fn):
    try:fn()
    except (ValueError,KeyError):return
    raise AssertionError('invalid mesh admitted')


def main():
    p=argparse.ArgumentParser();p.add_argument('--compiler',required=True,type=Path);p.add_argument('--engine',type=Path,default=ROOT.parent/'engine');p.add_argument('--evidence',required=True,type=Path);a=p.parse_args();tool=a.compiler.resolve();a.evidence.mkdir(parents=True,exist_ok=True)
    v=(a.engine/'graphics/arena_vertex.doc').read_bytes();f=(a.engine/'graphics/mesh_fragment.doc').read_bytes();scene=(a.engine/'radar_chase_3d.doc').read_text()
    for name,value in [('render_vertex_bindings',VERTEX),('render_fragment_bindings',FRAGMENT),('render_clip',CLIP),('render_varying',VARY),('render_color',COLOR)]:assert f'source {name}: text = "{value}"' in scene
    def build(vertex=v,fragment=f,vb=VERTEX,fb=FRAGMENT,clip=CLIP,vary=VARY,color=COLOR):return compile_mesh(tool,vertex,fragment,vb,fb,clip,vary,color)
    plan=build();assert plan.varying==plan.colors==((4,255),)*3;assert b'@vertex fn vs_main' in plan.wgsl and b'@fragment fn fs_main' in plan.wgsl and b'vf00000014' in plan.wgsl
    _,vr,_=stage(tool,v,0,VERTEX,CLIP+','+VARY);assert vr==((-3520,3520),(-1847,2498),(-1494,2301),(1024,1024),(4,255),(4,255),(4,255))
    changed=build(vertex=v.replace(b'sub(c,60)',b'sub(c,40)'));assert changed.wgsl!=plan.wgsl and changed.varying==((24,255),)*3
    bad=[lambda:build(vb=VERTEX.replace('scale:draw:6:1:3','scale:draw:6:1:2147483647')),lambda:build(vb=VERTEX.replace('red:draw:3:64:255','red:draw:3:0:255')),lambda:build(vb=VERTEX.replace('ny:vertex:4:-1:1','ny:vertex:3:-1:1')),lambda:build(vb=VERTEX.replace('x:vertex:0:-220:220','x:varying:0:-220:220')),lambda:build(vb=VERTEX.replace('camera_w:draw:7:1024:1024','camera_w:draw:7:0:0')),lambda:build(fb=FRAGMENT.replace('light_r:varying:0:0:255','light_r:varying:0:10:255')),lambda:build(vertex=v.replace(b'sub(c,60)',b'quot(c,60)')),lambda:build(vertex=v+b'\nfn unused(x)=add(x,2147483648)\n'),lambda:build(clip='world_x,clip_y,clip_z,nx'),lambda:build(color='color_r,color_g,unknown')]
    for fn in bad:rejects(fn)
    vertices=[[0,0,0,0,1]+[0]*7]*3;draw=[[0,0,0,200,150,100,1,1024]];indices=[0,1,2];plan.validate(vertices,draw,indices)
    for vert,d,idx in [([[221]+[0]*11]*3,draw,indices),(vertices,[[0,0,0,0,150,100,1,1024]],indices),(vertices,draw,[0,1,3]),(vertices,draw,[0,1]),(vertices,draw,[])]:rejects(lambda:plan.validate(vert,d,idx))
    (a.evidence/'mesh.wgsl').write_bytes(plan.wgsl);(a.evidence/'mesh-changed.wgsl').write_bytes(changed.wgsl)
    print(f'DOC11_MESH_STAGE_PASS: original two stages, source mutation, {len(bad)} negative source/authority cases, 5 upload rejections, sha256={hashlib.sha256(plan.wgsl).hexdigest()}; source and interval proof only, no device execution')
if __name__=='__main__':main()
