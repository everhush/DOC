# Autonomous scalability audit — issue #9

Status: exact production source/resource, CPU original-workload, early physical GPU and independent evidence verification passed. Full same-run independent compiler/application/physical regression remains in progress. This is a development evidence ledger, not a public release or manuscript change.

## Exact source identity

| Item | Git object |
|---|---|
| Production integration | `ad9a392e06faad670db39f934987b41bdec81798` |
| Full validation snapshot | `ed0cc865dbb0c416b903062c8869e6956635929e` |
| Runtime tree | `a7fe0554abea1a2b218929b33ad2f8f66f632f94` |
| Compiler tree | `9120f50dde55af7c0a656d43ece6acf824cbcab0` |
| Frozen reference tree | `a95a38bc6e9300aae815f83b570db5f99d32f221` |
| Original engine tree | `4d6044ac566fa8374f44e3f32f153d63b95f2b9f` |
| Unmodified main Typst | `0d6731a7cc9c9d5be83ba2ab247396d60c9b039d` |
| Unmodified calculus Typst | `5b11ff77ce093fe189253da1e3fec7b5a0ff00fe` |

The historical C++20 witness source and published dataset remain distinct (code 27a0139643237bfcaf05c71155fd137f297f6a53, data 8d3d647ea913732a39ad4cb83d17b9f7f3e20d17). The frozen Rust evaluator is a reference and bootstrap, not a production dependency.

## Decisions retained

- Generic CPU affinity/cgroup quota admission, no fixed total worker ceiling; same ready-frontier semantics, protected publication and no nested pools. Cost probe for independent frontier candidates; family and device placement retain generic grain/eligibility heuristics. These are not proofs of globally optimal placement.
- Bounded reusable scratch regions and immutable state-name index improve generic recurrence and large-graph repair without changing logical values.
- Application list and family extent derives from the region byte budget rather than the frozen reference's 4096-lane ceiling. Compiler workspace, source streams, text, natural and causal limits remain separate. Checked exact decimal input and exact list allocation preserve signed extrema, malformed-input rejection and failure cleanup.
- Physical GPU completion polling avoids unconditional millisecond sleeps; compact lexical family selector reduces transfer; grid-stride shader uses actual lane count and negotiated workgroup count limit. Portable local width 64 is not a total thread ceiling. No device name, workload name, or manually selected group cap appears in the production policy.
- Typed GPU planner retains conservative legacy admission and proves additional signed-32-bit expression bounds, including positive literal quotient/remainder. No arbitrary dynamic-divisor, managed-value or causal-recurrence GPU claim. Explicit GPU rejects unsupported input; auto may select admitted CPU/GPU work. The ordinary no-backend CLI defaults to CPU.

Rejected/superseded diagnostic iterations are kept as provenance: 32/128/256 local invocation widths offered no consistently superior general result; manually capped grid-stride sweeps are measurements only; invalid input range, harness assertions and transient Kaggle status transport failed earlier runs, not performance evidence.

## Reproducible execution and evidence

All new final timing runs use GitHub Actions CPU or actual Kaggle physical GPU. Historical local exploratory and software-adapter results are separate and not physical acceptance.

