#!/usr/bin/env python3
"""Authenticated physical-only pipeline campaign; exact build, one output archive."""
import csv,json,os,tarfile,tempfile,time
from pathlib import Path
from bundle import create_private_dataset
from dispatch import auth_environment,gpu_remaining_hours,kaggle,prepare_kernel,render_kernel_template,status_from_cli
from independent_bundle import pack,digest
H=Path(__file__).resolve().parent
MARKER='__DOC9_PIPELINE_SPEC__'
def main():
 sha=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT']
 assert os.environ['GITHUB_REPOSITORY_ID']=='1471748051'
 out=Path('doc9-pipeline-evidence');out.mkdir(exist_ok=True);build=Path('doc9-pipeline-build');meta=json.loads((build/'build.json').read_text())
 paths={'benchmark_scale_pipeline.py':Path('runtime-doc/tests/benchmark_scale_pipeline.py'),'ci/kaggle/doc_kaggle_gpu.py':H/'doc_kaggle_gpu.py','wgpu/lib/libwgpu_native.so':Path('doc9-wgpu/lib/libwgpu_native.so'),'build/build.json':build/'build.json'}
 ex=[]
 for key,rec in meta.items():
  p=build/key/'bench';assert digest(p)==rec['sha256'];name='build/'+key+'/bench';paths[name]=p;ex.append(name)
 spec=dict(sha=sha,run_id=run_id,attempt=attempt,accelerator='NvidiaTeslaT4',executables=ex)
 with tempfile.TemporaryDirectory(prefix='doc9-pipeline-private-') as td:
  root=Path(td);template=root/'template.py';template.write_text((H/'independent_bundle.py').read_text()+'\n'+(H/'pipeline_kernel.py').read_text());render_kernel_template(template,spec,placeholder=MARKER)
  env,owner=auth_environment(os.environ.get('KAGGLE_DOC_1',''),root/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
  if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
  dataset=root/'dataset';dataset.mkdir();checksum,manifest=pack(paths,dataset/'doc-gpu-bundle.bin',sha,run_id)
  spec.update(bundle_sha256=checksum,bundle_dataset=create_private_dataset(dataset,owner,run_id,attempt,env));(out/'provenance.json').write_text(json.dumps(dict(spec=spec,manifest=manifest),indent=2)+'\n')
  name=prepare_kernel(root/'kernel',template,spec,owner,placeholder=MARKER)
  kaggle(['kernels','push','-p',str(root/'kernel'),'--accelerator',spec['accelerator']],env,timeout=180)
  while True:
   state=status_from_cli(kaggle(['kernels','status',name],env));print('DOC9_PIPELINE_STATUS',state,flush=True)
   if state in ('COMPLETE','FAILED'):break
   time.sleep(20)
  remote=out/'remote';remote.mkdir();kaggle(['kernels','output',name,'-p',str(remote)],env,timeout=600)
  if state!='COMPLETE':raise RuntimeError('physical pipeline notebook failed')
  files=list(remote.rglob('doc9-pipeline-results.tar.gz'));assert len(files)==1
  with tarfile.open(files[0]) as t:
   rec=json.load(t.extractfile('provenance.json'));report=json.load(t.extractfile('measurements/summary.json'));assert rec==dict(sha=sha,run_id=run_id,bundle_sha256=checksum,physical=True,rows=report['rows'],processes=report['processes'],dispatches=report['dispatches'],result='pass')
   assert report['machine']['physical'] and report['machine']['build']==meta
   import io
   rows=list(csv.DictReader(io.TextIOWrapper(t.extractfile('measurements/samples.csv'))));assert len(rows)==report['rows'];assert sum(int(r['dispatch_ns'])>0 for r in rows)==report['dispatches']
   logs=[m for m in t.getmembers() if m.name.endswith('.stderr')];assert len(logs)==report['processes'];assert sum(b'physical=1 ' in t.extractfile(m).read() for m in logs)==report['dispatches']//report['machine']['epochs']
   (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
  print('DOC9_PIPELINE_VERIFIED',rec,flush=True)
if __name__=='__main__':main()
