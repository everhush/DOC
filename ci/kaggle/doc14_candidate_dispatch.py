#!/usr/bin/env python3
"""CI-only, quota-gated private execution of exact candidate-built GPU binaries."""
import ast
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import time
from bundle import create_private_dataset
from dispatch import auth_environment, gpu_remaining_hours, kaggle, prepare_kernel, render_kernel_template, status_from_cli
from independent_bundle import pack
from independent_micro_evidence import MICRO_GRAPHS, MICRO_EXECUTABLES, validate_micro_evidence
from scale_evidence import extract_scale, audit_coverage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'release'))
from physical_gpu import FILES, check_build, verify, host_t4_ids, require_t4, test_adapter_identity

MARKER = '__DOC14_PHYSICAL_SPEC__'
KERNEL = r'''
import os, sys, time, subprocess, tarfile
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
    results = Path('/tmp/doc14-scale-results'); results.mkdir()
    env = {k:v for k,v in os.environ.items() if not k.startswith('DOC_')}
    env.update(DOC_REQUIRE_PHYSICAL_GPU='1', LD_LIBRARY_PATH=str(root)+':'+env.get('LD_LIBRARY_PATH',''))
    for exe in (root/'scale').rglob('bench'): exe.chmod(0o700)
    try:
        for exe in (root/'micro').iterdir():
            if exe.is_file() and exe.suffix!='.expected': exe.chmod(0o700)
        with (results/'micro.log').open('wb') as log:
            subprocess.run([sys.executable,'-u',str(root/'micro-tests/test_gpu.py'),'--prebuilt',str(root/'micro'),'--wgpu-root',str(root),'--physical','--artifacts',str(results/'micro')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=2700)
        for category,script,flags in (
                ('families','benchmark_autonomous_family.py',['--epochs','6']),
                ('algorithms','benchmark_autonomous_algorithms.py',[])):
            with (results/(category+'.log')).open('wb') as log:
                subprocess.run([sys.executable,'-u',str(root/script),'--root',str(root/'scale'/category),'--out',str(results/category),'--physical','--samples','3',*flags],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=7200)
        (results/'summary.json').write_text(json.dumps(dict(sha=SPEC['sha'],run_id=SPEC['run_id'],bundle_sha256=SPEC['bundle_sha256'],hardware=True,result='pass'))+'\n')
    finally:
        with tarfile.open(LOGS/'doc9-autonomous-results.tar.gz','w:gz') as archive:
            for item in sorted(results.rglob('*')):
                if item.is_file() and not item.is_symlink():
                    archive.add(item,arcname='doc9-autonomous-evidence/'+item.relative_to(results).as_posix(),recursive=False)
if __name__=='__main__': main()
'''


def write_template(template):
    host = (HERE/'doc_kaggle_gpu.py').read_text()
    node, = [n for n in ast.parse(host).body if isinstance(n,ast.FunctionDef) and n.name=='experiment_provision_host_graphics']
    provision = ast.get_source_segment(host,node)
    template.write_text((HERE/'independent_bundle.py').read_text()+'\n'+provision+'\n'+KERNEL)
    # Compile the full rendered source before auth, quota checks or upload.
    render_kernel_template(template, {'sha':'0'*40,'run_id':'1','attempt':'1',
        'accelerator':'NvidiaTeslaT4','bundle_sha256':'0'*64,
        'bundle_dataset':'example/doc-gpu-1-1-bundle'}, placeholder=MARKER)


def preflight():
    test_adapter_identity()
    with tempfile.TemporaryDirectory(prefix='doc14-preflight-') as temp:
        write_template(Path(temp)/'kernel-template.py')
    print('DOC14_NOTEBOOK_TEMPLATE_PASS: complete rendered source compiles without credentials', flush=True)


