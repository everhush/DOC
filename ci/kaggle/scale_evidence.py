"""Bounded physical scaling archive intake (development evidence only)."""
import csv
import json
import math
import re
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

PREFIX = 'doc9-autonomous-evidence'
MAX_FILES = 10000
MAX_TOTAL = 512 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024


def extract_scale(archive, remote):
    """Validate all regular entries before extraction; never overwrite."""
    remote = Path(remote)
    if (remote / PREFIX).exists():
        raise ValueError('scale output already exists')
    with tarfile.open(archive, 'r:gz') as tar:
        members, seen, total = [], set(), 0
        for m in tar:
            p = PurePosixPath(m.name)
            if (len(members) >= MAX_FILES or m.name in seen or not m.isfile()
                    or p.as_posix() != m.name or not m.name.startswith(PREFIX + '/')
                    or any(s in ('', '.', '..') for s in m.name.split('/'))
                    or '\\' in m.name or any(ord(c) < 32 for c in m.name)
                    or not 0 <= m.size <= MAX_MEMBER):
                raise ValueError('unsafe scaling evidence member')
            total += m.size
            if total > MAX_TOTAL:
                raise ValueError('scaling evidence too large')
            seen.add(m.name)
            members.append(m)
        if not {PREFIX+'/summary.json', PREFIX+'/families/samples.csv', PREFIX+'/algorithms/samples.csv'} <= seen:
            raise ValueError('incomplete scale archive')
        for name in seen:
            if any(str(p) in seen for p in PurePosixPath(name).parents):
                raise ValueError('file/directory collision')
        tar.extractall(remote, members=members, filter='data')
    return remote / PREFIX


def audit_coverage(root):
    """Enforce independent workload coverage and compute descriptive tails."""
    output = {}
    for category, ordinal, timing in (('families', 'epoch', 'epoch_ns'), ('algorithms', 'round', 'epoch_sum_ns')):
        folder = root / category
        summary = json.loads((folder/'summary.json').read_text())
        machine = summary['machine']
        cap = machine['capacity']
        if type(cap) is not int or not 1 <= cap <= len(machine['affinity']) or machine['physical'] is not True or machine['samples'] != 3:
            raise ValueError('invalid machine/sample inventory')
        if category == 'families' and machine['epochs'] != 6:
            raise ValueError('incorrect family epoch count')
        sizes = {'add': (64,4096,65536,1048576,4194304), 'poly': (64,4096,65536,1048576,4194304)} if category == 'families' else {'stress': (4096,65536,262144), 'sort': (1024,16384,65536), 'reduce': (1024,16384,65536)}
        modes = [('cpu',str(i)) for i in range(1,cap+1)] + [('cpu','auto'),('gpu','auto'),('auto','auto')]
        expected = {(w,n,mode,workers,s,i) for w,ns in sizes.items() for n in ns for mode,workers in modes for s in range(1,4) for i in range(6 if category=='families' else 5 if w=='stress' else 2)}
        seen, groups = set(), defaultdict(list)
        with (folder/'samples.csv').open(newline='') as stream:
            for r in csv.DictReader(stream):
                key = (r['work'],int(r['lanes']),r['mode'],r['requested'],int(r['sample']),int(r[ordinal]))
                if key in seen or key not in expected or int(r['group_cap']) != 0 or int(r[timing]) <= 0:
                    raise ValueError('unexpected/duplicate scaling observation')
                seen.add(key)
                if key[-1] > 0:
                    groups[key[:4]].append(int(r[timing])/1e6)
        if seen != expected:
            raise ValueError('missing scaling observations')
        for p in (folder/'raw').glob('*.stderr'):
            log = p.read_bytes()
            adapters = [line for line in log.splitlines() if line.startswith(b'DOC11_GPU_ADAPTER:')]
            if adapters and not all(b' physical=1 ' in line and re.search(rb'\bT4\b',line) for line in adapters):
                raise ValueError('non-T4 adapter evidence')
        output[category] = [dict(work=k[0],lanes=k[1],mode=k[2],requested=k[3],warm_n=len(v),p50_ms=statistics.median(v),p95_ms=sorted(v)[math.ceil(.95*len(v))-1],p99_ms=sorted(v)[math.ceil(.99*len(v))-1]) for k,v in sorted(groups.items())]
    return output
