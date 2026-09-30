# Performance optimization audit

Audit date: 2026-09-30.

## Purpose

This pass tested whether the ready-frontier runtime could recover the larger scaling number from the earlier submission without changing DOC semantics, benchmark workload, externally supplied participant limits, or the paper's implementation scope.

The acceptance rule was conservative: keep a change only if it is semantics-preserving, simpler or comparably simple, passes correctness/sanitizer validation, and shows a repeatable improvement rather than a single favorable timing run.

## Authoritative baseline

At the time of this optimization audit, the reviewer-revision publication numbers came from `runtime/results/revision-2026-09-29/`:

| Participants | Raw mean | Raw speedup |
|---:|---:|---:|
| 1 | 150.221 ms | 1.000x |
| 2 | 82.267 ms | 1.826x |
| 3 | 60.325 ms | 2.490x |
| 4 | 46.412 ms | 3.237x |

Those values are raw arithmetic means over 20 fresh processes per participant limit after one unrecorded warmup. They were the manuscript values during the optimization audit and are retained below as historical context.

## Explored implementation changes

The optimization experiments were local exploratory passes and are not article evidence.

1. **Move small premise-vector preparation into the parallel frontier task.** One 20-sample pass produced an apparent four-participant speedup of about 3.31x, but repeated A/B measurement did not show a stable gain over run-to-run variation. Rejected as insufficiently repeatable.
2. **Replace the shared dynamic queue with an atomic next-index scheduler.** The combined variant produced about 3.09x at four participants on the comparable host. Rejected as a regression.
3. **Wake only the number of workers apparently needed by the current frontier.** This regressed the measured result and added scheduler policy complexity. Rejected.
4. **Remove per-task statistics atomics and aggregate counts inside the pool.** The resulting four-participant measurement was about 3.24x, effectively reproducing the retained 3.237x result rather than improving it. Rejected because it did not justify an implementation change.
5. **Remove the per-task callable copy / mutex read.** Paired measurements were noisy and did not establish a repeatable improvement when isolated from other changes. Not retained.

## Final decision

No optimization change is retained. The original reviewed runtime is simpler and already passes the conformance/sanitizer evidence. The later 100-sample bare-metal campaign uses the same runtime/benchmark implementation and reports a 3.544x four-participant raw-mean result without requiring a runtime optimization.

The earlier submission's approximately 3.85x value was collected on a different Intel host and with a median/paired-speedup presentation. It is not an apples-to-apples target for the revised raw-mean AMD/cgroup campaign.

Further attempts to force a larger number would require machine-specific affinity/scheduler tuning, a different workload, or broader runtime restructuring. Those changes would exceed the paper's current empirical scope or make the witness less natural relative to the semantics.

## Publication boundary

The final manuscript therefore makes no optimization-derived speedup claim. It reports the independently completed 100-sample bare-metal campaign as empirical evidence; complete ready-frontier evaluation is unchanged, `DOC_MAX_WORKERS` remains an external participant limit, and the four-participant result is not extrapolated to distributed or many-core scaling.


## Independent follow-up bottleneck analysis (2026-09-30)

A second investigation deliberately removed the earlier assumption that the retained 3.237x four-participant raw-mean result was close to the only attainable value.

### Exact-code comparison with the earlier submission

The following implementation files have the same Git history back to the initial submission commit `f4694c019306eedc1a31531b827e5a67fab19fca` and were not changed by the revision:

- `runtime/src/runtime.cpp`
- `runtime/include/doc/runtime.hpp`
- `runtime/benchmarks/benchmark.cpp`
- `runtime/benchmarks/workload_generator.cpp`

The old and revised benchmark records also identify the same benchmark-binary SHA-256:

`8c4f9d20da82192203fe800da5310a7ae5c3f9a94cd2171ced9a77b08fc66323`

Therefore the change from the earlier scaling result to the revised result is not a runtime-code or benchmark-code regression.

The earlier Intel Xeon Platinum 8573C scaling campaign contained 40 samples and reported median/paired statistics. Its raw means were approximately 144.135, 80.868, 55.027, and 39.513 ms for one through four participants, corresponding to raw-mean ratios of 1.000x, 1.782x, 2.619x, and 3.648x. Its published median/paired series was 1.000x, 1.959x, 2.853x, and 3.847x. The revised AMD EPYC campaign reports raw arithmetic means over its declared 20-process campaign.

