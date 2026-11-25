# Radar Chase — unified Issue #22 DOC game and automatic-work validation

**Gate:** [Issue #22](https://github.com/imxade/DOC/issues/22) must pass
exact-source validation before #11 starts. This is one minimal playable game
authored in the **existing** DOC language and driven by the existing Rust DOC
recurrence engine. It is not Bevy, GUI/editor, 3D, asset generation, new
DOC dialect or DOC→C compilation.

## Run on Linux x86_64

From repository root, no authored scheduling, worker or GPU directives:

~~~
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/radar_chase.doc
~~~

To permit actual automatic GPU **compute** on a physical WebGPU adapter,
compile the engine with optional GPU support (still **no** authored placement
or manual CPU/GPU partitioning):

~~~
cargo run --release --manifest-path runtime-rust/Cargo.toml --features webgpu --bin doc-game -- engine/radar_chase.doc
~~~

The ordinary no-feature binary remains a correct CPU-only deployment.
The compile-time WebGPU feature opts in to *device capability*, not a
per-workload backend or source-level placement directive. Once compiled,
the engine selects independently ready eligible tasks from the DOC graph.
If no admitted device is available, execution stays CPU-only.

W/A/S/D move, P pause, R restart, E create one prefab obstacle,
X remove the selected live obstacle, . idle tick, Q quit. Terminal
presentation renders '@' player, '*' coin, '#' level wall and
'X' dynamic prefab obstacle. A single replay can create an obstacle, collide
with it, remove it, collect both coins, win, pause and restart. Typed level and prefab coordinates are read from
engine/levels/ (read-only effects), and the game itself controls collisions,
score/win, pulse animation, spawn/despawn, safe capacity/identity and queries.

Combined fixed replay, headless:
~~~
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/radar_chase.doc --headless --replay=edsssxwddddsspr
~~~

Disk save/load and optional real audio file effect:
~~~
mkdir -p engine/state engine/audio
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/radar_chase.doc --headless --replay=edsss --save=state/demo.chk
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/radar_chase.doc --headless --load=state/demo.chk --replay=xwddddsspr
cargo run --release --manifest-path runtime-rust/Cargo.toml --bin doc-game -- engine/radar_chase.doc --headless --replay=ddsdd --audio-dir=audio
~~~

## What's covered in ONE actual DOC game

| Feature family | In-playthrough evidence | Important limit |
| --- | --- | --- |
| Game rules, input, collision | DOC source derives all next positions, wall/dynamic-obstacle blockers and scoring | 2D bounded grid, no general physics engine |
| Components/entities | DOC arrays of entity IDs, X/Y aligned columns, bounded spawn/despawn, non-reused high-watermark | Four live obstacle cap, not a general archetype ECS |
| Prefabs/typed data | Startup typed prefab files and DOC-sourced replacement facts; stable carried arrays | File-watcher hot reload not implemented |
| Queries and safety | DOC guarded slot queries, out-of-range failure paths, no torn entity publication | Bounded slots |
| Animation/timers | DOC fixed-step frame, coin phase pulse, pause/freeze/restart | No clip mixer |
| Save/restore | Same DOC graph source-fact checkpoint, independent resumed epoch 0, deterministic suffix | Existing checksum detects accidental corruption, not malicious tampering |
| Audio | DOC-derived coin cue outputs a PCM16 WAV file when explicitly enabled | Does not drive live speaker output |
| Independent workload | 128 derived per-tile player/coin radar signals, built as actual DOC states | This is 8x8 logical radar sensing for a small game; CPU/GPU compute eligibility applies only to total scalar expressions |
| Backend-neutral DOC authorship | Same unannotated source runs on CPU-only or auto CPU/WebGPU | Rendering is separate from GPU computation |
| Failure recovery | Invalid prefab reload, corrupt checkpoint, overflow and injected GPU failure tests | External already-published effects cannot be reversed |

The 128 radar cells are normal game occupancy queries: they inspect player
and coin world coordinates and produce typed boolean facts. DOC then reduces
all 128 facts to the pre-action player and coin cell indices, exposed by
`DOC_GAME_RADAR` each frame. No scan is dead demonstration work. They are not
tagged as GPU/CPU tasks. Ordinary gameplay, arrays, and file/resource
operations remain on the native CPU evaluator. GPU *compute* is selected
by validated scalar type/range, dependency readiness, number of independent
lanes, and actual device class.

## Automatic runtime scheduling — no source placement directives

The host calls automatic recurrence stabilization for successor epochs.
Initial/restore source admission and epoch zero use the existing CPU path.
At each successor ready DAG frontier:

1. A short or ineligible frontier uses the existing CPU worker scheduler.
   Worker concurrency is bounded by actual available logical processors and
   ready task count. No threads are spawned for tiny frontiers.
2. With a WebGPU-capable device available and >=64 eligible independent scalar
   definitions in a ready frontier, the scheduler emits a temporary GPU-only
   **typed projection** of those authored DOC expressions. Remaining ready
   states execute on CPU concurrently. No gameplay rules are reimplemented
   on the host or encoded as a bespoke shader.
3. The one WebGPU device/WGSL pipeline is reused across subsequent game
   epochs; each dispatch creates private input/results buffers. CPU and GPU
   candidates must BOTH finish before one frontier publication.
4. Unsupported inputs/types (including wide i64) stay on CPU in auto mode.
   With no eligible physical GPU, or device initialization fails before dispatch,
   all computation stays CPU and the reason is reported. When GPU work
   was selected and device execution fails, **no partial game epoch**
   publishes. There is no false GPU claim or CPU fallback masquerading as
   successful device execution.

The current crossover grain >=64 is a **conservative bounded policy**, not
a proof that GPU is faster for every program. Measure it before tuning.
Current verified GPU paths remain strict for explicitly selected
--backend=gpu via the standalone DOC CLI; auto scheduling is an additional
engine runtime policy. For software-only GitHub CI, the existing
DOC_GPU_ALLOW_SOFTWARE=1 test admission permits a CPU WebGPU adapter and logs
DOC_GPU_SOFTWARE_TEST_ONLY. This does not prove physical-GPU execution.
DOC_AUTO_DISABLE_GPU=1 is a **test-oracle override**, never required in DOC
game source. The default no-feature build correctly runs CPU only.

Diagnostic stderr markers include:

- DOC_AUTO_ADAPTER
- DOC_AUTO_FRONTIER: cpu=N gpu=M
- DOC_AUTO_GPU_SESSION_CREATED / DOC_AUTO_GPU_SESSION_REUSED
- DOC_RUST_GPU_FRONTIER_DISPATCH (actual WGSL compute readback)
- DOC_AUTO_SUMMARY
- DOC_GPU_SOFTWARE_TEST_ONLY on a software adapter

## Acceptance verification and evidence

~~~
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_radar_showcase
cargo test --manifest-path runtime-rust/Cargo.toml --test engine_radar_cli
cargo test --manifest-path runtime-rust/Cargo.toml --all-targets
cargo test --release --manifest-path runtime-rust/Cargo.toml --features webgpu --test engine_radar_showcase
~~~

The existing GitHub Linux workflow must pass its **new** CPU replay parity
and genuine software-WebGPU mixed-dispatch/failure jobs on the **same SHA**.
An unexecuted test or failed infrastructure job does not certify this gate.
Hardware, software-adapter and CPU-only evidence must be labeled separately.

The strengthened source revision [770e646](https://github.com/rtu0/doc2/commit/770e64692e5753c02eecd92746d9eed364d34f4b) passed both native Linux and software-WebGPU jobs in [45321007511](https://github.com/rtu0/doc2/actions/runs/45321007511). The entire winning replay completes 15 successor epochs: CPU-only 2,940 derived evaluations, 15 parallel frontiers at four available workers (zero at one worker); mixed llvmpipe 930 CPU + 2,010 GPU derived evaluations across 15 mixed frontiers, each 8 CPU/134 GPU, actual three 64-lane workgroups per dispatch, one reusable device/pipeline. CPU-only p50/p95 889/943 microseconds, peak RSS 3,604 KiB; software mixed p50/p95 968/21,106 microseconds, peak RSS 92,220 KiB for five-step samples. This is not a speedup or physical-GPU claim. Full replay victory at tick 13 (6,4), CPU oracle, natural fallback on unadmitted adapter, actual checkpoint and WAV effects, capacity/stale IDs, typed failures, and injected GPU rollback passed. The new single-main revision must pass exact-head CI again. Configured Kaggle runs now independently require real physical-device selection, identical complete game replay, mixed dispatch/readback and one session, comparable per-step measurements and injected-fault rollback using the exact-SHA game binary and data.

## Graphical Radar Chase (active #21 validation candidate)

```sh
cargo run --release --manifest-path runtime-rust/Cargo.toml --features window --bin doc-game-window -- engine/radar_chase.doc
# Automated real surface presentation and GPU-rendered cell verification:
DOC_GPU_ALLOW_SOFTWARE=1 xvfb-run -a cargo run --release --manifest-path runtime-rust/Cargo.toml --features window --bin doc-game-window -- engine/radar_chase.doc --replay=edsssxwddddsspr --verify-pixels
```

WASD or arrows move, E spawns, X despawns, P pauses, R restarts, Esc exits. The window title reports DOC score and state; shader displays player, coin, wall and live hazards, with DOC pulse animation and status border. The same DOC recurrence, carry fields and automatic compute scheduling are used; the renderer only reads published scene values. The window's software graphics and software compute CI are distinct from physical GPU proof. Replay presents every logical state, including epoch zero, and optional verification reads actual rendered pixels from a matching offscreen texture. This is a candidate until exact CI passes; physical graphics proof, input/resize and broader error validation remain required. Full editor, generated art and 3D remain deferred.
