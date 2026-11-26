#!/usr/bin/env python3
"""Build-time OS/toolchain adapter for the DOC-authored native compiler stages.

Only the native scanner decides declaration/import spans; only the native
compiler performs lexical/semantic analysis and emits C. This adapter transfers
bytes, opens confined files and invokes tools. It is not linked into programs.
"""
import argparse
import hashlib
import ast
import json
import os
import re
from pathlib import Path
import stat
import signal
import time
import subprocess
import tempfile

LIMIT = 65536


def bounded_read(fd):
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > LIMIT:
            raise ValueError('DOC input must be a bounded regular file')
        data = stream.read(LIMIT+1)
        if len(data) > LIMIT:
            raise ValueError('DOC input exceeds byte capacity')
        data.decode('utf-8')
        return data


def confined_read(root, raw):
    # Defense at the OS authority boundary, never a language parser.
    if not raw or len(raw)>256 or not raw.isascii():
        raise ValueError('invalid confined path')
    pieces=raw.split(b'/')
    if any(not p or p in (b'.',b'..') or any(not (chr(c).isalnum() or c in b'_.-') for c in p) for p in pieces):
        raise ValueError('invalid confined path component')
    directory=os.dup(root)
    try:
        for name in pieces[:-1]:
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
            os.close(directory);directory=child
        return bounded_read(os.open(pieces[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=directory))
    finally:
        os.close(directory)


def input_arg(data):
    if len(data)>LIMIT: raise ValueError('source byte capacity')
    arg='input=['+','.join(map(str,data))+']'
    if len(arg.encode())>=130000: raise ValueError('bootstrap command argument capacity')
    return arg


def invoke(tool, data, target, *extra, stream=False):
    if len(data)>LIMIT: raise ValueError('source byte capacity')
    args=[str(x) for x in tool]+['--demand='+target]
    if stream:
        proc=subprocess.run(args+['--input-stdin',*extra],input=data,capture_output=True,timeout=240)
    else:
        proc=subprocess.run(args+[input_arg(data),*extra],capture_output=True,timeout=240)
    prefix=(target+': ').encode()
    if proc.returncode or not proc.stdout.startswith(prefix) or not proc.stdout.endswith(b'\n'):
        raise ValueError('DOC stage rejected input: '+proc.stderr.decode('utf-8',errors='replace')[-4000:])
    return proc.stdout[len(prefix):-1]


def plans(scanner, data, module=False, stream=False):
    raw=ast.literal_eval(invoke(scanner,data,'plan','module='+str(module).lower(),stream=stream).decode('ascii'))
    if not isinstance(raw,list) or len(raw)%5 or any(type(x) is not int for x in raw):
        raise ValueError('malformed compiler span plan')
    last=0
    for i in range(0,len(raw),5):
        role,begin,end,a,b=raw[i:i+5]
        if not last<=begin<end<=len(data) or role not in (1,2,3,4,5) or module and role!=3:
            raise ValueError('invalid compiler declaration span')
        if role==4:
            if not begin<a<b<=end:raise ValueError('invalid compiler import span')
        elif (a,b)!=(-1,-1):raise ValueError('unexpected import metadata')
        last=end
        yield role,begin,end,a,b


def bundle(scanner, file, stream=False):
    file=Path(file).absolute()
    # The top-level file is explicitly granted; child module paths are confined.
    root=os.open(file.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        data=bounded_read(os.open(file.name,os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=root));out=bytearray();count=0
        for role,begin,end,a,b in plans(scanner,data,stream=stream):
            if role==4:
                count+=1
                if count>64:raise ValueError('module count capacity')
                body=confined_read(root,data[a:b])
                for _,start,stop,_,_ in plans(scanner,body,True,stream=stream):out.extend(body[start:stop]+b'\n')
            else:out.extend(data[begin:end]+b'\n')
            if len(out)>LIMIT:raise ValueError('bundled source capacity')
        return bytes(out)
    finally:os.close(root)


def emit(compiler, data, reactive=False, stream=False):
    count=int(invoke(compiler,data,'chunk_count',stream=stream))
    if not 1<=count<=128:raise ValueError('invalid compiler chunk count')
    return b''.join(invoke(compiler,data,'code','chunk='+str(i),stream=stream) for i in range(count))


def gpu_artifacts(planner, data, stream=False):
    """Transfer native DOC planner output; never infer or synthesize a kernel."""
    bounds=ast.literal_eval(invoke(planner,data,'bounds',stream=stream).decode('ascii'))
    if not isinstance(bounds,list) or not bounds or any(type(x) is not int or not -1<=x<=2147483648 for x in bounds):
        raise ValueError('invalid compiler GPU bounds')
    families=ast.literal_eval(invoke(planner,data,'families',stream=stream).decode('ascii'))
    if not isinstance(families,list) or len(families)!=len(bounds) or any(type(x) is not int or not -1<=x<len(bounds) or (x>=0 and (x==i or bounds[i]<0)) for i,x in enumerate(families)):
        raise ValueError('invalid compiler GPU family plan')
    shader=invoke(planner,data,'shader',stream=stream)
    if not shader or any(c not in (9,10,13) and not 32<=c<=126 for c in shader):
        raise ValueError('invalid generated WGSL bytes')
    admitted=[i for i,bound in enumerate(bounds) if bound>=0]
    cases=[int(case,16) for case in re.findall(rb'if\(state==0x([0-9a-f]{8})u\)',shader)]
    if shader.count(b'if(state==')!=len(admitted) or cases!=admitted:
        raise ValueError('GPU plan/kernel case identity mismatch')
    if shader.count(b'0xd0c11a5eu')!=1 or not shader.endswith(b'if(matched){out[idx*2u]=value;out[idx*2u+1u]=0xd0c11a5eu;}}'):
        raise ValueError('GPU plan/kernel publication contract mismatch')
    header=('static const int64_t doc_gpu_bound[]={'+','.join(map(str,bounds))+'};\n'
            'static const int32_t doc_gpu_family[]={'+','.join(map(str,families))+'};\n'
            'static const char doc_wgsl[]='+json.dumps(shader.decode('ascii'))+';\n').encode('ascii')
    return shader,header


def compile_c(argv, *, timeout=240, evidence=None):
    """Run the actual C toolchain, retire its process group on timeout, and
    optionally record the exact command and raw diagnostics for audit."""
    argv=[str(x) for x in argv];start=time.monotonic();expired=False
    with subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True) as proc:
        try:
            out,err=proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired=True
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            out,err=proc.communicate()
    if evidence is not None:
        Path(evidence).write_text(json.dumps(dict(argv=argv,seconds=round(time.monotonic()-start,3),timeout_seconds=timeout,timed_out=expired,returncode=proc.returncode,stdout=out.decode('utf-8',errors='replace'),stderr=err.decode('utf-8',errors='replace')),indent=2)+'\n')
    if expired:raise subprocess.TimeoutExpired(argv,timeout,output=out,stderr=err)
    if proc.returncode:raise subprocess.CalledProcessError(proc.returncode,argv,output=out,stderr=err)
    return out,err


def build_bundled(compiler, data, output, headers, reactive=False, emit_c=None, cc='cc', stream=False,
                  *, gpu_plan=None, wgpu_root=None, emit_wgsl=None, emit_gpu_header=None,
                  compile_timeout=240, compile_evidence=None, cc_flags=()):
    """Compile one admitted byte snapshot through native DOC C/WGSL stages."""
    output=Path(output).absolute();headers=Path(headers).resolve()
    if compile_timeout<=0:raise ValueError('C compile timeout must be positive')
    if compile_evidence is not None:
        destinations=[output,emit_c,emit_wgsl,emit_gpu_header,compile_evidence,str(compile_evidence)+'.candidate.c']
        paths=[Path(p).resolve() for p in destinations if p is not None]
        if len(set(paths))!=len(paths):raise ValueError('compile evidence aliases a build output')
    if (gpu_plan is None)!=(wgpu_root is None) or gpu_plan is not None and not reactive:
        raise ValueError('GPU build requires reactive compiler, GPU planner and WebGPU ABI root')
    if gpu_plan is None and (emit_wgsl is not None or emit_gpu_header is not None):
        raise ValueError('GPU output requested for a CPU-only build')
    code=emit(compiler,data,reactive,stream=stream)
    shader=header=None
    if gpu_plan is not None:
        wgpu=Path(wgpu_root).resolve()
        if not (wgpu/'include/webgpu/wgpu.h').is_file() or not (wgpu/'lib/libwgpu_native.so').is_file():
            raise ValueError('incomplete WebGPU ABI installation')
        shader,header=gpu_artifacts(gpu_plan,data,stream=stream)
    with tempfile.TemporaryDirectory(prefix='.doc-build-',dir=output.parent) as tmp:
        root=Path(tmp);src=root/'generated.c';exe=root/'program';src.write_bytes(code)
        flags=['-std=gnu11','-O1','-pthread','-I',str(headers)]
        link=[]
        if header is not None:
            (root/'gpu_generated.h').write_bytes(header)
            flags+=['-DDOC_ENABLE_GPU','-I',str(root),'-I',str(wgpu/'include')]
            link=['-L',str(wgpu/'lib'),'-Wl,-rpath,'+str(wgpu/'lib'),'-lwgpu_native']
        if reactive:
            flags+=['-DDOC_SOURCE_SHA256="'+hashlib.sha256(data).hexdigest()+'"'];link+=['-lm']
        if compile_evidence is not None:
            # Diagnostic-only sidecar; never replace the last successful
            # executable or --emit-c output until compilation succeeds.
            Path(str(compile_evidence)+'.candidate.c').write_bytes(code)
        try:compile_c([cc,*flags,*cc_flags,str(src),*link,'-o',str(exe)],timeout=compile_timeout,evidence=compile_evidence)
        except subprocess.CalledProcessError as exc:
            raise ValueError('C compiler failed: '+exc.stderr.decode('utf-8',errors='replace')[-4000:]) from exc
        if emit_c:Path(emit_c).write_bytes(code)
        if emit_wgsl:Path(emit_wgsl).write_bytes(shader)
        if emit_gpu_header:Path(emit_gpu_header).write_bytes(header)
        os.replace(exe,output)
    return code


def build(scanner, compiler, file, output, headers, reactive=False, emit_c=None, cc='cc', stream=False, **gpu):
    data=bundle(scanner,file,stream=stream)
    return build_bundled(compiler,data,output,headers,reactive,emit_c,cc,stream,**gpu)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('-o','--output',required=True,type=Path);p.add_argument('--scanner',required=True,type=Path);p.add_argument('--compiler',required=True,type=Path);p.add_argument('--headers',type=Path,default=Path(__file__).resolve().parent.parent/'runtime');p.add_argument('--reactive',action='store_true');p.add_argument('--emit-c',type=Path);p.add_argument('--cc',default='cc');p.add_argument('--cc-flag',action='append',default=[]);p.add_argument('--compile-timeout',type=int,default=240);p.add_argument('--compile-evidence',type=Path);p.add_argument('--stream',action='store_true',help='use byte stdin on self-hosted scanner/compiler tools');p.add_argument('--gpu-plan',type=Path);p.add_argument('--wgpu-root',type=Path);p.add_argument('--emit-wgsl',type=Path);p.add_argument('--emit-gpu-header',type=Path);a=p.parse_args()
    try:build([a.scanner.resolve()],[a.compiler.resolve()],a.source,a.output,a.headers,a.reactive,a.emit_c,a.cc,a.stream,gpu_plan=[a.gpu_plan.resolve()] if a.gpu_plan else None,wgpu_root=a.wgpu_root,emit_wgsl=a.emit_wgsl,emit_gpu_header=a.emit_gpu_header,compile_timeout=a.compile_timeout,compile_evidence=a.compile_evidence,cc_flags=a.cc_flag)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:p.exit(1,'DOC build: '+str(exc)+'\n')
if __name__=='__main__':main()
