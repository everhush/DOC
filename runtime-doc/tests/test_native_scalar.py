#!/usr/bin/env python3
"""Self-hosted, bounded native scalar ABI profile; no host DOC evaluation."""
import argparse, hashlib, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT/'compiler'))


def run(argv, *, expected=0, **kw):
    r = subprocess.run([str(x) for x in argv], capture_output=True, timeout=kw.pop('timeout',120), **kw)
    assert r.returncode == expected, (argv[0], r.returncode, r.stderr[-4000:])
    return r.stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage2',type=Path); p.add_argument('--scanner',type=Path)
    p.add_argument('--native',type=Path); p.add_argument('--evidence',required=True,type=Path)
    p.add_argument('--boot',action='store_true'); p.add_argument('--fixture-root',type=Path,default=REPO)
    a=p.parse_args(); out=a.evidence.resolve(); out.mkdir(parents=True,exist_ok=True)
    fixture=a.fixture_root.resolve(); src=(fixture/'runtime-rust/examples/native_boot.doc').read_bytes()
    if a.native:
        native=a.native.resolve()
    else:
        assert a.stage2 and a.scanner
        from doc_build import bundle, emit
        code=emit([a.stage2.resolve()],bundle([a.scanner.resolve()],ROOT/'compiler/native_scalar.doc',stream=True),stream=True)
        c=out/'native_scalar2.c'; c.write_bytes(code); native=out/'native_scalar2'
        # The macro diagnostic backtrace is not part of emitted C semantics.
        # Keep -O0 and fail closed; retain the command, time, and compiler output.
        from test_self_reproduction import run_cc
        run_cc(['cc','-std=gnu11','-O0','-ftrack-macro-expansion=0','-I',ROOT/'runtime',c,'-o',native],out,out,'native-scalar',timeout=600)
    def compile_doc(target,source=src,region='scratch',imp='x86_out8',name='boot',reject=False,region2='',intrinsic='',allow_read=False,allow_write=False,scalar1='',scalar2=''):
        argv=[native,'--demand='+target,'--input-stdin','grant_region="'+region+'"','grant_region2="'+region2+'"','grant_import="'+imp+'"','grant_intrinsic="'+intrinsic+'"','allow_read='+str(allow_read).lower(),'allow_write='+str(allow_write).lower(),'grant_scalar1="'+scalar1+'"','grant_scalar2="'+scalar2+'"','export_name="'+name+'"']
        r=subprocess.run([str(x) for x in argv],input=source,capture_output=True,timeout=120)
        if reject:
            assert r.returncode and not r.stdout,(target,r.returncode,r.stdout[:100])
            return
        prefix=(target+': ').encode(); assert r.returncode==0 and r.stdout.startswith(prefix) and r.stdout.endswith(b'\n'),r.stderr[-4000:]
        return r.stdout[len(prefix):-1]
    for target,filename in [('code','boot.c'),('header','boot.h')]:
        data=compile_doc(target); assert data==compile_doc(target); (out/filename).write_bytes(data)
    negatives=[('wrong-region',src,'other','x86_out8'),('wrong-import',src,'scratch','other'),('missing-chain',src.replace(b'(index,written)',b'(index)'),'scratch','x86_out8'),('wrong-type',src.replace(b'byte: int (seed) = add(seed,1)',b'byte: bool (seed) = eq(seed,1)'),'scratch','x86_out8'),('undeclared-premise',src.replace(b'(index,byte)',b'(index)'),'scratch','x86_out8'),('unsupported-region',src.replace(b'u8 plain',b'u16 volatile'),'scratch','x86_out8'),('wrong-arity',src.replace(b'x86_out8(port,read_back)',b'x86_out8(port)'),'scratch','x86_out8'),('duplicate-region',src.replace(b'native region scratch: u8 plain',b'native region scratch: u8 plain\nnative region scratch: u8 plain'),'scratch','x86_out8'),('overflow-source',src.replace(b'source seed: int = 64',b'source seed: int = 9223372036854775808'),'scratch','x86_out8'),('duplicate-state',src.replace(b'source seed: int = 64',b'source seed: int = 64\nsource seed: int = 3'),'scratch','x86_out8'),('hidden-import',src.replace(b'x86_out8(port,read_back)',b'unknown(port,read_back)'),'scratch','x86_out8')]
    for name,source,region,imp in negatives:
        assert source!=src or region!='scratch' or imp!='x86_out8'
        for target in ('code','header'): compile_doc(target,source,region,imp,reject=True)
        print('REJECT',name,flush=True)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie','-I',out,out/'boot.c',Path(__file__).with_name('native_scalar_host.c'),'-o',out/'host'])
    print(run([out/'host']).decode().strip(),flush=True)
    # Compile the unchanged frozen volatile/atomic fixture with separate grants.
    regions=(fixture/'runtime-rust/examples/native_regions.doc').read_bytes()
    for target in ('code','header'):
        data=compile_doc(target,regions,'device','','regions',region2='counter')
        assert data==compile_doc(target,regions,'device','','regions',region2='counter')
        (out/('regions.c' if target=='code' else 'regions.h')).write_bytes(data)
    region_negatives=[
        (regions,'device',''),
        (regions,'device','device'),
        (regions.replace(b'u32 atomic',b'u8 plain'),'device','counter'),
        (regions.replace(b'seq_cst()',b'relaxed()'),'device','counter'),
        (regions.replace(b'(index,delta,read_back)',b'(index,delta)'),'device','counter'),
        (regions.replace(b'counter(index,delta)',b'device(index,delta)'),'device','counter'),
        (regions.replace(b'u8 volatile',b'u8 atomic'),'device','counter'),
    ]
    for source,first,second in region_negatives:
        for target in ('code','header'):
            compile_doc(target,source,first,'','regions',reject=True,region2=second)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',out,out/'regions.c',Path(__file__).with_name('native_regions_host.c'),'-o',out/'region-host'])
    print(run([out/'region-host']).decode().strip(),flush=True)
    print('DOC11_NATIVE_REGIONS_PASS: unchanged volatile and atomic fixture, 14 compiler rejection checks',flush=True)
    # The unmodified frozen arena fixture exercises capacity and allocator policy.
    arena=(fixture/'runtime-rust/examples/native_arena.doc').read_bytes()
    for target in ('code','header'):
        data=compile_doc(target,arena,'arena','','arena')
        assert data==compile_doc(target,arena,'arena','','arena')
        (out/('arena.c' if target=='code' else 'arena.h')).write_bytes(data)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',out,out/'arena.c',Path(__file__).with_name('native_arena_host.c'),'-o',out/'arena-host'])
    print(run([out/'arena-host']).decode().strip(),flush=True)
    # Compile original frozen intrinsic examples, with explicit external admission.
    intr=(fixture/'runtime-rust/examples/native_intrinsic.doc').read_bytes()
    ext=(fixture/'runtime-rust/examples/native_intrinsic_external.doc').read_bytes()
    for name,source,grant in [('intrinsics',intr,''),('external',ext,'target_transform')]:
        for target,suffix in [('code','c'),('header','h')]:
            data=compile_doc(target,source,'','',name,intrinsic=grant)
            assert data==compile_doc(target,source,'','',name,intrinsic=grant)
            (out/(name+'.'+suffix)).write_bytes(data)
    neg_intr=[
        (ext,''),
        (ext,'other'),
        (ext.replace(b'external(target_transform)',b'external(other)'),'target_transform'),
        (ext.replace(b'-> i32',b'-> i64'),'target_transform'),
        (ext.replace(b'enabled: bool = true',b'enabled: int = 1'),'target_transform'),
        (intr.replace(b'native intrinsic leading',b'native intrinsic bit_count'),''),
        (intr.replace(b'(input,bits)',b'(input)'),''),
        (intr.replace(b'bit_count(input)',b'unknown(input)'),''),
        (intr.replace(b'bit_count(i64)',b'bit_count(i32)'),''),
        (intr.replace(b'source input: int = 0',b'source bit_count: int = 0\nsource input: int = 0'),''),
    ]
    for source,grant in neg_intr:
        for target in ('code','header'):
            compile_doc(target,source,'','','intrinsic_negative',reject=True,intrinsic=grant)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',out,out/'intrinsics.c',out/'external.c',Path(__file__).with_name('native_intrinsic_host.c'),'-o',out/'intrinsic-host'])
    print(run([out/'intrinsic-host']).decode().strip(),flush=True)
    print('DOC11_NATIVE_INTRINSICS_PASS: original built-in and external fixtures; 20 compiler rejection checks',flush=True)
    # The unchanged POSIX fixture must call actual read/write, not a host evaluator.
    buf=(fixture/'runtime-rust/examples/native_buffer.doc').read_bytes()
    for target,suffix in [('code','c'),('header','h')]:
        data=compile_doc(target,buf,'buffer','','buffer',allow_read=True,allow_write=True)
        assert data==compile_doc(target,buf,'buffer','','buffer',allow_read=True,allow_write=True)
        (out/('buffer.'+suffix)).write_bytes(data)
    buf_neg=[
        (buf,False,True),(buf,True,False),
        (buf.replace(b'read(i32,bytes)',b'read(i32,const_bytes)'),True,True),
        (buf.replace(b'write(i32,const_bytes)',b'write(i32,bytes)'),True,True),
        (buf.replace(b'read(input_fd,buffer',b'read(input_fd,other'),True,True),
        (buf.replace(b'(input_fd,offset,requested,enabled,skipped)',b'(input_fd,requested,enabled,skipped)'),True,True),
        (buf.replace(b'when enabled else skipped',b'when requested else skipped'),True,True),
        (buf.replace(b'native region buffer: u8 plain',b'native region buffer: u8 volatile'),True,True),
        (buf.replace(b'write(output_fd,buffer,offset,received)',b'write(output_fd,buffer,offset)'),True,True),
        (buf.replace(b'native import read(i32,bytes) -> i64',b'native import read(i32,bytes) -> i64\nnative import read(i32,bytes) -> i64'),True,True),
    ]
    for source,rd,wr in buf_neg:
        for target in ('code','header'):
            compile_doc(target,source,'buffer','','buffer_negative',reject=True,allow_read=rd,allow_write=wr)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',out,out/'buffer.c',Path(__file__).with_name('native_buffer_host.c'),'-o',out/'buffer-host'])
    print(run([out/'buffer-host'],timeout=10).decode().strip(),flush=True)
    print('DOC11_NATIVE_BUFFER_PASS: original POSIX fixture and 20 compiler rejection checks',flush=True)
    # Direct signed scalar imports, independently granted by exact symbol.
    conditional=(fixture/'runtime-rust/examples/native_conditional.doc').read_bytes()
    socket=(fixture/'runtime-rust/examples/native_socket.doc').read_bytes()
    for name,source,g1,g2 in [('conditional',conditional,'acquire','release'),('socket',socket,'socket','close')]:
        for target,suffix in [('code','c'),('header','h')]:
            data=compile_doc(target,source,'','',name,scalar1=g1,scalar2=g2)
            assert data==compile_doc(target,source,'','',name,scalar1=g1,scalar2=g2)
            (out/(name+'.'+suffix)).write_bytes(data)
    scalar_neg=[
        (conditional,'','release'),(conditional,'acquire',''),(conditional,'acquire','acquire'),
        (conditional.replace(b'acquire(i32)',b'acquire(i64)'),'acquire','release'),
        (conditional.replace(b'acquire(argument)',b'acquire(argument,argument)'),'acquire','release'),
        (conditional.replace(b'when enabled else absent',b'when argument else absent'),'acquire','release'),
        (conditional.replace(b'when enabled else absent',b'when enabled else enabled'),'acquire','release'),
        (conditional.replace(b'(acquired,acquired_ok,absent)',b'(acquired_ok,absent)'),'acquire','release'),
        (conditional.replace(b'native import acquire(i32) -> i32',b'native import acquire(i32) -> i32\nnative import acquire(i32) -> i32'),'acquire','release'),
        (conditional.replace(b'source argument: int = 7',b'source acquire: int = 7\nsource argument: int = 7'),'acquire','release'),
        (socket,'socket','other'),
        (socket.replace(b'socket(i32,i32,i32)',b'socket(i32,i32)'),'socket','close'),
        (socket.replace(b'socket(domain,socket_type,protocol)',b'socket(domain,socket_type)'),'socket','close'),
        (socket.replace(b'close(fd)',b'other(fd)'),'socket','close'),
    ]
    for source,g1,g2 in scalar_neg:
        for target in ('code','header'):
            compile_doc(target,source,'','','scalar_negative',reject=True,scalar1=g1,scalar2=g2)
    run(['cc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie','-I',out,out/'conditional.c',out/'socket.c',Path(__file__).with_name('native_scalar_calls_host.c'),'-o',out/'scalar-calls-host'])
    print(run([out/'scalar-calls-host'],timeout=10).decode().strip(),flush=True)
    print('DOC11_NATIVE_SCALAR_CALLS_PASS: original conditional and local socket fixtures, 28 compiler rejection checks',flush=True)
    # Renamed declarations and a changed graph prove this is not a fixed boot template.
    alt=src.replace(b'scratch',b'ram').replace(b'x86_out8',b'foreign_byte').replace(b'add(seed,1)',b'sub(seed,2)')
    ac=compile_doc('code',alt,'ram','foreign_byte','alternate'); assert b'__asm__("foreign_byte")' in ac and b'doc_sub(doc_v_seed' in ac and b'doc_export_alternate' in ac
    (out/'alternate.c').write_bytes(ac);run(['cc','-std=c11','-c',out/'alternate.c','-o',out/'alternate.o'])
    flags=['-m64','-std=c11','-O2','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-mno-red-zone','-mno-sse','-mno-mmx','-fno-asynchronous-unwind-tables']
    platform=fixture/'ci/freestanding'
    run(['cc',*flags,'-c',out/'boot.c','-o',out/'boot.o'])
    run(['cc',*flags,'-I',out,'-c',platform/'verify.c','-o',out/'verify.o'])
    run(['cc','-m64','-c',platform/'entry.S','-o',out/'entry.o'])
    run(['ld','-m','elf_x86_64','-nostdlib','-T',platform/'layout.ld',out/'entry.o',out/'boot.o',out/'verify.o','-o',out/'kernel64.elf'])
    assert not run(['nm','-u',out/'kernel64.elf']).strip()
    info=run(['readelf','-h','-l','-d',out/'kernel64.elf']); assert b'Advanced Micro Devices X86-64' in info and b'INTERP' not in info and b'(NEEDED)' not in info
    (out/'elf.txt').write_bytes(info); run(['objcopy','-O','elf32-i386',out/'kernel64.elf',out/'kernel.elf'])
    print('DOC11_NATIVE_SCALAR_PASS: 22 rejection checks, hosted ABI sanitizer tests, alternate graph, freestanding static ELF',flush=True)
    if a.boot:
        (out/'qemu-version.txt').write_bytes(run(['qemu-system-x86_64','--version']))
        run(['qemu-system-x86_64','-machine','pc','-cpu','qemu64','-m','64M','-display','none','-serial','none','-monitor','none','-no-reboot','-device','isa-debug-exit,iobase=0xf4,iosize=0x04','-debugcon','file:'+str(out/'device.txt'),'-global','isa-debugcon.iobase=0xe9','-kernel',out/'kernel.elf'],expected=33,timeout=30)
        assert (out/'device.txt').read_bytes()==b'AB'
        print('DOC11_FREESTANDING_BOOT_PASS: bytes=AB, negative bounds preserved',flush=True)
    else: print('QEMU boot not requested; static ELF is not boot evidence',flush=True)
    for f in (native,out/'boot.c',out/'boot.h',out/'kernel64.elf'):
        print(hashlib.sha256(f.read_bytes()).hexdigest(),f.name,flush=True)

if __name__=='__main__': main()
