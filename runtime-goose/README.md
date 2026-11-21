# Goose DOC runtime: SDL3-only graphics and GPU

The DOC runtime here is authored entirely in the Goose programming
language (not Go). The canonical native CPU interpreter is
doc_typed.goose. The native Goose-owned optional GPU engine is
doc_sdl3_gpu.goose. Both operate on the SAME directly authored DOC
source language. Rust is independent and keeps its wgpu GPU backend.

## What SDL3 handles

The optional upstream Goose gfx package wraps SDL3 GPU devices, Vulkan,
Metal and Direct3D 12 backends, storage buffers, command submission,
compute passes, ordered pipelines, resource release and readback.

Native Goose's embed_shader builtin compiles a small static GLSL
operator kernel catalog at build time, embedding SPIR-V, MSL and HLSL.
DOC does not maintain a separate Goose WGSL generator, custom shader
file emission, a backward compatibility CLI, or GPU dispatch through Rust.

The current GPU-eligible subset consists of signed i64 eq, lt and le
only after 32-bit eligibility proof; a Boolean conditional; a staged
dependent Boolean compute; and a second reduction stage. Native Goose
CPU evaluation and an independent Python test-only mathematical oracle
must agree on every GPU result before publication.

The runtime fails closed on unsupported DOC definitions, values outside
portable shader range, missing GPU devices, invalid lane counts, and
readback mismatches. A CPU fallback cannot claim a successful GPU pass.

SDL3 and the upstream gfx package are third-party C libraries.
DOC-authored runtime logic and GPU orchestration are pure Goose; no
DOC-owned C, C++, foreign GPU shim or Rust-hosted Goose GPU path remains.
SDL3 does not currently offer a WebGPU backend.

## Linux validation

The pinned Goose compiler is at revision
9412b80f52d833c4697cffdbbf1f4eeb5195cd41.

Build its optional gfx package with
CMake option -DGOOSE_BUILTIN_LIBS=gfx, then typecheck and build
runtime-goose/doc_sdl3_gpu.goose with the native Goose compiler.

Example native execution:

    xvfb-run -a env GOOSE_GFX_HEADLESS=1 SDL_VIDEODRIVER=x11 \
        SDL_GPU_DRIVER=vulkan ./doc-goose-sdl3 \
        runtime-rust/examples/integer_equality.doc eq 65

Independent native GPU parity:

    xvfb-run -a env GOOSE_GFX_HEADLESS=1 SDL_VIDEODRIVER=x11 \
        SDL_GPU_DRIVER=vulkan python3 runtime-goose/check-doc-sdl3-gpu.py \
        ./doc-goose-sdl3 validation-logs/sdl3

See the secondary .github/workflows/doc-validation.yml for the exact
dependency setup, full test matrix and optional hardware runner gates.

Known constraints: static pure-operation eligibility, platform GPU
availability, physical device-loss testing, broader DOC-to-GPU placement,
real-device benchmarks and a production graphical game engine remain
explicit acceptance gates. Mesa llvmpipe is a SOFTWARE Vulkan adapter.

Linux CI uses a virtual X11 display to enable SDL3's Vulkan-capable X11
video backend; the bare SDL offscreen driver on this runner lacks the
Vulkan_CreateSurface entrypoint. The compute dispatch and readback are still
fully Goose-owned SDL3 GPU calls, and the selected Mesa llvmpipe adapter is
SOFTWARE Vulkan (not accelerated physical hardware). Future hardware
performance claims must use opt-in self-hosted physical-GPU runners.

The secondary CI also compares the Rust wgpu and Goose SDL3 **observed GPU
results** for common DOC integer eq/lt/le source epochs. This is evidence
only; the GPU implementations and shader packaging remain independent.
