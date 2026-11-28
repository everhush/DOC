# DOC paper-ordered requirement trace

## Active scope reconciliation — 2026-11-25

The following legacy dual-runtime tables and historical explicit-only GPU descriptions are retained for provenance and must not be read as the current acceptance record. The active reference is Rust on rtu0/doc2/main, with generated WGSL, automatic CPU/GPU placement in admitted host entry points and strict explicitly selected GPU execution; see [BACKEND-EXECUTION-CONTRACT.md](BACKEND-EXECUTION-CONTRACT.md). Goose is archived, not an acceptance requirement. #24 closed on 11e22c484a35a183ed9f77a2125afa5f22746c41; #15 reviews that combined foundation before the independent #11 handoff. The normative paper and original C++20 empirical results are unchanged. See [current #15 conformance ledger](docs/PRE-SELF-HOSTING-AUDIT.md) for current source-linked decisions, gaps and explicit production obligations. No claim of universal conformance or inherited empirical speedup.

---


**Backend decision (2026-11-22):** Execution hardware is a host policy, not a new DOC model primitive. General-purpose CLI CPU default, strict `--backend=cpu|gpu`, no `auto` or implicit fallback. The general-purpose GPU target remains **NOT IMPLEMENTED** in both native CLIs; existing Rust wgpu and Goose SDL3 operation-specific GPU paths are bounded evidence only. A same-source selected-CPU versus selected-GPU general-purpose execution gate is **OPEN**. See [BACKEND-EXECUTION-CONTRACT.md](BACKEND-EXECUTION-CONTRACT.md) and the final local Issue #2.

**Status: partial manuscript audit with bounded executable evidence.** The normative source is `preprint-model/dependency-oriented-computation.typ`; the separate draft `preprint-calculus/dependency-oriented-calculus.typ` describes only a finite typed expression fragment. The active language/runtimes must remain independent of the historical C++ source, its model checkers and its benchmarks, which are archived in the pre-Rust snapshot.

For **every manuscript definition, equation, theorem, corollary, proof assumption, algorithm, conditional contract and performance claim**, maintain: (i) authoritative paper anchor/lines, (ii) actual acceptance contract, (iii) Rust code/test/evidence, (iv) Goose code/test/evidence, (v) counterexamples/negative tests, (vi) PASS/FAIL/NOT IMPLEMENTED/BLOCKED and evidence revision. The initial rows below are a top-level index. Future review must expand them *paragraph by paragraph*, not merely check a feature-name box. A conditional realization contract must never be reported as an unconditional finite-kernel theorem.

## Source-ordered trace and validation obligations

