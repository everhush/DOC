#!/usr/bin/env python3
"""Run one private hardware validation using this run's CPU and build-only GPU artifacts."""
import json,os,re,subprocess,tempfile,time
from pathlib import Path
from bundle import create_private_dataset
from dispatch import auth_environment,gpu_remaining_hours,kaggle,prepare_kernel,render_kernel_template,status_from_cli
from independent_bundle import pack,digest
from independent_micro_evidence import MICRO_GRAPHS,MICRO_EXECUTABLES,validate_micro_evidence,validate_destroy
HERE=Path(__file__).resolve().parent
INDEPENDENT_SPEC_MARKER='__DOC11_INDEPENDENT_RUN_SPEC__'

def write_template(path):
    path.write_text((HERE/'independent_bundle.py').read_text()+'\n'+(HERE/'autonomous_kernel.py').read_text(),encoding='utf-8')
def main():
    sha=os.environ['GITHUB_SHA'];run_id=os.environ['GITHUB_RUN_ID'];attempt=os.environ['GITHUB_RUN_ATTEMPT']
    if os.environ.get('GITHUB_REPOSITORY_ID')!='1471748051':raise ValueError('hardware dispatch is CI-fork only')
    out=Path('doc11-physical-evidence');out.mkdir(exist_ok=True)
    for p in ('doc11-game-evidence','doc11-stage2-gpu-evidence'):
        if (Path(p)/'source-sha.txt').read_text().strip()!=sha:raise ValueError('stale artifact '+p)
    for manifest in ('doc11-game-evidence/SHA256SUMS','doc11-stage2-gpu-evidence/physical-SHA256SUMS'):
        subprocess.run(['sha256sum','-c',manifest],check=True)
    paths={}
    def add(dest,src):paths[dest]=Path(src)
    for name in ('radar_chase','radar_chase_3d'):
        for f in (name,name+'.c',name+'-reference.txt'):add('games/'+f,'doc11-game-evidence/'+f)
        for f in (name+'-gpu',name+'.c',name+'.wgsl'):add('gpu/games/'+f,'doc11-stage2-gpu-evidence/games/'+f)
    for f in (*MICRO_EXECUTABLES,*(name+'.expected' for name in MICRO_GRAPHS)):
        add('gpu/micro/'+f,'doc11-stage2-gpu-evidence/micro/'+f)
    add('wgpu/lib/libwgpu_native.so','doc11-stage2-gpu-evidence/libwgpu_native.so')
    for f in ('test_gpu.py','test_stage2_game_gpu.py','test_stage2_games.py','gpu_game_trace.py','benchmark_autonomous_family.py','benchmark_autonomous_algorithms.py','benchmark_scale_pipeline.py'):
        add('runtime-doc/tests/'+f,'runtime-doc/tests/'+f)
    for f in ('doc_build.py',):
        add('runtime-doc/compiler/'+f,'runtime-doc/compiler/'+f)
    add('ci/kaggle/doc_kaggle_gpu.py','ci/kaggle/doc_kaggle_gpu.py')
    for p in subprocess.check_output(['git','ls-files','engine'],text=True).splitlines():
        if p.endswith('.doc') or p.startswith('engine/levels/'):add(p,p)
    executables=['games/radar_chase','games/radar_chase_3d','gpu/games/radar_chase-gpu','gpu/games/radar_chase_3d-gpu',*('gpu/micro/'+name for name in MICRO_EXECUTABLES)]
    for category in ('families','algorithms'):
        source=Path('doc11-stage2-gpu-evidence/scale')/category
        add('scale/'+category+'/build.json',source/'build.json')
        for key,record in json.loads((source/'build.json').read_text()).items():
            name='scale/'+category+'/'+key+'/bench';p=source/key/'bench'
            if digest(p)!=record['sha256']:raise ValueError('scale build hash')
            add(name,p);executables.append(name)
    spec={'sha':sha,'run_id':run_id,'attempt':attempt,'accelerator':'NvidiaTeslaT4','executables':executables}
    with tempfile.TemporaryDirectory(prefix='doc11-private-') as td:
        root=Path(td)
        template=root/'template.py';write_template(template)
        render_kernel_template(template,spec,placeholder=INDEPENDENT_SPEC_MARKER)
        env,owner=auth_environment(os.environ.get('KAGGLE_DOC_1',''),root/'config',os.environ.get('DOC_KAGGLE_USERNAME',''))
        if gpu_remaining_hours(kaggle(['quota','--format','json'],env))<=0:raise RuntimeError('INFRA_BLOCKED: GPU quota unavailable')
        dataset=root/'dataset';dataset.mkdir()
        checksum,manifest=pack(paths,dataset/'doc-gpu-bundle.bin',sha,run_id)
        spec.update(bundle_sha256=checksum,bundle_dataset=create_private_dataset(dataset,owner,run_id,attempt,env))
        (out/'provenance.json').write_text(json.dumps({'spec':spec,'manifest':manifest},indent=2)+'\n')
        kernel=root/'kernel';name=prepare_kernel(kernel,template,spec,owner,placeholder=INDEPENDENT_SPEC_MARKER)
        # Exactly one submission; no ambiguous automatic retries or redundant GPU jobs.
        kaggle(['kernels','push','-p',str(kernel),'--accelerator',spec['accelerator']],env,timeout=180)
        errors=0
        while True:
            try:
                state=status_from_cli(kaggle(['kernels','status',name],env));errors=0
            except RuntimeError as exc:
                errors+=1;print('DOC9_READ_ONLY_STATUS_RETRY',errors,type(exc).__name__,flush=True)
                if errors>=8:raise
                time.sleep(15);continue
            print('DOC11_PHYSICAL_STATUS:',state,flush=True)
            if state in ('COMPLETE','FAILED'):break
            time.sleep(30)
        remote=out/'remote';remote.mkdir(exist_ok=True)
        kaggle(['kernels','output',name,'-p',str(remote),'--force'],env,timeout=900)
        if state!='COMPLETE':raise RuntimeError('physical independent notebook failed')
        # Single archive avoids partial downloads of hundreds of process logs.
        import tarfile
        archives=list(remote.rglob('doc9-autonomous-results.tar.gz'))
        if len(archives)!=1:raise ValueError('missing exact remote evidence archive')
        with tarfile.open(archives[0]) as archive:
            archive.extractall(remote,filter='data')
        reports=list(remote.rglob('summary.json'))
        reports=[p for p in reports if json.loads(p.read_text()).get('bundle_sha256')==checksum]
        if len(reports)!=1:raise ValueError('missing or ambiguous hardware report')
        result=json.loads(reports[0].read_text())
        if result!={'sha':sha,'run_id':run_id,'bundle_sha256':checksum,'hardware':True,'result':'pass'}:raise ValueError('invalid hardware report')
        base=reports[0].parent
        for name,markers in {'micro.log':['DOC11_WEBGPU_PASS:','DOC11_GPU_DEVICE_LOSS_PASS:','DOC11_GPU_EPOCH_AUTHORITY_PASS:','DOC11_GPU_GRAPH_GENERATION_PASS:','physical_required=True'],'games.log':['DOC11_GAME_GPU_PASS: radar_chase ','DOC11_GAME_GPU_PASS: radar_chase_3d ','physical_required=True'],'family.log':['DOC9_AUTONOMOUS_FAMILY_PASS'],'algorithm.log':['DOC9_AUTONOMOUS_ALGORITHM_PASS']}.items():
            log=(base/name).read_text()
            if any(marker not in log for marker in markers):raise ValueError('missing raw device evidence '+name)
        validate_micro_evidence(base/'micro',Path('doc11-stage2-gpu-evidence/micro'))
        for name in ('radar_chase','radar_chase_3d'):
            if not re.search(r'(?m)^DOC11_GPU_ADAPTER: .* physical=1 ',(base/'games'/(name+'-auto.stderr')).read_text()):raise ValueError('nonphysical game adapter')
            if (base/'games'/(name+'-auto.stdout')).read_bytes()!=paths['games/'+name+'-reference.txt'].read_bytes():raise ValueError('hardware game replay mismatch')
        for name in ('families','algorithms'):
            report=json.loads((base/name/'summary.json').read_text())
            build=json.loads(paths['scale/'+name+'/build.json'].read_text())
            if not report['machine']['physical'] or report['machine']['build']!=build or report['dispatches']<=0:raise ValueError('scale provenance '+name)
            logs=list((base/name/'raw').glob('*.stderr'))
            if len(logs)!=report['processes']:raise ValueError('missing scale process evidence')
            if sum(x.read_bytes().count(b'DOC11_GPU_DISPATCH: lanes=') for x in logs)!=report['dispatches']:raise ValueError('dispatch trace mismatch')
            if any(b'DOC11_GPU_ADAPTER:' in x.read_bytes() and b'physical=1 ' not in x.read_bytes() for x in logs):raise ValueError('nonphysical scale session')
        print('DOC11_PHYSICAL_PASS: same-run exact artifact verification and real GPU conformance',flush=True)
if __name__=='__main__':main()
