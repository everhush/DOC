#!/usr/bin/env python3
"""Offline verification of final T4-patched comparison. No benchmark execution.

Pass the three same-run GitHub ZIPs (HVM build, DOC build, physical return),
their published digests, and exact workflow SHA/run ID. The original accepted
CPU ZIP can additionally bind each Bend input to that campaign.
"""
import argparse, hashlib, io, json, re, statistics, struct, tarfile, zipfile
from collections import defaultdict
from pathlib import Path
from verify_cpu_evidence import SIZES, values

def digest(data):
    return hashlib.sha256(data).hexdigest()

def checked_zip(path, expected):
    assert digest(path.read_bytes()) == expected.removeprefix('sha256:'), path
    z=zipfile.ZipFile(path)
    assert len(z.namelist())==len(set(z.namelist())), path
    return z

def find(z, suffix):
    hits=[n for n in z.namelist() if n==suffix or n.endswith('/'+suffix)]
    assert len(hits)==1,(suffix,hits)
    return hits[0]

def rounds(w): return 5 if w=='stress' else 2

def main():
    p=argparse.ArgumentParser()
    for name in ('hvm','doc','physical'):
        p.add_argument('--'+name,type=Path,required=True)
        p.add_argument('--'+name+'-sha256',required=True)
    p.add_argument('--source-sha',required=True)
    p.add_argument('--run-id',required=True)
    p.add_argument('--accepted-cpu',type=Path)
    p.add_argument('--accepted-cpu-sha256')
    p.add_argument('--summary',type=Path)
    a=p.parse_args()
    h=checked_zip(a.hvm,a.hvm_sha256)
    d=checked_zip(a.doc,a.doc_sha256)
    z=checked_zip(a.physical,a.physical_sha256)
    old=None
    if a.accepted_cpu:
        assert a.accepted_cpu_sha256
        old=checked_zip(a.accepted_cpu,a.accepted_cpu_sha256)
    assert b'release 12.8' in h.read(find(h,'toolkit.txt'))
    cp=find(h,'cases.json')
    hp=cp.removesuffix('cases.json')
    cases=json.loads(h.read(cp))
    expected={(w,n,e) for w,ns in SIZES.items() for n in ns for e in range(rounds(w))}
    assert len(cases)==len(expected)==47
    assert {(c['work'],c['n'],c['epoch']) for c in cases}==expected
    pp=find(z,'provenance.json').removesuffix('provenance.json')
    prov=json.loads(z.read(pp+'provenance.json'))
    spec=prov['spec']; manifest=prov['manifest']
    assert spec['sha']==manifest['sha']==a.source_sha
    assert spec['run_id']==manifest['run_id']==a.run_id
    assert spec['accelerator']=='NvidiaTeslaT4'
    assert d.read(find(d,'source-sha.txt')).decode().strip()==a.source_sha
    files=manifest['files']
    for c in cases:
        w,n,e=c['work'],c['n'],c['epoch']
        s=c['stem']; assert s==f'{w}-{n}-{e}'
        assert c['full']==((n<=65536 and w!='reduce') or w=='sort')
        stock=h.read(hp+'stock/'+s+'.cu')
        patched=h.read(hp+s+'.cu')
        bend=h.read(hp+s+'.bend')
        elf=h.read(hp+s+'.elf')
        assert elf.startswith(b'\x7fELF')
        for name,data,key in [(s+'.bend',bend,'source_sha'),(s+'.cu',patched,'cuda_sha'),(s+'.elf',elf,'binary_sha')]:
            assert digest(data)==c[key]
            assert files['hvm/'+name]=={'sha256':digest(data),'bytes':len(data)}
        assert digest(stock)==c['stock_cuda_sha']
        assert 'hvm/'+s+'.elf' in spec['executables']
        for x,y in [(b'L_NODE_LEN = 0x2000;',b'L_NODE_LEN = 0x1000;'),(b'L_VARS_LEN = 0x2000;',b'L_VARS_LEN = 0x1000;'),(b'TPB_L2 = 7;',b'TPB_L2 = 6;'),(b'BPG_L2 = 7;',b'BPG_L2 = 6;')]:
            assert stock.count(x)==1
            stock=stock.replace(x,y)
        assert stock==patched,s
        matches=re.findall(rb'^\s*static const u8 BOOK_BUF\[\]\s*=\s*\{([\d,\s]+)\};',patched,re.M)
        assert len(matches)==1,s
        buf=bytes(map(int,re.findall(rb'\d+',matches[0])))
        words=struct.unpack('<'+'I'*(len(buf)//4),buf)
        pos=1; maxima=[0,0,0]
        for _ in range(words[0]):
            pos+=65
            _,r,nd,v,_=words[pos:pos+5]
            pos+=5+2*(r+nd)
            maxima=[max(x,y) for x,y in zip(maxima,[r,nd,v])]
        assert pos==len(words) and maxima==c['max_definition_slots'] and max(maxima)<=64,s
        if old:
            assert old.read(find(old,f'{w}-{n}/epoch-{e}/main.bend'))==bend,s
    # Bind all transported executable bytes to the same-run build manifests.
    for category in ('families','algorithms'):
        name=f'scale/{category}/build.json'
        data=d.read(find(d,name))
        assert files[name]=={'sha256':digest(data),'bytes':len(data)}
        for key,rec in json.loads(data).items():
            name=f'scale/{category}/{key}/bench'
            data=d.read(find(d,name))
            assert digest(data)==rec['sha256']
            assert files[name]=={'sha256':digest(data),'bytes':len(data)}
            assert name in spec['executables']
    wgpu=d.read(find(d,'libwgpu_native.so'))
    assert files['wgpu/lib/libwgpu_native.so']=={'sha256':digest(wgpu),'bytes':len(wgpu)}
    for name in ('cases.json','toolkit.txt'):
        data=h.read(hp+name)
        assert files['hvm/'+name]=={'sha256':digest(data),'bytes':len(data)}
    # Check the remote tar against the extracted copy, never just trust the CI summary.
    archive=z.read(find(z,'doc9-hvm-results.tar.gz'))
    ep=pp+'remote/evidence/'
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as t:
        names=set()
        for m in t:
            if m.isdir(): continue
            assert m.isfile() and m.name.startswith('evidence/') and m.name not in names
            names.add(m.name)
            assert t.extractfile(m).read()==z.read(pp+'remote/'+m.name),m.name
        assert names=={'evidence/'+n[len(ep):] for n in z.namelist() if n.startswith(ep) and not n.endswith('/')}
    def read(name): return z.read(ep+name)
    report=json.loads(read('report.json'))
    assert report['sha']==a.source_sha and report['run_id']==a.run_id
    assert report['bundle_sha256']==spec['bundle_sha256']
    assert report['result']=='pass' and not report['failures'] and not json.loads(read('failures.json')),report
    assert b'Tesla T4' in read('nvidia.stdout') and b'release 12.8' in read('nvcc.stdout')
    rows=json.loads(read('samples.json')); assert len(rows)==report['samples']==198
    seen=set(); times=defaultdict(list); dispatches=0; doc_rounds=0
    for row in rows:
        eng,w,n,s,e=row['engine'],row['work'],row['n'],row['sample'],row.get('epoch')
        assert n in SIZES[w] and s in range(3) and row['ok'] and row['rc']==0 and row['wall_ns']>0
        key=(eng,w,n,e,s);assert key not in seen;seen.add(key)
        root=f'{w}-{n}/'
        if eng=='DOC':
            assert e is None and row['rounds']==rounds(w)
            raw,err=read(root+f'doc-{s}.stdout'),read(root+f'doc-{s}.stderr')
            assert b'physical=1 ' in err and b'live=0' in raw
            assert re.search(rb'DOC11_GPU_POOL_METRICS: event=closed .* live=0\b',err)
            pat=rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)' if w in ('add','poly') else rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)'
            rr=[list(map(int,x)) for x in re.findall(pat,raw)]
            assert rr==row['epochs'] and len(rr)==rounds(w)
            for i,x in enumerate(rr):assert x[0]==i and x[1]>0 and x[3]==sum(values(w,n,i)),key
            traces=re.findall(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',err)
            stages=(n.bit_length()-1)*n.bit_length()//2 if w=='sort' else n.bit_length()-1 if w=='reduce' else 1
            assert len(traces)==rounds(w)*stages,key
            assert all(0<int(l) and int(g)==min((int(l)+63)//64,65535) for l,g in traces),key
            dispatches+=len(traces);doc_rounds+=len(rr)
            times[(w,n,'doc')].append(row['wall_ns']/1e6/rounds(w))
            times[(w,n,'doc_epoch')].extend(x[1]/1e6 for x in rr[1:])
        else:
            assert eng=='HVM2-T4-patched' and e in range(rounds(w))
            root+=f'{w}-{n}-{e}-{s}'
            raw,err=read(root+'.stdout'),read(root+'.stderr')
            assert not re.search(rb'(?i)(failed to launch|failed to load book|too many (?:nodes|redexes)|cuda error|illegal memory access|out of memory|\bOOM\b)',raw+err)
            got=re.findall(rb'^Result:\s*([^\r\n]+)',raw,re.M)
            assert len(got)==1 and re.fullmatch(rb'[\d(), \t]+',got[0]),key
            nums=list(map(int,re.findall(rb'\d+',got[0])))
            v=values(w,n,e);offset=4096 if w in ('add','poly') else 0
            full=(n<=65536 and w!='reduce') or w=='sort'
            assert row['full_vector']==full and row['expected']==sum(v),key
            assert (nums==[x+offset for x in v]) if full else (len(nums)==2 and nums[0]+65536*nums[1]==sum(v)+n*offset),key
            assert re.search(rb'- ITRS: (\d+)',raw) and re.search(rb'- TIME: ([\d.]+)s',raw),key
            times[(w,n,'hvm')].append(row['wall_ns']/1e6)
    summary=[]
    for w,ns in SIZES.items():
        for n in ns:
            assert len(times[(w,n,'hvm')])==3*rounds(w) and len(times[(w,n,'doc')])==3
            hvm=statistics.median(times[(w,n,'hvm')]); doc=statistics.median(times[(w,n,'doc')])
            summary.append(dict(work=w,n=n,hvm_process_ms=hvm,doc_amortized_ms=doc,
                                doc_warm_epoch_ms=statistics.median(times[(w,n,'doc_epoch')]),hvm_doc_ratio=hvm/doc))
    assert dispatches==2121 and doc_rounds==141,(dispatches,doc_rounds)
    for r in summary: print(json.dumps(r))
    if a.summary: a.summary.write_text(json.dumps(summary,indent=2)+'\n')
    print('DOC9_T4_RETURNED_EVIDENCE_PASS',len(seen),'processes',dispatches,'DOC dispatches',doc_rounds,'DOC rounds')

if __name__=='__main__': main()
