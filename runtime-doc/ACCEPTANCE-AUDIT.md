# Independent implementation — acceptance audit

This is a working issue #11 audit, not issue #9's benchmark ledger or an acceptance declaration. The frozen Rust oracle remains unchanged (tree `a95a38bc6e9300aae815f83b570db5f99d32f221`). Do not extrapolate a historical test pass to a newer source tree.

## Verified historical evidence

[CI 45793328375](https://github.com/xad3play/DOC/actions/runs/45793328375), source `f525376c62b8bbb84c43e31df30c38af88788c6f`: bootstrap, Stage 2/3 native self-reproduction, CPU games, complete software WebGPU pass. Native compiler and mesh compiler C-toolchain timeouts mean the overall run failed and physical testing was skipped. Downloaded self, game and GPU archives matched the recorded archive digests; all 13 self, 13 game and 46 GPU manifest entries were independently checked against extracted files. The GPU manifest filename denotes files eligible for physical replay, not evidence of an executed physical test.

| Artifact | Archive SHA256 |
|---|---|
| Self-reproduction | `cd7b12011ee4109da3218d4d586ace6827774fcd88212b1f8059da04e9ad9ec3` |
| CPU games | `7459308efc6faef5ab03956b5dbf8123f078acacdd18af4bcfcdc02f543b1859` |
| WebGPU | `f89d79dfd5eb0762da51ca5f220b7dbdbdb65e34eaaed6662a68e4c7d01df919` |
| Native partial evidence | `617f31ebc550bb53594512fdb9da9a683e27ed7b2ad33c2c641757e9fa56774d` |

The verified Stage 2 and Stage 3 binary SHA256 is `22f0d5733b18a1c8aac280b59bf77bfa6025fbded664f7afc983763ae3ba95c6`; both generated C files share `333d74da030846d0a4756bf6c7ee45a78b9925b79ea04af0a4ce2b0405d2111d`. The native lifecycle compiler candidate C matches the previously locally tested `9f2f0b5ce4b89ad5ba52b6c949b9c08fad2ed5c9e287680026d9289c7a72ad41`, but GCC 13 did not finish its CI build.

[CI 45779847271](https://github.com/xad3play/DOC/actions/runs/45779847271) established mesh replay pixel parity, depth/mutation and device-loss rejection on an older tree. [CI 45768543512](https://github.com/xad3play/DOC/actions/runs/45768543512) established an earlier native QEMU AB boot. Neither substitutes for current-source revalidation.

## Placement and measured work

The generated program does not encode workload names or worker counts. The placement policy test records 1,246,979 native decisions without workload-specific hints. Eight source-free CPU replays matched the frozen reference. Actual affinity on the CPU measurement runner was two logical CPUs (Intel Xeon 6975P-C, Linux x86_64, GCC 13.3). Worker requests of four/eight correctly remained bounded by affinity. The following are fresh-process wall times including stdout and GNU time wrapper, nine samples per CPU configuration, not a steady-state kernel benchmark.

| Game | Frozen oracle p50 / p95 ms | Native 1 worker p50 / p95 ms | Native 2 workers p50 / p95 ms | Native auto p50 / p95 ms |
|---|---:|---:|---:|---:|
| Radar Chase | 9.196 / 10.311 | 1.733 / 1.930 | 2.045 / 3.024 | 2.030 / 2.149 |
| Radar Chase 3D | 13.023 / 13.090 | 2.462 / 2.618 | 2.940 / 3.070 | 2.923 / 3.054 |

Native peak RSS across the worker settings was 2,440–2,568 KiB (2D) and 2,472–2,632 KiB (3D), compared with reference maxima 3,336/3,400 KiB. The single-worker configuration was faster than the two-worker configuration for these small graphs. No linear scaling claim.

Actual software WebGPU replay from the separate GPU job:

| Game | Epochs | Total evaluations | GPU lanes | Other evaluations | Frontiers | Mixed / concurrent frontiers |
|---|---:|---:|---:|---:|---:|---:|
| Radar Chase | 16 | 1,222 | 876 | 346 | 110 | 5 / 5 |
| Radar Chase 3D | 17 | 1,445 | 878 | 567 | 213 | 5 / 5 |

"Other evaluations" is the recorded total minus dispatched GPU lanes, not a count of distinct CPU workers. Both graphs dispatched 11 times; failed successor epochs 3/4 published no partial output. Both also passed absent-adapter automatic CPU parity and explicit-GPU rejection. Region peak bytes were 1,573,330/1,579,250; allocations 83/821. Region live count returned to zero.

| Game | CPU replay wall ms (3 samples) | Mixed software replay wall ms (3 samples) | Open wall ms (3 samples) |
|---|---|---|---|
| Radar Chase | 3.848, 2.515, 3.868 | 324.685, 93.057, 93.589 | 58.384, 57.456, 57.957 |
| Radar Chase 3D | 3.843, 4.687, 3.726 | 354.477, 97.280, 97.264 | 59.968, 60.112, 60.561 |

Warm dispatch medians were 2.170–2.176 ms and 2.175–2.210 ms respectively; dispatch wall time includes transfer, submission, synchronization and readback. The first fresh process was substantially slower; the evidence does not isolate driver caches or kernel time. GPU job RSS includes WebGPU library/device overhead; mixed maxima were 131,856/133,236 KiB versus CPU-mode maxima 21,076/22,188 KiB in the same GPU job. This adapter is software, not physical. The measurements demonstrate correct mixed execution and overhead, not acceleration. Raw samples and exact argument, asset, generated-C, binary and typed-output hashes are in the original artifacts' `cpu-benchmark/summary.json`, `cpu-benchmark/samples.csv`, `games/summary.json`, and associated logs.

## Lifetime and authority audit

- Ordinary native regions own allocations explicitly; publication occurs only after a complete, non-poisoned attempt. Candidate failure/cancellation rolls back before publishing. Reader snapshots have explicit bounded admission; reclamation waits for the owning slot to be released. No tracing collector or reference counting is introduced as a DOC lifetime mechanism.
- The source-free CPU evidence includes ASan/UBSan allocation failures at 66 update and 33 snapshot ordinals, 128 replacements with two stalled readers, baseline/protected/peak bytes 2368/7104/531504 and live=0; matching TSan tests, cancellation and stale epoch checks, 32 commits while readers stall, 64 graph replacement transitions, managed carry/type/role reset and failed candidate rejection.
- Native GPU execution uses actual completion and readback, queue retirement after abandonment, explicit device-loss failure/recovery, and GPU graph generation replacement. The checked software run establishes these gates only on that source and adapter. WebGPU implementation internals are not asserted to be reference-count-free; DOC owns its runtime regions and retires device resources explicitly.
- Platform effects evidence: 16 typed epochs, three checkpoint splits, 19 malformed/authority rejection cases, typed reload parity/rollback and two exact PCM cues. Mesh packet parser: 17 Python rejection cases, 21 corrupt packets, 493 truncation points and 111 allocation failures, no partial publication. Native scalar/ABI lifecycle needs the complete current CI build and QEMU.
- Placed profile commits `6fa6f2d`, `18e2dec`, `e7dfb6f` add the bounded, single-process TCP witness corresponding to the paper's placement/recovery scope. Both endpoints' role, resource, generation, state, epoch, scalar type and checksum are validated. No resource changes while an attempt is open; old generation remains available to admitted readers. Failed transport poisons the attempt; failed resource removal invalidates lost derived values and transitive users; reconstruction restores acknowledged source facts from a schema-checked durable checkpoint. Generated evaluation uses received scalar copies, not remote code execution. Local focused sanitizer testing of transport (using reduced scalar primitives) passed 8,196 actual TCP frames, mutation/truncation, stale/duplicate/conflict, join/drain and failure cases. Full-runtime placed test, cancellation while receiving, checkpoint corruption/recovery and FD cleanup are committed but not yet integrated-CI verified. This is not a multi-process cluster, authenticated transport, arbitrary managed-value transport or consensus implementation.
- The frozen reference rejects duplicate declared formal parameters (`derive pair:int(x,x)`); repeated use of one declared parameter (`add(x,x)`) is valid. The placed test uses the latter; wire duplicate reception is tested separately.

## Current open acceptance gates

The active [CI 45820438889](https://github.com/xad3play/DOC/actions/runs/45820438889) tests `0f9b40935585a488f9b6a0b030a70d21b6f1657b` with explicit GCC 14 for the two previously timed-out tools, unchanged optimization semantics, bounded process group termination and raw compiler failure evidence. New placed-profile commits are upstream only, not in that run. Do not cancel it or claim these commits passed based on its result.

Before issue #11 closure: exact-revision self-reproduction and complete native/mesh/QEMU and software GPU gates, physical GPU execution of the original replay and adverse lifecycle cases with raw evidence, integrated placed transport/recovery tests and final ownership/placement audit. Recheck every acceptance gate at the final consolidated revision; leave issue #9 unopened until issue #11 has passed.

## 2026-11-26 direct local continuation — stronger lifetime/placement tests

Using actual f525376 Stage-2 reactive compiler and frozen oracle from CI archives, the complete scalar placed harness passed locally under GCC 14.2 ASan/UBSan and TSan. The current value, reactive, checkpoint, epoch, role and placement headers and host test files were reconstructed from the private repository and independently matched their Git blob hashes; the GPU-disabled branch of gpu_values.h was used verbatim, not a GPU mock or physical claim. The generated C SHA256 is 1c909269eb14931264be8e060b490633ecfacd8c3bbbfc5a36a0b15acca8a195. The actual placed transport test also passed 8,196 TCP frames with the full value substrate. Commit d18ca0f really clears lost derived materializations, marks transitive users, preserves an admitted reader's private copy, reconstructs on demand, binds the exact acknowledged checkpoint checksum and rejects another well-formed same-epoch checkpoint; all four committed file blobs matched the locally tested files. The updated direct reader regression replaces managed values 32 times while every reader slot is held, verifies exactly 32 evaluations each round and constant protected live bytes, then checks original borrowed snapshots and return to baseline; local ASan/UBSan and TSan passed. The new placed runner checks independent frozen-oracle parity, actual generated baseline, both sanitizers, and retains full command/output/provenance and synthetic checkpoint records in the game evidence manifest. All current-source CI and physical hardware evidence remains required.

Native compilation diagnostic: exact failed C (9f2f0b5c...) compiled locally with Clang 17 at -O0 in 3.88s, peak RSS 723140 KiB. Four unchanged frozen scoped/stream/conditional/socket source blobs plus repeat/multi-carry fixtures produced deterministic C/header; 46 lifecycle negatives rejected, exact hosted lifecycle and scalar-call test blobs passed ASan/UBSan (65,536 cleanup cycles, real POSIX stream and 128 socket/close pairs). Historical mesh compiler C (29bfe182...) compiled at Clang -O0 in 4.99s, peak RSS 473580 KiB. Shader source blobs and build adapter were hash-verified, original/mutated WGSL exactly matched archived output (original SHA256 1b8f7cfa6537d9bf56b0e561472c5f48569910f1be20f0224d9048911226e34c), 15 domain/upload rejections passed. This is source/domain proof, not new GPU rendering or QEMU evidence. Current GCC14 CI remains active and must not be cancelled.

### Direct continuation — generated live scene and native toolchain

- Exact CI 45820438889, 0f9b40935585a488f9b6a0b030a70d21b6f1657b: bootstrap, byte-identical independent Stage2/Stage3, CPU games and software WebGPU passed. Downloaded self, games and GPU archives matched published digests; all respective manifest entries verified. Native and mesh were still running at the point of this update; this is not physical GPU evidence.
- Exact archived native compiler C (SHA256 9f2f0b5ce4b89ad5ba52b6c949b9c08fad2ed5c9e287680026d9289c7a72ad41) built locally with Clang 17 -O0 in 3.88 s, 723140 KiB peak; 150 negative compiler checks, all seven original hosted ABI ASan/UBSan suites, including 4162 bit patterns, real stream and socket operations and 65536 cleanup iterations, passed. Exact original freestanding entry/verify/layout produced a linked ELF with no dynamic dependencies or undefined symbols; no local QEMU, so no boot claim. Archived mesh compiler C built with Clang 17 -O0 in 4.99 s, exact original and changed WGSL matched and all 15 domain/upload negatives passed. Next CI explicitly uses Clang 18 for these two bulky build-time compiler tools; no change to optimized application backend or gameplay, no silent compiler fallback.
- Native live 3D scene candidate: recurrence CLI and event-driven session share exactly the same private candidate construction and epoch policy. Carry/action authority is taken from committed DOC metadata. Actual Stage2-generated 3D game and original assets passed local ASan/UBSan for all 17 typed frames with byte-for-byte oracle parity (e6352ec27dcb177c8219f300caf24c0ae0807b9b9e7c94ab09d44d48c1e8f69c), rejected candidate and range-invalid projection rollback, zero live regions. Source-only checkpoint (6007 bytes) and two PCM WAV files match the command-line runtime exactly, bad checksum rejects, restored typed observations match. X11 platform adapter independently passed actual Xvfb RGB readback, resize, bounds and sanitizer cleanup. It presents validated WebGPU-rendered readback via XPutImage, not a GPU swapchain or physical desktop claim. No host geometry, lighting, gameplay, collision, physics or scoring.
- New exact-revision integration gate compiles the original generated game with the native generated compute/mesh WGSL and actual pinned WebGPU library, performs full deterministic and keyboard-triggered replay under Xvfb, requires exact per-frame oracle pixel digest plus XGetImage verification, resize without epoch advance, concurrent mixed compute, save/restore, WAV parity, and corrupted-checkpoint no-publication. Actual GPU-linked window build and integrated gate remain unverified locally (no GPU/header installation); only CI may establish this. Previous physical/offscreen gates unchanged and still required.


### Native Wayland addition (user-requested; pending CI)

The new native Wayland client uses the same generated scene, recurrence authority, admitted typed frame and WebGPU renderer. It connects to the compositor with xdg-shell, presents validated GPU readback through wl_shm XRGB8888, receives native wl_keyboard with xkbcommon, acknowledges configure, waits for actual surface frame callbacks and never reuses a busy buffer before wl_buffer.release. At most three buffers are admitted. The CI gate builds protocol bindings from the Ubuntu package and tests the original 17-frame replay under headless Weston, plus the original sequence via real keyboard events forwarded through Weston's nested X11 backend. The application has DISPLAY removed and links native Wayland (not XWayland); expected typed output and GPU RGBA digests match the frozen oracle, wire protocol and actual buffer acknowledgements are retained. Frame callbacks do not prove physical scanout or compositor pixel readback. Existing X11 and physical GPU gates remain mandatory. This environment has no Wayland headers/compositor and package DNS is unavailable, so native compilation/execution is pending CI, not claimed passed. Current 45834325970 tests an older revision and is not interrupted.
