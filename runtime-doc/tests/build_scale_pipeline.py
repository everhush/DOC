#!/usr/bin/env python3
"""Isolated variants: exact decimal input, compact family dispatch, bounded large lists."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from build_scale_geometry import replace,digest
H=Path(__file__).resolve().parent
VARIANTS=[
 ('control64',64,False,False,False,False),('fast64',64,True,False,False,False),
 ('compact64',64,False,True,False,False),('combined64',64,True,True,False,False),
 ('resource64',64,True,True,True,False),('resource128',128,True,True,True,False),
 ('resource256',256,True,True,True,False),('resource_stride64',64,True,True,True,True)]
FAST_PARSE='''static int64_t parse_i(const char **s){
    const char *p=skip(*s);int negative=*p=='-';if(*p=='-'||*p=='+')p++;
    if(*p<'0'||*p>'9')fail("integer literal");
    uint64_t limit=negative?UINT64_C(9223372036854775808):UINT64_C(9223372036854775807),v=0;
    do{unsigned d=(unsigned)(*p++-'0');if(v>limit/10||(v==limit/10&&d>limit%10))fail("integer literal");v=v*10+d;}while(*p>='0'&&*p<='9');
    *s=skip(p);if(!negative)return (int64_t)v;
    return v==UINT64_C(9223372036854775808)?INT64_MIN:-(int64_t)v;
}'''
OLD_PARSE='static int64_t parse_i(const char **s){const char *p=skip(*s);if(!isdigit((unsigned char)*p)&&*p!=\'-\'&&*p!=\'+\')fail("integer literal");errno=0;char *e;long long x=strtoll(p,&e,10);if(errno||p==e)fail("integer literal");*s=skip(e);return x;}'
def values(v,fast,resource):
 v=replace(v,'#define DOC_FAMILY_LIMIT 4096u','#define DOC_FAMILY_LIMIT DOC_LIST_LIMIT')
 anchor='#define REGION_LIMIT (64u*1024u*1024u)'
 if resource:
  v=replace(v,anchor,anchor+'\n#ifdef DOC_COMPILER_WORKSPACE\n#define DOC_LIST_LIMIT LIMIT\n#else\n#define DOC_LIST_LIMIT ((REGION_LIMIT-sizeof(Block))/sizeof(int64_t))\n#endif')
 else:v=replace(v,anchor,anchor+'\n#define DOC_LIST_LIMIT DOC_INPUT_LIMIT')
 v=replace(v,'static size_t bytes(V a){return a.kind==L?a.n*sizeof(int64_t):a.kind==T||a.kind==N?a.n:0;}','static size_t list_count(size_t n){if(n>DOC_LIST_LIMIT)fail("list capacity");return n;}\nstatic size_t bytes(V a){return a.kind==L?list_count(a.n)*sizeof(int64_t):a.kind==T||a.kind==N?a.n:0;}')
 v=replace(v,'vv(L,count(n),p)','vv(L,list_count(n),p)')
 v=replace(v,'size_t n=count(a.n+1);int64_t *p=','size_t n=list_count(a.n+1);int64_t *p=')
 if fast:
  v=replace(v,OLD_PARSE,FAST_PARSE)
  # Exact bounded allocation before parsing a well-formed list; malformed inputs
  # still pass through the original strict parser and failure rollback.
  old='int64_t *p=alloc_in(active,DOC_INPUT_LIMIT*sizeof(*p));size_t z=0;s=skip(s);if(*s!=\']\'){for(;;){if(z==DOC_INPUT_LIMIT)fail("list capacity");'
  new='size_t capacity=0;s=skip(s);if(*s!=\']\'){capacity=1;for(const char *q=s;*q&&*q!=\']\';q++)if(*q==\',\'){if(capacity==DOC_LIST_LIMIT)fail("list capacity");capacity++;}}int64_t *p=alloc_in(active,capacity*sizeof(*p));size_t z=0;if(*s!=\']\'){for(;;){if(z==capacity)fail("list capacity");'
  v=replace(v,old,new)
 return v
def gpu(g,wg,compact,stride):
 if wg!=64 or stride:
  g=replace(g,'gpu_limits.maxComputeInvocationsPerWorkgroup<64||gpu_limits.maxComputeWorkgroupSizeX<64',f'gpu_limits.maxComputeInvocationsPerWorkgroup<{wg}||gpu_limits.maxComputeWorkgroupSizeX<{wg}')
  g=replace(g,'(v.n+63)/64>gpu_limits.maxComputeWorkgroupsPerDimension','pipeline_groups(v.n)>gpu_limits.maxComputeWorkgroupsPerDimension')
  assert g.count('(count+63)/64')==3;g=g.replace('(count+63)/64','pipeline_groups(count)')
  stride_code='if(groups>gpu_limits.maxComputeWorkgroupsPerDimension)groups=gpu_limits.maxComputeWorkgroupsPerDimension;const char *p=getenv("DOC_DIAG_GROUP_CAP");if(p){char *end;unsigned long z=strtoul(p,&end,10);if(*p&&!*end&&z&&z<groups)groups=z;}' if stride else ''
  g=replace(g,'static WGPULimits gpu_limits;',f'''static WGPULimits gpu_limits;
static size_t pipeline_groups(size_t count){{size_t groups=(count+{wg-1})/{wg};{stride_code}return groups;}}''')
 if compact:
  g=replace(g,'selection_bytes=(uint64_t)count*4','selection_bytes=(uint64_t)(family_mode?1:count)*4')
  g=replace(g,'queue=calloc(count,sizeof(*queue));','queue=calloc(family_mode?1:count,sizeof(*queue));')
  g=replace(g,'for(size_t i=0;i<count;i++){queue[i]=(uint32_t)family;in[e->n+i]=(uint32_t)(int32_t)xs[i];}','queue[0]=(uint32_t)family;for(size_t i=0;i<count;i++)in[e->n+i]=(uint32_t)(int32_t)xs[i];')
 # Time the same phases, with no change to publication or retirement.
 g=replace(g,'uint64_t begin=gpu_wall_ns();const char *phase="preflight";','uint64_t begin=gpu_wall_ns(),pre=0,stage=0,reserve=0,encode=0,mapped_at=0;const char *phase="preflight";')
 for old,new in [('phase="host staging";','pre=gpu_wall_ns();phase="host staging";'),('phase="buffer reserve";','stage=gpu_wall_ns();phase="buffer reserve";'),('phase="bind/encode";','reserve=gpu_wall_ns();phase="bind/encode";'),('phase="submit/map";','encode=gpu_wall_ns();phase="submit/map";'),('phase="readback";','mapped_at=gpu_wall_ns();phase="readback";')]:g=replace(g,old,new)
 marker='gpu_dispatches++;fprintf(stderr,'
 g=replace(g,marker,'uint64_t finished=gpu_wall_ns();fprintf(stderr,"DOC9_DISPATCH_STAGE: preflight_ns=%llu staging_ns=%llu reserve_ns=%llu encode_ns=%llu submit_ns=%llu readback_ns=%llu\\n",(unsigned long long)(pre-begin),(unsigned long long)(stage-pre),(unsigned long long)(reserve-stage),(unsigned long long)(encode-reserve),(unsigned long long)(mapped_at-encode),(unsigned long long)(finished-mapped_at));'+marker)
 g=replace(g,'WGPUShaderSourceWGSL source=', 'fprintf(stderr,"DOC9_LIMITS: wg_invocations=%u wg_x=%u groups=%u storage=%llu buffer=%llu\\n",gpu_limits.maxComputeInvocationsPerWorkgroup,gpu_limits.maxComputeWorkgroupSizeX,gpu_limits.maxComputeWorkgroupsPerDimension,(unsigned long long)gpu_limits.maxStorageBufferBindingSize,(unsigned long long)gpu_limits.maxBufferSize);WGPUShaderSourceWGSL source=')
 return g
def shader_geometry(s,wg,compact,stride):
 s=replace(s,'@workgroup_size(64)',f'@workgroup_size({wg})')
 if compact:
  s=replace(s,'idx>=arrayLength(&queue)||arrayLength(&inputs)==0u','arrayLength(&queue)==0u||(arrayLength(&queue)!=1u&&idx>=arrayLength(&queue))||arrayLength(&inputs)==0u')
  s=replace(s,'let state=queue[idx];','let state=queue[select(idx,0u,arrayLength(&queue)==1u)];')
 if stride:
  assert compact
  s=replace(s,'fn main(@builtin(global_invocation_id) gid:vec3<u32>){let idx=gid.x;if(idx>=arrayLength(&out)/2u||arrayLength(&queue)==0u||(arrayLength(&queue)!=1u&&idx>=arrayLength(&queue))||arrayLength(&inputs)==0u){return;}',f'fn main(@builtin(global_invocation_id) gid:vec3<u32>, @builtin(num_workgroups) groups:vec3<u32>){{if(arrayLength(&queue)==0u||arrayLength(&inputs)==0u){{return;}}for(var idx=gid.x;idx<arrayLength(&out)/2u&&(arrayLength(&queue)==1u||idx<arrayLength(&queue));idx=idx+groups.x*{wg}u){{')
  s+='}'
 return s
def main():
 p=argparse.ArgumentParser()
 for k in ('accepted','wgpu','out'):p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();out=a.out.resolve();out.mkdir();src=a.accepted.resolve();wgpu=a.wgpu.resolve();manifest={}
 baseline=json.loads((src/'build.json').read_text())
 for work in ('add','poly'):
  for f,h in baseline[work].items():assert digest(src/work/f)==h
 for variant,wg,fast,compact,resource,stride in VARIANTS:
  d=out/variant;d.mkdir();h=d/'headers';shutil.copytree(H.parent/'runtime',h)
  f=h/'value_primitives.h';f.write_text(values(f.read_text(),fast,resource))
  f=h/'gpu_values.h';f.write_text(gpu(f.read_text(),wg,compact,stride))
  f=h/'reactive_values.h';s=f.read_text()
  s=replace(s,'static int batch_private(Epoch *e,int argc,char **argv,size_t *target){','static int batch_private(Epoch *e,int argc,char **argv,size_t *target){uint64_t ingest_start=gpu_wall_ns();')
  s=replace(s,'memset(e->need,*target==e->n?1:0,e->n);','uint64_t ingest_end=gpu_wall_ns();memset(e->need,*target==e->n?1:0,e->n);')
  anchor='return !epoch_cancelled(e)&&(!gpu_mode||gpu_healthy());}'
  s=replace(s,anchor,'fprintf(stderr,"DOC9_EPOCH_STAGE: ingest_ns=%llu stabilize_ns=%llu\\n",(unsigned long long)(ingest_end-ingest_start),(unsigned long long)(gpu_wall_ns()-ingest_end));'+anchor);f.write_text(s)
  for work in ('add','poly'):
   dest=d/work;dest.mkdir();code=(src/work/'generated.c').read_text();shader=(src/work/'generated.wgsl').read_text();header=(src/work/'gpu_generated.h').read_text()
   new=shader_geometry(shader,wg,compact,stride)
   (dest/'gpu_generated.h').write_text(header[:header.index('static const char doc_wgsl[]=')]+'static const char doc_wgsl[]='+json.dumps(new)+';\n')
   (dest/'generated.c').write_text(code);(dest/'generated.wgsl').write_text(new)
   host=replace((H/'benchmark_gpu_family_host.c').read_text(),'n<=4096&&epochs>1','n<=DOC_FAMILY_LIMIT&&epochs>1')
   host=replace(host,'(int64_t)(i+epoch)','(int64_t)((i+epoch)%32760)')
   (dest/'host.c').write_text(host)
   cmd=['cc','-std=gnu11','-O2','-pthread','-DDOC_ENABLE_GPU','-DDOC_SCALE_COMPLEX='+str(int(work=='poly')),'-I',h,'-I',dest,'-I',wgpu/'include',dest/'host.c','-L',wgpu/'lib','-lwgpu_native','-lm','-o',dest/'bench']
   subprocess.run([str(x) for x in cmd],check=True,timeout=120)
   manifest[variant+'/'+work]={'wg':wg,'fast':fast,'compact':compact,'resource':resource,'stride':stride,'sha256':digest(dest/'bench'),'shader_sha256':digest(dest/'generated.wgsl'),'header_sha256':digest(h/'gpu_values.h'),'value_sha256':digest(h/'value_primitives.h')}
 (out/'build.json').write_text(json.dumps(manifest,indent=2)+'\n');print('DOC9_PIPELINE_BUILD_PASS',len(manifest),flush=True)
if __name__=='__main__':main()
