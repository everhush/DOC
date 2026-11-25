#!/usr/bin/env python3
"""Static Linux release-scope guard; no credentials, compilers or GPU needed."""
import ast
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent.parent

def fail(reason):
    raise SystemExit("DOC_RUST_ONLY_SCOPE_FAILURE: "+reason)

def read(path):
    file=ROOT/path
    if not file.is_file(): fail("missing "+path)
    return file.read_text(encoding="utf-8")

def require(condition,reason):
    if not condition: fail(reason)

ci=read(".github/workflows/doc-validation.yml")
gpu_ci=read(".github/workflows/doc-kaggle-gpu.yml")
goose=read("runtime-goose/DEPRECATED.md")
require("DEPRECATED" in goose,"archived Goose source not explicitly marked deprecated")
require(re.search(r"(?m)^name: DOC Rust Linux validation$",ci),
        "Rust-only exact-SHA CI workflow must have stable name")
require(re.search(r"(?m)^  rust:$",ci) is not None,
        "CPU Rust job missing")
require(re.search(r"(?m)^  webgpu-compute:$",ci) is not None,
        "Rust wgpu job missing")
require(not re.search(r"(?m)^  (?:goose[^:]*|dual-native-gpu-parity):$",ci),
        "deprecated Goose job present in release CI")
require("GOOSE_BUILTIN_LIBS" not in ci and
        "runtime-goose/*.sh" not in ci and
        "doc-goose-sdl3-native-gpu" not in ci,
        "Goose compiler or SDL3 dependency leaked into Rust CI")
require("workflows: ['DOC Rust Linux validation']" in gpu_ci,
        "Kaggle trigger no longer matches exact Rust-only source run")
bundle=read("ci/kaggle/bundle.py")
mod=ast.parse(bundle)
values={}
for node in mod.body:
    if isinstance(node,ast.Assign) and len(node.targets)==1 and \
            isinstance(node.targets[0],ast.Name) and \
            node.targets[0].id in {"ARTIFACT_NAMES","GPU_EXECUTABLES","SOURCE_FILES"}:
        values[node.targets[0].id]=ast.literal_eval(node.value)
require(set(values)=={"ARTIFACT_NAMES","GPU_EXECUTABLES","SOURCE_FILES"},
        "Rust GPU artifact manifest lacks explicit reviewed inventory")
require(values["ARTIFACT_NAMES"]==("doc-rust-wgpu-validation",),
        "Kaggle must use exactly the successful Rust GPU artifact")
require(all(dst.startswith(("bin/","lib/")) and
            component=="rust" and "goose" not in src.lower()
            for dst,(component,src) in values["GPU_EXECUTABLES"].items()),
        "GPU artifact contains an inactive/foreign runtime")
require(all(path.startswith("runtime-rust/") or path=="LICENSE" or path in {
    "engine/radar_chase.doc","engine/engine_math.doc","engine/entity_pool.doc",
    "engine/radar_chase_3d.doc","engine/graphics/arena_vertex.doc","engine/graphics/mesh_fragment.doc","engine/levels/arena_vertices.txt","engine/levels/arena_indices.txt",
    "engine/levels/coin_chase.txt","engine/levels/showcase_xs.txt","engine/levels/showcase_ys.txt"}
            for path in values["SOURCE_FILES"]),
        "Kaggle includes sources from deprecated runtime")
require(all((ROOT/path).is_file() for path in values["SOURCE_FILES"]),
        "A SHA-pinned DOC source fixture is missing")
gpu=read("ci/kaggle/doc_kaggle_gpu.py")
require("def check_selected_rust_doc_gpu(" in gpu and
        "def check_selected_goose_doc_gpu(" not in gpu,
        "active physical GPU controller still depends on Goose")
require(all(marker in gpu for marker in (
        "DOC_GPU_GENERATED_SESSION_CREATED:", "DOC_GPU_GENERATED_PIPELINE_CREATED:")),
        "physical validation must verify actual generated compute pipeline")
