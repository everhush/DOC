# Rust DOC runtime — incomplete finite-kernel prototype

This package is a preliminary interpreter for a **finite typed acyclic DOC graph**, **not** a production-ready general-purpose language or the complete DOC paper's extensions. The required independent Goose backend is not yet implemented.

The minimal current source format accepts typed `source` and `derive` declarations with ordered premises, literals/variables, integer addition/subtraction/multiplication, equality and conditional expressions. Its active-set repair, sound exact/conservative cutoff and ready-frontier parallel path are source-level implementations but **have not yet been compiled or tested natively** in the current environment. Checked `i64` overflow aborts frontier publication; it is not a total result value and falls outside the paper's pure-total theorem.

When a working toolchain and checkout exist, the unverified smoke commands are:

```sh
cargo fmt --manifest-path runtime-rust/Cargo.toml --all -- --check
cargo test --manifest-path runtime-rust/Cargo.toml --all-targets
cargo run --manifest-path runtime-rust/Cargo.toml --bin doc -- runtime-rust/examples/repair.doc a=4 b=1
DOC_WORKERS=1 cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench
DOC_WORKERS=4 cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench
```

These commands are proposed validation, **not** reported passing. Current parallel execution launches scoped threads for wide frontiers; it lacks a persistent worker pool and production profiling. The preliminary benchmark is not comparable to the manuscript's historical measurements or to Goose.

The goal is **one original, minimal-core, general-purpose DOC source language** running independently under safe Rust and safe Goose, including the model's qualified demand/recurrence universality, immutable graph evolution, safe materializations, placed execution and effects, plus common executed conformance tests. Read [MODEL-REQUIREMENT-TRACE.md](../MODEL-REQUIREMENT-TRACE.md) for every acceptance boundary and [issue #9](https://github.com/imxade/DOC/issues/9) for benchmark records.

Submitted paper sources and their historically reported C++ experimental evidence are preserved unchanged; that earlier implementation is archived solely in the pre-Rust snapshot and is **not** a build or verification dependency of this crate.
