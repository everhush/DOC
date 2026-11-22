# DOC execution-backend contract — 2026-11-22 decision

This supersedes prior *automatic CPU/GPU selection* proposals. It is a **host execution policy**, not a DOC language or calculus primitive. One directly authored DOC program retains its logical meaning regardless of which supported backend is selected. Rust and Goose (not Go) remain independently implemented native runtimes.

## Normative behavior

1. **CPU by default.** The general-purpose native CLI runs CPU when no backend is specified. The first option immediately after the source path may be `--backend=cpu` or `--backend=gpu`. All other source assignments and supported CLI options follow this selection. There is no need to annotate DOC source code with backend decisions.
2. **Strict explicit execution.** `--backend=cpu` uses the native CPU runtime. `--backend=gpu` must either execute the *supported DOC computation* on a real selected GPU execution path or fail nonzero with an actionable diagnostic. Never silently execute an unsupported GPU computation on CPU, print GPU-success markers without actual GPU dispatch, or publish half-computed results. A GPU path may still use CPU for operating-system effects, device setup, transfers and necessary host coordination.
3. **No `auto` mode.** There is no automatic backend choice, cost model, runtime switching, or implicit CPU/GPU migration requirement. An explicit hybrid mode, if ever needed, requires a new separate documented opt-in contract. It must not silently change this strict behavior.
4. **Physical capability checks remain necessary.** The selected device must still be created/validated, with feature limits, memory, synchronization and errors handled safely. Driver/API selection under `wgpu` or SDL3 `gfx` is not automatic DOC CPU/GPU placement. A software Vulkan adapter (e.g., llvmpipe/lavapipe) may be used for *explicitly labeled software-backend tests* but must not count as physical GPU acceleration. Hardware proof requires a physically identified adapter.
5. **Same program, same semantics.** Both native Rust and Goose must preserve typed DOC source/repair behavior, demanded recurrence, immutable publication, graph generations, effects/failure boundaries, and output when supported on both execution backends. Resource constraints and unsupported constructs should be diagnosed, not silently downgraded.
6. **No speedup assumption.** CPU parallelism follows DOC ready-frontier dependencies. A GPU is not necessarily faster, and a full DOC program with OS I/O cannot literally run wholly inside a shader. GPU execution is about the declared computational evaluator, not an absence of CPU-side orchestration.

## Status at adoption (NOT a general-purpose GPU release)

The current general-purpose Rust `doc` and native Goose `doc-goose` CLIs are **CPU executors only**. They default to CPU, permit an explicit `--backend=cpu`, and **reject `--backend=gpu`** because a general-purpose DOC GPU evaluator has not been implemented. Both reject `--backend=auto` and unknown values.

```sh
# Both CLIs accept this shape: source path first, backend selector next.
doc program.doc
doc program.doc --backend=cpu
doc-goose program.doc
doc-goose program.doc --backend=cpu

# Both currently fail with DOC_GPU_UNSUPPORTED (strict fail-closed).
doc program.doc --backend=gpu
doc-goose program.doc --backend=gpu
```

Separate *GPU test executables* remain operational for bounded DOC-derived Boolean, signed integer comparisons, dependent stages and reductions. They **are not general-purpose DOC GPU interpreters**. Rust's dedicated `webgpu_bool` test executable defaults to GPU (because it is a GPU regression program); it supports `DOC_GPU_EXECUTION=gpu|cpu` with no `auto`. `webgpu_integer_eq` likewise offers explicit CPU/GPU selection. Goose's `doc_sdl3_gpu.goose` is a native Goose `gfx` / SDL3 **GPU-only** experimental execution path and fails closed when no device is available. Rust `wgpu` and Goose SDL3 are different native device interfaces; SDL3 does not expose the WebGPU API.

## Implementation work remaining — required for the selected-backend goal

- Design and implement a **general-purpose DOC GPU execution realization** beyond a fixed operator-kernel catalog. Define the evaluable computational subset, graph/recurrence representation, dynamic work where applicable, data model, scheduling/barriers, termination, memory ownership, error/cancellation and immutable publication policies. Avoid claiming arbitrary OS effects can run in shaders.
- Connect `--backend=gpu` from **both native general-purpose DOC CLIs** to genuinely executed supported GPU computations using independent Rust `wgpu` and Goose SDL3 `gfx` implementations. Unsupported programs/devices must reject, not fake GPU execution. Expand supported semantic coverage to meet the agreed HVM-like general-purpose goal.
- Execute identical DOC source cases in selected CPU and selected GPU modes, including nontrivial recurrence/dependent work, malformed/resource-limited inputs, injection/device loss, pure-state parity, no partial publication, physical-adapter identification, and honest CPU/GPU end-to-end performance measurements. Keep real and software GPU adapter evidence separate.
- Verify the strict selector with `bash ci/check-explicit-backend.sh DOC_EXECUTABLE runtime-rust/examples/repair.doc`, using both Rust and Goose native binaries. CI and `ci/run-all-local.sh` exercise this regression. This proves CLI admission only, **not GPU generality**.

## Scope and tracking

This changes **execution selection and acceptance criteria**, not the submitted manuscript's theorems or the game-engine priority. Do not add a `gpu` or `cpu` DOC core primitive. Do not reintroduce Goose's deprecated WGSL generator, Rust-hosted Goose GPU dispatch, C/C++ native DOC runtime, or unnecessary compatibility layers.

- [Secondary final local acceptance #2](https://github.com/x0796666-ui/DOC/issues/2)
- [Canonical language and runtime #7](https://github.com/imxade/DOC/issues/7)
- [Experimental evidence #9](https://github.com/imxade/DOC/issues/9)
- [Deferred DOC-native game engine #10](https://github.com/imxade/DOC/issues/10)

The strict backend selection contract must be satisfied independently in both runtimes before any general-purpose GPU readiness claim. Kaggle live validation remains a separate ChatGPT-side task; no DOC-imposed artificial GPU-run caps apply.
