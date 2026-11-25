#!/usr/bin/env python3
"""Checked binary mesh transport, exact game observation, independent C decoder."""
import argparse, dataclasses, os, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from mesh_build import MeshPlan
from mesh_frame import snapshots,pack,unpack_pixels


def run(cmd,*,input=None):
    return subprocess.run([str(x) for x in cmd],input=input,capture_output=True,timeout=90,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})


def reject(f):
    try:f()
    except (ValueError,SyntaxError):return
    raise AssertionError('invalid transport accepted')


def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--engine',type=Path,required=True);a=p.parse_args()
    # Domains are taken from the unchanged authored scene. The placeholder
    # shader is transport-only; the actual render gate uses generated WGSL.
    plan=MeshPlan(b'// transport-only',((-220,220),(-3,32),(-220,220),(-1,1),(-1,1))+(None,)*7,((-220,220),(-20,150),(-220,220),(64,255),(64,255),(64,255),(1,3),(1024,1024)),((4,255),)*3,((4,255),)*3)
    src=a.engine/'radar_chase_3d.doc';result=run([a.reference.resolve(),src.resolve()]);assert not result.returncode,result.stderr
    frame,=snapshots(result.stdout);assert len(frame.vertices)>0 and len(frame.draws)>2 and frame.clear==(12,18,30,255)
    with tempfile.TemporaryDirectory() as td:
        exe=Path(td)/'check';cc=run(['cc','-std=c11','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-pie','-no-pie','-I',ROOT/'runtime',ROOT/'tests/mesh_packet_check.c','-o',exe]);assert not cc.returncode,cc.stderr
        encoded=pack(plan,[frame,frame]);ok=run([exe],input=encoded);assert ok.returncode==0 and ok.stdout==b'2 2457600\n',ok
        invalid=[dataclasses.replace(frame,width=0),dataclasses.replace(frame,height=4097),dataclasses.replace(frame,clear=(0,0,0,256)),dataclasses.replace(frame,indices=(len(frame.vertices),)*3),dataclasses.replace(frame,draws=((0,0,*frame.draws[0][2:]),)),dataclasses.replace(frame,draws=((0,4,*frame.draws[0][2:]),)),dataclasses.replace(frame,draws=((4294967295,3,*frame.draws[0][2:]),)),dataclasses.replace(frame,vertices=((221,*frame.vertices[0][1:]),)+frame.vertices[1:]),dataclasses.replace(frame,draws=(frame.draws[0][:5]+(0,)+frame.draws[0][6:],)),dataclasses.replace(frame,width=4096,height=4096)]
        for i,bad in enumerate(invalid):reject(lambda:pack(plan,[bad,bad] if i==len(invalid)-1 else [bad]))
        reject(lambda:pack(plan,[frame]*33));reject(lambda:pack(dataclasses.replace(plan,wgsl=b'bad\0shader'),[frame]));reject(lambda:pack(dataclasses.replace(plan,vertex=((1,0),)*12),[frame]))
        reject(lambda:snapshots(result.stdout+b'\nrender_clear: [0,0,0,0]\n'));reject(lambda:snapshots(b'epoch: 2\n'+result.stdout));reject(lambda:snapshots(b'render_draws: []\n'));reject(lambda:unpack_pixels(b'', [frame]))
        assert len(unpack_pixels(bytes(frame.width*frame.height*8),[frame,frame]))==2
        raw=pack(plan,[frame]);start=16+20*12+len(plan.wgsl);verts=start+24;idx=verts+len(frame.vertices)*48;draw=idx+len(frame.indices)*4
        def word(offset,value):return raw[:offset]+struct.pack('<I',value)+raw[offset+4:]
        damaged=[b'',raw[:7],raw[:-1],raw+b'X',b'BADMAGIC'+raw[8:],word(8,65537),word(12,33),word(16,2),word(20,1000),word(start,0),word(start+4,4097),word(start+8,65537),word(start+12,4),word(start+16,129),word(verts,221),word(idx,len(frame.vertices)),word(draw,4294967295),word(draw+4,0),word(draw+4,4),word(draw+20,0),raw[:256]+b'\0'+raw[257:]]
        for bad in damaged:
            r=run([exe],input=bad);assert r.returncode==1 and not r.stdout and not any(x in r.stderr for x in (b'AddressSanitizer',b'LeakSanitizer',b'runtime error:')),r
        # Every truncation of a small valid packet rejects without leaking.
        small=dataclasses.replace(frame,vertices=frame.vertices[:3],indices=(0,1,2),draws=((0,3,*frame.draws[0][2:]),),width=1,height=1)
        packet=pack(plan,[small]);assert run([exe],input=packet).stdout==b'1 4\n'
        for n in range(len(packet)):
            r=run([exe],input=packet[:n]);assert r.returncode==1 and not r.stdout and not r.stderr,(n,r.stderr)
        print(f'DOC11_MESH_PACKET_PASS: real game frame, {len(invalid)+7} Python rejection cases, {len(damaged)} corrupt packets, {len(packet)} truncation points; ASan/UBSan, no partial publication')
if __name__=='__main__':main()
