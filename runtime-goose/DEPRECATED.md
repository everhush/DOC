# DEPRECATED — historical native Goose runtime (2026-11-23)

**Not part of the current DOC runtime, Linux release, CI acceptance, physical GPU conformance, or upcoming game-engine implementation.**

The user explicitly chose Rust-only active development. Existing Goose source, standalone SDL3/`gfx` GPU code, W1 experimental C ABI bridge, oracles, tests, and archived evidence remain here **unchanged for historical reference**. They are **not maintained as feature-parity or GPU-runtime obligations**. Do not delete this directory, attempt a silent Rust-powered Goose adapter, or claim it is a current production implementation.

The official current implementation is `runtime-rust/`, with one authored DOC language and explicit CPU/`wgpu` GPU selection. The initial target is Linux x86_64 only. The game engine will be written using DOC semantics targeting Rust, not a second Goose application. Any future resurrection of the Goose target requires separately scoped work and verified CI.

Previous commits and issue comments documenting dual-runtime findings are historical and remain intact. New release claims must cite **Rust-only exact-SHA** execution and physical GPU evidence.
