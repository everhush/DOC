#!/usr/bin/env python3
"""Candidate-only numerical/physical GPU smoke; never uses a reference evaluator."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'runtime-doc'
SOURCE = b'source xs:ints=[1,2,3]\nsource bias:int=5\nsource flag:bool=false\nderive ys:ints(xs,bias)=map_ints(xs,item,add(item,bias))\nderive unrelated:bool(flag,xs)=if(flag,eq(len(xs),0),true)\nderive count:int(ys)=len(ys)\n'
CASES = ((128, 5), (0, 5), (256, 6), (3, 7), (128, 8))


def vector(values):
    return '[' + ','.join(map(str, values)) + ']'


def fixture():
    args, lines = [], []
    for epoch, (n, bias) in enumerate(CASES):
        xs = list(range(n))
        if epoch:
            args.append('--next')
        args += ['xs=' + vector(xs), 'bias=' + str(bias)]
        lines += [f'epoch: {epoch}', 'xs: ' + vector(xs), f'bias: {bias}', 'flag: false',
                  'ys: ' + vector([x+bias for x in xs]), 'unrelated: true', f'count: {n}']
    return args, ('\n'.join(lines) + '\n').encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, detail):
    if not ok:
        raise ValueError(detail)


def run(exe, args, out, label, physical=False):
    env = dict(os.environ)
    for key in ('DOC_GPU_ALLOW_SOFTWARE', 'DOC_GPU_TEST_FAIL_DISPATCH', 'DOC_REQUIRE_PHYSICAL_GPU'):
        env.pop(key, None)
    env['DOC_REGION_METRICS'] = '1'
    if physical:
        env['DOC_REQUIRE_PHYSICAL_GPU'] = '1'
    result = subprocess.run([str(exe), *args], cwd=out, env=env, capture_output=True, timeout=180)
    (out / (label+'.stdout')).write_bytes(result.stdout)
    (out / (label+'.stderr')).write_bytes(result.stderr)
    return result


def physical(result):
    adapters = [x for x in result.stderr.splitlines() if x.startswith(b'DOC11_GPU_ADAPTER:')]
    require(adapters and all(b' physical=1 ' in x for x in adapters), 'missing or nonphysical adapter')
    require(b'DOC11_REGIONS: live=0 ' in result.stderr, 'missing zero-live-byte evidence')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True, help='clean native reactive2')
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--cpu-only', action='store_true')
    p.add_argument('--gpu-plan', type=Path)
    p.add_argument('--wgpu-root', type=Path)
    a = p.parse_args()
    require(a.cpu_only or (a.gpu_plan and a.wgpu_root), 'physical mode needs native planner and WebGPU ABI')
    require(not (a.cpu_only and (a.gpu_plan or a.wgpu_root)), 'ambiguous CPU-only mode')
    sys.path.insert(0, str(NATIVE/'compiler'))
    from doc_build import build_bundled
    out = a.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out/'family.doc').write_bytes(SOURCE)
    args, expected = fixture()
    (out/'family.expected').write_bytes(expected)
    compiler = [a.compiler.resolve()]
    cpu = out/'family-cpu'
    headers = NATIVE/'runtime'
    build_bundled(compiler, SOURCE, cpu, headers, True, out/'family-cpu.c', stream=True)
    result = run(cpu, ['--backend=cpu', *args], out, 'cpu')
    require(result.returncode == 0 and result.stdout == expected and b'DOC11_REGIONS: live=0 ' in result.stderr, 'CPU oracle mismatch')
    require(b'DOC11_GPU_DISPATCH:' not in result.stderr, 'unexpected CPU dispatch')
    if not a.cpu_only:
        gpu = out/'family-gpu'
        build_bundled(compiler, SOURCE, gpu, headers, True, out/'family-gpu.c', stream=True,
                      gpu_plan=[a.gpu_plan.resolve()], wgpu_root=a.wgpu_root.resolve(),
                      emit_wgsl=out/'family.wgsl', emit_gpu_header=out/'gpu_generated.h')
        result = run(gpu, ['--backend=auto', *args], out, 'auto', True)
        physical(result)
        require(result.returncode == 0 and result.stdout == expected, 'physical numerical mismatch')
        require(re.findall(rb'DOC11_GPU_FAMILY: state=3 lanes=(\d+)', result.stderr) == [b'128', b'256', b'128'], 'missing physical lane dispatch')
        strict = run(gpu, ['--backend=gpu', '--demand=ys', 'xs=[1,2,3]', 'bias=5'], out, 'strict', True)
        physical(strict)
        require(strict.returncode == 0 and strict.stdout == b'ys: [6,7,8]\n' and b'DOC11_GPU_DISPATCH:' in strict.stderr, 'strict GPU mismatch')
        empty = run(gpu, ['--backend=gpu', '--demand=ys', 'xs=[]'], out, 'empty', True)
        physical(empty)
        require(empty.returncode == 0 and empty.stdout == b'ys: []\n' and b'DOC11_GPU_DISPATCH:' not in empty.stderr, 'zero extent mismatch')
        bad = run(gpu, ['--backend=gpu', '--demand=ys', 'xs=[9223372036854775807]'], out, 'reject', True)
        physical(bad)
        require(bad.returncode != 0 and not bad.stdout and b'DOC_GPU_UNSUPPORTED' in bad.stderr, 'strict rejection failed')
    report = {'mode': 'cpu-oracle' if a.cpu_only else 'physical-gpu', 'compiler_sha256': digest(a.compiler), 'source_sha256': digest(out/'family.doc'), 'files': {f.name: digest(f) for f in sorted(out.iterdir()) if f.is_file()}}
    (out/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print('DOC14_GPU_CANDIDATE_CPU_ORACLE_PASS' if a.cpu_only else 'DOC14_GPU_CANDIDATE_PHYSICAL_PASS')


if __name__ == '__main__':
    main()
