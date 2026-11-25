# DOC game engine #10 — capability and evidence matrix

This is a **partial Rust-only Linux x86_64 engine**, not a Bevy-class completion claim. User-authorized scoped #10 completion **defers GUI/editor, game-asset generation and 3D**. The legacy P0/P1 table below is retained for provenance; its deferred rows do NOT block scoped closure. Remaining general-purpose, resource and headless/data correctness gates DO block closure.
Gameplay, scene decisions, collision rules, animation state and recurrence are
authored in DOC. Rust provides OS input/window/effects, stepping and wgpu/WGSL
presentation. The default computation backend is CPU; explicit GPU selection
never silently falls back. Deprecated Goose is not an active target.

| Acceptance family | Status | Executed evidence and limitations |
| --- | --- | --- |
| P0 world/components/queries | PARTIAL | DOC bounded aligned entity ID/x/y columns, arbitrary indexed removal/movement and guarded queries; three-entity demo plus reusable bounded prefab world (up to 1024 configured entries); carried high-watermark prevents ID recycling after full despawn, tested in 2/2 successful CI at `1c163eb`; typed prefab replacement and non-recycled IDs verified at earlier exact-head CI; latest I/O/resource test suite requires current CI signoff; no general archetypes/hierarchy |
| P0 lifecycle/scheduling | PARTIAL | Fixed-step DOC recurrence, deterministic replay, 1/2/4/8 worker parity, retained snapshots and atomic failed updates; generic typed source-fact checkpoint/independent fork, plus v1 confined checksummed disk save/load and process-level game resume equality tests (current CI pending); no full engine system scheduler or heap-free hot-path proof |
| P0 2D rendering | PARTIAL — SOFTWARE WINDOW PRESENTED | winit + wgpu WGSL grid window presented 12 actual Xvfb frames in Linux CI at `61006ca` (run 45120957008), with `DOC_GPU_SOFTWARE_TEST_ONLY`; no physical game-window device proof, sprites or texture pipeline |
| P0 3D rendering | DEFERRED (user instruction) | Not implemented; excluded from scoped #10 gate |
| P0 input/events | PARTIAL | Ordered terminal and window keyboard input plus deterministic replay; no remapping/gamepad or general event bus |
| P0 assets | PARTIAL | DOC typed startup scene effects and DOC-authored validated epoch-local prefab reload with explicit carried data; bounded Rust host typed data-resource pool with generation-counted stale-handle rejection, typed replacement, live/peak logical payload-byte accounting; no OS file watch or external texture cache (generation deferred), current CI pending |
| P0 scenes/prefabs | PARTIAL | Imported pure DOC modules, typed scene configuration and bounded DOC-authored prefab instantiation/removal; no general hierarchy; typed programmatic prefab replacement and generic durable DOC source-fact checkpoint now provided, exact-head CI pending |
| P0 animation | PARTIAL | DOC-authored 16-step looping coin pulse, pause freeze and restart reset, visualized in WGSL; no clip blending or skeletal animation |
| P0 UI/HUD | DEFERRED GUI (terminal retained) | Terminal score/pause/win feedback exists; graphical fonts/layout/widget system excluded from scoped #10 |
| P0 audio | MINIMAL FILE EFFECT (CI PENDING) | DOC derives frequency/duration on collection; opt-in Rust effect writes bounded valid PCM16 WAV cue files after stable epochs. This is real audio file output **not** a live device, mixer or playback guarantee |
| P0 tooling/manifest | PARTIAL | Source, replay and tests; headless Linux CLI with save/load, audio file effect and opt-in measured benchmark; broader editor/manifest UI deferred |
| P0 packaging/Linux | PARTIAL | Headless binary and optional window feature compile/install checks; no complete graphical Linux distribution |
| P1 picking/collision | PARTIAL | DOC-authored half-open 2D AABB composition and grid collision; touching edges excluded, signed-endpoint safety tested; no broad physics/raycast |
| P1 rendering pipeline | PARTIAL | Actual software-window WGSL presentation; no multipass/texture/material renderer |
| P1 camera/animation | DEFERRED 3D | No 3D camera, clips or skeletons; unrelated 2D pulse remains partial |
| P1 authoring/reload | PARTIAL | Deterministic replay and typed source-driven prefab replacement; no OS file-watch hot reload/profiler |
| P1 extensibility | PARTIAL | Pure DOC imports, collision/math helpers, bounded entity scene; versioned pure typed IR v1 exporter/handoff and reusable DOC helper modules; no broad engine API or generated C |
| P1 accessibility/input | MISSING | No input remapping or gamepad |

## Added core contracts awaiting exact-SHA signoff

- Durable typed checkpoint format: `DOC-CHECKPOINT/1`, bounded 8 MiB with graph/carry schema binding and accidental-corruption checksum (non-cryptographic). Restored DOC source facts compute a new independent epoch 0; old epochs and external side effects are never claimed to be replayed. A changed DOC schema or corrupt checkpoint fails closed.
- Resource handles: `DataResources` in `runtime-rust/src/resources.rs` uses typed values, bounded slots/payload bytes, monotonically advanced per-slot generations, validated replacement and release. Logical payload-byte peaks are *not* process heap allocations.
- Audio: `engine/coin_chase.doc` owns the audio cue derivations; `doc-game --audio-dir=existing/dir` writes playable WAV PCM files after complete DOC epochs. Does not claim speaker playback, mixer or device integration.
- Compiler handoff: `docs/DOC-TYPED-IR-V1.md` and `runtime-rust/src/typed_ir.rs` define/export a deterministic validated source-order typed expression graph. No C codegen or Issue #11 implementation has started.
- Measurements: `doc-bench` reports repeated cold-runtime+oracle CPU p50/p95 latency, counted allocation requests and Linux process peak RSS; `doc-game --measure` reports actual DOC epoch-advance p50/p95 and VmHWM separately. Measurements must be tied to CI artifacts; no hardware or production throughput claims.

