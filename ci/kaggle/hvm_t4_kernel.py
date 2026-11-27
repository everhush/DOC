
# Bundle verifier is prepended by the private dispatcher.
import os,runpy,subprocess,sys,statistics
SPEC=__DOC9_HVM_RUN_SPEC__
def main():
    output=Path('/tmp/doc9-hvm-evidence');output.mkdir()
    base=Path('/tmp/doc9-hvm-build')
    matches=[p for p in Path('/kaggle/input').rglob('doc-gpu-bundle.bin') if p.is_file() and digest(p)==SPEC['bundle_sha256']]
    assert len(matches)==1
    unpack(matches[0],base,SPEC['bundle_sha256'],SPEC['sha'],SPEC['run_id'])
    for name in SPEC['executables']:(base/name).chmod(0o700)
    sys.path.insert(0,str(base))
    from compare_cpu import oracle,result,run,cap
    report=dict(sha=SPEC['sha'],run_id=SPEC['run_id'],bundle_sha256=SPEC['bundle_sha256'],result='fail')
    failures=[];rows=[]
    try:
        host=runpy.run_path(str(base/'host.py'),init_globals={'__DOC_KAGGLE_RUN_SPEC__':SPEC},run_name='doc11_host_provision')
        host['experiment_provision_host_graphics']()
        xdg=output/'xdg';xdg.mkdir(mode=0o700)
        env={**os.environ,'XDG_RUNTIME_DIR':str(xdg),'LD_LIBRARY_PATH':str(base/'wgpu/lib')+':'+os.environ.get('LD_LIBRARY_PATH',''),'DOC_REQUIRE_PHYSICAL_GPU':'1','DOC_GPU_REQUIRE_HARDWARE':'1','CUDA_VISIBLE_DEVICES':'0','DOC_REGION_METRICS':'1'}
        for k in ('DOC_GPU_ALLOW_SOFTWARE','DOC_WORKERS','DOC_DIAG_GROUP_CAP','DOC_GPU_TEST_FAIL_DISPATCH'):env.pop(k,None)
        mask=cap();affinity=['taskset','-c',','.join(map(str,mask))]
        for label,cmd in [('nvidia',['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv']),('nvcc',['cat',str(base/'hvm/toolkit.txt')])]:
            rc,stdout,stderr,ns=run(cmd,output/label,env=env)
            assert rc==0,(label,stderr)
            if label=='nvidia':assert b'Tesla T4' in stdout
        cases=json.loads((base/'hvm/cases.json').read_text())
        grouped={}
        for c in cases:grouped.setdefault((c['work'],c['n']),[]).append(c)
        for (w,n),group in grouped.items():
            caseout=output/f'{w}-{n}';caseout.mkdir()
            family=w in ('add','poly')
            docbin=base/'scale'/('families/production' if family else 'algorithms')/w/'bench'
            expect=[sum(oracle(w,n,c['epoch'])) for c in group]
            pat=rb'epoch=(\d+) wall_ns=(\d+) evals=(\d+) checksum=(-?\d+)' if family else rb'round=(\d+) epoch_sum_ns=(\d+) algorithm_ns=(\d+) checksum=(-?\d+)'
            for sample in range(3):
                rc,stdout,stderr,wall=run(affinity+[docbin,'gpu',n,len(group)],caseout/f'doc-{sample}',env=env,timeout=240)
                got=[tuple(map(int,v)) for v in re.findall(pat,stdout)]
                ok=(rc==0 and b'live=0' in stdout and b'physical=1 ' in stderr and b'DOC11_GPU_DISPATCH:' in stderr and [x[0] for x in got]==list(range(len(group))) and [x[3] for x in got]==expect)
                rows.append(dict(engine='DOC',work=w,n=n,sample=sample,wall_ns=wall,rounds=len(group),epochs=got,ok=ok,rc=rc))
                if not ok:failures.append([w,n,'DOC',rc])
            for c in group:
                e=c['epoch'];stem=c['stem'];p=base/'hvm'/(stem+'.cu')
                assert digest(p)==c['cuda_sha'] and digest(base/'hvm'/(stem+'.bend'))==c['source_sha']
                exe=base/'hvm'/(stem+'.elf')
                assert digest(exe)==c['binary_sha']
                values=oracle(w,n,e);offset=4096 if family else 0
                for sample in range(3):
                    rc,stdout,stderr,wall=run(affinity+[exe],caseout/f'{stem}-{sample}',env=env,timeout=120)
                    ok=False
                    try:
                        got=result(stdout)
                        ok=(got==[x+offset for x in values]) if c['full'] else (len(got)==2 and got[0]+65536*got[1]==sum(values)+n*offset)
                    except ValueError:pass
                    # CUDA runtime errors can be printed even when exit status is zero.
                    ok=ok and rc==0 and not re.search(rb'(?i)(failed to launch|failed to load book|too many (?:nodes|redexes)|cuda error|illegal memory access|out of memory|\bOOM\b)',stdout+stderr)
                    rows.append(dict(engine='HVM2-T4-patched',work=w,n=n,epoch=e,sample=sample,wall_ns=wall,rc=rc,ok=ok,full_vector=c['full'],expected=sum(values)))
                    if not ok:failures.append([w,n,e,'HVM CUDA execution/oracle',rc]);break
            (output/'samples.json').write_text(json.dumps(rows,indent=2))
            (output/'failures.json').write_text(json.dumps(failures,indent=2))
            print('DOC9_HVM_T4',w,n,len(rows),len(failures),flush=True)
        if failures:raise RuntimeError('unqualified physical cases: '+str(len(failures)))
        report['result']='pass'
    except BaseException as exc:
        (output/'failure.txt').write_text(type(exc).__name__+': '+str(exc)[-12000:])
        raise
    finally:
        report.update(samples=len(rows),failures=failures)
        (output/'report.json').write_text(json.dumps(report,indent=2))
        with tarfile.open('/kaggle/working/doc9-hvm-results.tar.gz','w:gz') as tar:
            for p in sorted(output.iterdir()):
                if p.name!='xdg':tar.add(p,arcname='evidence/'+p.name)
if __name__=='__main__':main()
