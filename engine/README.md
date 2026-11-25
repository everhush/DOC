# Coin Chase — DOC language vertical slice for issue #10

This is a **playable terminal/headless game**, not a 2D/3D graphical Bevy-class
engine and not a closure claim for issue #10. The reusable pure `engine_math.doc`
module and `coin_chase.doc` contain all game rules: movement, bounds,
collision, coins, scoring, pause, terminal state, restart and the fixed-step clock.
Rust `doc-game` is a thin effect adapter for command input, deterministic
recurrence stepping and ASCII presentation. It does **not** implement gameplay.

Linux x86_64, from repo root:

```bash
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --replay=ddsdddddsspr
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_doc_game
```

Controls: `w/a/s/d` movement, `p` pause toggle, `r` restart, `.` idle tick,
`q` quit; press Enter after an interactive command. Each action advances one
DOC stable epoch. `--replay` is exact and deterministic; `--workers=N` changes
only execution parallelism, not game logic.

The recurrence carries only DOC-authored `next_*` results. Inputs are typed
facts for the next epoch, effects remain outside the graph. A failed epoch
publishes nothing, and retention snapshots remain owned and immutable. The
terminal renderer *observes* the DOC scene but cannot override its rules.
Strict CPU/GPU placement remains as defined by DOC. This recurrence host is
**CPU-only**; it does not claim GPU execution or silently select hardware.

**Current scoped status:** DOC-authored bounded entities and source-backed prefabs,
typed data effects/resource handles, disk save/resume, optional WAV file audio
effect and software-tested 2D WebGPU presentation exist as separate slices.
This is still **not a Bevy-class or general ECS engine**, nor a live speaker/
mixer or full sprite/texture asset pipeline. GUI/editor/HUD, automatic asset
generation and all 3D are user-deferred. See CAPABILITY-MATRIX.md and exact-SHA
CI before claiming release/completion.

## Experimental WebGPU 2D window

Run this optional Linux X11 graphical presentation host (requires an actual
WebGPU-capable physical GPU and working desktop/window session):

    cargo run --release --manifest-path runtime-rust/Cargo.toml --features window --bin doc-game-window -- engine/coin_chase.doc

Window event adapter: Arrow keys or WASD to move, P to pause, R to restart,
Escape to exit.
For bounded integration testing, use `--replay=ddsddddsspr`: the graphical
adapter steps each action at 16ms and exits after the final successfully
presented WebGPU frame. `DOC_WINDOW_SCENE` and `DOC_WINDOW_PRESENTED`
markers are actual DOC value observations and WebGPU surface presentation,
not mere compilation. CI may opt in to a software adapter with
`DOC_GPU_ALLOW_SOFTWARE=1`; this cannot certify physical-GPU rendering. The DOC source alone defines all gameplay; winit provides
only OS input/window events, and wgpu executes WGSL presentation at 60 Hz.
This is a **simple 2D grid renderer**, not a full sprite/asset/3D engine.
Window state/keyboard interaction cannot be exercised in headless GitHub CI;
the window must receive a real Linux desktop smoke test before claiming
graphical P0 success. No native graphics API is selected by DOC.

## Typed startup scene data (DOC input effect)

`engine/levels/coin_chase.txt` is a source-asset file containing one typed
`ints` value: `[width,height,wall_x,wall_y,goal]`.
`coin_chase.doc` declares `effect level: ints = read("levels/coin_chase.txt")`;
the engine's existing confined-file DOC frontend samples it **once at source
construction** and converts it into a versioned source fact. Derived dimensions,
obstacle collision and goal remain ordinary DOC expressions, not Rust
position rules. `engine_math.doc` exports the pure `same_cell` collision
helper for reuse. Changing the level file affects a subsequent launch; runtime
OS-event-driven live file watch remains open. A separate DOC-authored bounded prefab scene and typed reload facts are exercised in engine_prefab_doc; no broad hierarchy/archetype claim.
Malformed/missing effect assets fail before a new engine generation can publish.

## DOC-authored bounded entity lifecycle (experimental)

