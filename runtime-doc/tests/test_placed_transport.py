#!/usr/bin/env python3
"""Actual DOC-generated placed-role policy, loopback TCP and recovery evidence."""
import argparse,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'compiler'))
from doc_build import emit

def run(args,cwd,evidence,label):
    argv=[str(x) for x in args]
    env={**os.environ,'DOC_WORKERS':'4','DOC_REGION_METRICS':'1',
         'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','TSAN_OPTIONS':'halt_on_error=1'}
    result=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,timeout=120)
    (evidence/(label+'.stdout')).write_bytes(result.stdout)
    (evidence/(label+'.stderr')).write_bytes(result.stderr)
    (evidence/(label+'.json')).write_text(json.dumps(dict(argv=argv,returncode=result.returncode),indent=2)+'\n')
    assert result.returncode==0,(label,result.stderr[-4000:]);return result.stdout

def check(a,root):
    headers=a.headers.resolve();tests=a.tests.resolve();managed=a.managed.resolve();reactive=a.reactive.resolve();reference=a.reference.resolve()
    root.mkdir(parents=True,exist_ok=True)
    policy=(headers/'placed_policy.doc').read_bytes()+b'source marker:int=0\n'
    actual=[l for l in emit([managed],policy,stream=True).splitlines() if l.startswith(b'#define F_placed_')]
    expected=[l for l in (headers/'placed_policy_generated.h').read_bytes().splitlines() if l.startswith(b'#define F_placed_')]
    assert len(actual)==5 and actual==expected,'DOC placed policy drift'
    (root/'policy.doc').write_bytes(policy);(root/'policy-macros.h').write_bytes(b'\n'.join(actual)+b'\n')
    run(['cc','--version'],root,root,'cc-version')
    source=b'source a:int=1\nsource b:int=2\nderive x:int(a,b)=add(a,b)\nderive y:int(a,x)=mul(a,x)\nderive z:bool(x,y)=lt(x,y)\nderive pair:int(x)=add(x,x)\nderive end:int(pair,y)=add(pair,y)\n'
    (root/'graph.doc').write_bytes(source);code=emit([reactive],source,True,stream=True);(root/'generated.c').write_bytes(code)
    schema=hashlib.sha256(source).hexdigest();(root/'provenance.json').write_text(json.dumps(dict(source_sha256=schema,c_sha256=hashlib.sha256(code).hexdigest(),tools={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (managed,reactive,reference)}),indent=2)+'\n')
    common=['cc','-std=gnu11','-O1','-g','-pthread','-fno-pie','-no-pie','-I',headers,'-I',root]
    # The locally stabilized baseline used inside the host harness must also
    # agree with the independently implemented frozen reference evaluator.
    exe=root/'local';run([*common,root/'generated.c','-lm','-o',exe],root,root,'compile-local')
    expected=run([reference,root/'graph.doc','a=7','b=-2'],root,root,'reference')
    output=run([exe,'--backend=cpu','a=7','b=-2'],root,root,'local')
    assert output==expected and b'end: 45\n' in output
    for mode in ('address','thread'):
        san=['-fsanitize=thread'] if mode=='thread' else ['-fsanitize=address,undefined','-fno-sanitize-recover=all']
        if mode=='address':
            exe=root/'transport';run([*common,*san,tests/'placed_transport_host.c','-o',exe],root,root,'compile-transport')
            out=run([exe],root,root,'transport-run');assert b'DOC11_PLACED_TRANSPORT_PASS:' in out;print(out.decode().strip())
        exe=root/('epoch-'+mode)
        run([*common,*san,'-DDOC_SOURCE_SHA256="'+schema+'"',tests/'placed_epoch_host.c','-lm','-o',exe],root,root,'compile-'+mode)
        out=run([exe,root],root,root,'epoch-'+mode+'-run');assert b'DOC11_PLACED_EPOCH_PASS:' in out;print(mode+': '+out.decode().strip())
    print('DOC11_PLACED_ORACLE_PASS: independently evaluated scalar graph and actual generated CPU baseline agree; ASan/UBSan and TSan placed recovery passed')

def main():
    p=argparse.ArgumentParser();p.add_argument('--managed',required=True,type=Path);p.add_argument('--reactive',required=True,type=Path);p.add_argument('--reference',required=True,type=Path);p.add_argument('--headers',type=Path,default=ROOT/'runtime');p.add_argument('--tests',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--evidence',type=Path);a=p.parse_args()
    if a.evidence:check(a,a.evidence.resolve())
    else:
        with tempfile.TemporaryDirectory() as td:check(a,Path(td))
if __name__=='__main__':main()
