#!/usr/bin/env python3
"""One authenticated, exact-build physical scaling experiment; no retry submissions."""
import csv,json,os,subprocess,tempfile,time
from pathlib import Path
from bundle import create_private_dataset
from dispatch import auth_environment,gpu_remaining_hours,kaggle,prepare_kernel,render_kernel_template,status_from_cli
from independent_bundle import pack,digest
HERE=Path(__file__).resolve().parent
MARKER='__DOC9_SCALE_SPEC__'
def main():
 sha=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT']
 if os.environ['GITHUB_REPOSITORY_ID']!='1471748051':raise ValueError('private CI fork only')
 out=Path('doc9-physical-scale-evidence');out.mkdir(exist_ok=True)
 build=Path('doc9-scale-build');meta=json.loads((build/'build.json').read_text())
 paths={'benchmark_gpu_family.py':Path('runtime-doc/tests/benchmark_gpu_family.py'),'ci/kaggle/doc_kaggle_gpu.py':HERE/'doc_kaggle_gpu.py','wgpu/lib/libwgpu_native.so':Path('doc11-wgpu/lib/libwgpu_native.so'),'build/build.json':build/'build.json'}
 for w in ('add','poly'):
  for f,h in meta[w].items():
   p=build/w/f
   if digest(p)!=h:raise ValueError('build hash mismatch')
   paths['build/'+w+'/'+f]=p
 spec=dict(sha=sha,run_id=run_id,attempt=attempt,accelerator='NvidiaTeslaT4',executables=['build/add/bench','build/poly/bench'])
 with tempfile.TemporaryDirectory(prefix='doc9-scale-private-') as td:
  root=Path(td);template=root/'template.py';template.write_text((HERE/'independent_bundle.py').read_text()+'\n'+(HERE/'physical_scale_kernel.py').read_text())
  render_kernel_template(template,spec,placeholder=MARKER)
  env,owner=auth_environment(os.environ.get('KAGGLE_DOC_1',''),root/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
  if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
  dataset=root/'dataset';dataset.mkdir();checksum,manifest=pack(paths,dataset/'doc-gpu-bundle.bin',sha,run_id)
  spec.update(bundle_sha256=checksum,bundle_dataset=create_private_dataset(dataset,owner,run_id,attempt,env))
  (out/'provenance.json').write_text(json.dumps(dict(spec=spec,manifest=manifest),indent=2)+'\n')
  kernel=root/'kernel';name=prepare_kernel(kernel,template,spec,owner,placeholder=MARKER)
  kaggle(['kernels','push','-p',str(kernel),'--accelerator',spec['accelerator']],env,timeout=180)
  while True:
   state=status_from_cli(kaggle(['kernels','status',name],env));print('DOC9_SCALE_STATUS:',state,flush=True)
   if state in ('COMPLETE','FAILED'):break
   time.sleep(30)
  remote=out/'remote';remote.mkdir();kaggle(['kernels','output',name,'-p',str(remote),'--force'],env,timeout=240)
  if state!='COMPLETE':raise RuntimeError('physical scale notebook failed')
  reports=[p for p in remote.rglob('provenance.json') if json.loads(p.read_text()).get('bundle_sha256')==checksum]
  if len(reports)!=1:raise ValueError('missing exact-run report')
  p=reports[0];rec=json.loads(p.read_text());expected={w:meta[w]['bench'] for w in ('add','poly')}
  if rec!=dict(sha=sha,run_id=run_id,bundle_sha256=checksum,physical=True,result='pass',binaries=expected):raise ValueError('invalid physical provenance')
  measurements=p.parent/'measurements';report=json.loads((measurements/'summary.json').read_text());assert report['physical'] and report['binaries']==expected and report['epoch_count']==14960 and report['dispatch_count']==6120
  for name,count in [('epochs.csv',14960),('dispatches.csv',6120)]:
   with (measurements/name).open() as f:assert sum(1 for _ in csv.DictReader(f))==count
  logs=list((measurements/'raw').glob('*.stderr'));assert len(logs)==880
  physical=sum(b'physical=1 ' in p.read_bytes() for p in logs);assert physical==440
  print('DOC9_PHYSICAL_SCALING_PASS:',report['epoch_count'],report['dispatch_count'],physical,'physical device sessions',flush=True)
if __name__=='__main__':main()
