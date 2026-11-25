
# The dispatcher prepends the bounded bundle verifier; no GitHub credentials.
import os,runpy,subprocess,sys
SPEC=__DOC_KAGGLE_RUN_SPEC__
def main():
    output=Path('/kaggle/working/doc11-physical');output.mkdir(parents=True,exist_ok=False)
    base=Path('/tmp/doc11-build')
    candidates=[p for p in Path('/kaggle/input').rglob('doc-gpu-bundle.bin') if p.is_file()]
    matching=[p for p in candidates if digest(p)==SPEC['bundle_sha256']]
    if not matching:raise RuntimeError('INFRA_BLOCKED: exact precompiled independent dataset not mounted')
    manifest=unpack(matching[0],base,SPEC['bundle_sha256'],SPEC['sha'],SPEC['run_id'])
    for name in SPEC['executables']:(base/name).chmod(0o700)
    # Reuse established host-only NVIDIA graphics provisioning. Actual native
    # selected adapter and readback remain mandatory, never inferred from smi.
    host=runpy.run_path(str(base/'ci/kaggle/doc_kaggle_gpu.py'),init_globals={'__DOC_KAGGLE_RUN_SPEC__':SPEC},run_name='doc11_host_provision')
    host['experiment_provision_host_graphics']()
    xdg=output/'xdg';xdg.mkdir(mode=0o700)
    env={**os.environ,'XDG_RUNTIME_DIR':str(xdg),'LD_LIBRARY_PATH':str(base/'wgpu/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'DOC_REQUIRE_PHYSICAL_GPU':'1','DOC_GPU_REQUIRE_HARDWARE':'1'}
    env.pop('DOC_GPU_ALLOW_SOFTWARE',None)
    tests=base/'runtime-doc/tests';gpu=base/'gpu';games=base/'games';mesh=base/'mesh';wgpu=base/'wgpu'
    def run(label,*args):
        p=subprocess.run([sys.executable,'-u',*map(str,args)],cwd=base,env=env,capture_output=True,timeout=1200)
        (output/(label+'.log')).write_bytes(p.stdout+b'\n'+p.stderr)
        print(p.stdout.decode(errors='replace'),flush=True)
        if p.returncode:raise RuntimeError(label+' failed: '+p.stderr.decode(errors='replace')[-3000:])
    run('micro',tests/'test_gpu.py','--prebuilt',gpu/'micro','--wgpu-root',wgpu,'--physical')
    run('games',tests/'test_stage2_game_gpu.py','--games',games,'--prebuilt',gpu/'games','--wgpu-root',wgpu,'--evidence',output/'games','--physical')
    run('mesh',tests/'test_mesh_render.py','--prebuilt',mesh/'render','--game-output',output/'games/radar_chase_3d-auto.stdout','--scene-reference',mesh/'doc-scene3d','--wgpu-root',wgpu,'--evidence',output/'mesh','--physical')
    result={'sha':SPEC['sha'],'run_id':SPEC['run_id'],'bundle_sha256':SPEC['bundle_sha256'],'hardware':True,'result':'pass'}
    (output/'summary.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    print('DOC11_PHYSICAL_PASS: exact prebuilt micrographs, games, rollback, device loss and pixel parity',flush=True)
if __name__=='__main__':main()