### Work lower bound

Direct timing of the 40 unchanged prime-counting leaf computations produced approximately 146.703 ms of aggregate scalar leaf work. Ignoring the negligible reduction additions, the work-conservation lower bounds are therefore approximately:

| Participants | Work/p lower bound |
|---:|---:|
| 1 | 146.703 ms |
| 2 | 73.351 ms |
| 3 | 48.901 ms |
| 4 | 36.676 ms |

The retained revised campaign already contains runs near these limits:

- two participants: approximately 72.955 ms;
- three participants: approximately 49.961 ms, about 2.2% above work/3;
- four participants: approximately 36.851 ms, about 0.48% above work/4.

Thus the existing runtime can already reach essentially ideal four-way execution for this workload when the host supplies four CPUs cleanly.

### Scheduler-only overhead

A separate no-op reproduction of the same seven frontier sizes (40, 20, 10, 5, 2, 1, 1) measured the existing shared-queue worker-pool overhead. Repeated measurements were approximately:

- one participant: 0.15--0.20 microseconds;
- two participants: 7.4--10.2 microseconds;
- three participants: 20--26 microseconds;
- four participants: 43--48 microseconds.

At four participants this is roughly 0.1% of a 46 ms run and far below the multi-millisecond variation between retained process measurements.

### Independent scheduler and placement variants

Additional experiments compared:

- the existing mutex/deque dynamic queue;
- static per-participant partitioning;
- atomic next-index/chunked scheduling;
- targeted worker wake-up;
- fixed CPU affinity sets;
- a worker-start readiness barrier;
- direct access to the epoch callable instead of a per-task callable copy;
- per-task versus aggregated statistics counting;
- `-march=native` and LTO builds.

No alternative produced a repeatable general improvement large enough to replace the existing runtime. Static partitioning was particularly vulnerable when one vCPU was temporarily slow; the dynamic queue was more robust because faster participants continued draining remaining work. A worker-start readiness barrier sometimes improved the heavy four-participant first frontier by roughly 1--2 ms, but was neutral or negative at lower participant counts and increased overhead for cheap first frontiers, so it was not a general runtime improvement.

### Host variability

The current benchmark environment exposes five virtual CPUs with a four-CPU cgroup quota. Repeated local measurements showed substantial time-varying differences between vCPUs and observable hypervisor steal ticks in `/proc/stat`. Fixed CPU sets changed which runs were fast but did not produce a stable superior mapping. Multi-threaded runs also showed materially different aggregate CPU service time across otherwise identical executions.

This explains an important feature of both the old and revised raw data: the same executable sometimes produces near-ideal or even apparently superlinear paired ratios and sometimes materially slower multi-participant rows. Such variation is not consistent with a fixed serial bottleneck in the worker-pool implementation.

### Above-four-times absolute optimization boundary

Replacing the benchmark leaf's trial-division prime counter with a segmented sieve was tested only as a boundary experiment. It produced the same prime-count results and improved the leaf computation by well over 100x in local tests. This is a domain-specific optimization of the user function, not a DOC runtime optimization: the generic runtime has no semantic knowledge that independently declared leaf functions compute overlapping prime intervals. It is therefore intentionally excluded from the runtime and from article performance claims.

### Follow-up conclusion

For the unchanged parallel benchmark, there is no remaining generic runtime bottleneck large enough to explain the gap between a 3.237x raw-mean ratio and the near-4x samples. The implementation already reaches the work-conservation ceiling in favorable executions. Achieving a consistently higher raw mean on the current shared virtual host would require controlling host CPU service/placement, changing the benchmark granularity or user function, or introducing machine-specific scheduling policy. None is a justified generic DOC runtime optimization.

The final runtime therefore remains unchanged.


## Final 100-sample campaign adoption

The completed campaign in `runtime/results/independent-dedicated-100/` was subsequently adopted as the article's authoritative timing evidence. It used the unchanged runtime and benchmark code on bare-metal AMD Ryzen hardware, 100 fresh processes per row after three warmups, and participant limits 1--4. Its raw ratio-of-means scaling is 1.000x, 1.928x, 2.759x, and 3.544x. This supersedes the 20-sample EPYC values for article presentation but does not alter the optimization conclusion: no experimental scheduler modification was required or retained.
