# Experimental DOC Native Runtime Installation

The secondary CI workspace produces Linux native Rust and Goose DOC interpreter archives.
They are independently authored in Rust and Goose and accept the same .doc source files.
These Linux x86_64 archives are not yet production releases.

## Build locally

Rust: cargo build --release --manifest-path runtime-rust/Cargo.toml --bin doc
Rust: runtime-rust/target/release/doc runtime-rust/examples/repair.doc a=4 b=1
Goose: use the pinned upstream Goose compiler at SHA 9412b80f52d833c4697cffdbbf1f4eeb5195cd41
Goose: goose build runtime-goose/doc_typed.goose --offline -o ./doc-goose
Goose: ./doc-goose runtime-rust/examples/repair.doc a=4 b=1

## CI artifact contents

- doc-rust-linux-x86_64.tar.gz: bin/doc-rust, LICENSE, sample .doc source
- doc-goose-linux-x86_64.tar.gz: bin/doc-goose (CPU-only), LICENSE, sample .doc source
- doc-rust-gpu-linux-x86_64.tar.gz: bin/doc-rust-gpu (native wgpu-enabled DOC CLI), LICENSE, sample DOC source
- doc-goose-sdl3-linux-x86_64.tar.gz: doc-goose-sdl3 (native Goose gfx-enabled DOC CPU/selected-GPU CLI), LICENSE, sample DOC source
- Per-run dynamic library listings, software Vulkan results, and extracted-install smoke logs.
- CI extracts each archive into a temporary directory and runs the included binary.

## Safety and scope

The DOC interpreter source is native Rust or Goose; no DOC-owned C/C++ interpreter is added.
Upstream Goose is NOT transitive-C-free: its standard OS module uses native C runtime services
(see the pinned upstream stdlib/os.goose and gs_os_read_file). A literal requirement
for zero C code in the final linked Goose binary requires changing the upstream
Goose compiler/runtime backend. Do not claim the current Goose build meets that requirement.

The Linux release artifacts and tests exercise a **restricted** same-source Goose SDL3
GPU Boolean-derived path, but do not prove physical GPU coverage, general DOC GPU
integer/recurrence/effects execution, complete memory isolation/reconstruction, OS sandboxing,
all-worker parallel scheduling, or production readiness. These gates remain open.

## Explicit output effects

Use `doc FILE.doc --emit=STATE:relative/output.txt` or `doc-goose` with the same arguments to sample a complete derived/source value and write its canonical textual representation. The write is a separate fallible effect after DOC evaluation, using same-directory temporary-file replacement. It is not exactly-once execution or general transaction rollback. The relative output path must have an existing parent directory. The Rust backend canonicalizes its destination parent; Goose enforces a portable lexical path policy, not a symlink-safe OS sandbox.
