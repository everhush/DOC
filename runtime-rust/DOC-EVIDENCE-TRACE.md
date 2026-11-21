# DOC model/implementation/evidence trace — secondary development

This is a qualification ledger, not a substitute for the main paper.
Canonical model and calculus are unchanged.

| Contract | Rust realization | Goose realization | Qualification |
|---|---|---|---|
| Typed acyclic state graph | src/lib.rs | doc_typed.goose | Native tests and cross-runtime oracles |
| Private same-pre-valuation ready frontier | Runtime.step | stabilize | Finite conformance and randomized tests; proof is in paper |
| Source authority + cutoff | Runtime.update | update | Differential and failure tests |
| Finite demand | demand_requested | demand | Ancestor-closed test suite |
| Typed forward recurrence | src/recurrence.rs | run_recurrence | Two-counter, factorial, list fold, graph traversal, text |
| Large natural values | src/nat.rs | immutable Goose digit pool | Hundreds of digits and long finite prefixes |
| Structured and typed absence values | Ints,MaybeInt,Text | independent owned pools | Cross-runtime sorting, safe lookup, Unicode |
| Function/module composition | bounded elaboration | bounded iterative expansion | Same-source function and import oracles |
| Read and write effect boundary | typed read, staged output | typed read, atomic native write | Invalid path/partial computation tests |
| Compatible immutable graph generations | Runtime.replace_graph | private candidate validation | Old/changed authority and failure tests |
| Safe active readers | Rust pinned Arc snapshots | Goose copied thread values | Tested bounded cases; full parity OPEN |
| Evicted committed epoch reconstruction | Rust fact-log replay | NOT YET GENERAL | Goose remains OPEN |
| Automatic pool compaction | Rust ownership | Goose nat/ints/text pool compaction | Current roots and tested recurrence; full leak/pin proof OPEN |
| Automatic CPU parallelism | Rust workers | Goose scalar frontier queues | 1/2/4 workers; typed/general worker placement OPEN |
| DOC-to-WGSL | src/wgsl.rs | independent native Goose emitter | Restricted Boolean/signed comparison subset |
| Real WebGPU device execution | Rust wgpu host | Rust host executes Goose WGSL | Software Mesa success; Goose-owned WebGPU OPEN |
| Physical/browser WebGPU | opt-in hardware CI | same emitter, host external | Hardware SKIPPED, browser UNVERIFIED |
| Native release install | Rust Linux archive | Goose Linux archive | Extract/run CI green; other OS OPEN |
| Same-source matched benchmarks | Native Rust | Native Goose | 546 CLI raw samples, 186 worker samples; no speedup theorem |
| DOC-native playable game | NOT IMPLEMENTED | NOT IMPLEMENTED | Planned only after both runtimes and WebGPU |

**Priority open gates 1–4:** stable source/IR spec and full expressive
application tests, complete finite theorem-facing conformance, complete
safe physical realization and generation races in BOTH hosts, Goose
general typed worker transport and independent WebGPU device dispatch,
actual physical/browser GPU plus loss/recovery, fuzz/soak/portability,
and production releases. See primary issue #7 acceptance and #9
evidence ledger. Do not convert code presence into a PASS status.
