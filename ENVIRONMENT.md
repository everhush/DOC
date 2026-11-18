# Development environment and verification

The active DOC project targets two first-class runtime implementations: **Rust** and **Goose**, with one independent general-purpose DOC language and shared conformance tests. The precise compiler versions, reproducible installation, supported operating systems and local build/test recipes must be recorded after each backend actually compiles.

## Observed blocker (2026-11-18)

At the last recorded automation checks, the execution environment did **not** have `rustc`, `cargo`, or the Goose compiler, and did not expose a local checkout; GitHub DNS was unavailable from the isolated shell. Native execution, memory-safety tests and Rust-versus-Goose measurements were **not run**. Connected GitHub repository read/write tools do not themselves supply a compiler.

Do not use GitHub Actions (quota exhausted); use verified local toolchains. No C++ compiler, CMake or C++ reference implementation is required by the new DOC language or either runtime.

The source paper may be built separately with an appropriate Typst installation. The historical C++ research environment and the numerical evidence cited by the submitted paper are available only from the immutable [pre-Rust snapshot](https://github.com/imxade/DOC/tree/snapshot-2026-11-17-pre-rust-runtime), not the current runtime source tree.
