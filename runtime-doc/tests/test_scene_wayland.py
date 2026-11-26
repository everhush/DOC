#!/usr/bin/env python3
"""Actual native Wayland (not XWayland) using Weston and the shared renderer.
Headless replay and an independently nested compositor's real keyboard events.
Frame callbacks and buffer releases prove protocol progress, not scanout.
"""
import argparse,contextlib,hashlib,json,os,re,shutil,stat,subprocess,tempfile,time
from pathlib import Path
from test_scene_window import REPLAY,checked,capture,wait_log,write_shader_header
from doc_build import bundle,gpu_artifacts,compile_c

@contextlib.contextmanager
def compositor(out,backend):
    with tempfile.TemporaryDirectory(prefix='doc-wl-') as td:
        runtime=Path(td);runtime.chmod(0o700)
        env=dict(os.environ,XDG_RUNTIME_DIR=str(runtime))
        env.pop('WAYLAND_DISPLAY',None);env.pop('WAYLAND_SOCKET',None)
        if backend=='headless':env.pop('DISPLAY',None)
        socket='doc-native-wayland'
        cmd=['weston','--backend='+backend,'--shell=kiosk-shell.so','--renderer=pixman','--no-config','--idle-time=0','--width=640','--height=480','--socket='+socket,'--log='+str(out/(backend+'-weston.log'))]
        (out/(backend+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        with (out/(backend+'-weston.stderr')).open('wb') as log:
            proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    if proc.poll() is not None:raise AssertionError(('weston startup',backend,proc.returncode))
                    if (runtime/socket).exists() and stat.S_ISSOCK((runtime/socket).stat().st_mode):break
                    time.sleep(.05)
                else:raise TimeoutError('Weston socket unavailable')
                client=dict(env,WAYLAND_DISPLAY=socket,DOC_GPU_ALLOW_SOFTWARE='1',DOC_WORKERS='4',WAYLAND_DEBUG='client')
                client.pop('DISPLAY',None);client.pop('DOC_REQUIRE_PHYSICAL_GPU',None)
                yield client
                assert proc.poll() is None,'compositor exited before client validation completed'
            finally:
                if proc.poll() is None:proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()

def validate(stdout,stderr,expected,oracle,interactive=False):
    assert stdout==expected
    assert b'DOC11_WAYLAND_PASS:' in stderr and b'DOC11_MESH_ADAPTER: physical=0' in stderr
    assert re.search(rb'DOC11_GPU_ADAPTER:.*physical=0',stderr)
    assert re.search(rb'DOC11_GPU_FRONTIER: cpu=[1-9]\d* gpu=[1-9]\d* concurrent=1',stderr)
    assert re.search(rb'xdg_surface@\d+\.ack_configure\(',stderr) and re.search(rb'wl_surface@\d+\.attach\(',stderr)
    assert re.search(rb'wl_callback@\d+\.done\(',stderr) and re.search(rb'wl_buffer@\d+\.release\(',stderr)
    frames=re.findall(rb'^DOC11_WAYLAND_FRAME: epoch=(\d+) width=(\d+) height=(\d+) rgba=([a-f0-9]{16}) callback=(\d+) kind=commit$',stderr,re.M)
    assert [(int(ep),digest.decode()) for ep,w,h,digest,cb in frames]==[(ep,digest) for ep,_,digest in oracle],frames
    assert all((w,h)==(b'640',b'480') for _,w,h,_,_ in frames)
    assert all(int(f[-1])>i for i,f in enumerate(frames))
    match=re.search(rb'DOC11_WAYLAND_BUFFER_LIFETIME: frames=(\d+) releases=(\d+) slots=3',stderr)
    assert match and int(match[1])>=len(frames) and int(match[2])>=int(match[1])-3
    if interactive:
        assert re.findall(rb'^DOC11_WAYLAND_INPUT: key=(.)$',stderr,re.M)==[c.encode() for c in REPLAY]
        assert b'DOC11_WAYLAND_FOCUS' in stderr and re.search(rb'wl_keyboard@\d+\.key\(',stderr)
    return len(frames)

def main():
    p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--wgpu-root',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--cc',default='clang-18');a=p.parse_args()
    repo=Path(__file__).resolve().parents[2];runtime=repo/'runtime-doc/runtime'
    games=a.games.resolve();render=a.render.resolve();wgpu=a.wgpu_root.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True)
    assets=out/'assets';shutil.copytree(repo/'engine/levels',assets/'levels',dirs_exist_ok=True);assert not list(assets.rglob('*.doc'))
    data=bundle([games/'scanner2'],repo/'engine/radar_chase_3d.doc',stream=True)
    shader,gpu_header=gpu_artifacts([games/'gpu_plan2'],data,stream=True)
    (out/'compute.wgsl').write_bytes(shader);(out/'gpu_generated.h').write_bytes(gpu_header)
    shutil.copyfile(games/'radar_chase_3d.c',out/'scene_generated.c');write_shader_header(render,out)
    schema=hashlib.sha256(data).hexdigest()
    protocol=Path('/usr/share/wayland-protocols/stable/xdg-shell/xdg-shell.xml')
    shutil.copyfile(protocol,out/'xdg-shell.xml')
    checked(['wayland-scanner','client-header',protocol,out/'xdg-shell-client-protocol.h'])
    checked(['wayland-scanner','private-code',protocol,out/'xdg-shell-protocol.c'])
    flags=checked(['pkg-config','--cflags','--libs','wayland-client','xkbcommon'],capture_output=True,text=True).stdout.split()
    versions=checked(['pkg-config','--modversion','wayland-client','xkbcommon'],capture_output=True).stdout
    (out/'versions.txt').write_bytes(checked(['weston','--version'],capture_output=True).stdout+versions)
    exe=out/'doc-scene-wayland'
    compile_c([a.cc,'-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-DDOC_MESH_LIBRARY','-DDOC_SOURCE_SHA256="'+schema+'"','-I',runtime,'-I',out,'-I',wgpu/'include',runtime/'scene_wayland.c',runtime/'mesh_render.c',out/'xdg-shell-protocol.c','-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-lm',*flags,'-o',exe],timeout=300,evidence=out/'compile-wayland.json')
    direct=checked(['readelf','-d',exe],capture_output=True).stdout;(out/'direct-linkage.txt').write_bytes(direct)
    assert b'libwayland-client.so' in direct and b'libxkbcommon.so' in direct and b'libwgpu_native.so' in direct and b'libX11.so' not in direct and b'libdoc' not in direct
    expected=(games/'radar_chase_3d-reference.txt').read_bytes();oracle=json.loads((render/'render-summary.json').read_text())['oracle'];assert len(oracle)==len(REPLAY)+1
    args=[exe,'--asset-root='+str(assets),'--output-root='+str(out),'--backend=auto']
    with compositor(out,'headless') as env:
        stdout,stderr=capture(args+['--replay='+REPLAY],out,'headless',env)
        frames=validate(stdout,stderr,expected,oracle)
    # Weston uses its X11 backend only as a virtual output/input device. The
    # game has DISPLAY removed, no direct X11 linkage and native wl_keyboard
    # events; this is not a game running as an XWayland client.
    with compositor(out,'x11') as env:
        assert os.environ.get('DISPLAY')
        log=out/'keyboard.stderr';typed=out/'keyboard.stdout'
        with log.open('wb') as err,typed.open('wb') as std:
            proc=subprocess.Popen([str(x) for x in args+['--input-only']],cwd=out,env=env,stdout=std,stderr=err)
            try:
                wait_log(proc,log,rb'^DOC11_WAYLAND_READY$')
                wins=checked(['xdotool','search','--onlyvisible','--name','Weston'],capture_output=True,text=True).stdout.split()
                assert len(wins)==1,wins
                win=wins[0]
                checked(['xdotool','windowfocus','--sync',win])
                checked(['xdotool','mousemove','--window',win,'320','240','click','1'])
                wait_log(proc,log,rb'^DOC11_WAYLAND_FOCUS$')
                for ep,key in enumerate(REPLAY,1):
                    checked(['xdotool','key','space' if key=='j' else key])
                    wait_log(proc,log,rb'^DOC11_WAYLAND_PRESENTED: epoch='+str(ep).encode()+rb'$')
                checked(['xdotool','key','Escape'])
                assert proc.wait(timeout=30)==0
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
        interactive=validate(typed.read_bytes(),log.read_bytes(),expected,oracle,True)
    (out/'wayland-summary.json').write_text(json.dumps(dict(native_wayland=True,xwayland=False,headless_frames=frames,keyboard_frames=interactive,compositor='Weston',actual_frame_callbacks=True,bounded_buffer_release=True,physical_gpu=False,compositor_scanout_readback=False,generated_c_sha256=hashlib.sha256((out/'scene_generated.c').read_bytes()).hexdigest(),schema=schema),indent=2)+'\n')
    print(f'DOC11_NATIVE_WAYLAND_PASS: {frames} headless and {interactive} real keyboard-triggered native Wayland frames, exact typed/GPU-pixel parity, compositor callbacks and buffer retirement; not XWayland or physical scanout')
if __name__=='__main__':main()
