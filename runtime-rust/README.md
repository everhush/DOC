# Rust DOC calculus and finite-kernel runtime

This is a correctness-first executable implementation of the **finite acyclic DOC kernel**, not a complete implementation of the extensions and not a production-ready or HVM-compatible machine.

## Commands

    cargo test --manifest-path runtime-rust/Cargo.toml
    cargo run --manifest-path runtime-rust/Cargo.toml --bin doc -- runtime-rust/examples/repair.doc a=4 b=1
    DOC_WORKERS=1 cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench
    DOC_WORKERS=4 cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench

No external crates. Source language: signed 64-bit integers, booleans, pure literals and formal premise variables, add/sub/mul/eq/if. Declarations in the text syntax appear in topological order; library graphs accept any finite acyclic order.

Programmatic source updates validate fully before changing values. Every legal nonempty ready-frontier subset evaluates from one settled valuation; successful candidates publish at a logical barrier. Sound exact cutoff suppresses propagation, and always-propagate is a conservative alternative. The finite-kernel theorem assumes total functions: a checked integer overflow reports a failed evaluation before publication and is not a proved total DOC value.

Parallel evaluation currently launches scoped OS threads for wide frontiers. It needs an amortized pool and extensive profiling. The smoke benchmark is NOT comparable to HVM or the preserved C++ campaign.

## Remaining work

- Versioned recurrence, finite demand support, retention and carry.
- Graph-version replacement with observational compatibility.
- General typed value domains and physical pin/evict/reconstruct obligations.
- Placed/distributed execution, resource changes and fail-stop recovery.
- Typed result values for errors, effect boundary, resource controls.
- Fuzzing, model-checking, concurrent mutation boundary tests, cancellation and CI security review.
- Compiler optimizations, persistent scheduler, reproducible matched baselines and HVM comparison.

See paper-calculus/dependency-oriented-calculus.typ for the draft calculus. No existing journal manuscript files have been edited.
