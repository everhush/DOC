#!/usr/bin/env python3
"""Offline verification of an autonomous physical campaign's returned evidence.

Uses only archived records and independent mathematical checksums. Does not
execute a benchmark, initialize a device, or require Kaggle credentials.
"""
import argparse,csv,functools,hashlib,io,json,math,re,statistics,tarfile
from collections import defaultdict
from pathlib import Path

@functools.lru_cache(None)
def family_checksum(work,n,epoch):
    bias=epoch%7-3
    period={'add':32760,'poly':9}[work]
    values=[(i+epoch)%period for i in range(period)]
    if work=='add':values=[x+bias for x in values]
    else:values=[bias*sum((x-4)**j for j in range(6)) for x in values]
    q,r=divmod(n,period)
    return q*sum(values)+sum(values[:r])

@functools.lru_cache(None)
def algorithm_checksum(work,n,round_no):
    if work=='reduce':return n//2
    if work=='sort':
        state=2026+round_no;total=0
        for _ in range(n):
            state=(state*1664525+1013904223)&0xffffffff
            total+=(state>>16)&32767
        return total
    assert work=='stress'
    a,m,b=25173,65521,13849+round_no
    # Independently evaluate the affine modular composition in closed form.
    slope=pow(a,32,m);offset=b*sum(pow(a,j,m) for j in range(32))%m
    values=[(slope*((i+round_no)%32760)+offset)%m for i in range(32760)]
    q,r=divmod(n,32760)
    return q*sum(values)+sum(values[:r])

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(physical,build,sha,run_id):
    p=json.loads((physical/'provenance.json').read_text())
    spec=p['spec'];manifest=p['manifest']
    assert spec['sha']==manifest['sha']==sha and str(spec['run_id'])==str(manifest['run_id'])==str(run_id)
    remote=physical/'remote';root=remote/'doc9-autonomous-evidence'
    record=json.loads((root/'summary.json').read_text())
    assert record==dict(sha=sha,run_id=str(run_id),bundle_sha256=spec['bundle_sha256'],hardware=True,result='pass')
    archives=list(remote.rglob('doc9-autonomous-results.tar.gz'))
    assert len(archives)==1
    with tarfile.open(archives[0]) as archive:
        members=[m for m in archive.getmembers() if m.isfile()]
        assert len({m.name for m in members})==len(members)
        for m in members:
            path=(remote/m.name).resolve();assert path.is_relative_to(remote.resolve())
            assert path.read_bytes()==archive.extractfile(m).read(),m.name
    total={'epochs_and_rounds':0,'processes':0,'dispatches':0,'physical_sessions':0,'summary_rows':0,'raw_files':len(members)}
    for category,checksum,round_key,ns_key,median_key,mean_key in (
        ('families',family_checksum,'epoch','epoch_ns','median_ms','mean_ms'),
        ('algorithms',algorithm_checksum,'round','epoch_sum_ns','epoch_median_ms','epoch_mean_ms')):
        folder=root/category;source=build/'scale'/category
        report=json.loads((folder/'summary.json').read_text());machine=report['machine']
        exact=json.loads((source/'build.json').read_text())
        assert machine['physical'] and machine['build']==exact
        assert machine['capacity']>=1 and machine['capacity']<=len(machine['affinity'])
        for name,entry in exact.items():
            for filename,key in [('bench','sha256'),('source.doc','source_sha256'),('generated.c','generated_sha256'),('generated.wgsl','shader_sha256')]:
                assert digest(source/name/filename)==entry[key],(name,filename)
            path='scale/'+category+'/'+name+'/bench'
            assert manifest['files'][path]['sha256']==entry['sha256']
        with (folder/'samples.csv').open(newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==report['rows']
        seen=set();groups=defaultdict(list);processes=set()
        for r in rows:
            work,n,ordinal=r['work'],int(r['lanes']),int(r[round_key])
            assert int(r['checksum'])==checksum(work,n,ordinal),(category,r)
            key=(work,n,r['mode'],r['requested'],int(r['group_cap']))
            assert key[-1]==0 # production execution, not a diagnostic cap
            row_id=(r['sample'],*key,ordinal);assert row_id not in seen;seen.add(row_id)
            groups[key].append(r)
            if category=='families':
                tag=f'{int(r["sample"]):02d}-{work}-{r["variant"]}-{n}-{r["mode"]}-{r["requested"]}-{r["group_cap"]}'
                line=f'epoch={ordinal} wall_ns={r["epoch_ns"]} evals=1 checksum={r["checksum"]}'
                if r['mode']=='cpu':assert 1<=int(r['workers'])<=machine['capacity']
                else:assert int(r['workers'])==0
            else:
                tag=f'{int(r["sample"]):02d}-{work}-{n}-{r["mode"]}-{r["requested"]}-{r["group_cap"]}'
                line=f'round={ordinal} epoch_sum_ns={r["epoch_sum_ns"]} algorithm_ns={r["algorithm_ns"]} checksum={r["checksum"]}'
                assert 1<=int(r['max_workers'])<=machine['capacity']
            assert line.encode() in (folder/'raw'/(tag+'.stdout')).read_bytes()
            processes.add((tag,r['mode']))
        assert len(processes)==report['processes']==len(list((folder/'raw').glob('*.stderr')))
        dispatches=physical_sessions=0
        for tag,mode in processes:
            log=(folder/'raw'/(tag+'.stderr')).read_bytes()
            stdout=(folder/'raw'/(tag+'.stdout')).read_bytes()
            assert b'live=0' in stdout
            traces=[tuple(map(int,x)) for x in re.findall(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',log)]
            dispatches+=len(traces)
            if mode=='cpu':assert not traces and b'DOC11_GPU_ADAPTER:' not in log
            else:
                physical_sessions+=1
                assert b'physical=1 ' in log and b'event=closed' in log
                limit=int(re.search(rb'DOC9_LIMITS: wg_invocations=\d+ wg_x=\d+ groups=(\d+)',log)[1])
                assert all(groups==min((lanes+63)//64,limit) for lanes,groups in traces)
            for w in re.findall(rb'DOC11_CPU_FAMILY: lanes=\d+ workers=(\d+)',log):
                assert 1<=int(w)<=machine['capacity']
        assert dispatches==report['dispatches']
        if 'physical_sessions' in report:assert physical_sessions==report['physical_sessions']
        assert len(report['summary'])==len(groups)
        for r in report['summary']:
            key=(r['work'],r['lanes'],r['mode'],r['requested'],r['group_cap'])
            warm=[int(x[ns_key])/1e6 for x in groups[key] if int(x[round_key])>0]
            assert math.isclose(statistics.median(warm),r[median_key]) and math.isclose(statistics.fmean(warm),r[mean_key])
        total['epochs_and_rounds']+=len(rows);total['processes']+=len(processes)
        total['dispatches']+=dispatches;total['physical_sessions']+=physical_sessions;total['summary_rows']+=len(groups)
    return dict(sha=sha,run_id=str(run_id),**total)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--physical',type=Path,required=True);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--source-sha',required=True);p.add_argument('--run-id',required=True)
    args=p.parse_args()
    report=verify(args.physical,args.build,args.source_sha,args.run_id)
    print('DOC9_AUTONOMOUS_EVIDENCE_PASS:',json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
