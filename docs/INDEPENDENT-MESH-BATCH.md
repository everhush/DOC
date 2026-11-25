# Independent mesh rendering batch (2026-11-25)

Imported baseline: 0e1b7e6a1f0316e1833b6773b84caf206d8a8e46 (exact tracked snapshot of rtu0/doc2 ea58334a3209f8b599f3fef22e0a103c58512b45). Frozen Rust tree a95a38bc6e9300aae815f83b570db5f99d32f221 remains unchanged.

The DOC compiler supplies WGSL and the native game supplies typed frame observations. mesh_frame.py and mesh_packet.h implement the checked host transport; mesh_render.c is a Linux WebGPU platform adapter, not a game or expression evaluator. The renderer admits the complete batch before GPU use, retains resources through mapped completion, and publishes pixels only after successful completion of the entire batch. Test-only device destruction must produce no published pixels. The compiler-produced mesh domain and shader pairing is trusted at this host boundary; the packet decoder is not a shader verifier or a proof of provenance for arbitrary external WGSL.

Local transport evidence: real unchanged 3D game frame from archived frozen oracle; ASan/UBSan decoder, 17 high-level rejections, 21 corrupt packets, all 493 truncation points rejected without partial publication. All 17 replay frames also passed transport validation. No physical GPU or wgpu-native C library was available locally. Renderer and device-loss/pixel parity tests are candidates pending actual device execution; do not mark these gates passed based on the transport tests.

CI extends the existing Stage-2 mesh job to verify 17 replay pixel proofs against the frozen Rust oracle and final PPM bytes, depth-order independence, three lit faces, fragment mutation, repeatability, malformed packets and device destruction. One batched workflow only; separate physical acceptance remains required. #11 remains open; #9 follows only after #11 is accepted.
