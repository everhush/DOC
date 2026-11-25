# Rust-only complexity audit and protection ledger

**Status:** implementation and scope inventory; **NOT a completed four-pass acceptance or a performance measurement**. Binding Linux x86_64 initial target. Old Rust/Goose double-implementation requirements have been superseded by the explicit user decision on 2026-11-23. Retained Goose source is deprecated and not built or shipped.

## Audit baseline and evidence boundaries

- Historic two-runtime source baseline: `8eb6a5e095581f0bcaac0e4d734243fd3ad221e3`, before current Rust-only CI; separate old 5/5 success on `e0f523d` is historical, not evidence for the current branch.
- Rust WGSL instruction architecture source: `ffa699a2` adds a typed Rust bytecode encoder and reusable WGSL pipeline, `8e490cc` adds a one-pipeline regression.
- Deprecation + Rust-only CI source: `1b120c2a` drops the Goose CI jobs, preserves `runtime-goose/DEPRECATED.md` with historical tests.
- Rust-only hardware artifact/provenance source: `2260ca8f` removes Goose artifact, Xvfb and SDL3 packaging requirements from Kaggle and changes result gates to Rust-only.
- Strict physical adapter/proof source: `49ff9f6c` adds software-only rejection and exact once-per-device Rust WGSL kernel provenance.
- Current workflow source changes require **new exact-SHA Rust CPU + WebGPU software-adapter and physical hardware execution**. Until they pass, no new accepted performance, memory or release conclusions.

## Surviving Rust/general infrastructure candidate decisions

| Candidate | Decision | Safety/proof state |
| --- | --- | --- |
| R1 duplicated GPU shader preflight and per-stage WGSL compilation | CONSOLIDATED in source. Rust GPU preflight stores IDs/typed eligibility; WGSL now one compiled reusable pipeline per device. | Source and CI marker added; exact-head compilation/GPU parity/compile-count evidence pending |
| R2 duplicated recurrence CLI parsing | CONSOLIDATED in earlier Rust change. | Typed authority tests previously added; exact-head regression pending |
| R3 incorrect 16 KiB text diagnostic | CORRECTED: integer byte-length overflow, not a real 16 KiB limit. | Large UTF-8 and diagnostic boundary differential tests remain required |
| R4 scoped worker spawn and task copies | KEEP currently: scoped threads, hardware-limited adaptive task grain and ownership barrier. | Prior two-logical-CPU benchmark showed negative and positive changes; do not invent a stable speedup; pool reuse needs new measurements |
| R5 language and GPU limits | KEEP when structural/resource/device safety proof applies; review arbitrary parser limits separately. | Bounds are not an artificial CPU/GPU worker quota; boundary stress remains open |
| R6 graph candidate revalidation | KEEP while public graph mutation may bypass constructor invariants. | Before removing, prove private/immutable validated graph representation and stale-reader concurrency |
| R7 repeated shader pipelines/readbacks | PARTIALLY CONSOLIDATED: Rust shader compiled once. | Repeated frontiers still allocate buffers and block on validated readback; cache only after actual safe lifecycle and benchmark proof |
| R8 retained readers, generation snapshots, memory reclamation | KEEP until equivalent safe replacement demonstrated. | Must test pinning and lifetime across source/graph epochs, panic/device loss and concurrent readers |
| C1 Kaggle authentication duplication | CONSOLIDATED earlier to production/shared credential parser. | No secret publication, read-only preflight, 0600 credentials and exact-SHA guarantee retained |
| C2 CI YAML size and duplicative jobs | CONSOLIDATED 5→2 mandatory Rust jobs; keep separate software and physical GPU evidence. | CI runner acceptance on latest SHA is still pending |
| C3 Kaggle dataset status/mount retry state machine | KEEP: exact SHA/bundle SHA256/verified authenticated private dataset download and narrowly scoped retry are integrity/security obligations. | Failure injection and notebook run required |
| C4 historical helper binaries/fixtures | KEEP as non-shipping reference oracles, with release packaging strictly limited to Rust binaries and vetted DOC fixtures. | New scope static test checks no deprecated Goose artifact leakage |

Goose G1–G11 proposals are **ARCHIVED/not planned** in the current release. No elimination of historical test oracles or attribution. Issue #18 is closed not planned because Goose was retired, not because its WebGPU API ever worked.

## Four-pass acceptance protocol on final SHA

A new source revision resets the audit ledger. To close #15 after code convergence, complete and record **four distinct reviews of the same final SHA**: (1) Rust language/typed semantics and GPU lowering; (2) memory and concurrency/resource ownership; (3) physical Vulkan + software oracles/failure modes and measured before/after costs; (4) CI/artifacts/packaging/security/evidence consistency. A newly found defect or source mutation resets the count. Do not close by asserting unexecuted benchmarks, a fixed line-count reduction, or obsolete dual-runtime evidence. Preserve raw files in Actions artifacts, not as new Git source data.

Pending acceptance specifically requires Rust source tests, negative property tests, device-readback failure and loss, real Kaggle GPU selected-DOC execution, CPU/oracle equivalence, memory/resource stress, and Linux release artifact smoke. See `docs/RUST-ONLY-ACCEPTANCE.md`.
