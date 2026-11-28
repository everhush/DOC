#!/usr/bin/env python3
"""Exercise an isolated native tool installation; outputs are evidence, not release assets."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = b'fn twice(x)=add(x,x)\nsource a:int=9\nderive b:int(a)=twice(a)\nsource xs:ints=[1,2,3]\nderive ys:ints(xs)=map_ints(xs,x,mul(x,2))\n'
EXPECTED = b'a: 9\nb: 18\nxs: [1,2,3]\nys: [2,4,6]\n'
INVALID = {
    'bad-type': b'source a:int=true\n',
    'cycle': b'derive a:int(b)=add(b,1)\nderive b:int(a)=add(a,1)\n',
    'undefined': b'source a:int=1\nderive b:int(a)=add(a,missing)\n',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--scanner', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--stream', action='store_true')
    a = p.parse_args()
    out = a.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    prefix = out / 'installed'
    for name in ('compiler', 'runtime', 'tools'):
        (prefix / name).mkdir(parents=True)
    shutil.copy2(ROOT / 'runtime-doc/compiler/doc_build.py', prefix / 'compiler/doc_build.py')
    for path in sorted((ROOT / 'runtime-doc/runtime').glob('*.h')):
        shutil.copy2(path, prefix / 'runtime' / path.name)
    for src, name in ((a.compiler.resolve(), 'managed'), (a.scanner.resolve(), 'module_scan')):
        shutil.copy2(src, prefix / 'tools' / name)
        (prefix / 'tools' / name).chmod(0o755)
    work = out / 'user-workspace'
    work.mkdir()
    source = work / 'sample.doc'
    source.write_bytes(SAMPLE)
    exe = work / 'sample'
    c = work / 'sample.c'
    base = [sys.executable, str(prefix / 'compiler/doc_build.py'), '--scanner', str(prefix / 'tools/module_scan'), '--compiler', str(prefix / 'tools/managed'), '--output', str(exe), '--emit-c', str(c)]
    if a.stream:
        base.append('--stream')
    build = subprocess.run(base + [str(source), '--compile-evidence', str(out / 'compile.json')], cwd=work, capture_output=True, timeout=600)
    (out / 'build.stdout').write_bytes(build.stdout)
    (out / 'build.stderr').write_bytes(build.stderr)
    assert build.returncode == 0, build.stderr[-4000:]
    before = {str(f.relative_to(out)): digest(f) for f in (exe, c)}
    relocated = out / 'relocated'
    relocated.mkdir()
    shutil.copy2(exe, relocated / 'app')
    run = subprocess.run([str(relocated / 'app')], cwd=relocated, env={'DOC_REGION_METRICS': '1'}, capture_output=True, timeout=30)
    (out / 'app.stdout').write_bytes(run.stdout)
    (out / 'app.stderr').write_bytes(run.stderr)
    assert run.returncode == 0 and run.stdout == EXPECTED and b'DOC11_REGIONS: live=0 ' in run.stderr, (run.stdout, run.stderr)
    linkage = subprocess.check_output(['readelf', '-d', str(relocated / 'app')], text=True)
    (out / 'app-linkage.txt').write_text(linkage)
    assert re.findall(r'\(NEEDED\).*?\[(.*?)\]', linkage) == ['libc.so.6'], linkage
    rejected = {}
    for name, data in INVALID.items():
        bad = work / (name + '.doc')
        bad.write_bytes(data)
        check = subprocess.run(base + [str(bad)], cwd=work, capture_output=True, timeout=120)
        (out / (name + '.stderr')).write_bytes(check.stderr)
        assert check.returncode != 0, name
        assert all(digest(out / path) == value for path, value in before.items()), name
        rejected[name] = check.returncode
    report = {'compiler_sha256': digest(prefix / 'tools/managed'), 'scanner_sha256': digest(prefix / 'tools/module_scan'), 'source_sha256': digest(source), 'sample_sha256': digest(exe), 'generated_c_sha256': digest(c), 'stream': a.stream, 'negative_cases': rejected, 'needed': ['libc.so.6'], 'scope': 'isolated native CPU install smoke; not a complete distribution'}
    (out / 'install-smoke.json').write_text(json.dumps(report, indent=2) + '\n')
    print('DOC14_INSTALL_SMOKE_PASS: isolated tools, relocated native app, independent scalar/list oracle, three rejected inputs, prior output preserved')


if __name__ == '__main__':
    main()
