# DOC Rust-only non-game release acceptance (binding scope, 2026-11-23)

This supersedes *dual-runtime* acceptance in older historical documentation and tracks the user-approved Rust-only release. Historical Goose source is preserved under `runtime-goose/` with a deprecation marker, but is not built, tested or packaged as an active DOC backend.

## Hard gates before game issue #10

1. **Rust language and semantics:** Directly authored general-purpose DOC programs in `runtime-rust` must parse/typecheck and support useful functions/modules, typed structured data and text, explicit effects, finite incremental graph repair, exact cutoff, demand, signed/large naturals where supported, recurrence with finite requested-prefix, graph replacement, protected readers, and deterministic publication/recovery. Run robust positive/negative, property/stress, invalid-input, device/CPU failure and memory/retention tests. **GPU need not run host I/O or every general-purpose operation inside a shader**; unsupported GPU operations must strictly reject.
2. **Rust CPU:** `doc FILE.doc` defaults to CPU; `--backend=cpu` is explicit and results agree with an independent mathematical/source oracle. Dependence-ready concurrency discovers host logical hardware without artificial thread caps, but skips unprofitable small tasks. Preserve deterministic ordering, atomic result publication, exact cutoff, no races and fail-stop behavior.
3. **Rust wgpu:** `--backend=gpu` uses actual wgpu/WGSL compute for its **documented eligible pure DOC fragment**, rather than silently running it on CPU. Validate eligibility, device limits, full typed readback, complete stage/epoch publication and source-update/recurrence parity on same source. Reuse compiled WGSL kernels where measured and correct. Genuine GPU device-loss and memory exhaustion tests, injected failures, and unsupported input rejection must not leak partial state.
4. **Exact-SHA Linux CI:** Rust native CPU and WebGPU software-adapter jobs build from a clean checkout; source/negative tests, parser/effects, graph/epoch/demand/recurrence, memory/concurrency and release/install smoke checks pass. Software WebGPU execution is **never** a hardware performance claim. Preserve failed and raw logs, checksums and binary provenance.
5. **Physical hardware and benchmarks:** a separate Kaggle physical GPU (for example the Kaggle T4) through WebGPU job must verify the SHA-pinned CI-built Rust artifact and hash; detect physically attached adapter and driver, execute the authored DOC GPU source and independent Rust CPU oracle, verify 1/multiworkgroup and recurrent workloads, report failures and reproducible CPU/GPU comparisons with negative speedups. Kaggle quota is external; no DOC-added artificial session limits. **Detected T4 hardware alone is not a DOC GPU execution pass.**
6. **Release readiness:** Linux x86_64 installable Rust CLI, usage docs, dependency/known-unsupported matrix, error/ownership/resource contract, benchmarks, model-paper/source claim trace, immutable source SHA and durable evidence record. Issue #14 governs any later separately approved public repository; do not rewrite development history or discard prior Goose results.

## Scope / issue mapping

- **#7** = Rust DOC general-purpose/runtime/lifetime/parallelism gate. Retire Goose dual-parity requirements prospectively.
- **#15** = Rust-only source/CI/runtime simplification and safety audit. Goose remediation proposals are archived and no longer blockers. Keep meaningful Rust constraints and record same-SHA reviews/metrics.
- **#17** = Rust `wgpu` + WGSL only, no extra DOC API selector. Goose Dawn/SDL/FFI migration is canceled prospectively. Actual GPU result proofs still required.
- **#9** = Rust-only current physical GPU and benchmark evidence, historical dual-runtime records unchanged.
- **#10** = DOC-authored Rust-target game engine. **Do not start before required gates are supported by raw exact-SHA evidence.**

Current status on the date of this scope decision: **NOT YET SIGNED OFF**. Keep gaps visible; deprecating Goose is not itself proof of Rust completeness.