| Gate | Run | Result and artifact |
|---|---|---|
| Physical geometry diagnostic | [46048894528](https://github.com/xad3play/DOC/actions/runs/46048894528) | PASS; 5040 epochs, 3240 physical dispatches |
| Large-family pipeline diagnostic | [46048894537](https://github.com/xad3play/DOC/actions/runs/46048894537) | PASS attempt 2; 2556 epochs, 1116 dispatches |
| Standard algorithm CPU diagnostic | [46049477411](https://github.com/xad3play/DOC/actions/runs/46049477411) | PASS; 243 rounds |
| Standard algorithm physical diagnostic | [46050273592](https://github.com/xad3play/DOC/actions/runs/46050273592) | PASS; 777 rounds, 4224 dispatches |
| Production source and resource | [46052604155](https://github.com/xad3play/DOC/actions/runs/46052604155) | PASS; artifact 15224808904, SHA256 9d7c1b800675a5e17729eb9de603b7e7be11231b080587b16e849332f1843769 |
| Production historical workload CPU | [46053929420](https://github.com/xad3play/DOC/actions/runs/46053929420) | PASS; artifact 15225438430, SHA256 52ea07cf37b2f09ef76a2d2296b1d21c65143ff0127c4460d0b6515210479c84 |
| Production physical preflight | [46053188589](https://github.com/xad3play/DOC/actions/runs/46053188589) | PASS; artifact 15226800551, SHA256 50a6b7c5da1cb7d11e7ceb484237c523daf1fb196aab709fcda8e8ce7e2b4e16 |
| Production physical build | same run | artifact 15225636606, SHA256 ded359f3a046e1b38c662849d2d4bb63187d8f85a99f173805d96bad890ef123 |
| Independent returned-evidence audit | [46056113923](https://github.com/xad3play/DOC/actions/runs/46056113923) | PASS; artifact 15227225064, SHA256 a719e435495cdd73c4e4711c41880aac8a516760fc50172567ab88b2bbf00c55 |
| Full same-run independent validation | [46052437755](https://github.com/xad3play/DOC/actions/runs/46052437755) | PASS, all six jobs; physical artifact 15227957875, SHA256 aeaf10e30d72c2cee5aaa5c2a09316586923a7eb1ad5d1a17f4dd20e10399f91 |

Offline verification of unpacked GitHub artifacts (no benchmark or adapter execution):
```sh
python3 runtime-doc/tests/verify_autonomous_evidence.py \
  --physical physical --build doc11-stage2-gpu-evidence \
  --source-sha da93c980bbb8999b1f7c1d8b2491167c4c612bb5 --run-id 46053188589
```
All 880 raw tar members, 1827 CSV rows, 133 summary rows, 399 process pairs, 114 physical sessions and 4374 GPU dispatches verified. Independent closed-form polynomial/modular checks and LCG/reduction checksums, exact raw timings and binary/source/shader hashes. Per-lane numerical equality is separately checked by the timed harness outside the measured epoch; sorting uses independent qsort. No raw binary/log artifacts are tracked here.

## CPU results and limits

GitHub exposed two CPU affinity threads. Ordinary integrated DOC prime graph: 119 states, 79 evaluated derives, 7 frontiers, numerical oracle 76216, ten repetitions per configuration. Median times 2083.876 ms (one), 1196.414 ms (two), 1196.991 ms (auto). Auto speedup 1.741x; it matches explicitly requested two workers without hints.

The full original-size test-only historical-callback/CSR runtime witness includes 2217 rows with warmups (30 recorded repetitions and 3 warmups per row). It preserves original graph sizes, numerical callbacks and work counts but is not whole-program integration through the current compiler. Historical witness and native test host have different source ingress and metadata costs. Examples of warm medians: original vs native auto financial1024 3.1275/2.2705 ms; sorting512 8.3178/2.8808 ms; dense-cheap 30.7120/35.9546 ms. Equality cutoff preserves one evaluation. Original prime callback witness two-worker scaling is only about 1.03x on this particular shared runner (original 95.5921/93.2350 ms; native 95.8335/93.4598 ms); do not substitute the integrated DOC prime speedup for that measurement.

No claim that every original-size historical graph compiles through the current bounded compiler. The actual integrated prime graph and ordinary production family kernels are separate stronger compiler-emitted witnesses; large unrolled source workspaces remain a bounded implementation limitation.

## Physical results

Kaggle exposes four affinity CPUs and a four-CPU cgroup quota. Host lists two Tesla T4s (driver 580.178.04, 15360 MiB each); the runtime selects one physical adapter, not multi-GPU. Negotiated maximum workgroups per dimension 65535; 64 local invocations per group. At 4194304 admitted lanes the actual dispatch automatically uses 65535 workgroups and grid-stride covers the remainder. This is 1024x the previous fixed family ceiling, not a claim of 4.19 million simultaneous physical threads.

Warm median epoch times in ms; all modes use identical source/workload and independently checked outputs. Three fresh processes; each family has six epochs (first omitted from warm median); algorithm stress five rounds, sorting/reduction two. Device initialization, host input construction and independent oracle are outside epoch timing; source ingress, evaluation and publication are inside. Staged sort/reduction require host orchestration and packing; algorithm wall times separately include that work and oracle. Exact raw distributions, cold/device initialization and dispatch metrics are in the artifacts.

| Workload | Serial CPU | CPU auto | Strict GPU | Auto backend |
|---|---:|---:|---:|---:|
| Addition 64 | 0.00368 | 0.13895 | 0.21324 | 0.21265 |
| Addition 1048576 | 41.66639 | 33.40959 | 36.03025 | 36.97335 |
| Addition 4194304 | 235.52232 | 190.95026 | 229.16563 | 226.49314 |
| Polynomial 65536 | 4.79097 | 3.16040 | 1.69324 | 1.62024 |
| Polynomial 1048576 | 83.49648 | 52.04590 | 28.26764 | 28.46458 |
| Polynomial 4194304 | 382.01030 | 249.54002 | 194.51110 | 197.44213 |
| Modular map 262144 | 113.47645 | 65.97702 | 7.80232 | 7.54800 |
| Staged sort 65536 | 934.97618 | 578.18701 | 391.68411 | 393.16476 |
| Staged reduction 65536 | 3.91482 | 4.29413 | 5.83556 | 4.39542 |

Modular auto backend speedup 15.03x vs serial. Four-worker CPU modular result 66.45888 ms (1.71x); explicit worker limits are comparison controls only. Polynomial 64->4096 lanes, strict GPU: 40.26x end-to-end throughput increase (62.9% of proportional 64x) and 47.65x dispatch-wall throughput increase (74.5%). Earlier diagnostic baseline 30.15x end-to-end; earlier manually tuned combined diagnostic 42.78x. Different sessions, no physical-core efficiency interpretation. Negative results and saturation remain visible. No universal speedup or backend profitability guarantee.

## Correctness and readiness boundaries

The production source/resource preflight used ASan/UBSan, checked signed extrema and malformed input, million-element list, over-region rejection, shared-domain reference parity, 4097/16384 expanded native list oracles, allocation failure across 66 update and 33 snapshot ordinals, 128 replacements with stalled readers and zero live memory. Early hardware preflight uses actual compiler-generated shaders, no software device, verifies original 16/17 epoch game replays, actual mixed frontiers, injected failure rollback, actual device loss, submitted-work retirement, graph replacement, protected snapshot, strict numeric admission, pool growth/reuse/closure. Both games retain prior typed observations, with 876/878 GPU lanes and rejected successor epochs 3/4. Prior unchanged mesh/window evidence stays historical.

The complete same-run validation must finish before #9 is closed. No manuscript edits or public release. #14 must distinguish finite-model theorems, conditional extensions, implementation checks and historical/current empirical evidence; neither paper may imply unbounded physical resources, universal speedup, automatic discovery of all semantic dependencies or distributed elasticity from these results.

## Final same-run validation — 2026-11-28

Supersedes the pending status above. All six jobs of 46052437755 completed successfully at ed0cc865dbb0c416b903062c8869e6956635929e, with identical production runtime and compiler trees. Independent archive recheck: physical artifact 15227957875, 880 byte-matched archive members, 1827 numerical rows independently recomputed, 399 process pairs, 114 physical sessions and 4374 verified GPU dispatches. The actual selected adapter was one Tesla T4, not a software adapter. Original paper CPU regression and returned-evidence audit also passed. This is final DOC production evidence, separate from the newly requested private HVM comparison. No public release or manuscript change.
