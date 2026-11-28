#!/usr/bin/env python3
"""Actual native WebGPU dispatch, mixed frontier and epoch failure gates."""
import argparse,os,subprocess,tempfile,sys,shutil,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'compiler'))
from doc_build import build_bundled,emit,gpu_artifacts

# Independent expected output for the five curated physical micrographs.
FAMILY = '''source xs:ints=[1,2,3]
source bias:int=5
source flag:bool=false
derive ys:ints(xs,bias)=map_ints(xs,item,add(item,bias))
derive unrelated:bool(flag,xs)=if(flag,eq(len(xs),0),true)
derive count:int(ys)=len(ys)
'''


def value(x):
    if isinstance(x, bool):
        return str(x).lower()
    if isinstance(x, list):
        return '['+','.join(map(str,x))+']'
    return str(x)


def micro_expected(name):
    epochs=[]
    if name=='scalar':
        for a in (-2147483648,0):
            b=2147483647
            epochs.append([('a',a),('b',b),('lo',a<b),('hi',b<=a),('pick',a if a<b else b)])
    elif name=='arithmetic':
        for a in (2,4):
            b=-3; x=a*b; y=a+b
            epochs.append([('a',a),('b',b),('x',x),('y',y),('z',x<y)])
    elif name in ('wide','mixed'):
        for x,xs in ((2,[1,2]),(3,[4])):
            row=[('x',x)]
            if name=='mixed': row.append(('xs',xs))
            row.extend((f'g{i}',x==i) for i in range(96))
            if name=='mixed': row.extend((f'c{i}',xs+[i]) for i in range(32))
            epochs.append(row)
    elif name=='family':
        for n,b in ((128,5),(0,5),(256,6),(3,7),(128,8)):
            xs=list(range(n))
            epochs.append([('xs',xs),('bias',b),('flag',False),('ys',[x+b for x in xs]),('unrelated',True),('count',n)])
    else:
        raise ValueError('unknown micrograph: '+name)
    return ''.join(f'epoch: {i}\n'+''.join(f'{k}: {value(v)}\n' for k,v in row) for i,row in enumerate(epochs)).encode()

def run(cmd,cwd,physical=False,extra=None):
 env={**os.environ,'DOC_REGION_METRICS':'1','DOC_WORKERS':'4','DOC_GPU_ALLOW_SOFTWARE':'1'}
 env.pop('DOC_GPU_TEST_FAIL_DISPATCH',None)
 if extra:env.update(extra)
 if physical:
  env.pop('DOC_GPU_ALLOW_SOFTWARE',None)
  env['DOC_REQUIRE_PHYSICAL_GPU']='1'
 return subprocess.run([str(x) for x in cmd],cwd=cwd,capture_output=True,timeout=180,env=env)
def check(cmd,cwd,prefix=None,physical=False):
 r=run(cmd,cwd,physical);assert r.returncode==0,(cmd[0],r.stderr[-6000:])
 if prefix is not None:
  assert r.stdout.startswith(prefix) and r.stdout.endswith(b'\n'),r.stdout[:500];return r.stdout[len(prefix):-1]
 return r.stdout