| Manuscript section / approximate source lines | Required property and evidence boundary | Rust evidence | Goose evidence |
| --- | --- | --- | --- |
| Introduction and problem/semantic boundary (191–243) | Demonstrate one general model for initially unmaterialized and later reactively repaired typed state; external effects are explicit source facts or separately handled | Native finite-source CLI exercised | Native typed finite DAG and two source batches exercised in `runtime-goose/check-doc-typed.sh`; explicit effects remain open |
| Model intuition / structural properties (244–279) | Reactive dependency propagation, temporal reuse, independent ready frontier, protected logical identity, conditional placement/elasticity; distinguish structural affordances from actual performance | Partial finite model | `runtime-goose/doc_graph.goose` and `doc_typed.goose` implement serial minimal-frontier repair and exact cutoff; protected identity, placement and elasticity NOT IMPLEMENTED |
| Standing assumptions (280–300) | Explicit finite DAG, typed pure deterministic total local functions, repair-admissible seeds, cutoff soundness, admitted source batches; model failure values/effects correctly | Partial; bounded `i64` overflow is a host error outside total-function theorem | `runtime-goose/doc_typed.goose` checks finite topological declarations and typed operations; checked `i64` overflow exits, not a total DOC failure value. Partial, not full theorem contract |
| Typed logical state and local definition (324–389) | Stable identities independent of addresses, premise sequences incl. repeated occurrences, single derived producer, induced user graph, `bot` as absence not null, typed valuation/satisfaction | Basic typed graph / int/bool only | `runtime-goose/doc_bool.goose` admits exactly two named Boolean sources and one named Boolean result. The native conformance script rejects duplicate or missing source declarations, premature definitions, and invalid expressions. |
| Computational expansion (390–418) | Refine local definitions to finite boundary-equivalent DAGs and physically fuse where meaning preserved; different scheduling granularity must not alter observations | No expansion equivalence gate | Absent |
| Initial/later stabilization (419–462) | Initial source facts and retained stable derived results yield same repair semantics; changing source values yields selective reactive repair | Basic code only | Absent |
| Finite transition (463–572) | Repair-admissible `(nu,A)`, atomic validated source batch, minimal active ready set, any nonempty legal subset, same-pre-valuation independent candidates, sound cutoff, whole-frontier logical commit, no partial publication on local failure | Finite subset exercised by `runtime-rust/tests/semantics.rs` including atomic batch and failed frontier cases | `doc_typed.goose` evaluates a finite ready set before publication and uses exact value cutoff. Native two-batch differential tests exercised the admitted subset. Independent schedule variation and recoverable failure remain open |
| Central metatheory (573–622) | For every legal finite schedule: invariant preservation, termination, unique stable valuation equal complete topological reevaluation, at-most-once per fixed episode, independent ready commutation, dependency-local repair | Finite schedule tests and randomized oracle executed in `runtime-rust/tests` | Native typed evaluator agreed with Rust and a separate arithmetic oracle for 32 initial and repaired valuations. Full schedule independence remains open |
| Reactivity/reuse/parallelism (623–672) | Measurements on equal semantic workloads: density sweeps, cutoff hit rate, eligible concurrent work and overhead, no claimed universal speedup | No native benchmark evidence | Absent |
| Optimization and provenance (673–702) | Preserve independent local-kernel optimization vs cross-update reuse; types cover value invariants while graph/valuation/activation carry computational currentness | Not evidenced | Absent |
| Demand / forward recurrence / universality (703–772) | Ancestor-closed demand equivalence; finite demanded-prefix support; single typed forward carry, explicit noncarried facts, retention/halting/divergence rules; implement *unbounded or arbitrarily extensible* computation and validate the deterministic two-counter-machine simulation | `runtime-rust/src/recurrence.rs`, `tests/recurrence.rs`, `examples/triangular.doc`, `examples/counter_transfer.doc`: bounded prefix and typed carry; native 1/4-worker oracle invoked in `runtime-goose/check-doc-typed.sh` | `runtime-goose/doc_typed.goose` and `check-doc-typed.sh`: bounded typed carry and direct instruction oracle for `counter_transfer.doc` through epoch 40, with stop-on-zero true/false. Goose/Rust checks included in CI run 44754504333, but exact-SHA evidence for later 7fb4c8d is UNVERIFIED. **Not universal:** `i64` bounded, no arbitrarily extensible naturals, full demand/retention or proof of all two-counter programs |
| Graph-version replacement (773–800) | Validate candidate privately, compatibility of name, role, type, equality, semantic key and ordered premise identities; atomic generation switch, reject stale in-flight work | Not implemented | Absent |
| Safe physical realization (801–855) | Immutable complete publication, pin active reads, protect logically available/evicted values, reconstruct correctly, fence old reconstructions, prevent dangling access, eventually reclaim unreachable materialization under progress/retention assumptions; no required GC or user-visible free | Not implemented | Absent |
| Placement / transport / bounded recovery (856–938) | Orthogonal value/evaluation placement, role generations, stale/duplicate/wrong-role transport handling, moving resources without changing logical semantics; join/drain under quiescence and bounded fail-stop reconstruction under explicit single-authority assumptions | Not implemented | Absent |
| Distribution and effects (939–964) | Require explicit conflict, replica, retention, partition, authorization and irreversible-effect policy; pure derived rules never secretly perform effects | Not implemented | Absent |
| Worked interpretations and validation (965–1193) | General-purpose usable examples, real input/output at explicit boundary, source-to-result conformance, negative cases, reproducible local 1/2/4-core and memory measurements with raw data; distinguish original historical data from new claims | Finite source examples and software-adapter WebGPU dispatch/readback executed. General-purpose and matched measurements remain open | Native typed Boolean/int examples and bounded recurrence oracles executed in CI; independently generated WGSL dispatched by Rust host on Mesa lavapipe in run 44754504333. **No Goose-owned WebGPU host/device implementation**, general-purpose programs, or matched memory/performance results |
| Limitations, related work, appendices (1194–1374) | Guard against overclaiming consensus, universal speedup, generic distributed recovery or proof of all extensions; check compact equations against implementations | Paper preserved; trace incomplete | Trace incomplete |

