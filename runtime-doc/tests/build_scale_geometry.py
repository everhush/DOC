#!/usr/bin/env python3
"""Test-only exact-emission geometry and admission variations. No software GPU."""
import argparse,hashlib,json,re,shutil,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent
VARIANTS=[('base',64,4096,False,50000),('wide64',64,65536,False,50000),('wide32',32,65536,False,50000),('wide128',128,65536,False,50000),('wide256',256,65536,False,50000),('stride64',64,65536,True,50000),('poll64',64,65536,False,1000)]
def replace(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for k in ('accepted','wgpu','out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir();src=a.accepted.resolve();wgpu=a.wgpu.resolve();manifest={}
 baseline=json.loads((src/'build.json').read_text())
 for work in ('add','poly'):
  for f,h in baseline[work].items():assert digest(src/work/f)==h
 for variant,wg,limit,stride,poll in VARIANTS:
  d=out/variant;d.mkdir();headers=d/'headers';shutil.copytree(H.parent/'runtime',headers)
  f=headers/'value_primitives.h';v=f.read_text();v=replace(v,'#define DOC_FAMILY_LIMIT 4096u',f'#define DOC_FAMILY_LIMIT {limit}u');f.write_text(v)
  f=headers/'gpu_values.h';g=f.read_text()
  if variant!='base':
   stride_code='const char *p=getenv("DOC_DIAG_GROUP_CAP");if(p){char *end;unsigned long z=strtoul(p,&end,10);if(*p&&!*end&&z&&z<groups)groups=z;}' if stride else ''
   g=replace(g,'static WGPULimits gpu_limits;',f'''static WGPULimits gpu_limits;
static size_t diag_groups(size_t count){{
    size_t groups=(count+{wg-1})/{wg};
    {stride_code}
    return groups;
}}'''.replace('\\"','"'))
   g=replace(g,'gpu_limits.maxComputeInvocationsPerWorkgroup<64||gpu_limits.maxComputeWorkgroupSizeX<64',f'gpu_limits.maxComputeInvocationsPerWorkgroup<{wg}||gpu_limits.maxComputeWorkgroupSizeX<{wg}')
   g=replace(g,'(v.n+63)/64>gpu_limits.maxComputeWorkgroupsPerDimension','diag_groups(v.n)>gpu_limits.maxComputeWorkgroupsPerDimension')
   assert g.count('(count+63)/64')==3
   g=g.replace('(count+63)/64','diag_groups(count)')
   g=replace(g,'struct timespec interval={0,50000},start,now;',f'struct timespec interval={{0,{poll}}},start,now;')
  # Record actual negotiated limits, not assumptions about a T4.
  g=replace(g,'WGPUShaderSourceWGSL source=', 'fprintf(stderr,"DOC9_LIMITS: wg_invocations=%u wg_x=%u groups=%u storage=%llu buffer=%llu\\n",gpu_limits.maxComputeInvocationsPerWorkgroup,gpu_limits.maxComputeWorkgroupSizeX,gpu_limits.maxComputeWorkgroupsPerDimension,(unsigned long long)gpu_limits.maxStorageBufferBindingSize,(unsigned long long)gpu_limits.maxBufferSize);WGPUShaderSourceWGSL source=')
  f.write_text(g)
  for work in ('add','poly'):
   dest=d/work;dest.mkdir();code=(src/work/'generated.c').read_text();shader=(src/work/'generated.wgsl').read_text();header=(src/work/'gpu_generated.h').read_text()
   assert shader.count('@workgroup_size(64)')==1
   new=shader.replace('@workgroup_size(64)',f'@workgroup_size({wg})')
   if stride:
    old='fn main(@builtin(global_invocation_id) gid:vec3<u32>){let idx=gid.x;if(idx>=arrayLength(&out)/2u||idx>=arrayLength(&queue)||arrayLength(&inputs)==0u){return;}'
    new=replace(new,old,f'fn main(@builtin(global_invocation_id) gid:vec3<u32>, @builtin(num_workgroups) groups:vec3<u32>){{if(arrayLength(&inputs)==0u){{return;}}for(var idx=gid.x;idx<arrayLength(&out)/2u&&idx<arrayLength(&queue);idx=idx+groups.x*{wg}u){{')
    new+='}'
   # Only dispatch geometry changes. The compiler-emitted typed lane expressions and marker stay intact.
   head=header[:header.index('static const char doc_wgsl[]=')]
   (dest/'gpu_generated.h').write_text(head+'static const char doc_wgsl[]='+json.dumps(new)+';\n')
   (dest/'generated.c').write_text(code);(dest/'generated.wgsl').write_text(new)
   host=(H/'benchmark_gpu_family_host.c').read_text()
   host=replace(host,'n<=4096&&epochs>1','n<=DOC_FAMILY_LIMIT&&epochs>1')
   (dest/'host.c').write_text(host)
   cmd=['cc','-std=gnu11','-O2','-pthread','-DDOC_ENABLE_GPU','-DDOC_SCALE_COMPLEX='+str(int(work=='poly')),'-I',headers,'-I',dest,'-I',wgpu/'include',dest/'host.c','-L',wgpu/'lib','-lwgpu_native','-lm','-o',dest/'bench']
   subprocess.run([str(x) for x in cmd],check=True,timeout=120)
   manifest[variant+'/'+work]={'wg':wg,'limit':limit,'stride':stride,'poll_ns':poll,'sha256':digest(dest/'bench'),'shader_sha256':digest(dest/'generated.wgsl'),'header_sha256':digest(headers/'gpu_values.h'),'value_sha256':digest(headers/'value_primitives.h')}
 (out/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('DOC9_GEOMETRY_BUILD_PASS',len(manifest),flush=True)
if __name__=='__main__':main()
