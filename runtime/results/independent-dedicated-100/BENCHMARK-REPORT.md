# DOC complete benchmark report

Generated at `2026-09-30T14:55:22.543847+00:00` from `100` fresh processes per row.
Every benchmark executable checks result equality and exits nonzero on disagreement.

## Method

- One fresh process is used for every recorded measurement.
- Scenario order alternates forward and reverse for successive samples to reduce monotonic time-drift bias.
- Processor capacity is imposed externally through `DOC_MAX_WORKERS`; application graphs contain no worker count.
- One symmetric Tukey 1.5-IQR rule is used throughout. For paired direct/DOC rows, both timings must remain within their independently computed bounds.
- Raw, retained, excluded, bounds, summary, machine, and command records are all preserved beside this report.

## Host and run configuration

| Property | Value |
|---|---|
| Platform | Linux-6.18.53-x86_64-with-glibc2.42 |
| Compiler | g++ (GCC) 15.3.0 |
| Build mode | Release |
| CPU | AMD Ryzen AI 7 350 w/ Radeon 860M |
| Kernel | Linux 6.18.53 #1-NixOS SMP PREEMPT_DYNAMIC Mon Sep 21 13:06:06 UTC 2026 GNU/Linux |
| External limit | DOC_MAX_WORKERS environment variable; affinity/cgroup limits are recorded separately |
| Affinity CPUs | 16 |
| Cgroup CPU quota | None |
| Samples per row | 100 |
| Warmups per row | 3 |
| Benchmark SHA-256 | `49fd6b6d3b99e184dcb0471a48841a5344a411f2645cc5e0b4ddde3a3d7d286b` |
| Driver SHA-256 | `2755857a06f6c34c63d32d27f9c3d34620f34807fac8463369125086a79d4b58` |

## Initial evaluation, update density, and negative control

| Scenario | Direct mean | DOC mean | Evaluations | Retained |
|---|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | 349.942563 ms | 348.470007 ms | 4,095 | 95/100 |
| 1 changed source | 348.196546 ms | 0.595238 ms | 12 | 79/100 |
| 8 changed sources | 347.334517 ms | 1.727500 ms | 23 | 87/100 |
| 64 changed sources | 345.704658 ms | 10.790721 ms | 132 | 84/100 |
| 512 changed sources | 346.826596 ms | 85.898645 ms | 1,007 | 82/100 |
| 2,048 changed sources | 341.663941 ms | 342.601583 ms | 4,038 | 85/100 |
| Dense cheap negative control | 0.290818 ms | 55.790368 ms | 245,730 | 80/100 |

Exact cutoff: 0.004704 ms, 1 evaluation, 1 equality cutoff, retained 95/100. Its sub-millisecond timing is structural evidence, not a stable speed claim.

## Ready-frontier scaling

| Participants | Filtered mean | Filtered speedup | Raw mean | Raw speedup | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 268.990182 ms | 1.000x | 270.150884 ms | 1.000x | 97/100 |
| 2 | 139.508744 ms | 1.928x | 140.116979 ms | 1.928x | 96/100 |
| 3 | 97.694747 ms | 2.753x | 97.909380 ms | 2.759x | 99/100 |
| 4 | 76.008640 ms | 3.539x | 76.227757 ms | 3.544x | 98/100 |

## Incremental financial projection workload

This workload models 4,096 business units, each with four input cells and a 360-period fixed-point projection, followed by a balanced consolidation tree. It compares complete serial reevaluation, a conventional serial cached repair using a segment tree, and DOC repair; all three outputs must agree.

| Changed units | Full raw mean | Cached raw mean | DOC raw mean | DOC filtered mean | DOC evaluations | Retained |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 7.845494 ms | 0.002397 ms | 2.226469 ms | 2.131584 ms | 13 | 80/100 |
| 64 | 7.890013 ms | 0.128387 ms | 2.405297 ms | 2.307541 ms | 133 | 76/100 |
| 1,024 | 7.896386 ms | 2.045092 ms | 4.397884 ms | 4.280325 ms | 2,049 | 79/100 |

