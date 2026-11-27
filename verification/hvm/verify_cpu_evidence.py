#!/usr/bin/env python3
"""Offline independent verification of the matched CPU evidence archive.

No HVM/Bend, DOC compiler, executable, or GPU is invoked. Supply the published
GitHub ZIP digest, and do not treat rejected/partial runs as full acceptance.
"""
import argparse, hashlib, json, re, statistics, zipfile
from functools import lru_cache
from pathlib import Path

SIZES={'add':(64,4096,65536,1048576,4194304),'poly':(64,4096,65536,1048576,4194304),'stress':(4096,65536,262144),'sort':(1024,16384,65536),'reduce':(1024,16384,65536)}
@lru_cache(maxsize=8)
def values(w,n,e):
    if w=='sort':
        x=2026+e;out=[]
        for _ in range(n):
            x=(x*1664525+1013904223)%(2**32);out.append(x//65536%32768)
        return sorted(out)
    if w=='add':return [(i+e)%32760+e%7-3 for i in range(n)]
    if w=='poly':
        b=e%7-3;table=[b*sum(x**j for j in range(6)) for x in range(-4,5)]
        return [table[(i+e)%9] for i in range(n)]
    if w=='stress':
        a=pow(25173,32,65521);c=(13849+e)*sum(pow(25173,j,65521) for j in range(32))%65521
        return [(a*((i+e)%32760)+c)%65521 for i in range(n)]
    if w=='reduce':return [(i+e)%2 for i in range(n)]
    raise AssertionError(w)

def main():
    p=argparse.ArgumentParser();p.add_argument('zip',type=Path);p.add_argument('--sha256',required=True);p.add_argument('--source-sha',required=True);a=p.parse_args()
    assert hashlib.sha256(a.zip.read_bytes()).hexdigest()==a.sha256
    with zipfile.ZipFile(a.zip) as z:
        names=z.namelist();assert len(set(names))==len(names)
        manifest={}
        for line in z.read('SHA256SUMS').decode().splitlines():
            h,n=line.split('  ',1);n=n.removeprefix('doc9-hvm-evidence/')
            assert n not in manifest and n in names and hashlib.sha256(z.read(n)).hexdigest()==h,n
            manifest[n]=h
        assert set(manifest)==set(names)-{'SHA256SUMS'}
        assert z.read('source-sha.txt').decode().strip()==a.source_sha
        assert z.read('runtime-tree.txt').decode().strip()=='a7fe0554abea1a2b218929b33ad2f8f66f632f94'
        assert z.read('compiler-tree.txt').decode().strip()=='9120f50dde55af7c0a656d43ece6acf824cbcab0'
        m=json.loads(z.read('machine.json'));assert '2.0.22' in m['hvm'] and '0.2.38' in m['bend'];cap=len(m['affinity']);assert cap
        rows=json.loads(z.read('samples.json'));assert not json.loads(z.read('failures.json'))
        assert len(rows)==198
        results=[];keys=set();identities=set()
        for r in rows:
            eng,w,n,s=r['engine'],r['work'],r['n'],r['sample'];e=r.get('epoch')
            assert n in SIZES[w] and s in range(3) and r['ok'] and r['rc']==0 and r['wall_ns']>0
            k=(eng,w,n,e,s);assert k not in keys;keys.add(k)
            rounds=5 if w=='stress' else 2
            if eng=='HVM2':
                assert e in range(rounds)
                root=f'{w}-{n}/epoch-{e}/';ident=json.loads(z.read(root+'identity.json'));identities.add(root)
                assert ident['source']==manifest[root+'main.bend'] and ident['generated']==manifest[root+'main.c'] and ident['binary']==manifest[root+'hvm-bench']
                tpc=re.search(rb'#define TPC_L2 (\d+)',z.read(root+'main.c'));assert tpc and 2**int(tpc[1])<=cap
                raw=z.read(root+f'hvm-{s}.stdout');err=z.read(root+f'hvm-{s}.stderr')
                got=re.findall(rb'^Result:\s*([^\r\n]+)',raw,re.M);assert len(got)==1 and re.fullmatch(rb'[\d(), \t]+',got[0]);got=list(map(int,re.findall(rb'\d+',got[0])))
                v=values(w,n,e);offset=4096 if w in ('add','poly') else 0
                full=(n<=65536 and w!='reduce') or w=='sort'
                assert r['expected']==sum(v)==ident['expected'] and r['full_vector']==ident['full_vector']==full
                assert (got==[x+offset for x in v]) if full else (len(got)==2 and got[0]+65536*got[1]==sum(v)+n*offset),k
                assert not re.search(rb'(?i)\bOOM\b|out of memory|segmentation fault',raw+err)
                assert re.search(rb'- ITRS: (\d+)',raw) and re.search(rb'- TIME: ([\d.]+)s',raw)
                wall=r['wall_ns']/1e6
            else:
                assert eng=='DOC' and e is None;root=f'{w}-{n}/'
                raw=z.read(root+f'doc-{s}.stdout');err=z.read(root+f'doc-{s}.stderr')
                assert b'live=0' in raw and b'DOC11_GPU_ADAPTER:' not in err
                pat=rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)' if w in ('add','poly') else rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)'
                rr=[list(map(int,x)) for x in re.findall(pat,raw)];assert rr==r['epochs'] and len(rr)==r['rounds']==rounds
                for i,x in enumerate(rr):assert x[0]==i and x[3]==sum(values(w,n,i)),k
                workers=[int(x) for x in re.findall(rb'workers=(\d+)',err)];assert not workers or max(workers)<=cap
                wall=r['wall_ns']/1e6/rounds
            rss=re.search(rb'MAX_RSS_KIB=(\d+)',err);assert rss
            results.append((eng,w,n,wall,int(rss[1])))
        assert len(identities)==47
        summary=json.loads(z.read('summary.json'))
        for w,ns in SIZES.items():
            for n in ns:
                h=[r for r in results if r[:3]==('HVM2',w,n)];d=[r for r in results if r[:3]==('DOC',w,n)]
                assert len(h)==3*(5 if w=='stress' else 2) and len(d)==3
                sh=statistics.median(r[3] for r in h);sd=statistics.median(r[3] for r in d)
                record=next(x for x in summary if (x['work'],x['n'])==(w,n))
                assert abs(record['hvm_process_ms_median']-sh)<1e-8 and abs(record['doc_process_amortized_ms_median']-sd)<1e-8
                print(w,n,'HVM ms',round(sh,3),'DOC amortized ms',round(sd,3),'HVM RSS KiB',statistics.median(r[4] for r in h),'DOC RSS KiB',statistics.median(r[4] for r in d))
        print('DOC9_HVM_CPU_EVIDENCE_PASS',len(manifest),'files',len(rows),'processes',len(identities),'HVM binaries')
if __name__=='__main__':main()
