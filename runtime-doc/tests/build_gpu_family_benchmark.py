#!/usr/bin/env python3
"""Build identical CPU/auto/GPU typed family executables using the actual DOC compiler and planner."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'compiler'))
from doc_build import emit,gpu_artifacts

def main():
 p=argparse.ArgumentParser()
 for k in ('reactive','planner','wgpu','out'):p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--headers',type=Path,default=HERE.parent/'runtime');a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);wgpu=a.wgpu.resolve()
 manifest={}
 for name,expr in [('add','add(item,bias)'),('poly',None)]:
  if expr is None:
   expr='bias'
   for _ in range(5):expr=f'add(mul({expr},item),bias)'
  src=f'source xs:ints=[1,2,3]\nsource bias:int=0\nderive ys:ints(xs,bias)=map_ints(xs,item,{expr})\n'.encode()
  d=out/name;d.mkdir();(d/'source.doc').write_bytes(src)
  code=emit([a.reactive.resolve()],src,True,stream=True);shader,header=gpu_artifacts([a.planner.resolve()],src,stream=True)
  assert b'[-' not in header # header is validated by the planner interface
  assert b'doc_gpu_family[]={-1,-1,0}' in header,header
  (d/'generated.c').write_bytes(code);(d/'generated.wgsl').write_bytes(shader);(d/'gpu_generated.h').write_bytes(header)
  cmd=['cc','-std=gnu11','-O1','-pthread','-DDOC_ENABLE_GPU','-DDOC_SCALE_COMPLEX='+str(int(name=='poly')),'-I',str(a.headers.resolve()),'-I',str(d),'-I',str(wgpu/'include'),str(HERE/'benchmark_gpu_family_host.c'),'-L',str(wgpu/'lib'),'-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native','-lm','-o',str(d/'bench')]
  subprocess.run(cmd,check=True,timeout=180)
  manifest[name]={f:hashlib.sha256((d/f).read_bytes()).hexdigest() for f in ('source.doc','generated.c','generated.wgsl','gpu_generated.h','bench')}
 (out/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('DOC9_GPU_SCALE_BUILD_PASS:',json.dumps(manifest),flush=True)
if __name__=='__main__':main()
