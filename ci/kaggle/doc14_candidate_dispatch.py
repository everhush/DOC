#!/usr/bin/env python3
"""CI-only, quota-gated private execution of exact candidate-built GPU binaries."""
import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from bundle import create_private_dataset
from dispatch import auth_environment, gpu_remaining_hours, kaggle, prepare_kernel, status_from_cli
from independent_bundle import pack

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'release'))
from physical_gpu import FILES, check_build, verify

MARKER = '__DOC14_PHYSICAL_SPEC__'
KERNEL = '''
import os, sys, time, subprocess
SPEC = __DOC14_PHYSICAL_SPEC__
LOGS = Path('/kaggle/working')
ENV = {**os.environ, "DEBIAN_FRONTEND":"noninteractive", "APT_LISTCHANGES_FRONTEND":"none", "NEEDRESTART_MODE":"a"}
def main():
    matches = [p for p in Path('/kaggle/input').rglob('doc-gpu-bundle.bin') if p.is_file() and digest(p)==SPEC['bundle_sha256']]
    if len(matches)!=1: raise ValueError('missing or ambiguous exact private candidate bundle')
    root = Path('/tmp/doc14-physical-build')
    unpack(matches[0], root, SPEC['bundle_sha256'], SPEC['sha'], SPEC['run_id'])
    (root/'family-gpu').chmod(0o700)
    experiment_provision_host_graphics()
    xdg = root/'xdg'; xdg.mkdir(mode=0o700)
    os.environ['XDG_RUNTIME_DIR'] = str(xdg)
    sys.path.insert(0, str(root))
    from physical_gpu import execute
    execute(root, SPEC['sha'], SPEC['run_id'], SPEC['bundle_sha256'], LOGS/'doc14-physical.json')
if __name__=='__main__': main()
'''


def main():
    if os.environ.get('GITHUB_REPOSITORY_ID')!='1317169134' or os.environ.get('GITHUB_REF')!='refs/heads/master':
        raise ValueError('trusted master CI only')
    sha, rid, attempt = (os.environ[k] for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'))
    build = Path('gpu-build').resolve()
    record = check_build(build, sha)
    out = Path('physical-evidence').resolve()
    out.mkdir(exist_ok=False)
    spec = {'sha':sha,'run_id':rid,'attempt':attempt,'accelerator':'NvidiaTeslaT4'}
    # Reuse only the already-established host provisioning function, not the old reference test controller.
    host = (HERE/'doc_kaggle_gpu.py').read_text()
    node, = [n for n in ast.parse(host).body if isinstance(n,ast.FunctionDef) and n.name=='experiment_provision_host_graphics']
    provision = ast.get_source_segment(host,node)
    files = {name:build/name for name in (*FILES,'build.json')}
    files.update({name:ROOT/'release'/name for name in ('physical_gpu.py','test_gpu_candidate.py')})
    with tempfile.TemporaryDirectory(prefix='doc14-private-') as temp:
        td = Path(temp)
        template = td/'kernel-template.py'
        template.write_text((HERE/'independent_bundle.py').read_text()+'\n'+provision+'\n'+KERNEL)
        env, owner = auth_environment(os.environ.get('KAGGLE_DOC_1',''),td/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
        if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:
            raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
        dataset = td/'dataset'; dataset.mkdir()
        checksum, manifest = pack(files,dataset/'doc-gpu-bundle.bin',sha,rid)
        spec.update(bundle_sha256=checksum,bundle_dataset=create_private_dataset(dataset,owner,rid,attempt,env,readiness_attempts=40))
        (out/'provenance.json').write_text(json.dumps({'sha':sha,'run_id':rid,'attempt':attempt,'bundle_sha256':checksum,'manifest':manifest},indent=2)+'\n')
        kernel = td/'kernel'
        name = prepare_kernel(kernel,template,spec,owner,placeholder=MARKER)
        kaggle(['kernels','push','-p',str(kernel),'--accelerator',spec['accelerator']],env,timeout=180)
        errors = 0
        while True:
            try:
                state = status_from_cli(kaggle(['kernels','status',name],env)); errors=0
            except RuntimeError:
                errors+=1
                if errors>=8: raise
                time.sleep(15); continue
            print('DOC14_PHYSICAL_STATUS:',state,flush=True)
            if state in ('COMPLETE','FAILED'): break
            time.sleep(30)
        remote = out/'remote'; remote.mkdir()
        kaggle(['kernels','output',name,'-p',str(remote),'--force'],env,timeout=900)
        if state!='COMPLETE': raise RuntimeError('physical candidate notebook failed')
        reports = list(remote.rglob('doc14-physical.json'))
        if len(reports)!=1 or reports[0].stat().st_size>4*1024*1024:
            raise ValueError('missing, ambiguous or oversized physical report')
        verify(json.loads(reports[0].read_text()),record,sha,rid,checksum)


if __name__=='__main__': main()
