#!/usr/bin/env python3
"""Clean-source compiler and bounded CPU tests from a separate native bootstrap."""
import argparse, hashlib, json, os, pathlib, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE=ROOT/"runtime-doc"
POLICIES=(
 ("effects_policy.doc","effects_policy_generated.h","F_effect_",3),
 ("epoch_authority.doc","epoch_policy_generated.h","F_life_",4),
 ("graph_generation.doc","graph_generation_generated.h","F_graph_",3),
 ("placed_policy.doc","placed_policy_generated.h","F_placed_",5),
 ("placement_policy.doc","placement_policy_generated.h","F_place_",4),
 ("recurrence_policy.doc","recurrence_policy_generated.h","F_rec_",6),
)
sys.path.insert(0,str(NATIVE/"compiler"))
from doc_build import bundle, emit
CPU_INPUTS = (
    'compiler/doc_build.py', 'compiler/managed.doc', 'compiler/module_scan.doc',
    'compiler/managed_reactive.doc', 'compiler/lexer_core.doc', 'compiler/parser_core.doc',
    'compiler/common_core.doc', 'compiler/general_core.doc', 'compiler/managed_core.doc',
    'compiler/managed_reactive_core.doc', 'compiler/module_scan_core.doc',
    'tests/test_self_reproduction.py', 'tests/test_placement_policy.py',
    'tests/test_epoch_authority.py', 'tests/test_allocation_failure.py',
    'tests/test_graph_generation.py', 'tests/test_recurrence_policy.py',
    'tests/recurrence_authority_host.c', 'tests/scalable_scratch_test.c',
    'tests/name_index_test.c', 'tests/scale_resource_boundary.c',
    'runtime/effects_policy.doc', 'runtime/epoch_authority.doc',
    'runtime/graph_generation.doc', 'runtime/placed_policy.doc',
    'runtime/placement_policy.doc', 'runtime/recurrence_policy.doc',
    'runtime/value_primitives.h', 'runtime/reactive_values.h',
    'runtime/checkpoint_io.h', 'runtime/epoch_authority.h', 'runtime/graph_reader_slots.h',
    'runtime/graph_host.h', 'runtime/graph_variant_abi.h', 'runtime/graph_variant_adapter.h',
    'runtime/placed_epoch.h', 'runtime/placed_transport.h', 'runtime/placed_authority.h',
    'runtime/recurrence_values.h',
)
def check_cpu_inputs(native):
    missing = [path for path in CPU_INPUTS if not (native/path).is_file() or (native/path).is_symlink()]
    if missing:
        raise ValueError('missing or nonregular clean CPU inputs: ' + ', '.join(missing))
    print(f'DOC14_CPU_INPUTS_PASS: {len(CPU_INPUTS)} required source inputs', flush=True)
def run(argv,cwd=ROOT,timeout=1200):
    print("+", " ".join(map(str,argv)),flush=True)
    subprocess.run(list(map(str,argv)),cwd=cwd,check=True,timeout=timeout)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bootstrap",type=pathlib.Path,required=True)
    p.add_argument("--bootstrap-sha256",required=True)
    p.add_argument("--scanner",type=pathlib.Path,required=True)
    p.add_argument("--scanner-sha256",required=True)
    p.add_argument("--evidence",type=pathlib.Path,required=True)
    p.add_argument("--physical-wgpu-root",type=pathlib.Path,help="require actual physical GPU validation with a separately verified WebGPU ABI installation")
    a=p.parse_args()
    check_cpu_inputs(NATIVE)
    assert (ROOT/"release/test_install.py").is_file(), "missing isolated install regression"
    assert (ROOT/"release/test_gpu_candidate.py").is_file(), "missing candidate GPU oracle"
    boot=a.bootstrap.resolve();scanner=a.scanner.resolve();out=a.evidence.resolve()
    assert sha(boot)==a.bootstrap_sha256 and sha(scanner)==a.scanner_sha256
    assert not (ROOT/"runtime-rust").exists() and not (ROOT/"runtime-goose").exists()
    headers=NATIVE/"runtime"
    assert not list(headers.glob("*_generated.h")),"requires pristine candidate"
    out.mkdir(parents=True,exist_ok=True)
    for source,generated,prefix,count in POLICIES:
        code=emit([boot],(headers/source).read_bytes()+b"\nsource marker:int=0\n")
        lines=[line for line in code.splitlines() if line.startswith(("#define "+prefix).encode())]
        assert len(lines)==count,(source,len(lines))
        (headers/generated).write_bytes(b"\n".join(lines)+b"\n")
    run([sys.executable,NATIVE/"tests/test_self_reproduction.py","--native",boot,"--evidence",out/"self"])
    stage2=out/"self/stage2"; stage2.chmod(0o755)
    def tool(src, name, scan, stream):
        code=emit([stage2],bundle([scan],NATIVE/"compiler"/src,stream=stream),stream=True)
        c=out/(name+".c"); c.write_bytes(code); exe=out/name
        run(["cc","-std=gnu11","-O1","-pthread","-I",headers,c,"-o",exe])
        return exe
    scan2=tool("module_scan.doc","scanner2",scanner,False)
    reactive=tool("managed_reactive.doc","reactive2",scan2,True)
    run([sys.executable,ROOT/"release/test_install.py","--compiler",stage2,"--scanner",scan2,"--stream","--evidence",out/"install-smoke"])
    for name,args in (
        ("test_placement_policy.py",["--managed",stage2]),
        ("test_epoch_authority.py",["--managed",stage2,"--reactive",reactive]),
        ("test_allocation_failure.py",["--reactive",reactive]),
        ("test_graph_generation.py",["--managed",stage2,"--reactive",reactive]),
        ("test_recurrence_policy.py",["--managed",stage2,"--reactive",reactive]),
    ):
        run([sys.executable,NATIVE/"tests"/name,*args])
    for name in ("scalable_scratch_test","name_index_test","scale_resource_boundary"):
        exe=out/name
        run(["cc","-std=gnu11","-O1","-g","-pthread","-fsanitize=address,undefined","-fno-sanitize-recover=all","-fno-pie","-no-pie","-I",headers,NATIVE/"tests"/(name+".c"),"-o",exe])
        run([exe])
    (out/"native-hashes.json").write_text(json.dumps({str(f.relative_to(out)):sha(f) for f in (stage2,out/"self/stage3",scan2,reactive)},indent=2)+"\n")
    gpu_args=[sys.executable,ROOT/"release/test_gpu_candidate.py","--compiler",reactive,"--evidence",out/"gpu-oracle"]
    if a.physical_wgpu_root:
        planner=tool("gpu_plan.doc","gpu_plan2",scan2,True)
        gpu_args.extend(["--gpu-plan",planner,"--wgpu-root",a.physical_wgpu_root.resolve()])
    else:
        gpu_args.append("--cpu-only")
    run(gpu_args)
    print("DOC14_CLEAN_CPU_CANDIDATE_PASS: separate native bootstrap, no reference evaluator in candidate")
if __name__=="__main__":
    main()
