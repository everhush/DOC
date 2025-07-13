# Performance optimization audit

Audit date: 2026-09-30.

## Purpose

This pass tested whether the ready-frontier runtime could recover the larger scaling number from the earlier submission without changing DOC semantics, benchmark workload, externally supplied participant limits, or the paper's implementation scope.

The acceptance rule was conservative: keep a change only if it is semantics-preserving, simpler or comparably simple, passes correctness/sanitizer validation, and shows a repeatable improvement rather than a single favorable timing run.

## Authoritative baseline

The publication numbers remain the retained campaign in `runtime/results/revision-2026-09-29/`:

| Participants | Raw mean | Raw speedup |
|---:|---:|---:|
| 1 | 150.221 ms | 1.000x |
| 2 | 82.267 ms | 1.826x |
| 3 | 60.325 ms | 2.490x |
| 4 | 46.412 ms | 3.237x |

Those values are raw arithmetic means over 20 fresh processes per participant limit after one unrecorded warmup. They are the only scaling values used in the manuscript.

## Explored implementation changes

The optimization experiments were local exploratory passes and are not article evidence.

1. **Move small premise-vector preparation into the parallel frontier task.** One 20-sample pass produced an apparent four-participant speedup of about 3.31x, but repeated A/B measurement did not show a stable gain over run-to-run variation. Rejected as insufficiently repeatable.
2. **Replace the shared dynamic queue with an atomic next-index scheduler.** The combined variant produced about 3.09x at four participants on the comparable host. Rejected as a regression.
3. **Wake only the number of workers apparently needed by the current frontier.** This regressed the measured result and added scheduler policy complexity. Rejected.
4. **Remove per-task statistics atomics and aggregate counts inside the pool.** The resulting four-participant measurement was about 3.24x, effectively reproducing the retained 3.237x result rather than improving it. Rejected because it did not justify an implementation change.
5. **Remove the per-task callable copy / mutex read.** Paired measurements were noisy and did not establish a repeatable improvement when isolated from other changes. Not retained.

## Final decision

No optimization change is retained. The original reviewed runtime is simpler, already passes the conformance/sanitizer evidence, and its 3.237x four-participant result is reproducible within normal run variation on the retained environment.

The earlier submission's approximately 3.85x value was collected on a different Intel host and with a median/paired-speedup presentation. It is not an apples-to-apples target for the revised raw-mean AMD/cgroup campaign.

Further attempts to force a larger number would require machine-specific affinity/scheduler tuning, a different workload, or broader runtime restructuring. Those changes would exceed the paper's current empirical scope or make the witness less natural relative to the semantics.

## Publication boundary

The final manuscript therefore makes no optimization-derived speedup claim beyond the retained campaign. The implementation and paper remain synchronized: complete ready-frontier evaluation is unchanged, `DOC_MAX_WORKERS` remains an external participant limit, and the single-host four-CPU result is not extrapolated to distributed or many-core scaling.
