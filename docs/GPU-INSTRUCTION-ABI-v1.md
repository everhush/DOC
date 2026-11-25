# DOC GPU instruction ABI v1 — Rust/WebGPU active subset

## Status and ownership

The active selected-GPU implementation is Rust-owned:
`runtime-rust/src/gpu_abi.rs` encodes checked DOC expressions;
`runtime-rust/shaders/doc_reusable.wgsl` interprets them using `wgpu`.
The shader is compiled once per selected device/evaluation, then independent
ready frontiers use private premise, program, descriptor and result buffers.

No underlying platform graphics API is part of this protocol. Previous
Goose/WGSL prototypes are deprecated historical research, not a production
backend. This ABI currently represents **pure, total, bounded Boolean and
signed i32 expressions only**; no arbitrary DOC effects, structures,
collection values or whole-program GPU generality is claimed.

## Wire layout

All payloads are little-endian 32-bit words:

| Buffer | Element | Meaning |
| --- | --- | --- |
| Premises | i32 | Input bit pattern (Boolean 0/1 or signed integer) |
| Instructions | two i32 | `opcode, operand`, 8 bytes |
| Stage descriptors | four i32 | `instruction_offset, instruction_count, premise_offset, kind`, 16 bytes |
| Output | u32 | Canonical Boolean 0/1 or signed i32 bitcast |

Instruction opcodes: `1` load indexed premise, `2` immediate integer,
`3` equality, `4` less-than, `5` less-or-equal, `6` total pure
conditional, `7` addition, `8` subtraction, `9` multiplication.

The instruction stack is capped at 128 words. Invalid opcodes, premature
pops, noncanonical Boolean outputs, overflowing descriptor arithmetic,
unsupported types and out-of-bounds buffers must fail closed. A single
arithmetic operation admits numeric leaves within ±32767; nested bounded
chains of 2–12 operators require leaves within ±4, with conservative
signed-i32 safety proof. No runtime CPU evaluation substitutes for an
accepted GPU derived value.

## Scheduling and publication

All premises must already be settled and immutable for the current ready
frontier. Each GPU lane writes only its own private output. The host
performs full typed readback and canonical-value validation **before**
making the frontier visible to successor dependencies. Epoch changes,
source repair and demanded recurrence use the same typed authority rules
as the CPU semantic oracle. A shader failure, device loss, mapping error,
unsupported expression or dependency mismatch publishes **no incomplete
graph or epoch**.

The executor checks the adapter's actual WebGPU workgroup and storage
limits. A software WebGPU adapter may be used only under an explicit
developer/CI correctness flag, never as physical-acceleration evidence.

## Release requirements

Exact-source Rust CPU and software-WebGPU CI must pass, and separately
the same SHA-pinned Rust executable must run physically on a real
`wgpu` GPU adapter with 1/multiworkgroup and recurrence tests. Benchmark
evidence must include end-to-end pipeline/device/transfer costs, fail-stop
checks, and raw output. Current source implementation is not automatically
a complete general-purpose-GPU or game-readiness certificate.
