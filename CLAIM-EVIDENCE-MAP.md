# DOC claim-to-evidence map

## Active scope reconciliation — 2026-11-25

The following legacy dual-runtime tables and historical explicit-only GPU descriptions are retained for provenance and must not be read as the current acceptance record. The active reference is Rust on rtu0/doc2/main, with generated WGSL, automatic CPU/GPU placement in admitted host entry points and strict explicitly selected GPU execution; see [BACKEND-EXECUTION-CONTRACT.md](BACKEND-EXECUTION-CONTRACT.md). Goose is archived, not an acceptance requirement. #24 closed on 11e22c484a35a183ed9f77a2125afa5f22746c41; #15 reviews that combined foundation before the independent #11 handoff. The normative paper and original C++20 empirical results are unchanged. See [current #15 conformance ledger](docs/PRE-SELF-HOSTING-AUDIT.md) for current source-linked decisions, gaps and explicit production obligations. No claim of universal conformance or inherited empirical speedup.

---


## Current Linux x86_64 acceptance ledger (2026-11-23; feature SHA `82d739eb1bdb6f3052d47f392c4459a6d5220b03`)

**This section supersedes older implementation-status statements and old-fork CI blocker descriptions below; historical records are retained for provenance, not treated as current signoff.** Active source and CI: private [rtu0/DOC feature branch](https://github.com/rtu0/DOC/tree/feat/webgpu-dual-runtime-ci); `master` and canonical [imxade/DOC](https://github.com/imxade/DOC) are not automatic release targets. The only initial host target is Linux x86_64.

- **Executed software validation:** exact feature-SHA [push 45081374463](https://github.com/rtu0/DOC/actions/runs/45081374463) and [PR 45081379899](https://github.com/rtu0/DOC/actions/runs/45081379899) each completed **five successful native Linux jobs with executed steps**: Rust typed/finite/WGSL, Goose CPU/differential, Rust wgpu Mesa, Goose native SDL3 gfx Mesa, and independent GPU-result parity. This proves those tested programs and software Vulkan adapters, **not physical GPU acceleration** or complete language semantics.
- **Selected GPU subset:** Both independent native CLIs accept explicitly selected GPU execution for admitted pure finite Boolean/signed-i32 source DAGs, including bounded nested arithmetic and independent ready-frontier workgroups; unsupported source/device paths must fail closed. Rust uses wgpu; Goose uses SDL3 gfx Vulkan, **not** Rust dispatch or a Goose WGSL generator. The 128-independent-node case uses two 64-thread workgroups. GPU recurrence, heterogeneous dynamic values, arbitrary graphs/effects, device-loss recovery and complete general-purpose coverage are **OPEN**.
- **CPU scheduling:** Hardware-aware ready-frontier scheduling is implemented independently in Rust and Goose. The executed 512-node oracle covers worker requests 1/2/4/8/17/auto with hardware-bound effective workers. Three-trial, two-logical-core whole-CLI medians at this SHA: Rust 1=1.827508 ms, auto=1.862291 ms; Goose 1=3.476167 ms, auto=3.950140 ms. These are workload-specific and show **no speedup** for auto on this cheap workload; they are not isolated kernel timings.
- **Physical GPU is INFRA_BLOCKED:** [Kaggle 45081722864](https://github.com/rtu0/DOC/actions/runs/45081722864) verified private exact-byte binary transport and requested NvidiaTeslaT4, but the notebook had zero NVIDIA device nodes, no NVIDIA kernel driver, no CUDA driver library, and zero Torch CUDA devices. Consequently **no physical Vulkan GPU workload ran**. This is neither a GPU PASS nor an observed runtime shader failure. No DOC-imposed Kaggle quotas, cooldowns, dedup restrictions or session caps apply.
- **Remaining non-game gates OPEN:** full shared typed language/IR equivalence; demand/recurrence and typed failure coverage on selected GPU; graph generations and protected-reader lifetime/reclamation in both runtimes; effect/cancellation/fail-stop and recovery; physical selected-adapter parity and raw benchmarks; Linux native install/release, stress/fuzz and paragraph-level manuscript trace at a final exact SHA. Prior local AMD physical evidence is historical bounded-kernel evidence, not proof of the current feature SHA or general-purpose execution. Canonical [acceptance #7](https://github.com/imxade/DOC/issues/7) and [evidence #9](https://github.com/imxade/DOC/issues/9) remain open; [game #10](https://github.com/imxade/DOC/issues/10) remains deferred. [rtu0 PR #1](https://github.com/rtu0/DOC/pull/1) remains draft.

---


**Execution backend acceptance update (2026-11-22):** CPU is the default for both native general-purpose CLIs, explicit `--backend=cpu|gpu` is strict, and there is no `auto` or silent CPU fallback. The two general-purpose GPU branches currently reject `--backend=gpu`; bounded native GPU parity does **not** establish HVM-like general-purpose GPU execution. See [BACKEND-EXECUTION-CONTRACT.md](BACKEND-EXECUTION-CONTRACT.md). This is a new OPEN implementation/acceptance requirement, not a claim of passing evidence.

**Evidence classes must never be merged:** a paper's theorem argument is not a machine-checked proof; an archived executable witness is not a current runtime; an unexecuted test file is not a passing test; an implementation plan is not evidence of a feature.

The submitted DOC manuscript and its original experimental measurements remain unchanged. The earlier C++20 executable witness, its checker source and raw data are preserved **only** at [`snapshot-2026-11-17-pre-rust-runtime`](https://github.com/imxade/DOC/tree/snapshot-2026-11-17-pre-rust-runtime) and are **not** active code, an execution dependency, or a current baseline.

| Manuscript claim or contract | Formal scope and manuscript support | Rust: current evidence | Goose: current evidence |
| --- | --- | --- | --- |
| Finite repair, admissibility and termination | Finite kernel, paper §§ Core semantics and Central metatheory | Executed finite-subset release build and tests in `runtime-rust` | Native evaluation of one Boolean definition over two named sources; no repair engine |
| Unique stable valuation / schedule independence | Finite pure total typed acyclic theorem argument | `runtime-rust/tests/randomized.rs` and `tests/semantics.rs` compare finite schedules against an oracle | Not implemented |
| Typed atomic source updates and incremental dependency-local propagation | Finite kernel | Finite subset exercised in `runtime-rust/tests/semantics.rs` | Not implemented |
| Exact/conservative sound cutoff and temporal reuse | Finite kernel | Finite subset exercised in `runtime-rust/tests/semantics.rs` | Not implemented |
| Ready-frontier independent evaluation / logical barrier publication | Finite kernel; physical concurrency separate | Scoped-thread prototype exercised by `parallel_matches_sequential` and finite schedule tests | Not implemented |
| Computational expansion/fusion preserves boundary | Conditional boundary-equivalence obligation | Not verified | Not implemented |
| Boolean WGSL placement and differential evidence | A pure, total Boolean subset runs on Vulkan software compute | 130 native WebGPU outputs matched the DOC CPU evaluator | Native Goose emits the Boolean shader from the same DOC source. The shared Rust WebGPU host dispatched it and both CPU oracles matched all 130 readbacks. Goose-owned dispatch, staged workloads and device-loss evidence remain open |
| Ancestor-closed demand | Demand-restriction theorem | Not implemented | Not implemented |
| Typed forward recurrence, finite prefixes, retention, divergence | Separate recurrence extension | `runtime-rust/src/recurrence.rs` checks typed forward carry, epoch-local facts, latest-epoch retention and private commit for bounded values | `runtime-goose/doc_typed.goose` independently evaluates bounded prefixes with template defaults and both use `--through` on shared source. Extensible naturals and divergence evidence remain open |
| Universality with unbounded values and recurrence | Paper's two-counter-machine simulation argument; **not** a property of one finite graph | No executed language-level demonstration | Not implemented |
| Immutable compatible graph-version replacement | Conditional graph-version contract | Not implemented | Not implemented |
| Safe physical realization: immutable complete values, pinning, reclamation, reconstruction, generations | Normative realization contract under progress assumptions; **not** core finite theorem | Not implemented | Not implemented |
| Placement, transport, resource join/drain and bounded fail-stop recovery | Conditional placed-realization assumptions, no consensus/partition-tolerance claim | Not implemented | Not implemented |
| Explicit effect and nondeterminism boundary | Paper's policy boundary | Not implemented | Not implemented |
| Sparse/dense repair performance, capacity scaling, negative controls | Historical empirical claim on specific hardware, not universal | No matched measurements | No matched measurements |
| General-purpose usable language and independent binary/runtime toolchains | New product acceptance goal, not a theorem of the original finite calculus | Not established | Not established |

See [MODEL-REQUIREMENT-TRACE.md](MODEL-REQUIREMENT-TRACE.md) for a detailed **paper-ordered audit worklist**. Each future positive result must include tested revision, actual commands and raw evidence. Record comparative benchmarks in [issue #9](https://github.com/imxade/DOC/issues/9). For the current finite-subset build, exact revision, commands and adapter evidence, see [secondary validation run 44550920946](https://github.com/x0796666-ui/DOC/actions/runs/44550920946). Full production and cross-runtime conformance gates remain open.


## 2026-11-22 current-code evidence update (supersedes stale table cells above)

The original table is a historical implementation snapshot and should not be
read as the current status of Goose: it now has a native typed DOC runtime
(`runtime-goose/doc_typed_core.goose`, `doc_typed.goose`), independent
frontend, ready-frontier repair, demand and typed forward recurrence, exact
arbitrary naturals, functions/modules, collections, UTF-8, sampled file
effects, graph-replacement and protected-reader tests. Rust has corresponding
source and tests under `runtime-rust/`. These bounded executable tests do
**not** establish full general-purpose production acceptance, all schedule
independence theorem obligations, or the conditional safe-realization proofs.

- **Executed secondary CI:** [44980780808](https://github.com/x0796666-ui/DOC/actions/runs/44980780808),
  revision `d76bebc`: seven native CPU, Rust wgpu/Goose SDL3 Mesa Vulkan,
  independent GPU-result parity and native packaging jobs passed. Newer revisions,
  including the physical branch merge, have not yet produced an executing
  seven-job pass due jobs failing before recording steps.
- **Hardware evidence:** Physical local Rust wgpu adapter was AMD Radeon
  860M, IntegratedGpu/Vulkan RADV. Native Goose independently dispatched
  SDL3 Vulkan and returned 77 oracle checks plus 42 matching Rust/Goose
  eq/lt/le episodes. The local machine also enumerated software llvmpipe;
  Goose logs did not identify its chosen physical device. Therefore a
  same-single-device rerun is required before marking *Goose physical
  selection* PASS. This is **not** a failed observed result-parity check.
- **Performance evidence:** local agent reported 31 samples each for Rust
  and Goose 1/2/4 workers (including slower multi-worker cases), and staged
  Rust GPU host timings. The full samples and comprehensive same-hardware
  distributions have not been committed. No speedup is implied.
- **Exact integration provenance:** [831d6f6](https://github.com/x0796666-ui/DOC/commit/831d6f65191ee071052a2ca5804bfaa283280eb5),
  [local hardware evidence index](local-evidence/README.md),
  [new offline log validator](ci/verify-local-gpu-evidence.py). Current
  branch evidence is derived from local-agent submitted text logs; new
  physical device testing must be performed locally.
- **Still not accepted:** complete typed error/effect/cancellation semantics,
  full pinned-reader/eviction/reconstruction and Goose pool-safety lifetime,
  transport, placement and bounded fail-stop policies, distribution packaging,
  exhaustive paper-order implementation trace and production tests.

## 2026-11-22 local acceptance and dual-runtime completion update

Final local validation of Gates 1–8 was executed on the physical development workstation:

- **Gate 1–5 Language, Semantics, Demand, Memory & Effects:** Fully exercised across both
  independent runtimes via `runtime-rust/Cargo.toml` test suite and `runtime-goose/check-doc-typed.sh`
  (`DOC_TYPED_FINITE_PASS`), covering Booleans, checked signed integers, arbitrary naturals,
  UTF-8 text, dynamic collections, safe options, functions, composition, user modules,
  ancestor-closed demand, 2-counter machine simulation, atomic generation switching, pinned readers,
  and sampled file effects (`--emit`).
- **Gate 6 Single Physical GPU Proof:** Ran with Mesa device selection debug
  `DOC_HW_VK_SELECT=1002:1114!`. `local-evidence/forced-hardware/forced-physical-adapter.log`
  proves that exactly one physical Vulkan device was exposed: `AMD Radeon 860M Graphics (RADV KRACKAN1)`
  (vendorID `0x1002`, deviceID `0x1114`, `PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU`). Rust wgpu and Goose
  SDL3 executed under this forced single adapter, producing 42 matching GPU episodes and 77 Goose checks.
  Both `local-evidence` and `local-evidence/forced-hardware` pass `ci/verify-local-gpu-evidence.py`.
- **Gate 7 Benchmarks, Release Packages & Local Verification:**
  - Sample-level CSV benchmark distributions committed in `local-evidence/typed-check/doc-matched-samples.csv`,
    `doc-churn-memory-samples.csv`, and `doc-ready-frontier-workers.csv`.
  - Self-contained Linux release packages `doc-rust-linux-x86_64.tar.gz` and `doc-goose-linux-x86_64.tar.gz`
    built, verified via out-of-tree unpack-and-run smoke tests, checksummed in `local-evidence/release/SHA256SUMS`,
    and uploaded to GitHub release `v0.1.0-alpha.local-acceptance`.
  - Independent local test runner `ci/run-all-local.sh` committed and verified.
  - **Hosted CI Status (BLOCKED / OPEN):** GitHub Actions runs 45036875107 and 45033392874 failed with
    zero executed steps (`steps: []`) in 1–3s across all jobs due to private repository runner quota / billing
    limits on `x0796666-ui/DOC`. Per gate rules, this gate remains OPEN pending repository owner intervention.
  - **Linux initial target:** native Rust/Goose compilation, packaged installation, CPU parity,
    software Vulkan and physical GPU evidence are the platform acceptance gates.
- **Gate 8 Ledger & Signoff:** Machine-readable final manifest published at `local-evidence/final-manifest.json`.

Implementation handoff is [secondary Issue #1](https://github.com/x0796666-ui/DOC/issues/1);
canonical acceptance is [#7](https://github.com/imxade/DOC/issues/7)
and [#9](https://github.com/imxade/DOC/issues/9). The local branch merge
does not close either issue or complete the game engine.

