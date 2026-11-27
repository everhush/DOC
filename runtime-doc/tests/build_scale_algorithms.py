#!/usr/bin/env python3
"""Build diagnostic range planner with accepted independent compiler. No GPU execution here."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'compiler'))
from doc_build import bundle,emit,gpu_artifacts,invoke
from build_scale_pipeline import values,gpu,shader_geometry,replace,digest
def checked(args,timeout=900):
 q=subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout)
 if q.returncode:raise RuntimeError(str(args)+'\n'+q.stderr.decode(errors='replace')[-8000:])
 return q.stdout
def main():
 p=argparse.ArgumentParser()
 for k in ('stage2','scanner','reactive','planner','wgpu','out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir();src=out/'compiler-src';shutil.copytree(H.parent/'compiler',src)
 f=src/'gpu_core.doc';s=f.read_text()+'\n'+(H/'scale_range_core.doc').read_text()
 s=replace(s,'fn g_mul(a:i32,b:i32)->i32{return a*b;}', 'fn g_mul(a:i32,b:i32)->i32{return a*b;} fn g_quot(a:i32,b:i32)->i32{return a/b;} fn g_rem(a:i32,b:i32)->i32{return a%b;}');f.write_text(s)
 f=src/'gpu_plan.doc';s=f.read_text()
 old='derive bounds: ints (gpu_state) = slice(gpu_state,4,sub(len(gpu_state),4))'
 new='''derive legacy_bounds: ints (gpu_state) = slice(gpu_state,4,sub(len(gpu_state),4))
derive extended_state: ints (gpu_seed,syntax,directory,links,gnumbers,gowners,event_count) = recur(gpu_seed,s,eq(get(s,0),event_count),sx_scan(s,syntax,directory,links,gnumbers,gowners))
derive extended_valid: ints (extended_state) = slice(extended_state,4,sub(len(extended_state),4))
derive range_seed: ints (event_count) = append(empty(),sub(event_count,1))
derive range_initial: ints (range_seed,legacy_bounds,decl_count) = recur(range_seed,s,eq(len(s),add(decl_count,1)),append(s,get(legacy_bounds,sub(len(s),1))))
derive range_big: ints (range_initial,syntax,directory,links,gnumbers,extended_valid,gowners) = recur(range_initial,s,lt(get(s,0),0),sx_step(s,syntax,directory,links,gnumbers,extended_valid,gowners,2147483647))
derive range_reset: ints (range_big,event_count) = replace_at(range_big,0,sub(event_count,1))
derive range_mid: ints (range_reset,syntax,directory,links,gnumbers,extended_valid,gowners) = recur(range_reset,s,lt(get(s,0),0),sx_step(s,syntax,directory,links,gnumbers,extended_valid,gowners,32767))
derive bounds: ints (range_mid,decl_count) = slice(range_mid,1,decl_count)'''
 f.write_text(replace(s,old,new))
 data=bundle([a.scanner.resolve()],f,stream=True);(out/'planner.doc').write_bytes(data)
 print('bundled range planner',len(data),'bytes',flush=True)
 c=emit([a.stage2.resolve()],data,stream=True);(out/'planner.c').write_bytes(c)
 planner=out/'planner';checked(['clang-18','-std=gnu11','-O0','-pthread','-fmacro-backtrace-limit=1','-I',H.parent/'runtime',out/'planner.c','-o',planner])
 print('compiled diagnostic planner',digest(planner),flush=True)
 # Legacy scalar/map bounds are unchanged, unsafe divisors remain rejected.
 def bounds(p,source):return json.loads(invoke([p],source.encode(),'bounds',stream=True).decode())
 def program(expr):return 'source xs:ints=[1,2,3]\nsource bias:int=13849\nderive ys:ints(xs,bias)=map_ints(xs,item,'+expr+')\n'
 legacy=['add(item,bias)','mul(item,bias)','if(le(item,bias),item,bias)','add(mul(item,bias),1)']
 for e in legacy:
  x=program(e);assert bounds(planner,x)==bounds(a.planner.resolve(),x),(e,bounds(planner,x))
 for e in ['quot(item,0)','quot(item,bias)','rem(item,-1)','mul(2147483647,2147483647)']:
  assert bounds(planner,program(e))[-1]<0,e
 assert bounds(planner,program('quot(item,32768)'))[-1]==2147483647
 assert bounds(planner,program('rem(item,32768)'))[-1]==2147483647
 print('range admission positive and negative cases passed',flush=True)
 expr='item'
 for _ in range(32):expr=f'rem(add(mul({expr},25173),bias),65521)'
 left='quot(rem(item,1073741824),32768)';right='rem(item,32768)'
 comparator=f'if(le(item,1073741823),if(le({left},{right}),{left},{right}),if(le({left},{right}),{right},{left}))'
 reduction='add(quot(item,32768),rem(item,32768))'
 programs={'stress':expr,'sort':comparator,'reduce':reduction}
 manifest={}
 for name,e in programs.items():
  source=program(e).encode();d=out/name;d.mkdir();(d/'source.doc').write_bytes(source)
  code=emit([a.reactive.resolve()],source,True,stream=True);shader,header=gpu_artifacts([planner],source,stream=True)
  print('actual emitted algorithm',name,'bounds',bounds(planner,source.decode()),flush=True)
  assert b'doc_gpu_family[]={-1,-1,0}' in header,header
  (d/'generated.c').write_bytes(code);(d/'generated.wgsl').write_bytes(shader)
  h=d/'headers';shutil.copytree(H.parent/'runtime',h)
  f=h/'value_primitives.h';f.write_text(values(f.read_text(),True,True))
  f=h/'gpu_values.h';f.write_text(gpu(f.read_text(),64,True,True))
  # Use the same diagnostic geometry wrapper for every actual emitted kernel.
  new=shader_geometry(shader.decode(),64,True,True)
  (d/'gpu_generated.h').write_text(header.decode().split('static const char doc_wgsl[]=')[0]+'static const char doc_wgsl[]='+json.dumps(new)+';\n');(d/'dispatch.wgsl').write_text(new)
  checked(['cc','-std=gnu11','-O2','-pthread','-DDOC_ENABLE_GPU','-DDOC_ALGORITHM='+str(['stress','sort','reduce'].index(name)),'-I',h,'-I',d,'-I',a.wgpu.resolve()/'include',H/'scale_algorithm_host.c','-L',a.wgpu.resolve()/'lib','-lwgpu_native','-lm','-o',d/'bench'])
  manifest[name]={'sha256':digest(d/'bench'),'source_sha256':digest(d/'source.doc'),'generated_sha256':digest(d/'generated.c'),'shader_sha256':digest(d/'dispatch.wgsl'),'bounds':bounds(planner,source.decode()),'wg':64}
 (out/'build.json').write_text(json.dumps(manifest,indent=2)+'\n');print('DOC9_ALGORITHM_BUILD_PASS',flush=True)
if __name__=='__main__':main()
