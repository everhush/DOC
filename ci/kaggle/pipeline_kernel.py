
import os,runpy,subprocess,sys
SPEC=__DOC9_PIPELINE_SPEC__
def main():
 out=Path('/kaggle/working');base=Path('/tmp/doc9-pipeline')
 candidates=[p for p in Path('/kaggle/input').rglob('doc-gpu-bundle.bin') if p.is_file() and digest(p)==SPEC['bundle_sha256']]
 if len(candidates)!=1:raise RuntimeError('exact authenticated bundle unavailable')
 unpack(candidates[0],base,SPEC['bundle_sha256'],SPEC['sha'],SPEC['run_id'])
 for name in SPEC['executables']:(base/name).chmod(0o700)
 host=runpy.run_path(str(base/'ci/kaggle/doc_kaggle_gpu.py'),init_globals={'__DOC_KAGGLE_RUN_SPEC__':SPEC},run_name='doc9_pipeline_host')
 host['experiment_provision_host_graphics']()
 xdg=base/'xdg';xdg.mkdir(mode=0o700)
 env={**os.environ,'XDG_RUNTIME_DIR':str(xdg),'LD_LIBRARY_PATH':str(base/'wgpu/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'DOC_REQUIRE_PHYSICAL_GPU':'1','DOC_GPU_REQUIRE_HARDWARE':'1'}
 env.pop('DOC_GPU_ALLOW_SOFTWARE',None)
 p=base/'measurements'
 try:
  q=subprocess.run([sys.executable,'-u',str(base/'benchmark_scale_pipeline.py'),'--root',str(base/'build'),'--out',str(p),'--physical','--samples','3','--epochs','6'],env=env,capture_output=True,timeout=3600)
  (base/'campaign.log').write_bytes(q.stdout+b'\n'+q.stderr)
  print(q.stdout.decode(errors='replace'),flush=True)
  if q.returncode:raise RuntimeError(q.stderr.decode(errors='replace')[-4000:])
  report=json.loads((p/'summary.json').read_text());assert report['machine']['physical'] and report['dispatches']>0
  rec=dict(sha=SPEC['sha'],run_id=SPEC['run_id'],bundle_sha256=SPEC['bundle_sha256'],physical=True,rows=report['rows'],processes=report['processes'],dispatches=report['dispatches'],result='pass')
  (base/'provenance.json').write_text(json.dumps(rec,sort_keys=True)+'\n')
 except BaseException as error:
  (base/'failure.txt').write_text(type(error).__name__+': '+str(error)[-12000:]+'\n')
  raise
 finally:
  with tarfile.open(out/'doc9-pipeline-results.tar.gz','w:gz') as tar:
   if p.exists():tar.add(p,arcname='measurements')
   for item in ('provenance.json','campaign.log','failure.txt'):
    if (base/item).exists():tar.add(base/item,arcname=item)
 print('DOC9_PIPELINE_PHYSICAL_PASS',rec,flush=True)
if __name__=='__main__':main()
