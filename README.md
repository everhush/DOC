# Dependency-Oriented Computation (DOC)

DOC is a persistent dependency-graph computation model for typed, reactive incremental repair, with additional, **separately scoped** contracts for recurrence, changing graph versions, safe physical realization, placement and external effects.

## Explicit execution-backend policy — 2026-11-22

General-purpose DOC execution is **CPU by default**. Both native Rust and Goose CLIs accept `FILE.doc --backend=cpu` and strictly reject `FILE.doc --backend=gpu` until their general-purpose GPU evaluators exist; there is no `auto` mode, no automatic CPU/GPU switching and no silent CPU fallback. Dedicated Rust wgpu and native Goose SDL3 gfx GPU examples remain bounded regression paths, **not** general-purpose GPU implementations. See [BACKEND-EXECUTION-CONTRACT.md](BACKEND-EXECUTION-CONTRACT.md) for the normative decision, limitations, and completion gates.

## Current development objective

Build one small, expressive, general-purpose **DOC language** with **two independent runtimes**:

- runtime-rust/ — independently authored native Rust DOC runtime and Rust wgpu GPU host.
- runtime-goose/doc_typed.goose — independent native Goose DOC runtime (Goose, NOT Go).
- runtime-goose/doc_sdl3_gpu.goose — Goose-owned GPU compute via the upstream Goose gfx SDL3 package, replacing the removed Goose WGSL generator and Rust-hosted Goose GPU bridge.

Neither backend is production-ready. The finite acyclic core alone is **not** Turing-complete. The manuscript's claimed universality explicitly requires separate demand-driven unbounded *versioned recurrence*, unbounded values and adequate branching, with finite requested-prefix execution. Ordinary programs also need explicit effects, diagnostics, functions, data, packages and safe physical lifetime management.

**No active C++ runtime, CMake build, legacy C++ benchmark suite or GitHub Actions workflows remain on `master`.** The prior research snapshot is available at [`snapshot-2026-11-17-pre-rust-runtime`](https://github.com/imxade/DOC/tree/snapshot-2026-11-17-pre-rust-runtime), commit `1ab3e3987477b1638f1abde58102704fa353d656`. It is a historical research and reproducibility artifact, **not** an implementation or oracle dependency for the new runtimes. Submitted manuscript sources are deliberately preserved; any references there to the historical witness and numbers refer to that archived research, not to the current language implementations.

## Normative sources and evidence

- [Main manuscript](paper/dependency-oriented-computation.typ): formal DOC semantics, metatheory, conditional extensions, realization contracts and historically measured claims.
- [Independent calculus draft](paper-calculus/dependency-oriented-calculus.typ): a limited typed finite calculus, **not** the full general-purpose language.
- [Paper-ordered acceptance trace](MODEL-REQUIREMENT-TRACE.md): required semantics, language completeness, two-runtime conformance and unverified gaps.
- [Claim/evidence boundaries](CLAIM-EVIDENCE-MAP.md): distinctions between theorem arguments, historical research evidence, new implementation and production evidence.
- [Issue #7](https://github.com/imxade/DOC/issues/7): implementation and production gates for both runtimes.
- [Issue #8](https://github.com/imxade/DOC/issues/8): open-ended research on model-level memory-safety gaps.
- [Issue #9](https://github.com/imxade/DOC/issues/9): append-only Rust-versus-Goose conformance, safety and benchmark results.

## Implementation invariants

1. User-facing code is the same independent DOC language under both runtimes, not a Python, Rust or Goose dialect.
2. Use **as few fundamental semantic primitives as correctness and universality permit**; validate expressivity with formal lowering and executable representative programs. Surface convenience is not a new primitive by default.
3. Pure deterministic finite computations retain DOC's typed graph, validated source batches, ready frontiers, same-pre-state private evaluation, immutable atomic publication and sound equality cutoff. Do not infer general-purpose external effects from the finite theorem.
4. Support the paper's qualified demand/recurrence, graph-version, protected observation/reclamation, and bounded placed-realization properties under their separate assumptions.
5. Memory safety, automatic lifetime, explicit effect boundaries, and safe-by-default Rust/Goose code; unsafe exceptions require an independently tested narrow justification.
6. Real local compilation, executed conformance tests, practical programs and reproduced performance evidence are release gates. No benchmark results or production compliance are claimed without measurements. GitHub Actions are used only in the SECONDARY development repository, not on the primary research repository.

For Rust DOC architecture consult runtime-rust/README.md; for native Goose SDL3 GPU architecture consult runtime-goose/README.md. Neither should yet be called a general-purpose production distribution.

## Development graphics architecture (no dual-host Goose GPU fallback)

Rust and Goose execute the same DOC source semantics independently. Rust
retains wgpu. Goose exclusively uses SDL3's GPU API, through the upstream
Goose gfx package, for graphics and supported pure GPU compute. The legacy
Goose WGSL generator, shader-export CLI, and the Goose-to-Rust-wgpu GPU
host bridge have been removed. The two GPU paths are NOT interchangeable
at the implementation level; parity is a TEST requirement, not a shared
backend implementation.

Goose's built-in embed_shader compiles static GLSL compute kernels at
compile time into backend code for Vulkan (SPIR-V), Metal (MSL), and
Direct3D 12 (HLSL). SDL3 does not currently provide a WebGPU backend.
SDL3 and the upstream Goose gfx package contain third-party C code; all
DOC-authored Goose runtime and GPU orchestration source remains native
Goose, without locally maintained C or C++ runtime components or shims.

Device dispatch, GPU result publication, SDL3 resource lifetime and
real-adapter tests are tracked separately from CPU semantics. Mesa
software Vulkan proves backend execution correctness only; physically
accelerated Vulkan/Metal/D3D12 still require separate hardware tests.
See runtime-goose/README.md and the active secondary CI workflow.
