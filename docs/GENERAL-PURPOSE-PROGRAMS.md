# DOC general-purpose source-program inventory and semantic baseline (Issue #10)

**Target:** Current Rust-only DOC evaluator, Linux x86_64; optional strict WGSL/WebGPU pure-compute fragment. This is the **source-language baseline for the future Issue #11 compiler**, not an AOT implementation or a claim of all-purpose language completeness. The implementation and tests, not this document, are normative evidence.

## Existing runnable independent source families

| General software need | Direct DOC source / independent tests | Scope and limits |
| --- | --- | --- |
| Signed arithmetic, checked failures, booleans and branching | `examples/typed_arithmetic.doc`, `boolean_conditional.doc`, `tests/semantics.rs` | Integer i64/Boolean; overflow rejected rather than wrapped |
| Arbitrary natural numbers, simple arithmetic and recurrence | `factorial_nat.doc`, `functions_nat.doc`, `tests/nat_recurrence.rs` | Native CPU big-natural domain |
| Functions, pure modules and typed arguments | `functions_int.doc`, `module_clamp.doc`, `tests/functions.rs`, `tests/modules.rs` | Bounded source expansion; not unrestricted recursive functions or generic polymorphism |
| Dynamic integer collections, indexing, immutable updates | `list_fold.doc`, `safe_index.doc`, `tests/dynamic_lists.rs`, `tests/safe_maybe.rs` | `ints`, `maybe_int`, `append`, `tail`, `get`, `try_get`, `remove_at`, `replace_at`; no heterogeneous maps/records |
| Text and source updates | `text_program.doc`, `text_recurrence.doc`, `tests/utf8_text.rs` | UTF-8 byte-length, concatenation, prefix; no full text processing/regex standard library |
| Sorting and finite searching | `sort4_int.doc`, `sort4_nat.doc`, `search_list.doc`, `tests/sorting.rs`, `tests/general_search_doc.rs` | Sorting example is fixed four-value network; finite list search advances through DOC recurrence |
| Demand and incremental state changes | `demand_lazy.doc`, `repair.doc`, `tests/demand.rs`, `tests/source_epochs.rs` | Versioned graph and source operations; demand is ancestor-closed |
| Recurrent algorithms and stable snapshots | `recurrence_facts.doc`, `list_fold.doc`, `tests/recurrence.rs`, `tests/recurrence_checkpoint.rs` | Epoch-local external facts; explicitly carried sources persist; new `current_source_facts` and `fork_current` provide *in-memory* typed checkpoint and logical fork, plus a bounded v1 schema-checked on-disk checkpoint, fresh-epoch restore and corrupt-file rejection (current exact CI pending) |
| File-backed typed data/effects | `effect_demo.doc`, `tests/effects.rs`, `tests/output_effect.rs`, `engine/prefab_scene.doc` | Confined typed source facts and output; generational bounded data resource handles and real PCM WAV file effect added (current CI pending); no live speaker mixer or reversible committed external effect |
| Parallelism, atomic failure and resource lifetime | `parallel_frontier.doc`, `tests/engine_foundation_safety.rs`, `tests/published_lifetime.rs`, `tests/publication_stress.rs` | Actual bounded worker and failure tests; scheduling algorithm remains host runtime responsibility |
| Stateful 2D/headless domain application | `engine/coin_chase.doc`, `engine/entity_scene.doc`, `engine/prefab_scene.doc` and engine tests | DOC owns gameplay and component decisions; capped prefab instances and explicit typed reload; no general ECS/3D/editor |

## Current typed execution contract (canonical DOC-TYPED-IR/1 handoff)

- **Value domains:** `int` (checked signed i64), `bool`, canonical `nat`, `ints`, `maybe_int`, `text`. Each source and derive is statically typed. Graph parsing rejects unknown types/functions, incompatible branches/premises, name collisions and cycles.
- **Graph:** `source` supplies a typed value; `derive` declares typed premises and a pure expression. The frontend validates a DAG, and a native runtime executes ordered dependency frontiers, cutoff/invalidation and complete stable publications. Failed candidates do not replace the last valid generation. The current `Graph`/`Expr` Rust structures remain the reference representation; `runtime-rust/src/typed_ir.rs` exports canonical, checked `DOC-TYPED-IR/1` according to `docs/DOC-TYPED-IR-V1.md`. This is not a C ABI or an AOT implementation.
- **Evaluation and effects:** The source `if` expression is branch-lazy. Typed `effect NAME: TYPE = read("path")` reads confined data once when the graph is constructed. Explicit output effects run after stabilization; no I/O inside pure frontiers. Unsupported operations are errors, not hidden fallbacks.
- **Recurrence:** Forward carries grant exclusive authority over named sources; all ordinary externally supplied facts apply to **only one epoch**, and a failed epoch does not advance. In-memory and disk typed checkpoint restoration starts at fresh epoch 0, captures only stable latest source values and never replays external effects or claims historical epoch transfer.
- **Placement:** CPU is default. Explicit `--backend=gpu` admits only validated eligible pure WGSL work; unsupported graph language/effects do not execute on CPU under the guise of GPU success. Mesa software validation and a physical GPU have separate evidence classes.

## Important gaps: do not silently call these implemented

- General user-defined records/structs, maps/dictionaries, parametric container types, unbounded recursive calls, generalized file streams/network sockets, an event loop as a first-class language primitive and a large built-in standard library.
- Arbitrary scene hierarchies/archetypes and dynamically typed prefab schemas; current prefabs are aligned bounded integer coordinate columns, with explicit source-driven replacement.
- Checkpoint *version migration*, OS-event-driven asset watch/reload, actual live speaker playback/mixer, and external device-lifetime proof. The implemented audio adapter writes valid PCM WAV files only.
- Final exact-HEAD CI measurements and production tuning; benchmark instrumentation now reports cold graph evaluation allocation requests/quantiles and live DOC game step latency/process RSS, distinct from true heap retention and physical GPU.
- IR **reader/optimizations**, C codegen, standalone compiled DOC binaries and self-hosting belong to Issue #11. A v1 textual typed AST exporter and semantics specification are Issue #10 compiler-preparation, not work begun on #11.

## Reproduction

From repository root on Linux:

```sh
cargo test --manifest-path runtime-rust/Cargo.toml --all-targets
cargo run --manifest-path runtime-rust/Cargo.toml --bin doc -- runtime-rust/examples/search_list.doc --until=done --max-epochs=10 remaining=next_remaining index=next_index found_at=next_found_at needle=next_needle
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_prefab_doc
cargo test --manifest-path runtime-rust/Cargo.toml --test recurrence_checkpoint
cargo test --manifest-path runtime-rust/Cargo.toml --test recurrence_disk_checkpoint
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_save_resume
cargo test --manifest-path runtime-rust/Cargo.toml --test data_resources
cargo test --manifest-path runtime-rust/Cargo.toml --test audio_output
cargo test --manifest-path runtime-rust/Cargo.toml --test typed_ir_contract
```

**Evidence rule:** A committed test or listed command is not a pass. Check the exact feature SHA's GitHub Actions Rust and separately labeled WebGPU jobs; report physical-GPU evidence only from actual device execution. Issue #10 remains open for non-deferred gaps.
