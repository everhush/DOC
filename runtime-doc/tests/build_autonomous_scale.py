#!/usr/bin/env python3
"""Build ordinary production-emitted families and algorithms; no runtime overrides."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent/'compiler'))
from doc_build import emit,gpu_artifacts,invoke
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for x in ('reactive','planner','wgpu','out'):p.add_argument('--'+x,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir();wgpu=a.wgpu.resolve()
 def program(expr):return f'source xs:ints=[1,2,3]\nsource bias:int=13849\nderive ys:ints(xs,bias)=map_ints(xs,item,{expr})\n'.encode()
 def bounds(expr):
  return json.loads(invoke([a.planner.resolve()],program(expr),'bounds',stream=True))[-1]
 for x in ('quot(item,0)','quot(item,bias)','rem(item,-1)','mul(2147483647,2147483647)'):
  assert bounds(x)<0,x
 assert bounds('quot(item,32768)')==2147483647
 assert bounds('rem(item,32768)')==2147483647
 assert bounds('add(item,bias)')==32767
 expr='bias'
 for _ in range(5):expr=f'add(mul({expr},item),bias)'
 stress='item'
 for _ in range(32):stress=f'rem(add(mul({stress},25173),bias),65521)'
 left='quot(rem(item,1073741824),32768)';right='rem(item,32768)'
 sort=f'if(le(item,1073741823),if(le({left},{right}),{left},{right}),if(le({left},{right}),{right},{left}))'
 for category,programs in [('families',{'production/add':'add(item,bias)','production/poly':expr}),('algorithms',{'stress':stress,'sort':sort,'reduce':'add(quot(item,32768),rem(item,32768))'})]:
  manifest={}
  for name,expr in programs.items():
   d=out/category/name;d.mkdir(parents=True);data=program(expr);(d/'source.doc').write_bytes(data)
   code=emit([a.reactive.resolve()],data,True,stream=True);shader,header=gpu_artifacts([a.planner.resolve()],data,stream=True)
   assert b'doc_gpu_family[]={-1,-1,0}' in header and b'@builtin(num_workgroups)' in shader and b'arrayLength(&queue)==1u' in shader
   (d/'generated.c').write_bytes(code);(d/'generated.wgsl').write_bytes(shader);(d/'gpu_generated.h').write_bytes(header)
   if category=='families':
    host=(H/'benchmark_gpu_family_host.c').read_text().replace('n<=4096&&epochs>1','n<=DOC_FAMILY_LIMIT&&epochs>1').replace('(int64_t)(i+epoch)','(int64_t)((i+epoch)%32760)')
    flag='-DDOC_SCALE_COMPLEX='+str(int(name.endswith('poly')))
   else:
    host=(H/'scale_algorithm_host.c').read_text();flag='-DDOC_ALGORITHM='+str(['stress','sort','reduce'].index(name))
   (d/'host.c').write_text(host)
   subprocess.run(['cc','-std=gnu11','-O2','-pthread','-DDOC_ENABLE_GPU',flag,'-I',str(H.parent/'runtime'),'-I',str(d),'-I',str(wgpu/'include'),str(d/'host.c'),'-L',str(wgpu/'lib'),'-lwgpu_native','-lm','-o',str(d/'bench')],check=True,timeout=180)
   manifest[name]={'sha256':sha(d/'bench'),'source_sha256':sha(d/'source.doc'),'generated_sha256':sha(d/'generated.c'),'shader_sha256':sha(d/'generated.wgsl'),'bounds':bounds(expr),'wg':64}
  (out/category/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('DOC9_AUTONOMOUS_BUILD_PASS: ordinary compiler output; no geometry patch or manual group caps',flush=True)
if __name__=='__main__':main()
