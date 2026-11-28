#!/usr/bin/env python3
"""Verify a source tar against an exact-commit manifest before any extraction."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

LIMIT = 64 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def valid_path(name):
    parts = PurePosixPath(name).parts
    return bool(parts) and not name.startswith('/') and '\\' not in name and all(
        p not in ('.', '..') and all(ord(c) >= 32 and ord(c) != 127 for c in p)
        for p in parts) and '/'.join(parts) == name


def verify(archive, manifest, commit, output=None):
    require(re.fullmatch(r'[0-9a-f]{40}', commit), 'invalid source commit')
    require(archive.stat().st_size <= LIMIT and manifest.stat().st_size <= LIMIT,
            'candidate input exceeds capacity')
    metadata = json.loads(manifest.read_text(encoding='utf-8'))
    require(metadata['source_commit'] == commit, 'source commit mismatch')
    entries = metadata['files']
    require(isinstance(entries, list) and 0 < len(entries) <= 4096, 'invalid file count')
    expected = {}
    dirs = {'.'}
    total = 0
    for entry in entries:
        name = entry['path']
        require(valid_path(name) and name not in expected, 'invalid or duplicate manifest path')
        require(entry['mode'] in ('100644', '100755'), 'invalid manifest mode')
        require(type(entry['bytes']) is int and 0 <= entry['bytes'] <= LIMIT, 'invalid byte count')
        require(re.fullmatch(r'[0-9a-f]{64}', entry['sha256']) and
                re.fullmatch(r'[0-9a-f]{40}', entry['git_blob']), 'invalid digest')
        expected[name] = entry
        dirs.update(str(p) for p in PurePosixPath(name).parents)
        total += entry['bytes']
    require(total <= LIMIT and not (set(expected) & dirs), 'invalid total size or file/directory collision')
    files = {}
    seen = set()
    with tarfile.open(archive, mode='r:') as source:
        for member in source:
            name = member.name.removeprefix('./')
            require(name == '.' or valid_path(name), 'unsafe archive path')
            require(name not in seen, 'duplicate archive member')
            seen.add(name)
            if member.isdir():
                require(name in dirs and member.size == 0, 'unexpected directory')
                continue
            require(member.type == tarfile.REGTYPE and name in expected, 'unexpected or nonregular file')
            entry = expected[name]
            require(member.size == entry['bytes'] and member.mode == int(entry['mode'], 8) & 0o777,
                    'size or mode mismatch: ' + name)
            data = source.extractfile(member).read()
            require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'SHA-256 mismatch: ' + name)
            blob = b'blob ' + str(len(data)).encode() + b'\0' + data
            require(hashlib.sha1(blob).hexdigest() == entry['git_blob'], 'Git blob mismatch: ' + name)
            decoded = data.decode('utf-8')
            require(all(ord(c) >= 32 or c in '\n\r\t\f' for c in decoded), 'nontext content: ' + name)
            files[name] = data
    require(set(files) == set(expected), 'missing manifest files')
    if output is not None:
        output.mkdir(parents=False, exist_ok=False)
        for name, data in files.items():
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(int(expected[name]['mode'], 8) & 0o777)
    print(f'DOC14_MANIFEST_PASS: {commit}, {len(files)} files, {total} bytes')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    verify(a.archive, a.manifest, a.commit, a.output)


if __name__ == '__main__':
    main()