## Minimum semantic primitives: revise and justify at every continuation

The **main paper**, not syntax imitation, constrains the design. A candidate small *semantic basis* to evaluate, not a fixed language syntax, is: typed values and pure local transformations; stable source/derived state and dependency edges; atomic source-boundary transitions; private eligible frontier evaluation and publication; typed forward recurrence plus finite demand; and explicit host-effect admission/observation boundaries. Prefer expressing variables, loops, functions, user types, modules and ergonomics as well-defined composition or elaboration where practical, not one bespoke model primitive each.

**Irreducibility/expression tests:** (1) Can removing any proposed primitive be compensated by a semantics-preserving lowering? (2) Can a normal application encode functions, bindings, branching, unbounded data and structured calls? (3) Does the actual design simulate the paper's deterministic two-counter machine using finite step logic, typed forward carry, arbitrary natural values, demand and halt, rather than claiming a finite bounded machine is Turing complete? (4) Does the lowering preserve source-reactive incremental semantics and safe realization? (5) Do Rust and Goose independently execute the same source and return identical outcomes?

Provide a constructive lowering and independently executable finite-prefix differential checks for the Turing-completeness argument. Finite test suites cannot prove universal computation or verify an infinite non-halting run; distinguish a mathematical argument from bounded tests.

## Evidence gates before real-world use

