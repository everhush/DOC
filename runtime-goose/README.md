# Goose DOC runtime: SDL3-only graphics and GPU

The DOC runtime here is authored entirely in the Goose programming
language (not Go). The canonical native CPU interpreter is
doc_typed.goose. The native Goose-owned optional GPU engine is
doc_sdl3_gpu.goose. Both operate on the SAME directly authored DOC
source language. Rust is independent and keeps its wgpu GPU backend.

## Explicit backend execution policy

Both DOC evaluator binaries accept the **same, directly authored DOC source**
and use CPU unless `--backend=gpu` is explicitly selected.

- `doc-goose` is the independent **CPU-only** Linux interpreter built from
  `doc_typed.goose`. It intentionally rejects selected GPU execution.
- `doc-goose-sdl3`, built from `doc_sdl3_gpu.goose` using upstream Goose's
  native SDL3 `gfx` module, defaults to CPU for `FILE.doc` and
  `FILE.doc source=value`, and runs explicit `FILE.doc --backend=cpu`
  or strict `FILE.doc --backend=gpu`. GPU computes **each supported derived state**
  using native Goose-owned SDL3 Vulkan dispatch/readback; CPU hosts only
  type-admission, device setup, and dependency ordering. No Rust GPU bridge.
- The experimentally eligible GPU subset comprises **finite pure typed
  Boolean/i32 scalar dependency graphs** and **bounded stable recurrence
  epochs** over those graphs. Supported operators include comparisons,
  conditionals, one conservatively bounded arithmetic operator (integer
  leaves in [-32767,32767]), and nested 2..12 integer arithmetic operators
  with tighter per-leaf/host-premise bounds [-4,4]. Consecutive dependent
  stages dispatch on GPU; independent ready states execute in parallel
  Vulkan workgroups. Complete typed readback precedes dependency updates
  and atomic epoch publication. DOC `int` is i64, so GPU admission rejects
  unsupported values, wide arithmetic, arbitrary naturals, lists, text,
  effects, imports, device loss and unproved resource cases. Neither CPU
  substitution nor host-side calculation of a claimed GPU-derived state is
  permitted.
- No automatic backend selection or game-specific language operators exist.

The strict selected DOC-source path has actually passed Linux Mesa SDL3 GPU
compute tests, including 58 independent signed-boundary/Boolean oracle cases,
eight additional DAG/arithmetic/128-state wide-frontier fixtures, eleven
negative cases (including `auto` rejection and atomic failure), and three
no-selector CPU-default cases. The standalone bounded SDL3 kernel validation
now covers 81 checks, including GPU lane counts greater than 4096. Mesa llvmpipe
is **software Vulkan**, not physical acceleration evidence. Physical NVIDIA
Vulkan evidence is separately required in Kaggle, with status still open.

See [backend policy](../BACKEND-EXECUTION-CONTRACT.md) and
[the exact test harness](check-selected-gpu-source.py).


## Adaptive native Goose execution scheduler (Linux)

CPU execution detects available logical threads using `hardware_threads()`
and no longer caps the default at four or overrides at 16. Each ready pure
scalar frontier gets at most one worker per available CPU, with at least
32 independent tasks per spawned worker to amortize thread overhead.
In default automatic mode a sampled small-expression work estimate
avoids an expensive full-frontier scan and a measured worker-spawn slowdown
for trivial 512-node Boolean frontiers; explicit worker overrides remain
available for scaling
and failure testing. `DOC_GOOSE_WORKERS` is a test/budget override, capped
to detected hardware; unsupported pool-backed expressions remain
single-threaded for memory safety.

Selected GPU mode computes ready, **independent** Boolean/i32 derived
definitions as separate SDL3 Vulkan lanes within 64-wide workgroups. The
next dependent frontier waits until every previous lane has completed and
been validated. This has no effect on explicit backend choice and provides
no general GPU support for heterogeneous/effectful definitions. SDL3
`gfx` does not expose a complete driver-specific workgroup-limit API;
the initial Linux Vulkan path enforces its portable X-dimension safety
envelope. Physical GPU proof is separate from Mesa Vulkan correctness.

## What SDL3 handles

The optional upstream Goose gfx package wraps SDL3 GPU devices on the
initial Linux Vulkan target, storage buffers, command submission,
compute passes, ordered pipelines, resource release and readback.

Native Goose's `embed_shader` compiles the SDL3 Vulkan compute
shaders at build time. The bounded operator catalog remains available
for independent GPU measurements; the source-driven DOC evaluator instead
encodes the authored expression as typed stack instructions and executes
it in a Goose-owned compute shader. DOC has no Goose WGSL generator and
never dispatches Goose compute through Rust.

The independent bounded GPU benchmark also covers signed eq, lt, le,
conditional, staged dependency and reduction workloads. It must agree
with native CPU results and a separate Python-only mathematical oracle
before results are accepted.

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

Known constraints: finite/bounded recurrent Boolean-i32 scalar source
eligibility, independently verified physical GPU availability, actual GPU
device-loss testing, heterogeneous/dynamic DOC graph and effect semantics,
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
