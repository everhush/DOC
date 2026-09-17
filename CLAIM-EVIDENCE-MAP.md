# DOC claim-to-evidence map — active Rust + Goose project

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
| Boolean WGSL placement and differential evidence | A pure, total Boolean subset runs on Vulkan software compute | 130 native WebGPU outputs matched the DOC CPU evaluator | The independent native Boolean evaluator matched all 130 outputs against the same DOC source and inputs. Goose shader lowering and dispatch are not implemented |
| Ancestor-closed demand | Demand-restriction theorem | Not implemented | Not implemented |
| Typed forward recurrence, finite prefixes, retention, divergence | Separate recurrence extension | Not implemented | Not implemented |
| Universality with unbounded values and recurrence | Paper's two-counter-machine simulation argument; **not** a property of one finite graph | No executed language-level demonstration | Not implemented |
| Immutable compatible graph-version replacement | Conditional graph-version contract | Not implemented | Not implemented |
| Safe physical realization: immutable complete values, pinning, reclamation, reconstruction, generations | Normative realization contract under progress assumptions; **not** core finite theorem | Not implemented | Not implemented |
| Placement, transport, resource join/drain and bounded fail-stop recovery | Conditional placed-realization assumptions, no consensus/partition-tolerance claim | Not implemented | Not implemented |
| Explicit effect and nondeterminism boundary | Paper's policy boundary | Not implemented | Not implemented |
| Sparse/dense repair performance, capacity scaling, negative controls | Historical empirical claim on specific hardware, not universal | No matched measurements | No matched measurements |
| General-purpose usable language and independent binary/runtime toolchains | New product acceptance goal, not a theorem of the original finite calculus | Not established | Not established |

See [MODEL-REQUIREMENT-TRACE.md](MODEL-REQUIREMENT-TRACE.md) for a detailed **paper-ordered audit worklist**. Each future positive result must include tested revision, actual commands and raw evidence. Record comparative benchmarks in [issue #9](https://github.com/imxade/DOC/issues/9). For the current finite-subset build, exact revision, commands and adapter evidence, see [secondary validation run 44550920946](https://github.com/x0796666-ui/DOC/actions/runs/44550920946). Full production and cross-runtime conformance gates remain open.