require("DOC_GPU_GENERATED_PIPELINE_REUSED:" in ci,
        "software game replay must prove generated pipeline reuse")
require("DOC_GPU_SOFTWARE_TEST_ONLY" in gpu,
        "real hardware controller does not reject software GPU evidence")
dispatch=read("ci/kaggle/dispatch.py")
require("rust_gpu_episodes" in dispatch and
        "selected_goose_doc_gpu_cases" not in dispatch and
        "goose_sdl3_checks" not in dispatch,
        "remote GPU proof still assumes Goose execution")
require("DOC Rust Linux validation" in bundle and
        "DOC Rust Linux validation" in ci,
        "GitHub exact-SHA accepted workflow mismatch")
require(all(s not in gpu for s in ("vulkaninfo","VK_DRIVER_FILES","VK_ICD_FILENAMES","WGPU_BACKEND")),
        "Kaggle actively configures a native API or driver implementation")
rust_gpu=read("runtime-rust/src/gpu.rs")
require("wgsl::lower_parallel_frontier(" in rust_gpu and
        "doc_reusable.wgsl" not in rust_gpu and
        "gpu_abi::encode_derived" not in rust_gpu,
        "active compute must compile typed DOC source, not interpret shader bytecode")
require("wgpu::Instance::default()" in rust_gpu,
        "Rust GPU instance is no longer provider-agnostic")
require(all(s not in rust_gpu for s in ("Backends::VULKAN","Backend::Vulkan","DOC_GPU_NATIVE_API")),
        "Native API pinning leaked into active Rust GPU execution")
for path in ("runtime-rust/examples/webgpu_bool.rs",
             "runtime-rust/examples/webgpu_integer_eq.rs"):
    source=read(path)
    require("wgpu::Instance::default()" in source,
            "GPU example bypasses WebGPU provider selection: "+path)
    require("Backends::VULKAN" not in source and "Backend::Vulkan" not in source,
            "GPU example forces native provider: "+path)
# Obsolete native-API scripts were dual-runtime historical probes; keep their
# evidence in Git history, not in a current WebGPU-only release tree.
for legacy in (
    "ci/physical-vulkan-dual-parity.sh",
    "ci/verify-local-gpu-evidence.py",
    "ci/test_local_gpu_evidence.py",
    "ci/test_gpu_evidence_integration.py",
):
    require(not (ROOT/legacy).exists(),
            "retired native GPU proof script still shipped: "+legacy)

# This guard checks DOC's own active entry points, not Linux driver packages.
# The host must still provide a compatible driver for wgpu's internal provider.
for path in (
    "runtime-rust/src/gpu.rs",
    "runtime-rust/examples/webgpu_bool.rs",
    "runtime-rust/examples/webgpu_integer_eq.rs",
    "ci/kaggle/doc_kaggle_gpu.py",
    "ci/kaggle/dispatch.py",
    "ci/run-all-local.sh",
):
    code=read(path)
    require(not any(marker in code for marker in (
        "vulkaninfo", "VK_DRIVER_FILES", "VK_ICD_FILENAMES",
        "MESA_VK_DEVICE_SELECT", "DOC_HW_VK_SELECT",
        "SDL_GPU_DRIVER", "Backends::VULKAN",
        "Backend::Vulkan", "WGPU_BACKEND",
    )), "native API selection escaped WebGPU abstraction: "+path)
require("runtime-goose/" not in read("ci/run-all-local.sh"),
        "active local test runner still depends on deprecated Goose")

require("naga::back::spv" not in read("runtime-rust/src/wgsl.rs") and
        "runtime-goose/" not in read("runtime-rust/src/wgsl.rs"),
        "active Rust shader validation still translates native binaries or imports Goose")
require('"spv-out"' not in read("runtime-rust/Cargo.toml"),
        "Rust dev dependency still enables manual native shader output")
require((ROOT/"docs/RUST-ONLY-ACCEPTANCE.md").is_file(),
        "reviewed Rust-only acceptance contract missing")
print("DOC_RUST_ONLY_SCOPE_CONTRACT_PASS")
