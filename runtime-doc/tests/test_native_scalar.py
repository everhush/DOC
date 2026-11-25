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
        run(['cc','-std=gnu11','-O0','-I',ROOT/'runtime',c,'-o',native],timeout=300)
    def compile_doc(target,source=src,region='scratch',imp='x86_out8',name='boot',reject=False,region2=''):
        argv=[native,'--demand='+target,'--input-stdin','grant_region="'+region+'"','grant_region2="'+region2+'"','grant_import="'+imp+'"','export_name="'+name+'"']
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