Neither runtime may be marked production ready without: a functioning native compiler/toolchain on supported machines; common DOC source-language specification and independent parser/type-checker/evaluator; packaged CLI/library plus useful real-world programs with documented I/O/effects; bounded and randomized independent semantic oracles; reproducible full build/test/lint/fuzz/concurrency/reclamation validation; typed error/cancellation and real exception handling; safe default code with reviewed exceptions; recurrence, graph-version and physical-lifetime contracts tested per paper; honest profile-based benchmark raw data and resource envelopes. Record local toolchain, commands, outputs, commit SHAs and failures in [#7](https://github.com/imxade/DOC/issues/7) and comparisons in [#9](https://github.com/imxade/DOC/issues/9).

**Both implementations currently fail these gates.** Historical C++ paper evidence is not an acceptance shortcut.

### Review for the independently executed Boolean slice

Typed Boolean selection already expresses the interlock `if(a,b,false)` and the shared conditional fixture. The Goose parser's bounded call stack is an implementation resource limit. It adds no language-level recursion or loop operator. Evaluating both Boolean arms is observationally equivalent on this admitted pure, total subset. An extension with partial arithmetic or effects would need to preserve selected-branch behavior explicitly.

The paper's universality construction additionally needs an arbitrarily extensible natural domain and forward typed carry under demand. A finite case on the program counter can select increment, zero-test/conditional decrement, or halt. Each step can remain acyclic and feed only its successor epoch. The Boolean tests exercise selection only. They do not establish carry, retention, finite-prefix agreement, or the halting behavior of an executable two-counter model.


### Review for bounded recurrence and independent Boolean lowering

The triangular-number program needs two typed carry bindings, a fixed increment, and ordinary addition in each acyclic epoch. The CLI demand and carry bindings control epoch instantiation. They add neither a same-epoch loop operator nor arithmetic to the model. Prefix agreement in the executable tests follows from the recurrence equations `index' = index + 1` and `total' = total + index'`, with both starting at zero. Induction gives `total = index * (index + 1) / 2`, the separate test oracle. This argument is confined to prefixes where all machine-integer operations fit. Extensible counters and the universal machine proof obligations remain separate.

Historical only: Goose once emitted WGSL and depended on a Rust wgpu host for GPU dispatch (run 44751969485). That route was deleted, not retained as a fallback. The current Goose GPU route is native Goose SDL3 `gfx` with statically embedded shaders; Rust independently retains wgpu. SDL3 is not WebGPU. See the dated evidence addendum below.


## Evidence addendum — 2026-11-21, native Goose SDL3 transition

This addendum supersedes **stale implementation status in the source-ordered table above**, but does not silently upgrade any finite-core theorem or physical-realization contract. The table remains a manuscript-order index, **not yet a paragraph-complete trace**. Source of truth for this addendum: [secondary CI run 44887109976](https://github.com/x0796666-ui/DOC/actions/runs/44887109976), at commit `2a79399ac4460d8f36b53db3f15d54d1febd2f47`; all seven standard Rust/Goose/portability/software-GPU jobs passed, both opt-in physical-GPU jobs were skipped.

| Paper-order contract and classification | Native Rust location / evidence | Native Goose location / evidence | Honest status |
| --- | --- | --- | --- |
| Finite typed acyclic local computation, ready-frontier atomic repair and equality cutoff (finite-core) | `runtime-rust/src/lib.rs`, finite tests, CI Rust job | `runtime-goose/doc_typed_core.goose`, `doc_typed.goose`, CI Goose job | Executed admitted subset; exhaustive schedule-independence proof-to-code coverage OPEN |
| Demand, forward carry, exact arbitrary naturals and two-counter finite prefixes (recurrence/demand, **not** finite-kernel Turing completeness) | `runtime-rust/src/recurrence.rs`, `nat.rs`, recurrence tests | `runtime-goose/doc_typed_core.goose`, digit arena and epoch compaction; Goose recurrence checks | Finite-prefix tests PASS in preceding runs; unbounded theoretical simulation argument is separate from finite execution; resource-exhaustion policy OPEN |
| Typed structured values, directly authored applications and effects (general-purpose realization) | `runtime-rust/src/lib.rs`, native frontend/CLI and application tests | `runtime-goose/doc_typed_core.goose`, independent frontend/CLI and application tests | Signed comparisons, sorting, bounded pure functions/imports, sampled read effects and matched benchmarks exercised; full effects/packages/collections/error API NOT IMPLEMENTED |
| Graph-generation replacement, compatible atomic commit (graph-version replacement) | `runtime-rust/src/publication.rs` contains partial fencing; full graph replacement not demonstrated | Native Goose generation replacement not demonstrated | NOT IMPLEMENTED end-to-end |
| Immutable snapshots, reader pinning, eviction/reconstruction and eventual safe reclamation (safe physical realization) | Partial publication/generation checks; concurrent reader lifetime gate OPEN | Epoch digit compaction exists; active-reader protected snapshots and reconstruction OPEN | NOT IMPLEMENTED end-to-end |
| Independent placement, transport generations, join/drain and bounded fail-stop recovery (placed realization, conditional on authority/quiescence) | `runtime-rust/src/wgsl.rs`, Rust wgpu device path; transport proof obligations OPEN | `runtime-goose/doc_sdl3_gpu.goose` imports `gfx` and `doc_typed_core`; static `embed_shader`, own SDL3 GPU buffers/dispatch/readback; no Goose WGSL generator or Rust bridge | 77 native Goose SDL3 Mesa-Vulkan checks and 42 independent Rust-wgpu/Goose-SDL3 observed GPU episodes PASS; no physical Vulkan/Metal/D3D12, browser, transport or fail-stop proof |
| Effect admission, failure policy, resource/device loss and no consensus claims (policy-dependent boundary) | Explicit source effect subset; Rust GPU error/fallback tests | Read-only sampled file effect; SDL3 missing-device failure is strict, no Rust-host fallback | Full typed failure recovery, device loss under load, effect sequencing, authorization and partition policy OPEN; consensus not claimed |

**Minimum semantic-basis review:** The existing stable typed sources, pure finite DAG definitions, atomic repair/publication, and separate typed forward recurrence with finite demand remain distinct model operators. `if` is a pure value selector, not an effect or graph-generation operator. Bounded function calls, module imports, sorting networks and collection operators are source elaborations/local pure transformations; none establishes a new irreducible DOC scheduling primitive. Explicit file reads are admitted effects, not pure derived definitions. SDL3/wgpu are physical placement implementations, not new DOC operators. Removing atomic publication would permit partial-frontier observations; removing forward carry/demand would confine execution to the finite acyclic kernel. Conversely, introducing a separate game, thread or GPU core primitive is not justified by the existing evidence.

**Known documentation debt:** This document's older table still references obsolete Goose WGSL and old bounded-only natural limitations; those entries are historical and superseded here. A complete paragraph-by-paragraph audit of the manuscript, with exact theorem assumptions, tests, measurements and per-runtime statuses, remains OPEN. No release or production-parity claim follows from green CI.


## Evidence addendum — 2026-11-22, local AMD physical adapter and branch integration

This adds **observed local-machine evidence**, not a new language theorem or
full physical-realization/production certification. It supersedes the
2026-11-21 addendum's statement that no physical Vulkan evidence exists for
Rust, but retains the older finite-theorem and conditional-realization gaps.

- Local agent checked AMD Radeon 860M (RADV KRACKAN1, NixOS kernel 6.18.62,
  Mesa 26.3.0) at the source base
  `70394f1b65ee6d6ddad348cf497eb9b6f1fa8d52`, pushed as
  `feat/physical-gpu-parity` commit `b8111b6`.
- Rust `wgpu` explicitly logged `IntegratedGpu` / `Vulkan` / `radv`
  and 42 signed eq/lt/le source episodes. Independent Goose SDL3 Vulkan
  logged 77 native GPU/CPU checks and 42 matching GPU-result episodes.
  Data: [local-evidence](local-evidence/README.md), including 89 raw text
  files, device inventory and parity CSV.
- **Qualification:** Local Vulkan inventory also lists CPU llvmpipe. Goose
  logged `DOC_GOOSE_SDL3_DEVICE: vulkan`, but not the exact GPU model or
  PCI ID. Hence physical-GPU identity is verified for Rust but remains
  unconfirmed for Goose despite correct observed cross-runtime parity.
  [Linux Mesa forced-device repro](ci/physical-vulkan-dual-parity.sh)
  requires a new on-device run; it is not previously executed evidence.
  **Update (2026-11-22):** The forced-device run was executed with
  `DOC_HW_VK_SELECT=1002:1114!`. `local-evidence/forced-hardware/forced-physical-adapter.log`
  proves that exactly one physical device was exposed (`AMD Radeon 860M Graphics (RADV KRACKAN1)`).
  All 42 episodes and 77 Goose checks passed under this forced physical adapter.
- Local benchmark summaries report 31 samples per runtime/worker setting,
  with 1/2/4 workers and median/p95, but **individual raw latency samples
  and a full matched end-to-end GPU campaign remain OPEN**. Observed workload
  regressions (e.g. additional workers slower on these cases) must be retained.
  **Update (2026-11-22):** Sample-level CSVs with per-repetition wall, CPU,
  and RSS measurements are now committed in `local-evidence/typed-check/doc-matched-samples.csv`,
  `doc-churn-memory-samples.csv`, and `doc-ready-frontier-workers.csv`.
- Integrated two-parent merge
  [831d6f6](https://github.com/x0796666-ui/DOC/commit/831d6f65191ee071052a2ca5804bfaa283280eb5)
  preserves the local evidence plus later independent worker failure-atomic
  tests. [8d1275d](https://github.com/x0796666-ui/DOC/commit/8d1275dae6d87ba48182613f096d860ba028aa7e)
  adds offline auditing of all 42 recorded parity episodes.
- The later secondary [CI 44991253090](https://github.com/x0796666-ui/DOC/actions/runs/44991253090)
  showed failed jobs with zero executable steps, as did 44989812444,
  45033392874, and 45036875107. Their *runtime correctness* outcome is
  **UNVERIFIED** due to GitHub runner allocation/quota exhaustion on private repo.
  The local run-all entrypoint `ci/run-all-local.sh` passes all tests locally.

**Open contracts are unchanged:** complete recoverable typed effects/errors,
safe concurrent graph replacement across both runtimes, protected physical
lifetime and reconstruction, Goose pool slot reuse, transport and fail-stop
policies under stated assumptions, independent same-source real applications,
matched performance distributions, distribution packaging, and paragraph-level
paper-to-code evidence. [Secondary Issue #1](https://github.com/x0796666-ui/DOC/issues/1)
is the local engineering handoff and stays open until all three non-game
milestones truly pass. Do not infer universal acceleration or paper-parity
from bounded GPU observations.