## Complete graph-expressed bitonic network

| Changed inputs | Direct mean | DOC mean | Evaluations | Cutoffs | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.075343 ms | 9.841016 ms | 1,986 | 691 | 84/100 |
| 8 | 0.077032 ms | 9.696120 ms | 2,830 | 763 | 87/100 |
| 64 | 0.080936 ms | 10.693791 ms | 8,828 | 994 | 91/100 |
| 256 | 0.061646 ms | 10.253324 ms | 13,808 | 256 | 78/100 |
| 512 | 0.046277 ms | 10.493118 ms | 23,040 | 0 | 75/100 |

The network has 11,520 compare-exchanges and 23,552 total states. Every run checks DOC output against both direct execution of the same Batcher network and `std::sort`.

## Full timing distributions

The table below reports every timing metric in the matrix. Confidence intervals use a two-sided 95% Student-t interval for up to 31 observations and the normal approximation above that; no interval is reported for a single observation. Filter sensitivity is the percentage change from the raw mean to the filtered mean.

| Scenario | Metric | n | Raw mean | Median | SD | 95% CI | Min | Max | Filtered mean | Sensitivity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | direct_ms | 100 | 351.142689 | 348.497456 | 10.909870 | [349.004355, 353.281024] | 338.995114 | 394.825408 | 349.942563 | -0.342% |
| Cold 2,048-leaf reduction | doc_ms | 100 | 349.868497 | 344.758694 | 11.443823 | [347.625508, 352.111486] | 339.766963 | 401.484721 | 348.470007 | -0.400% |
| 1 changed source | direct_ms | 100 | 350.676119 | 346.250466 | 11.762457 | [348.370678, 352.981561] | 338.513723 | 391.802389 | 348.196546 | -0.707% |
| 1 changed source | doc_ms | 100 | 0.661136 | 0.596359 | 0.177572 | [0.626332, 0.695941] | 0.543233 | 1.896067 | 0.595238 | -9.967% |
| 8 changed sources | direct_ms | 100 | 351.020602 | 344.931081 | 15.651746 | [347.952860, 354.088344] | 338.821246 | 451.399977 | 347.334517 | -1.050% |
| 8 changed sources | doc_ms | 100 | 1.761442 | 1.723499 | 0.134534 | [1.735073, 1.787811] | 1.667808 | 2.548229 | 1.727500 | -1.927% |
| 64 changed sources | direct_ms | 100 | 348.162947 | 343.685634 | 10.604230 | [346.084518, 350.241376] | 339.143401 | 389.252615 | 345.704658 | -0.706% |
| 64 changed sources | doc_ms | 100 | 11.044469 | 10.770118 | 0.787315 | [10.890156, 11.198783] | 10.629973 | 15.124542 | 10.790721 | -2.298% |
| 512 changed sources | direct_ms | 100 | 349.452185 | 345.244313 | 10.071486 | [347.478173, 351.426196] | 340.427159 | 382.308149 | 346.826596 | -0.751% |
| 512 changed sources | doc_ms | 100 | 87.670661 | 85.334247 | 4.641059 | [86.761013, 88.580308] | 84.678790 | 104.945680 | 85.898645 | -2.021% |
| 2,048 changed sources | direct_ms | 100 | 345.351700 | 340.232232 | 12.606833 | [342.880761, 347.822640] | 335.512457 | 401.547062 | 341.663941 | -1.068% |
| 2,048 changed sources | doc_ms | 100 | 346.975180 | 341.090605 | 13.359283 | [344.356761, 349.593600] | 335.867269 | 395.973815 | 342.601583 | -1.260% |
| Exact equality cutoff | elapsed_ms | 100 | 0.004786 | 0.004604 | 0.000864 | [0.004617, 0.004956] | 0.002605 | 0.007814 | 0.004704 | -1.730% |
| Dense cheap negative control | direct_ms | 100 | 0.309150 | 0.288325 | 0.049571 | [0.299434, 0.318866] | 0.281954 | 0.558327 | 0.290818 | -5.930% |
| Dense cheap negative control | doc_ms | 100 | 57.657713 | 56.035786 | 6.629355 | [56.358359, 58.957067] | 50.592874 | 87.307037 | 55.790368 | -3.239% |
| 1 participant | elapsed_ms | 100 | 270.150884 | 266.036467 | 11.034681 | [267.988086, 272.313681] | 258.476006 | 315.580464 | 268.990182 | -0.430% |
| 2 participants | elapsed_ms | 100 | 140.116979 | 139.399197 | 5.621626 | [139.015140, 141.218817] | 130.022256 | 159.974913 | 139.508744 | -0.434% |
| 3 participants | elapsed_ms | 100 | 97.909380 | 97.215508 | 6.032289 | [96.727051, 99.091708] | 90.546443 | 119.158019 | 97.694747 | -0.219% |
| 4 participants | elapsed_ms | 100 | 76.227757 | 75.622121 | 3.718809 | [75.498870, 76.956643] | 67.735001 | 87.435222 | 76.008640 | -0.287% |
| 1 changed business unit | cached_ms | 100 | 0.002397 | 0.002340 | 0.000327 | [0.002333, 0.002461] | 0.001974 | 0.004218 | 0.002308 | -3.726% |
| 1 changed business unit | direct_ms | 100 | 7.845494 | 7.586821 | 0.760885 | [7.696360, 7.994627] | 7.419260 | 11.232951 | 7.586134 | -3.306% |
| 1 changed business unit | doc_ms | 100 | 2.226469 | 2.158652 | 0.318284 | [2.164085, 2.288852] | 1.866251 | 3.578984 | 2.131584 | -4.262% |
| 64 changed business units | cached_ms | 100 | 0.128387 | 0.122478 | 0.014726 | [0.125501, 0.131274] | 0.121255 | 0.200822 | 0.123282 | -3.977% |
| 64 changed business units | direct_ms | 100 | 7.890013 | 7.553198 | 0.822129 | [7.728876, 8.051150] | 7.419490 | 11.200827 | 7.579908 | -3.930% |
| 64 changed business units | doc_ms | 100 | 2.405297 | 2.323402 | 0.348805 | [2.336931, 2.473663] | 2.014206 | 3.800584 | 2.307541 | -4.064% |
| 1,024 changed business units | cached_ms | 100 | 2.045092 | 1.972590 | 0.184506 | [2.008929, 2.081255] | 1.934696 | 2.968522 | 1.981818 | -3.094% |
| 1,024 changed business units | direct_ms | 100 | 7.896386 | 7.586559 | 0.793885 | [7.740785, 8.051988] | 7.422678 | 11.494858 | 7.621760 | -3.478% |
| 1,024 changed business units | doc_ms | 100 | 4.397884 | 4.299283 | 0.492841 | [4.301287, 4.494481] | 3.924100 | 7.233912 | 4.280325 | -2.673% |
| 1 changed input | direct_cold_ms | 100 | 0.468286 | 0.428529 | 0.169224 | [0.435118, 0.501454] | 0.318578 | 1.267649 | 0.444895 | -4.995% |
| 1 changed input | direct_update_ms | 100 | 0.079358 | 0.074375 | 0.010510 | [0.077298, 0.081418] | 0.072168 | 0.108522 | 0.075343 | -5.060% |
| 1 changed input | doc_cold_ms | 100 | 11.696416 | 11.042307 | 1.997555 | [11.304895, 12.087937] | 9.763994 | 19.370548 | 11.214117 | -4.123% |
| 1 changed input | doc_update_ms | 100 | 10.338453 | 9.834066 | 1.588892 | [10.027030, 10.649876] | 8.971556 | 18.127529 | 9.841016 | -4.812% |
| 8 changed inputs | direct_cold_ms | 100 | 0.459911 | 0.425042 | 0.127693 | [0.434883, 0.484939] | 0.320573 | 0.866925 | 0.452140 | -1.690% |
| 8 changed inputs | direct_update_ms | 100 | 0.080042 | 0.074700 | 0.010475 | [0.077989, 0.082095] | 0.071356 | 0.120403 | 0.077032 | -3.761% |
| 8 changed inputs | doc_cold_ms | 100 | 11.252574 | 10.838508 | 1.407484 | [10.976707, 11.528441] | 9.661793 | 17.332264 | 10.963869 | -2.566% |
| 8 changed inputs | doc_update_ms | 100 | 10.263208 | 9.680597 | 2.094366 | [9.852712, 10.673703] | 9.069410 | 24.995702 | 9.696120 | -5.525% |
| 64 changed inputs | direct_cold_ms | 100 | 0.473889 | 0.412010 | 0.179292 | [0.438748, 0.509031] | 0.322956 | 1.203293 | 0.463619 | -2.167% |
| 64 changed inputs | direct_update_ms | 100 | 0.083238 | 0.074319 | 0.015442 | [0.080211, 0.086265] | 0.070982 | 0.144456 | 0.080936 | -2.765% |
| 64 changed inputs | doc_cold_ms | 100 | 11.759847 | 10.970634 | 2.145146 | [11.339399, 12.180296] | 9.787164 | 20.858264 | 11.446164 | -2.667% |
| 64 changed inputs | doc_update_ms | 100 | 11.111407 | 10.368830 | 1.933654 | [10.732411, 11.490403] | 9.163351 | 18.463071 | 10.693791 | -3.758% |
| 256 changed inputs | direct_cold_ms | 100 | 0.436465 | 0.387189 | 0.132482 | [0.410498, 0.462432] | 0.321227 | 0.903102 | 0.416057 | -4.676% |
| 256 changed inputs | direct_update_ms | 100 | 0.065962 | 0.060889 | 0.011499 | [0.063708, 0.068216] | 0.059080 | 0.139990 | 0.061646 | -6.543% |
| 256 changed inputs | doc_cold_ms | 100 | 11.299640 | 10.677236 | 1.424727 | [11.020393, 11.578886] | 9.818749 | 16.379618 | 10.992545 | -2.718% |
| 256 changed inputs | doc_update_ms | 100 | 10.634272 | 10.179386 | 1.219109 | [10.395327, 10.873217] | 9.398810 | 16.085243 | 10.253324 | -3.582% |
| 512 changed inputs | direct_cold_ms | 100 | 0.464854 | 0.449590 | 0.123764 | [0.440596, 0.489111] | 0.321289 | 0.944329 | 0.448728 | -3.469% |
| 512 changed inputs | direct_update_ms | 100 | 0.052379 | 0.046462 | 0.020352 | [0.048390, 0.056368] | 0.045605 | 0.218634 | 0.046277 | -11.651% |
| 512 changed inputs | doc_cold_ms | 100 | 11.477505 | 10.871669 | 1.886703 | [11.107711, 11.847299] | 9.780665 | 20.108724 | 10.982320 | -4.314% |
| 512 changed inputs | doc_update_ms | 100 | 11.036844 | 10.373667 | 1.858592 | [10.672560, 11.401128] | 9.551085 | 20.201967 | 10.493118 | -4.926% |

## Outlier accounting

Recorded measurements: **2,000**. Excluded measurements: **273**. No result is removed merely for showing a smaller speedup; exclusion depends only on the same declared symmetric timing bounds.

## Evidence boundary

The suite supports a cost-shape claim, not universal superiority: sparse repair can avoid work; exact equality can stop propagation; coarse ready frontiers can consume externally granted processors; and dense or fine-grained workloads can lose to direct execution. Exact ratios are host- and workload-specific.

## Generated files

- `raw.csv`: every process measurement
- `retained.csv`: measurements used for filtered means
- `outliers.csv`: symmetrically excluded measurements
- `filter-bounds.csv`: the exact bounds used for each timing field
- `summary.csv`: raw and filtered distribution fields plus filter sensitivity
- `statistics.csv`: long-form n, mean, median, standard deviation, 95% confidence interval, minimum, and maximum
- `machine.json`: host, binary hash, and methodology
- `run-config.json`: requested scenarios and command-line settings
- `commands.log`: configure, build, and test commands
