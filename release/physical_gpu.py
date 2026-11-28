#!/usr/bin/env python3
"""Build and independently verify a candidate-only physical GPU fixture."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from test_gpu_candidate import SOURCE, fixture, digest, require

ROOT = Path(__file__).resolve().parents[1]
FILES = ('family.doc', 'family-gpu', 'family.c', 'family.wgsl', 'gpu_generated.h', 'libwgpu_native.so')


def build(a):
    sys.path.insert(0, str(ROOT/'runtime-doc/compiler'))
    from doc_build import bundle, emit, build_bundled
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    headers = ROOT/'runtime-doc/runtime'
    planner = out/'gpu_plan2'
    code = emit([a.stage2.resolve()], bundle([a.scanner.resolve()], ROOT/'runtime-doc/compiler/gpu_plan.doc', stream=True), stream=True)
    (out/'gpu_plan2.c').write_bytes(code)
    subprocess.run(['cc','-std=gnu11','-O1','-pthread','-I',str(headers),str(out/'gpu_plan2.c'),'-o',str(planner)], check=True, timeout=600)
    (out/'family.doc').write_bytes(SOURCE)
    build_bundled([a.reactive.resolve()], SOURCE, out/'family-gpu', headers, True, out/'family.c', stream=True,
                  gpu_plan=[planner], wgpu_root=a.wgpu.resolve(), emit_wgsl=out/'family.wgsl', emit_gpu_header=out/'gpu_generated.h')
    # Keep the upstream provider outside the uploaded build artifact.
    provider = a.wgpu.resolve()/'lib/libwgpu_native.so'
    require(provider.is_file(), 'missing external WebGPU provider')
    report = {'source_sha': a.commit, 'inputs': {name:digest(getattr(a,name)) for name in ('stage2','scanner','reactive')},
              'planner_sha256': digest(planner), 'files': {name:digest(provider if name=='libwgpu_native.so' else out/name) for name in FILES}}
    (out/'build.json').write_text(json.dumps(report, indent=2)+'\n')
    print('DOC14_GPU_BUILD_ONLY_PASS: no device opened', flush=True)


def check_build(root, sha):
    report = json.loads((root/'build.json').read_text())
    require(re.fullmatch(r'[0-9a-f]{40}', sha) and report['source_sha']==sha, 'stale build')
    require(set(report['files'])==set(FILES), 'incomplete GPU build inventory')
    for name, expected in report['files'].items():
        p = root/name
        require(p.is_file() and not p.is_symlink() and digest(p)==expected, 'GPU build digest mismatch: '+name)
    require((root/'family.doc').read_bytes()==SOURCE, 'fixture identity mismatch')
    return report


def commands():
    args, _ = fixture()
    return {'auto': (['--backend=auto', *args], None),
            'strict': (['--backend=gpu','--demand=ys','xs=[1,2,3]','bias=5'], None),
            'empty': (['--backend=gpu','--demand=ys','xs=[]'], None),
            'reject': (['--backend=gpu','--demand=ys','xs=[9223372036854775807]'], None),
            'fault': (['--backend=auto', *args], '2')}


def host_t4_ids(inventory):
    """Host NVML inventory and adapter PCI IDs must agree; description is driver text."""
    require(isinstance(inventory,str) and len(inventory)<=65536, 'invalid GPU host inventory')
    ids = set()
    for row in csv.reader(io.StringIO(inventory), skipinitialspace=True):
        require(len(row)==3, 'invalid GPU host inventory row')
        name, pci, driver = (v.strip() for v in row)
        require(name in ('Tesla T4','NVIDIA T4') and re.fullmatch(r'0x[0-9a-fA-F]{8}',pci)
                and re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',driver), 'unexpected GPU host inventory')
        combined=int(pci,16)
        require(combined & 0xffff == 0x10de and combined >> 16 != 0, 'invalid NVIDIA PCI identity')
        ids.add((combined & 0xffff, combined >> 16))
    require(bool(ids), 'empty GPU host inventory')
    return ids


def require_t4(log, ids, context):
    adapters = [x for x in log.splitlines() if x.startswith('DOC11_GPU_ADAPTER:')]
    require(bool(adapters), 'missing adapter evidence: '+context)
    for line in adapters:
        match = re.fullmatch(r'DOC11_GPU_ADAPTER: type=1 backend=6 physical=1 vendor=0x([0-9a-fA-F]{4,8}) device=0x([0-9a-fA-F]{4,8}) description=.*',line)
        require(match is not None and tuple(int(x,16) for x in match.groups()) in ids,
                'selected physical adapter does not match host Tesla T4 PCI identity: '+context)


def test_adapter_identity():
    ids = host_t4_ids('Tesla T4, 0x1EB810DE, 580.178.04\nTesla T4, 0x1EB810DE, 580.178.04\n')
    good = 'DOC11_GPU_ADAPTER: type=1 backend=6 physical=1 vendor=0x10de device=0x1eb8 description=580.178.04'
    require_t4(good,ids,'positive')
    for bad in ('',good.replace('physical=1','physical=0'),good.replace('type=1','type=2'),
                good.replace('backend=6','backend=7'),good.replace('0x10de','0x1002'),
                good.replace('0x1eb8','0x1234'),good.replace('vendor=0x10de device=0x1eb8 ', ''),
                good+'\n'+good.replace('physical=1','physical=0')):
        try: require_t4(bad,ids,'negative')
        except ValueError: pass
        else: raise AssertionError('bad adapter accepted')
    for bad in ('','NVIDIA A100, 0x1EB810DE, 580.178.04\n','Tesla T4, 0x1EB81002, 580.178.04\n',
                'Tesla T4, invalid, 580.178.04\n','Tesla T4, 0x1EB810DE, invalid\n',
                'Tesla T4, 0x1EB810DE, 580.178.04\nNVIDIA A100, 0x20B010DE, 580.178.04\n'):
        try: host_t4_ids(bad)
        except ValueError: pass
        else: raise AssertionError('bad host inventory accepted')
    print('DOC14_ADAPTER_IDENTITY_PASS: driver-only description accepted only with matching physical PCI IDs; 14 negative cases rejected', flush=True)


def verify(report, build_record, sha, run_id, bundle_sha):
    require(report['source_sha']==sha and report['run_id']==str(run_id) and report['bundle_sha256']==bundle_sha and report['build']==build_record, 'stale physical report')
    ids = host_t4_ids(report['host_gpu_csv'])
    cases = report['cases']
    require(set(cases)==set(commands()), 'incomplete physical cases')
    for name, row in cases.items():
        err = row['stderr']; out = row['stdout']; rc = row['returncode']
        require(type(rc) is int and isinstance(err,str) and isinstance(out,str), 'invalid raw evidence')
        require_t4(err, ids, name)
        require('DOC11_REGIONS: live=0 ' in err, 'missing region closure: '+name)
        if name=='auto':
            require(rc==0 and out.encode()==fixture()[1], 'physical oracle mismatch')
            require(re.findall(r'DOC11_GPU_FAMILY: state=3 lanes=(\d+)',err)==['128','256','128'] and 'DOC11_GPU_DISPATCH:' in err, 'missing family dispatch')
        elif name=='strict':
            require(rc==0 and out=='ys: [6,7,8]\n' and 'DOC11_GPU_DISPATCH:' in err, 'strict mismatch')
        elif name=='empty':
            require(rc==0 and out=='ys: []\n' and 'DOC11_GPU_DISPATCH:' not in err, 'empty mismatch')
        elif name=='reject':
            require(rc!=0 and not out and 'DOC_GPU_UNSUPPORTED' in err, 'unsupported range accepted')
        elif name=='fault':
            require(rc!=0 and out==fixture()[1].decode().split('epoch: 2\n')[0] and 'DOC11_GPU_INJECTED_FAILURE: dispatch=2' in err, 'failed dispatch published a candidate')
    print('DOC14_PHYSICAL_SMOKE_PASS: exact numerical, dispatch, admission and rollback evidence', flush=True)


def execute(root, sha, run_id, bundle_sha, output):
    build_record = check_build(root, sha)
    report = {'source_sha':sha,'run_id':str(run_id),'bundle_sha256':bundle_sha,'build':build_record,'cases':{}}
    try:
        report['host_gpu_csv'] = subprocess.run(['nvidia-smi','--query-gpu=name,pci.device_id,driver_version','--format=csv,noheader,nounits'], check=True, capture_output=True, text=True, timeout=30).stdout
        host_t4_ids(report['host_gpu_csv'])
        for name,(args,fault) in commands().items():
            env = {k:v for k,v in os.environ.items() if not k.startswith('DOC_')}
            env.update(DOC_REQUIRE_PHYSICAL_GPU='1', DOC_REGION_METRICS='1', LD_LIBRARY_PATH=str(root)+':'+env.get('LD_LIBRARY_PATH',''))
            if fault: env['DOC_GPU_TEST_FAIL_DISPATCH']=fault
            result = subprocess.run([str(root/'family-gpu'),*args], cwd=root, env=env, capture_output=True, timeout=180)
            report['cases'][name] = {'returncode':result.returncode,'stdout':result.stdout.decode(),'stderr':result.stderr.decode()}
        verify(report,build_record,sha,run_id,bundle_sha)
    finally:
        output.write_text(json.dumps(report, indent=2)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage2',type=Path,required=True)
    p.add_argument('--scanner',type=Path,required=True)
    p.add_argument('--reactive',type=Path,required=True)
    p.add_argument('--wgpu',type=Path,required=True)
    p.add_argument('--commit',required=True)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    require(re.fullmatch(r'[0-9a-f]{40}',a.commit), 'invalid source commit')
    build(a)


if __name__=='__main__': main()