The reusable `entity_pool.doc` pure functions and the standalone
`entity_scene.doc` define an entity ID/component-column world **in DOC**.
An ordered action fact spawns a new monotonic ID, removes a selected live
entity by slot, or moves a selected entity. Aligned typed ID/x/y columns and
query validity are derived without Rust gameplay rules. The scene has an explicit three-entity capacity
and safe negative/out-of-range query handling. New pure DOC `remove_at` and
`replace_at` operators fail on invalid indexes before publication. It demonstrates dynamic
DOC-authored entity lifetime across recurrence epochs, snapshot retention
and failure rollback; it is **not** a general archetype ECS,
archetype storage, a renderer, or a feature-complete engine.

Run `cargo test --manifest-path runtime-rust/Cargo.toml --test engine_entities_doc`.

## DOC-authored presentation animation

`coin_chase.doc` carries a bounded 16-step `next_animation_phase` across
epochs. The phase loops deterministically, **freezes on pause**, and resets on
restart; it is not computed by the Rust input adapter or by the renderer.
The wgpu fragment shader reads the DOC phase through its existing uniform and
uses it to pulse the coin color. This is a first animated 2D visual-state test,
**not** an animation clip/blend/skeletal system. The new replay regression
checks the DOC transition independently of the window.

The entity scene clamps a requested capacity to a fixed three-entity hard
budget. A DOC-carried lifetime allocation high-watermark guards against reusing
an entity ID even after every live entity has despawned; the recurrence host
rejects external rewrites of this carried state. The scene is still a bounded
prototype, not a general-purpose archetype ECS. Validate the full-despawn,
retained-handle and failed-rewind regression in `engine_entities_doc` before
claiming this invariant verified on a particular commit.


## Explicit save/resume, typed resources, audio and measurement

Keep the DOC source file and typed level file stable across checkpoint restore;
the checkpoint rejects mismatched graph/source/carry schema or corruption.

~~~
mkdir -p engine/state engine/audio
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --replay=dds --save=state/run.chk
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --load=state/run.chk --replay=ddddsspr
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --replay=ddsdd --audio-dir=audio
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/coin_chase.doc --headless --replay=ddsddddsspr --measure
~~~

The saved file is DOC-CHECKPOINT/1, a bounded, typed source-fact checkpoint
with schema binding, a non-cryptographic accidental corruption checksum, and
atomic same-directory replacement. Restored programs start at a *new* epoch 0
with the same logical DOC valuation; past epochs and already emitted external
effects are not replayed. An invalid file or directory is a hard error; neither
tool invents missing directories or writes outside the source directory.

The game derives audio_hz and audio_ms in coin_chase.doc from its COLLECTED
logic. With --audio-dir=existing/dir, the narrow host adapter emits a valid
PCM16 WAV file at each successful collection epoch, e.g. audio/cue_5.wav.
It does not pretend to play sound through speakers or supply an audio mixer.

The independent host-side DataResources store is typed and bounded to at most
1024 slots, with per-slot monotonically advancing generations and explicit
payload-byte budgets. It rejects stale/reused handles, wrong types and failed
replacements. These byte counters are logical stored payloads, not observed
heap allocations. The Rust DOC benchmark separately counts process allocation
requests, measures CPU latency quantiles, and reads Linux process VmHWM.
Use CI artifacts from the **same SHA** to interpret numeric results.

Typed compiler handoff: docs/DOC-TYPED-IR-V1.md and
runtime-rust/src/typed_ir.rs define and emit a validated, deterministic
DOC-TYPED-IR/1 AST. It is not generated C or Issue #11 implementation.

Additional exact-source checks:
~~~
cargo test --manifest-path runtime-rust/Cargo.toml --test recurrence_disk_checkpoint
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_save_resume
cargo test --manifest-path runtime-rust/Cargo.toml --test data_resources
cargo test --manifest-path runtime-rust/Cargo.toml --test audio_output
cargo test --manifest-path runtime-rust/Cargo.toml --test typed_ir_contract
~~~