def main():
    if os.environ.get('GITHUB_REPOSITORY_ID')!='1317169134' or os.environ.get('GITHUB_REF')!='refs/heads/master':
        raise ValueError('trusted master CI only')
    sha, rid, attempt = (os.environ[k] for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT'))
    build = Path('gpu-build').resolve()
    record = check_build(build, sha)
    out = Path('physical-evidence').resolve()
    out.mkdir(exist_ok=False)
    spec = {'sha':sha,'run_id':rid,'attempt':attempt,'accelerator':'NvidiaTeslaT4'}
    files = {name:build/name for name in (*FILES,'build.json')}
    notices = Path('physical-dependencies/wgpu-notices').resolve()
    for name in ('wgpu-native.LICENSE.MIT','wgpu-native.LICENSE.APACHE','webgpu-headers.LICENSE'):
        files['provider-notices/'+name] = notices/name
    files.update({name:ROOT/'release'/name for name in ('physical_gpu.py','test_gpu_candidate.py')})
    sys.path.insert(0,str(ROOT/'runtime-doc/tests'))
    from test_gpu import micro_expected
    for name in MICRO_GRAPHS:
        if (build/'micro'/(name+'.expected')).read_bytes()!=micro_expected(name):
            raise ValueError('wrong independent micrograph oracle: '+name)
    for name in (*MICRO_EXECUTABLES,*(name+'.expected' for name in MICRO_GRAPHS)):
        files['micro/'+name]=build/'micro'/name
    files['micro-tests/test_gpu.py']=ROOT/'runtime-doc/tests/test_gpu.py'
    files['micro-tests/doc_build.py']=ROOT/'runtime-doc/compiler/doc_build.py'
    for name in ('benchmark_autonomous_family.py','benchmark_autonomous_algorithms.py','benchmark_scale_pipeline.py'):
        files[name] = ROOT/'runtime-doc/tests'/name
    for category,keys in (('families',('production/add','production/poly')),('algorithms',('stress','sort','reduce'))):
        scale_root = build/'scale'/category
        manifest = json.loads((scale_root/'build.json').read_text())
        if set(manifest)!=set(keys): raise ValueError('incomplete scale build')
        files['scale/'+category+'/build.json']=scale_root/'build.json'
        for key in keys:
            exe = scale_root/key/'bench'
            from independent_bundle import digest
            if digest(exe)!=manifest[key]['sha256']: raise ValueError('scale executable hash mismatch')
            files['scale/'+category+'/'+key+'/bench']=exe
    with tempfile.TemporaryDirectory(prefix='doc14-private-') as temp:
        td = Path(temp)
        template = td/'kernel-template.py'
        write_template(template)
        env, owner = auth_environment(os.environ.get('KAGGLE_DOC_1',''),td/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
        if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:
            raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
        dataset = td/'dataset'; dataset.mkdir()
        checksum, manifest = pack(files,dataset/'doc-gpu-bundle.bin',sha,rid)
        spec.update(bundle_sha256=checksum,bundle_dataset=create_private_dataset(dataset,owner,rid,attempt,env,readiness_attempts=40))
        (out/'provenance.json').write_text(json.dumps({'spec':{k:spec[k] for k in ('sha','run_id','attempt','accelerator','bundle_sha256')},'manifest':manifest},indent=2)+'\n')
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
        report=json.loads(reports[0].read_text())
        verify(report,record,sha,rid,checksum)
        ids=host_t4_ids(report['host_gpu_csv'])
        archives=list(remote.rglob('doc9-autonomous-results.tar.gz'))
        if len(archives)!=1: raise ValueError('missing or ambiguous scaling evidence archive')
        extracted=extract_scale(archives[0],remote)
        validate_micro_evidence(extracted/'micro',build/'micro')
        for log in (extracted/'micro').glob('*.stderr'):
            require_t4(log.read_text(),ids,log.name)
        if b'DOC11_WEBGPU_PASS: 5 native actual-device comparisons' not in (extracted/'micro.log').read_bytes():
            raise ValueError('missing full micrograph execution result')
        print('DOC14_PHYSICAL_MICRO_VERIFIED: 5 graphs, device loss, epoch retirement, graph replacement',flush=True)
        sys.path.insert(0,str(ROOT/'runtime-doc/tests'))
        from verify_autonomous_evidence import verify as verify_scale
        verified=verify_scale(out,build,sha,rid)
        tails=audit_coverage(extracted, ids)
        (out/'scale-verified.json').write_text(json.dumps({'verified':verified,'descriptive_warm_tails':tails},indent=2)+'\n')
        print('DOC14_PHYSICAL_SCALE_VERIFIED:',json.dumps(verified,sort_keys=True),flush=True)


if __name__=='__main__':
    if sys.argv[1:]==['--preflight']:
        preflight()
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit('usage: doc14_candidate_dispatch.py [--preflight]')
