# DOC — Dependency-Oriented Computation

**Current target: one Rust runtime, Linux x86_64, WebGPU/WGSL for selected GPU computation.**

DOC is a typed dependency-graph programming model for incremental repair, exact
cutoff, demanded evaluation and explicitly controlled effects and recurrence.
The canonical research ledger and active development are in this private repository, [imxade/DOC](https://github.com/imxade/DOC), on `master`. The designated CI-only fork is `xad3play/DOC`; synchronize it from upstream after verifying private access and fork identity. No fork-only engineering commits. The former development repositories are historical only. See [migration and batch-validation policy](docs/DEVELOPMENT-MIGRATION.md).
See [migration provenance](docs/PUBLIC-MIGRATION.md) and [Radar Chase](engine/RADAR-CHASE.md).
Issue #22 and #21 have passed. #24 closed on 11e22c4; #15 is the active pre-self-hosting conformance gate. See [Stage-0 native C compiler](docs/DOC-AOT.md), [current #15 conformance ledger](docs/PRE-SELF-HOSTING-AUDIT.md), and [independent runtime reservation](runtime-doc/README.md). Rust freezes only after #15 acceptance; all subsequent #11 implementation belongs in runtime-doc/.

## Active and archived implementations

- `runtime-rust/` is the **only active** DOC CPU runtime and GPU implementation.
  CPU is the standalone CLI default; the WebGPU-capable game host uses automatic dependency-frontier placement. `--backend=gpu` requests the actual Rust `wgpu`
  provider with WGSL; no DOC-level graphics API selection, direct driver
  configuration, or implicit CPU fallback is permitted in explicitly selected GPU mode. Auto mode reports CPU-only placement when no usable GPU is available.
- `runtime-goose/` is **deprecated historical source**, not built, shipped,
  tested as release acceptance, or required for game-engine issue #10. See
  [DEPRECATED.md](runtime-goose/DEPRECATED.md). Older dual-runtime claims and
  measurements remain in Git history and issue comments for provenance.

The code does **not** directly invoke platform graphics APIs. The native
GPU implementation `wgpu` chooses a compatible underlying provider and
driver. Runtime and tests use only the exposed WebGPU adapter/device,
pipeline, workgroup and storage APIs. The physical-GPU gate accepts actual
discrete/integrated adapters and rejects CPU/software adapters unless a
clearly labeled software-only **test** is explicitly enabled. This says
nothing about other host platforms being supported by the DOC CLI.

## Run directly authored DOC programs

```sh
cargo build --release --manifest-path runtime-rust/Cargo.toml --bin doc
runtime-rust/target/release/doc runtime-rust/examples/repair.doc --backend=cpu

cargo build --release --manifest-path runtime-rust/Cargo.toml --features webgpu --bin doc
runtime-rust/target/release/doc runtime-rust/examples/boolean_staged.doc --backend=gpu
```

For CPU, `--backend=cpu` can be omitted. For GPU, an explicitly selected,
physically supported WebGPU adapter is required. Only the documented
pure, bounded Boolean and signed-integer DAG fragment runs inside current
WGSL compute. Source imports/effects, heterogeneous structures, unsupported
large integers and arbitrary graph functions are **not** silently run as
GPU shaders. GPU-facing failures must leave no partially published DOC state.
The host remains responsible for source authority, effects, dependent
frontier barriers, recurrence epochs and resource lifetimes.

## Tests and acceptance

- [Linux Rust CI](.github/workflows/doc-validation.yml):
  exact-source Rust language/safety tests plus labeled **WebGPU
  software-device** correctness and release-package checks.
- [Physical accelerator CI](.github/workflows/doc-kaggle-gpu.yml):
  checks private exact-commit artifact hashes and runs real Rust wgpu
  computations with physical WebGPU adapter-class verification and same-source
  CPU/oracle comparisons. It uses **no native graphics API probes or
  driver-specific overrides**. A requested accelerator alone never counts.
- [Backend contract](BACKEND-EXECUTION-CONTRACT.md),
  [Rust-only acceptance checklist](docs/RUST-ONLY-ACCEPTANCE.md),
  [GPU instruction ABI](docs/GPU-INSTRUCTION-ABI-v1.md),
  [complexity audit](docs/RUST-ONLY-COMPLEXITY-AUDIT.md).

**Release and game-engine readiness are not implied by a green CPU job or
an available accelerator.** Issues [#7](https://github.com/imxade/DOC/issues/7),
[#9](https://github.com/imxade/DOC/issues/9),
[#15](https://github.com/imxade/DOC/issues/15), and
[#17](https://github.com/imxade/DOC/issues/17) track the remaining verified
Rust-only gates. [#10](https://github.com/imxade/DOC/issues/10) begins only
after the accepted source SHA, runtime semantics, physical GPU computation,
and Linux release evidence are jointly signed off.

## Licensing

Copyright (c) 2026 Rituraj Basak. The research paper, reports and documentation
are licensed under CC BY 4.0. Original software is additionally available
under Apache 2.0; recipients may choose that license for the software.
See [license scope](LICENSE), [Apache 2.0 license](LICENSE-APACHE), and
[attribution notice](NOTICE). Existing CC BY 4.0 grants and third-party
licenses remain in effect.
