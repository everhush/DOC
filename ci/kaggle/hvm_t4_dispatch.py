#!/usr/bin/env python3
"""Submit one private real T4 comparison, verify exact DOC and HVM inputs."""
import json,os,subprocess,tempfile,time,tarfile
from pathlib import Path
from bundle import create_private_dataset
from dispatch import auth_environment,gpu_remaining_hours,kaggle,prepare_kernel,status_from_cli
from independent_bundle import pack,digest
HERE=Path(__file__).resolve().parent
MARK='__DOC9_HVM_RUN_SPEC__'
def main():
    sha=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT']
    assert os.environ['GITHUB_REPOSITORY_ID']=='1317169134' and os.environ['GITHUB_REF_NAME']=='master'
    out=Path('doc9-hvm-physical');out.mkdir()
    root=Path('doc11-stage2-gpu-evidence')
    assert (root/'source-sha.txt').read_text().strip()==sha
    subprocess.run(['sha256sum','-c',root/'physical-SHA256SUMS'],check=True)
    paths={'wgpu/lib/libwgpu_native.so':root/'libwgpu_native.so','compare_cpu.py':Path('verification/hvm/compare_cpu.py'),'host.py':HERE/'doc_kaggle_gpu.py'}
    executables=[]
    for category in ('families','algorithms'):
        base=root/'scale'/category
        paths[f'scale/{category}/build.json']=base/'build.json'
        for key,rec in json.loads((base/'build.json').read_text()).items():
            p=base/key/'bench';assert digest(p)==rec['sha256']
            name=f'scale/{category}/{key}/bench';paths[name]=p;executables.append(name)
    for p in Path('doc9-hvm-cuda').iterdir():
        if p.suffix in ('.bend','.cu','.json','.elf') or p.name=='toolkit.txt':paths['hvm/'+p.name]=p
        if p.suffix=='.elf':executables.append('hvm/'+p.name)
    spec=dict(sha=sha,run_id=run_id,attempt=attempt,accelerator='NvidiaTeslaT4',executables=executables)
    with tempfile.TemporaryDirectory(prefix='doc9-hvm-private-') as td:
        temp=Path(td);template=temp/'template.py'
        template.write_text((HERE/'independent_bundle.py').read_text()+'\n'+(HERE/'hvm_t4_kernel.py').read_text())
        env,owner=auth_environment(os.environ.get('KAGGLE_DOC_1',''),temp/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
        if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
        dataset=temp/'dataset';dataset.mkdir()
        checksum,manifest=pack(paths,dataset/'doc-gpu-bundle.bin',sha,run_id)
        spec.update(bundle_sha256=checksum)
        # Keep public-safe provenance even when private transport fails.
        (out/'provenance.json').write_text(json.dumps(dict(spec=spec,manifest=manifest),indent=2))
        spec.update(bundle_dataset=create_private_dataset(dataset,owner,run_id,attempt,env,readiness_attempts=40))
        kernel=temp/'kernel';name=prepare_kernel(kernel,template,spec,owner,placeholder=MARK)
        kaggle(['kernels','push','-p',str(kernel),'--accelerator',spec['accelerator']],env,timeout=180)
        for _ in range(360):
            state=status_from_cli(kaggle(['kernels','status',name],env))
            print('DOC9_HVM_PHYSICAL_STATUS',state,flush=True)
            if state in ('COMPLETE','FAILED'):break
            time.sleep(30)
        else:raise RuntimeError('physical comparison did not finish within polling limit')
        remote=out/'remote';remote.mkdir()
        kaggle(['kernels','output',name,'-p',str(remote),'--force'],env,timeout=900)
        archives=list(remote.rglob('doc9-hvm-results.tar.gz'))
        if len(archives)!=1:raise RuntimeError('missing physical evidence archive')
        with tarfile.open(archives[0]) as tar:tar.extractall(remote,filter='data')
        report=json.loads((remote/'evidence/report.json').read_text())
        assert report['sha']==sha and report['run_id']==run_id and report['bundle_sha256']==checksum
        assert state=='COMPLETE' and report['result']=='pass',report
        print('DOC9_HVM_T4_PATCHED_PASS')
if __name__=='__main__':main()