def graph_generation(a,root,comp,plan,headers,wgpu):
 if a.prebuilt:
  exe=a.prebuilt.resolve()/'gpu_graph_generation'
 else:
  variants={'old':b'source amount:int=2\nderive total:int(amount)=add(amount,1)\n', 'new':b'source amount:int=99\nsource extra:int=4\nderive total:int(amount)=mul(amount,2)\nderive combined:int(total,extra)=add(total,extra)\n'}
  flags=['cc','-std=gnu11','-O1','-pthread','-I',headers]
  objects=[]
  for name,source in variants.items():
   part=root/('graph_'+name);part.mkdir()
   shader,header=gpu_artifacts([plan],source,stream=a.stream)
   code=emit([comp],source,True,stream=a.stream)
   (part/'gpu_generated.h').write_bytes(header)
   wrapper=('#define main '+name+'_unused_main\n').encode()+code+('\n#undef main\n#define DOC_VARIANT_SYMBOL '+name+'_variant\n#define DOC_VARIANT_BACKEND 1\n#include "graph_variant_adapter.h"\n').encode()
   (part/'variant.c').write_bytes(wrapper)
   obj=part/'variant.o'
   check([*flags,'-DDOC_ENABLE_GPU','-I',part,'-I',wgpu/'include','-c',part/'variant.c','-o',obj],root)
   objects.append(obj)
   if a.artifacts:
    (a.artifacts/('graph_'+name+'.doc')).write_bytes(source)
    (a.artifacts/('graph_'+name+'.wgsl')).write_bytes(shader)
    (a.artifacts/('graph_'+name+'.c')).write_bytes(wrapper)
  exe=root/'gpu_graph_generation'
  check([*flags,Path(__file__).resolve().parent/'gpu_graph_generation_host.c',*objects,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',exe],root)
  if a.artifacts:shutil.copy2(exe,a.artifacts/'gpu_graph_generation')
 if a.build_only:return
 result=run([exe],root,a.physical)
 if a.artifacts:
  (a.artifacts/'gpu_graph_generation.stdout').write_bytes(result.stdout)
  (a.artifacts/'gpu_graph_generation.stderr').write_bytes(result.stderr)
 assert result.returncode==0 and b'DOC11_GPU_GRAPH_GENERATION_PASS:' in result.stdout,(result.stdout,result.stderr)
 assert result.stderr.count(b'DOC11_GPU_DISPATCH:')>=6 and result.stderr.count(b'DOC11_GPU_POOL_METRICS: event=closed')==4 and b'DOC11_GPU_INJECTED_FAILURE: dispatch=1' in result.stderr,result.stderr
 adapters=[line for line in result.stderr.splitlines() if line.startswith(b'DOC11_GPU_ADAPTER:')]
 assert len(adapters)==4 and (not a.physical or all(b'physical=1 ' in line for line in adapters)),result.stderr
 print(result.stdout.decode().strip(),result.stderr.decode(),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--prebuilt',type=Path);p.add_argument('--build-only',action='store_true');p.add_argument('--artifacts',type=Path);p.add_argument('--reference',type=Path);p.add_argument('--reactive',type=Path);p.add_argument('--gpu-plan',type=Path);p.add_argument('--wgpu-root',required=True,type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');p.add_argument('--physical',action='store_true');p.add_argument('--stream',action='store_true');a=p.parse_args();ref=a.reference.resolve() if a.reference else None;comp=a.reactive.resolve() if a.reactive else None;plan=a.gpu_plan.resolve() if a.gpu_plan else None;headers=a.headers.resolve();wgpu=a.wgpu_root.resolve();checks=0
 if a.artifacts:a.artifacts.mkdir(parents=True,exist_ok=True)
 assert a.prebuilt or (comp and plan)
 assert not a.build_only or (a.artifacts and not a.prebuilt)
 scalar='source a:int=-2147483648\nsource b:int=2147483647\nderive lo:bool(a,b)=lt(a,b)\nderive hi:bool(a,b)=le(b,a)\nderive pick:int(a,b,lo)=if(lo,a,b)\n'
 arithmetic='source a:int=2\nsource b:int=-3\nderive x:int(a,b)=mul(a,b)\nderive y:int(a,b)=add(a,b)\nderive z:bool(x,y)=lt(x,y)\n'
 wide='source x:int=2\n'+''.join(f'derive g{i}:bool(x)=eq(x,{i})\n' for i in range(96))
 mixed='source x:int=2\nsource xs:ints=[1,2]\n'+''.join(f'derive g{i}:bool(x)=eq(x,{i})\n' for i in range(96))+''.join(f'derive c{i}:ints(xs)=append(xs,{i})\n' for i in range(32))
 family=FAMILY if not a.prebuilt else ''
 family_args=[]
 for n,b in [(128,5),(0,5),(256,6),(3,7),(128,8)]:
  if family_args:family_args.append('--next')
  family_args.extend(['xs=['+','.join(map(str,range(n)))+']','bias='+str(b)])
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);src=root/'test.doc';c=root/'generated.c';exe=root/'app';gh=root/'gpu_generated.h'
  if not a.prebuilt:
   metric_exe=root/'pool_metrics'
   check(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I',headers,Path(__file__).resolve().parent/'gpu_pool_metrics_test.c','-o',metric_exe],root)
   print(check([metric_exe],root).decode().strip(),flush=True)
  for name,program,args,mode in [('scalar',scalar,['--next','a=0'],'gpu'),('arithmetic',arithmetic,['--next','a=4'],'gpu'),('wide',wide,['--next','x=3'],'gpu'),('mixed',mixed,['--next','x=3','xs=[4]'],'auto'),('family',family,family_args,'auto')]:
   src.write_text(program);snapshot=program.encode()
   if a.prebuilt:
    exe=a.prebuilt.resolve()/name;expected=(a.prebuilt.resolve()/(name+'.expected')).read_bytes()
    assert expected==micro_expected(name), 'prebuilt numerical oracle mismatch: '+name
   else:
    code=build_bundled([comp],snapshot,exe,headers,True,c,stream=a.stream,gpu_plan=[plan],wgpu_root=wgpu,emit_wgsl=root/'generated.wgsl',emit_gpu_header=gh)
    assert code==emit([comp],snapshot,True,stream=a.stream)
    assert (root/'generated.wgsl').stat().st_size>0 and gh.stat().st_size>0
    saved=exe.read_bytes()
    try:build_bundled([comp],snapshot,exe,headers,True,stream=a.stream,gpu_plan=[plan],wgpu_root=root/'absent')
    except ValueError:pass
    else:raise AssertionError('accepted missing WebGPU ABI installation')
    assert exe.read_bytes()==saved,'failed GPU build replaced previous executable'
    expected=micro_expected(name)
    if ref:assert check([ref,src,*args],root)==expected, 'optional reference differs from independent oracle: '+name
    if a.artifacts:
     shutil.copy2(exe,a.artifacts/name);(a.artifacts/(name+'.expected')).write_bytes(expected)
     (a.artifacts/(name+'.wgsl')).write_bytes((root/'generated.wgsl').read_bytes())
     (a.artifacts/(name+'.c')).write_bytes(c.read_bytes())
   if a.build_only:
    if name=='mixed':
     harness=root/'device_loss.c';harness.write_text("#define main generated_main\n#include \"generated.c\"\n#undef main\n#include <assert.h>\nint main(void){\n    Epoch e; size_t target; epoch_init(&e,states,sizeof(states)/sizeof(states[0]));\n    gpu_mode=2; assert(gpu_open(e.n));\n    epoch_begin(&e); assert(batch(&e,0,NULL,&target)); epoch_finish(&e,1);\n    assert(gpu_dispatches>0);\n    V *saved=calloc(e.n,sizeof(V)); unsigned char *dirty=malloc(e.n),*have=malloc(e.n);\n    assert(saved&&dirty&&have);\n    for(size_t i=0;i<e.n;i++)if(states[i].name)saved[i]=*states[i].slot;\n    memcpy(dirty,e.dirty,e.n);memcpy(have,e.have,e.n);\n    gpu_destroy_verified();\n    assert(!gpu_healthy());\n    char *updates[]={\"x=3\",\"xs=[4]\"};\n    epoch_begin(&e);assert(!batch(&e,2,updates,&target));epoch_finish(&e,0);\n    assert(!memcmp(dirty,e.dirty,e.n)&&!memcmp(have,e.have,e.n));\n    for(size_t i=0;i<e.n;i++)if(states[i].name)assert(equal(saved[i],*states[i].slot));\n    free(saved);free(dirty);free(have);\n    /* Only an explicit host decision may recover on CPU. */\n    gpu_close();gpu_mode=0;\n    epoch_begin(&e);assert(batch(&e,2,updates,&target));epoch_finish(&e,1);\n    size_t x=find_state(&e,\"x\",1),g3=find_state(&e,\"g3\",2),c0=find_state(&e,\"c0\",2);\n    assert(x<e.n&&g3<e.n&&c0<e.n);\n    assert(num(*states[x].slot)==3&&truth(*states[g3].slot));\n    V v=*states[c0].slot;assert(v.kind==L&&v.n==2&&((const int64_t*)v.p)[0]==4&&((const int64_t*)v.p)[1]==0);\n    epoch_free(&e);assert(live_bytes==0);\n    puts(\"DOC11_GPU_DEVICE_LOSS_PASS: actual device destroyed; rollback and explicit CPU recovery; live=0\");\n    return 0;\n}\n")
     loss=root/'device_loss';check(['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-I',root,'-I',headers,'-I',wgpu/'include',harness,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',loss],root)
     if a.artifacts:shutil.copy2(loss,a.artifacts/'device_loss')
     authority=root/'gpu_epoch_authority'
     authority_source=Path(__file__).resolve().parent/'gpu_epoch_authority_host.c'
     check(['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-I',root,'-I',headers,'-I',wgpu/'include',authority_source,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',authority],root)
     if a.artifacts:shutil.copy2(authority,a.artifacts/'gpu_epoch_authority')
    continue
   actual=run([exe,'--backend='+mode,*args],root,a.physical)
   if a.artifacts:
    (a.artifacts/(name+'.actual')).write_bytes(actual.stdout)
    (a.artifacts/(name+'.stderr')).write_bytes(actual.stderr)
   assert actual.returncode==0 and actual.stdout==expected,(name,actual.stderr,actual.stdout[:300],expected[:300]);assert b'DOC11_GPU_DISPATCH:' in actual.stderr and b'DOC11_REGIONS: live=0 ' in actual.stderr,actual.stderr
   if a.physical:assert b'physical=1' in actual.stderr
   if name=='wide':assert b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2' in actual.stderr,actual.stderr
   if name=='mixed':
    assert b'DOC11_GPU_BUFFER_POOL: action=created' in actual.stderr and b'DOC11_GPU_BUFFER_POOL: action=reused' in actual.stderr,actual.stderr
    injected=run([exe,'--backend=auto',*args],root,a.physical,{'DOC_GPU_TEST_FAIL_DISPATCH':'2'});assert injected.returncode and b'epoch: 0' in injected.stdout and b'epoch: 1' not in injected.stdout and b'DOC11_GPU_INJECTED_FAILURE: dispatch=2' in injected.stderr and b'DOC11_REGIONS: live=0 ' in injected.stderr,injected
    # Destroy the actual adapter device after a successful mixed frontier.
    # Verify the previously published state and masks in the same process.
    if a.prebuilt:
     loss=a.prebuilt.resolve()/'device_loss'
    else:
     harness=root/'device_loss.c';harness.write_text("#define main generated_main\n#include \"generated.c\"\n#undef main\n#include <assert.h>\nint main(void){\n    Epoch e; size_t target; epoch_init(&e,states,sizeof(states)/sizeof(states[0]));\n    gpu_mode=2; assert(gpu_open(e.n));\n    epoch_begin(&e); assert(batch(&e,0,NULL,&target)); epoch_finish(&e,1);\n    assert(gpu_dispatches>0);\n    V *saved=calloc(e.n,sizeof(V)); unsigned char *dirty=malloc(e.n),*have=malloc(e.n);\n    assert(saved&&dirty&&have);\n    for(size_t i=0;i<e.n;i++)if(states[i].name)saved[i]=*states[i].slot;\n    memcpy(dirty,e.dirty,e.n);memcpy(have,e.have,e.n);\n    gpu_destroy_verified();\n    assert(!gpu_healthy());\n    char *updates[]={\"x=3\",\"xs=[4]\"};\n    epoch_begin(&e);assert(!batch(&e,2,updates,&target));epoch_finish(&e,0);\n    assert(!memcmp(dirty,e.dirty,e.n)&&!memcmp(have,e.have,e.n));\n    for(size_t i=0;i<e.n;i++)if(states[i].name)assert(equal(saved[i],*states[i].slot));\n    free(saved);free(dirty);free(have);\n    /* Only an explicit host decision may recover on CPU. */\n    gpu_close();gpu_mode=0;\n    epoch_begin(&e);assert(batch(&e,2,updates,&target));epoch_finish(&e,1);\n    size_t x=find_state(&e,\"x\",1),g3=find_state(&e,\"g3\",2),c0=find_state(&e,\"c0\",2);\n    assert(x<e.n&&g3<e.n&&c0<e.n);\n    assert(num(*states[x].slot)==3&&truth(*states[g3].slot));\n    V v=*states[c0].slot;assert(v.kind==L&&v.n==2&&((const int64_t*)v.p)[0]==4&&((const int64_t*)v.p)[1]==0);\n    epoch_free(&e);assert(live_bytes==0);\n    puts(\"DOC11_GPU_DEVICE_LOSS_PASS: actual device destroyed; rollback and explicit CPU recovery; live=0\");\n    return 0;\n}\n")
     loss=root/'device_loss';check(['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-I',root,'-I',headers,'-I',wgpu/'include',harness,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',loss],root)
     if a.artifacts:shutil.copy2(loss,a.artifacts/'device_loss')
    lost=run([loss],root,a.physical)
    if a.artifacts:
     (a.artifacts/'device_loss.stdout').write_bytes(lost.stdout)
     (a.artifacts/'device_loss.stderr').write_bytes(lost.stderr)
    assert lost.returncode==0 and b'DOC11_GPU_DEVICE_LOSS_PASS:' in lost.stdout,(lost.stdout,lost.stderr)
    assert b'DOC11_WGPU_DESTROY_CONFIRMED:' in lost.stderr and b'DOC11_WGPU_QUEUE_RETIRED:' in lost.stderr and (b'DOC11_GPU_LOST_CALLBACK:' in lost.stderr or b'DOC11_WGPU_LOSS_PROBE: status=success type=validation\nValidation Error\n\nCaused by:\n  In wgpuDeviceCreateBuffer\n    Parent device is lost\n' in lost.stderr), lost.stderr
    if a.physical:assert b'physical=1' in lost.stderr,lost.stderr
    print(lost.stdout.decode().strip(),lost.stderr.decode(),flush=True)
    if a.prebuilt:
     authority=a.prebuilt.resolve()/'gpu_epoch_authority'
    else:
     authority=root/'gpu_epoch_authority'
     authority_source=Path(__file__).resolve().parent/'gpu_epoch_authority_host.c'
     check(['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-I',root,'-I',headers,'-I',wgpu/'include',authority_source,'-L',wgpu/'lib','-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-o',authority],root)
     if a.artifacts:shutil.copy2(authority,a.artifacts/'gpu_epoch_authority')
    retired=run([authority],root,a.physical)
    if a.artifacts:
     (a.artifacts/'gpu_epoch_authority.stdout').write_bytes(retired.stdout)
     (a.artifacts/'gpu_epoch_authority.stderr').write_bytes(retired.stderr)
    assert retired.returncode==0 and b'DOC11_GPU_EPOCH_AUTHORITY_PASS:' in retired.stdout and b'DOC11_GPU_RETIRED: outcome=device-lost' in retired.stderr and b'DOC11_GPU_RETIRED: outcome=queue-complete' in retired.stderr,(retired.stdout,retired.stderr)
    assert b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2' in retired.stderr and b'DOC11_GPU_BUFFER_POOL: action=reused' in retired.stderr and b'DOC11_GPU_BUFFER_POOL: action=grown' in retired.stderr and b'DOC11_GPU_POOL_METRICS: event=closed' in retired.stderr,retired.stderr
    assert b'DOC11_WGPU_QUEUE_RETIRED: destroy=0' in retired.stderr and b'DOC11_WGPU_QUEUE_RETIRED: destroy=1' in retired.stderr and (b'DOC11_GPU_LOST_CALLBACK:' in retired.stderr or b'DOC11_WGPU_LOSS_PROBE: status=success type=validation\nValidation Error\n\nCaused by:\n  In wgpuDeviceCreateBuffer\n    Parent device is lost\n' in retired.stderr) and b'DOC11_WGPU_DESTROY_CONFIRMED:' in retired.stderr,retired.stderr
    if a.physical:assert b'physical=1' in retired.stderr
    print(retired.stdout.decode().strip(),retired.stderr.decode(),flush=True)
    assert b'DOC11_GPU_FRONTIER: cpu=32 gpu=96' in actual.stderr,actual.stderr;bad=run([exe,'--backend=gpu'],root,a.physical);assert bad.returncode and not bad.stdout and b'DOC_GPU_UNSUPPORTED' in bad.stderr,bad
   if name=='family':
    assert re.findall(rb'DOC11_GPU_FAMILY: state=3 lanes=(\d+)',actual.stderr)==[b'128',b'256',b'128'],actual.stderr
    assert len(re.findall(rb'DOC11_GPU_FRONTIER: cpu=1 gpu=1 concurrent=1',actual.stderr))==3,actual.stderr
    assert b'DOC11_GPU_BUFFER_POOL: action=grown' in actual.stderr and b'DOC11_GPU_BUFFER_POOL: action=reused' in actual.stderr,actual.stderr
    bad=run([exe,'--backend=auto',*args,'--next','xs=[9223372036854775807]','flag=true'],root,a.physical)
    assert bad.returncode and bad.stdout==expected and b'DOC11_REGIONS: live=0 ' in bad.stderr,bad
    injected=run([exe,'--backend=auto',*args],root,a.physical,{'DOC_GPU_TEST_FAIL_DISPATCH':'2'})
    assert injected.returncode and b'epoch: 1\n' in injected.stdout and b'epoch: 2\n' not in injected.stdout and b'DOC11_GPU_INJECTED_FAILURE: dispatch=2' in injected.stderr and b'DOC11_REGIONS: live=0 ' in injected.stderr,injected
    strict=run([exe,'--backend=gpu','--demand=ys','xs=[1,2,3]','bias=5'],root,a.physical)
    assert strict.returncode==0 and strict.stdout==b'ys: [6,7,8]\n' and b'DOC11_GPU_FAMILY: state=3 lanes=3' in strict.stderr,strict
    empty=run([exe,'--backend=gpu','--demand=ys','xs=[]'],root,a.physical)
    assert empty.returncode==0 and empty.stdout==b'ys: []\n' and b'DOC11_GPU_DISPATCH:' not in empty.stderr,empty
    rejected=run([exe,'--backend=gpu','--demand=ys','xs=[9223372036854775807]'],root,a.physical)
    assert rejected.returncode and not rejected.stdout and b'DOC_GPU_UNSUPPORTED' in rejected.stderr,rejected
    if a.artifacts:
     for label,record in [('family-overflow',bad),('family-injected',injected),('family-strict',strict),('family-empty',empty),('family-rejected',rejected)]:
      (a.artifacts/(label+'.stdout')).write_bytes(record.stdout);(a.artifacts/(label+'.stderr')).write_bytes(record.stderr)
    print('DOC11_GPU_FAMILY_PASS: 512 actual lanes, 3 mixed frontiers, resizing, zero extent, strict admission, checked rollback',flush=True)
   if name=='arithmetic':
    bad=run([exe,'--backend=gpu','--next','a=40000'],root,a.physical);assert bad.returncode and b'epoch: 1' not in bad.stdout and b'epoch: 0' in bad.stdout and b'DOC_GPU_UNSUPPORTED' in bad.stderr,bad
   print(name,actual.stderr.decode(),flush=True);checks+=1
  graph_generation(a,root,comp,plan,headers,wgpu)
 if a.build_only:
  print('DOC9_GPU_BUILD_ONLY_PASS: exact compiled micrographs and adverse harnesses; no device opened',flush=True);return
 print(f'DOC11_WEBGPU_PASS: {checks} native actual-device comparisons; generated typed WGSL, signed extrema, nested dependency barriers, strict rejection, mixed CPU/GPU; physical_required={a.physical}')
if __name__=='__main__':main()
