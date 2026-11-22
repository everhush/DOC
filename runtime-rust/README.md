# Native Rust DOC runtime — actively validated subset (not a production release)

DOC is a dependency-oriented declarative dataflow language with
incremental evaluation, functional derived computations, explicit source/effect
boundaries, typed recurrence, and immutable graph-generation semantics.
The same directly authored DOC programs also run in an **independent native
Goose runtime** (Goose is *not* Go). Neither runtime implements the whole
paper's realization contracts or merits an unconditional production-ready claim.

## Implemented and tested subsets

- Native Rust DOC source parser/validator, typed `source`, `derive`,
  bounded elaborated functions/imports and separate read/write effect boundaries
- `bool`, checked `int`, arbitrary-precision `nat`, integer collections
  `ints`, `maybe_int` and UTF-8 `text`; typed arithmetic/selection,
  comparison, collection manipulation, text concatenation and indexed reads
- Atomic validated source batches, legal ready-frontier execution, exact and
  conservative cutoff, demand-local stabilization, and same-episode rejection
  of stale worker/source/graph tokens
- Finite requested-prefix recurrence with typed forward carry, source-fact
  retention choices, two-counter and sorting examples
- Conservative graph replacement, private candidate stabilization and
  owned concurrent-reader publication through `src/publication.rs`
- Optional Rust `wgpu` device execution for eligible bounded pure operations,
  staged Boolean reductions, source episodes and CPU differential tests

This is **not** the complete general-purpose language. Fallible operations
still use host error paths in important places, and physical-lifetime,
reconstruction/eviction, placement/transport and fail-stop policy obligations
are not fully discharged. No all-algorithms-to-GPU claim is made.

## Local build and correctness

From repository root with Rust installed:

```bash
cargo test --release --manifest-path runtime-rust/Cargo.toml --all-targets
cargo build --release --manifest-path runtime-rust/Cargo.toml --bin doc
runtime-rust/target/release/doc runtime-rust/examples/repair.doc a=4 b=1
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench
```

For optional GPU-eligible expressions with a supported adapter and driver:

```bash
cargo test --release --manifest-path runtime-rust/Cargo.toml \
  --features webgpu --example webgpu_integer_eq
cargo build --release --manifest-path runtime-rust/Cargo.toml \
  --features webgpu --examples
DOC_GPU_REQUIRE_HARDWARE=1 DOC_GPU_EXECUTION=gpu \
  runtime-rust/target/release/examples/webgpu_bool --staged-repair
```

The native Goose counterpart is in `runtime-goose/doc_typed.goose` and
`runtime-goose/doc_sdl3_gpu.goose`. Goose GPU dispatch uses its **own SDL3
gfx** backend, not a Rust bridge or DOC-owned WGSL generator. See
[`runtime-goose/README.md`](../runtime-goose/README.md).

## Evidence and remaining acceptance gates

The last checked full seven-job standard CI success was
[run 44980780808](https://github.com/x0796666-ui/DOC/actions/runs/44980780808)
at `d76bebc5db3d`; later source revisions require fresh *executing* job
evidence. More recent GitHub Actions runs recorded zero runner job steps and
cannot be treated as correctness regressions or passes.

The local-agent branch added actual AMD Radeon 860M (RADV Vulkan) Rust adapter
logs, native Goose SDL3 Vulkan outputs, 77 Goose checks and 42 matching
independent Rust/Goose GPU episodes, now merged in
[commit 831d6f6](https://github.com/x0796666-ui/DOC/commit/831d6f65191ee071052a2ca5804bfaa283280eb5).
The Goose logs **do not identify the selected Vulkan GPU model** and the
host also enumerated software llvmpipe, so Goose's physical GPU identity needs
a controlled-device rerun. See [local evidence](../local-evidence/README.md),
[offline audit](../ci/verify-local-gpu-evidence.py), and
[the local test harness](../ci/physical-vulkan-dual-parity.sh).

Production acceptance still requires broader typed error/effect semantics,
complete graph-version and lifetime contracts in **both** runtimes,
stale-work/eviction/reconstruction and Goose pool-reuse safety, long concurrency
and memory soaks, placed transport/fail-stop policy, installation/release
artifacts, and matched raw performance distributions.

Track implementation and hardware follow-up in
[secondary handoff #1](https://github.com/x0796666-ui/DOC/issues/1),
formal acceptance in [canonical #7](https://github.com/imxade/DOC/issues/7)
and experimental evidence in [canonical #9](https://github.com/imxade/DOC/issues/9).
The historic C++ witness and published benchmark numbers remain archived
research evidence only, not a dependency or current native runtime baseline.
