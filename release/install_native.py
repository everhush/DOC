#!/usr/bin/env python3
"""Install hash-verified native DOC tools in a new, relocatable prefix.

Authenticate the input evidence and source separately before invoking this tool.
No evaluator, network access, C build, or external GPU library is installed.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {'managed': 'self/stage2', 'module_scan': 'scanner2', 'reactive': 'reactive2'}
HEADERS = tuple('checkpoint_io.h epoch_authority.h gpu_pool_metrics.h gpu_values.h graph_host.h graph_reader_slots.h graph_variant_abi.h graph_variant_adapter.h placed_authority.h placed_epoch.h placed_transport.h reactive_values.h recurrence_values.h value_primitives.h webgpu_loss_evidence.h webgpu_retirement.h effects_policy_generated.h epoch_policy_generated.h graph_generation_generated.h placed_policy_generated.h placement_policy_generated.h recurrence_policy_generated.h'.split())
LAUNCHER = '''#!/usr/bin/env python3
import argparse, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description='Compile a DOC source into a native executable')
p.add_argument('source', type=Path)
p.add_argument('-o', '--output', required=True, type=Path)
p.add_argument('--reactive', action='store_true')
p.add_argument('--wgpu-root', type=Path)
p.add_argument('--emit-c', type=Path)
p.add_argument('--emit-wgsl', type=Path)
p.add_argument('--emit-gpu-header', type=Path)
a = p.parse_args()
if not (root/'install-manifest.json').is_file(): p.error('incomplete installation')
if a.wgpu_root and not (root/'tools/gpu_plan').is_file(): p.error('GPU planner not installed')
if (a.emit_wgsl or a.emit_gpu_header) and not a.wgpu_root: p.error('GPU outputs require --wgpu-root')
cmd = [sys.executable, str(root/'compiler/doc_build.py'), str(a.source), '-o', str(a.output), '--scanner', str(root/'tools/module_scan'), '--compiler', str(root/'tools'/('reactive' if a.reactive or a.wgpu_root else 'managed')), '--stream']
if a.reactive or a.wgpu_root: cmd += ['--reactive']
if a.wgpu_root: cmd += ['--gpu-plan', str(root/'tools/gpu_plan'), '--wgpu-root', str(a.wgpu_root)]
for opt, value in (('--emit-c',a.emit_c),('--emit-wgsl',a.emit_wgsl),('--emit-gpu-header',a.emit_gpu_header)):
    if value is not None: cmd += [opt,str(value)]
raise SystemExit(subprocess.call(cmd))
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError('missing or nonregular input: '+str(path))
    return path


def verified(path, expected):
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}',expected) or digest(regular(path))!=expected:
        raise ValueError('input hash mismatch: '+str(path))
    return path


def install(a):
    if not re.fullmatch(r'[0-9a-f]{40}',a.source_commit):
        raise ValueError('exact source commit required')
    evidence = a.native_evidence.resolve()
    manifest = json.loads(verified(evidence/'native-hashes.json',a.native_manifest_sha256).read_text())
    tools = {name:verified(evidence/rel,manifest[rel]) for name,rel in TOOLS.items()}
    if bool(a.gpu_build)!=bool(a.gpu_manifest_sha256):
        raise ValueError('GPU build and manifest hash must be supplied together')
    if a.gpu_build:
        build = a.gpu_build.resolve()
        gpu = json.loads(verified(build/'build.json',a.gpu_manifest_sha256).read_text())
        if gpu['source_sha']!=a.source_commit or gpu['inputs']!={'stage2':manifest['self/stage2'],'scanner':manifest['scanner2'],'reactive':manifest['reactive2']}:
            raise ValueError('GPU build does not match native compiler inputs')
        tools['gpu_plan'] = verified(build/'gpu_plan2',gpu['planner_sha256'])
    sources = {'compiler/doc_build.py':regular(ROOT/'runtime-doc/compiler/doc_build.py')}
    sources.update({'runtime/'+name:regular(ROOT/'runtime-doc/runtime'/name) for name in HEADERS})
    sources.update({name:regular(ROOT/name) for name in ('LICENSE','LICENSE-APACHE','NOTICE')})
    sources.update({'tools/'+name:path for name,path in tools.items()})
    prefix = a.prefix.absolute()
    # No existing prefix can be replaced; all failed fresh installs are removed.
    prefix.mkdir(exist_ok=False)
    try:
        files = {}
        for name,path in sources.items():
            target = prefix/name
            target.parent.mkdir(parents=True,exist_ok=True)
            data = path.read_bytes()
            target.write_bytes(data)
            target.chmod(0o755 if name.startswith('tools/') else 0o644)
            files[name] = digest(target)
        for name,rel in TOOLS.items():
            verified(prefix/'tools'/name,manifest[rel])
        if a.gpu_build:
            verified(prefix/'tools/gpu_plan',gpu['planner_sha256'])
        (prefix/'bin').mkdir()
        launcher = prefix/'bin/doc'
        launcher.write_text(LAUNCHER)
        launcher.chmod(0o755)
        files['bin/doc'] = digest(launcher)
        (prefix/'install-manifest.json').write_text(json.dumps({'source_commit':a.source_commit,'native_manifest_sha256':a.native_manifest_sha256,'gpu_manifest_sha256':a.gpu_manifest_sha256,'files':files},indent=2)+'\n')
    except BaseException:
        shutil.rmtree(prefix)
        raise
    print('DOC14_NATIVE_INSTALL_PASS:',prefix,flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix',required=True,type=Path)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--native-evidence',required=True,type=Path)
    p.add_argument('--native-manifest-sha256',required=True)
    p.add_argument('--gpu-build',type=Path)
    p.add_argument('--gpu-manifest-sha256')
    try:
        install(p.parse_args())
    except (OSError,ValueError,KeyError,TypeError) as e:
        p.exit(1,'DOC install: '+str(e)+'\n')


if __name__=='__main__': main()
