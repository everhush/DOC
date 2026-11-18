# DOC language and runtime direction

The language, compiler, standard library, and runtime are to be **native Rust implementations**. The user-facing DOC language is its own language: its syntax may be clear, lightweight, and indentation-structured where useful, but it is not a dialect, subset, transpilation target, or compatibility layer of another general-purpose language. There must be no interpreter or scripting-language dependency in the production DOC build or execution path.

The current `runtime-rust/` crate executes only the small finite, typed, pure DOC kernel, with a provisional flat `.doc` text format. That format is not frozen as the final language syntax. A native Rust lexer, parser, type checker, IR, and code generator/interpreter will replace or expand this provisional frontend.

## Desired general-purpose facilities (scoped, independently validated)

- Simple functions, bindings, conditionals, data structures, pattern matching or equivalent decisions, modules, and a small coherent set of primitives.
- Explicitly typed source facts and derived computations, with automatic dependency repair and independently scheduled ready definitions.
- Controlled repetition/recurrence, including bounded and unbounded computation as separately specified extensions; don't misapply the finite theorem to divergence.
- Automatic safe value lifetime, with a future realization contract for physical reclamation and reconstruction, not programmer-visible free calls.
- Host I/O and nondeterminism at **explicit effect boundaries**, never silently inside the pure deterministic definitions required by finite DOC correctness.
- Explicit error and cancellation values / effects. No implicit claim that machine overflow or host exceptions satisfy the total-function premise.
- Compiler and runtime engineering fit for real applications: diagnostics, stable modules and packages, tooling, resource limits, security, concurrency, and eventual distributable binaries.

Use Rust for the implementation, and adopt safety or ownership properties only when they fit DOC's semantics; do not force Rust's source syntax or full borrow checker onto DOC's source language. Do not redefine DOC to include database management, actor supervision, cluster orchestration, or remote-resource APIs merely to make the language general-purpose.

## Verification and evidence

Native compilation and end-to-end runtime execution are mandatory before production readiness. Run tests locally without GitHub Actions: parsing and type checking; independent model and runtime oracles; complete source-to-execution integration; single/multi-core work; memory and concurrency safety; and fair workload-matched performance profiles. Track open gates in issue #7.

The historical C++20 research artifact and its original supporting verification scripts remain preserved for the submitted publication's reproducibility. They are **not runtime or language dependencies** of the new Rust implementation.