## Reproducible verification boundaries

- Rust engine replay: `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_doc_game`
- Entity lifecycle: `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_entities_doc`
- Collision safety: `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_collision_doc`
- Typed scene/prefab replacement: `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_prefab_doc`
- Independent general-purpose finite search: `cargo test --manifest-path runtime-rust/Cargo.toml --test general_search_doc`
- In-memory recurrence checkpoint/fork: `cargo test --manifest-path runtime-rust/Cargo.toml --test recurrence_checkpoint`
- Durable disk checkpoint and corruption/carry/schema/path rejection: `cargo test --manifest-path runtime-rust/Cargo.toml --test recurrence_disk_checkpoint`
- Process replay after disk restore and actual DOC audio cue: `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_save_resume`
- Typed bounded data handles and failure-safe replacement: `cargo test --manifest-path runtime-rust/Cargo.toml --test data_resources`
- Real PCM16 audio and confinement: `cargo test --manifest-path runtime-rust/Cargo.toml --test audio_output`
- Deterministic typed IR v1 export: `cargo test --manifest-path runtime-rust/Cargo.toml --test typed_ir_contract`
- Exact-CI Linux CPU benchmark: `DOC_BENCH_WIDTH=512 DOC_WORKERS=4 cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-bench`
- Actual game-step measurement: `cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --measure --replay=ddsddddsspr`
- General-purpose program inventory and candid limits: [`docs/GENERAL-PURPOSE-PROGRAMS.md`](../docs/GENERAL-PURPOSE-PROGRAMS.md)
- Linux graphical replay: `cargo run --manifest-path runtime-rust/Cargo.toml --features window --bin doc-game-window -- engine/coin_chase.doc --replay=ddsddddsspr` in an available window session; headless software-adapter CI must be labeled as such.
- Exact-source 2/2 Linux success: [45205060016](https://github.com/rtu0/DOC/actions/runs/45205060016) at `1c163eb` includes lifetime entity-handle fix. The generic search, prefab and fork additions completed [45216790374](https://github.com/rtu0/DOC/actions/runs/45216790374), 2/2 green at `1b470ef`. New durable checkpoints, resource handles, audio file effects, typed IR and measured benchmark **require a new exact-HEAD green CI run**, never infer green from older CI.
- Physical Kaggle Tesla T4 source compute parity is independently established for earlier Rust source in [45117230549](https://github.com/rtu0/DOC/actions/runs/45117230549), not for the graphical game window or the current engine SHA.

**Issue #10 was closed under its scoped acceptance; see [the accepted evidence](https://github.com/imxade/DOC/issues/10#issuecomment-7111101261).** Historical text below describes its earlier gate, superseded by that closure. The historical all-P0/4-P1, graphical GUI/editor, generated assets and 3D gates are superseded. Still open until exact-head execution: durable checkpoint and audio-file validation, typed handle release and recovery, IR v1 golden tests and measured CPU latency/allocation samples; no general archetypes, OS file watching, live audio device or unrestricted records/maps. The latter non-core extensions remain explicit future gaps rather than falsely passed. Do not call the bounded prefab demo a full ECS. Software WebGPU presentation is neither physical-window certification nor proof of a general renderer.

Issue #14's future public release is SOURCE-AVAILABLE with legal text still
undecided. Preserve historical license metadata pending rights/legal approval;
do not describe the eventual release as OSI open source.

## Issue #22 — unified game and automatic placement (strengthened candidate validated)

[Radar Chase](RADAR-CHASE.md) is a single DOC-authored headless/terminal game
candidate that integrates bounded entities, prefab spawn/despawn and collision,
typed assets and reload, stable IDs, game input and replay, animation, score/win,
checkpoint restore, file audio and 128 game-visible independent radar signals.
Automatic engine execution uses dependency-ready frontiers and a conservative
per-definition scalar/range proof, with CPU workers and optional WebGPU compute
in one private publication barrier. No per-game scheduling directives. Missing
or unusable devices before dispatch select the truthful CPU-only path. A failed
selected-device dispatch does not publish the successor epoch. Reused device and
pipeline are separate from the optional window renderer.

The exact strengthened native CPU/software-WebGPU candidate passed 2/2 in [45321007511](https://github.com/rtu0/doc2/actions/runs/45321007511), including the complete real game, worker parity and 15 actual mixed frontiers. See [Radar Chase evidence](RADAR-CHASE.md). Single-main consolidation and optional configured physical-gpu proof are checked separately. Software-WebGPU compute is not a
physical-GPU claim. Do not begin #11 until [#22](https://github.com/imxade/DOC/issues/22)
passes native replay/worker parity, actual mixed compute, failures and measurement
on the same final SHA.
