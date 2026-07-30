# DOC complete benchmark report

Generated at `2026-07-29T15:12:28.060769+00:00` from `20` fresh processes per row.
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
| Platform | Linux-6.12.13-x86_64-with-glibc2.41 |
| Compiler | c++ (Debian 14.2.0-19) 14.2.0 |
| Build mode | Release |
| CPU | INTEL(R) XEON(R) PLATINUM 8573C |
| Kernel | Linux 6.12.13 #1 SMP Thu Jul 23 17:57:28 UTC 2026 GNU/Linux |
| External limit | DOC_MAX_WORKERS environment variable; affinity/cgroup limits are recorded separately |
| Affinity CPUs | 5 |
| Cgroup CPU quota | 4.0 |
| Samples per row | 20 |
| Warmups per row | 0 |
| Benchmark SHA-256 | `8c4f9d20da82192203fe800da5310a7ae5c3f9a94cd2171ced9a77b08fc66323` |
| Driver SHA-256 | `2755857a06f6c34c63d32d27f9c3d34620f34807fac8463369125086a79d4b58` |

## Initial evaluation, update density, and negative control

| Scenario | Direct mean | DOC mean | Evaluations | Retained |
|---|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | 288.519941 ms | 286.095473 ms | 4,095 | 17/20 |
| 1 changed source | 294.818480 ms | 0.334745 ms | 12 | 14/20 |
| 8 changed sources | 290.561904 ms | 1.266982 ms | 23 | 16/20 |
| 64 changed sources | 294.942571 ms | 8.867390 ms | 132 | 16/20 |
| 512 changed sources | 286.756730 ms | 72.080774 ms | 1,007 | 17/20 |
| 2,048 changed sources | 282.153309 ms | 283.681869 ms | 4,038 | 16/20 |
| Dense cheap negative control | 0.218975 ms | 36.197347 ms | 245,730 | 15/20 |

Exact cutoff: 0.002128 ms, 1 evaluation, 1 equality cutoff, retained 20/20. Its sub-millisecond timing is structural evidence, not a stable speed claim.

## Ready-frontier scaling

| Participants | Filtered mean | Filtered speedup | Raw mean | Raw speedup | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 224.491868 ms | 1.000x | 239.533697 ms | 1.000x | 17/20 |
| 2 | 127.354575 ms | 1.763x | 136.679465 ms | 1.753x | 18/20 |
| 3 | 112.816400 ms | 1.990x | 130.477816 ms | 1.836x | 19/20 |
| 4 | 85.642649 ms | 2.621x | 91.113979 ms | 2.629x | 19/20 |

## Incremental financial projection workload

This workload models 4,096 business units, each with four input cells and a 360-period fixed-point projection, followed by a balanced consolidation tree. It compares complete serial reevaluation, a conventional serial cached repair using a segment tree, and DOC repair; all three outputs must agree.

| Changed units | Full raw mean | Cached raw mean | DOC raw mean | DOC filtered mean | DOC evaluations | Retained |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5.315847 ms | 0.001332 ms | 2.355978 ms | 1.924928 ms | 13 | 16/20 |
| 64 | 4.778584 ms | 0.074718 ms | 1.941784 ms | 1.922077 ms | 133 | 14/20 |
| 1,024 | 5.213841 ms | 1.234868 ms | 4.063995 ms | 3.418937 ms | 2,049 | 16/20 |

## Complete graph-expressed bitonic network

| Changed inputs | Direct mean | DOC mean | Evaluations | Cutoffs | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.047181 ms | 9.099246 ms | 1,986 | 691 | 18/20 |
| 8 | 0.047390 ms | 8.848260 ms | 2,830 | 763 | 17/20 |
| 64 | 0.046390 ms | 8.987333 ms | 8,828 | 994 | 14/20 |
| 256 | 0.038982 ms | 9.239995 ms | 13,808 | 256 | 17/20 |
| 512 | 0.031304 ms | 9.129710 ms | 23,040 | 0 | 17/20 |

The network has 11,520 compare-exchanges and 23,552 total states. Every run checks DOC output against both direct execution of the same Batcher network and `std::sort`.

## Full timing distributions

The table below reports every timing metric in the matrix. Confidence intervals use a two-sided 95% Student-t interval for up to 31 observations and the normal approximation above that; no interval is reported for a single observation. Filter sensitivity is the percentage change from the raw mean to the filtered mean.

| Scenario | Metric | n | Raw mean | Median | SD | 95% CI | Min | Max | Filtered mean | Sensitivity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | direct_ms | 20 | 296.291698 | 290.918312 | 22.773707 | [285.633397, 306.949998] | 275.357723 | 355.354899 | 288.519941 | -2.623% |
| Cold 2,048-leaf reduction | doc_ms | 20 | 292.741054 | 285.230924 | 19.279055 | [283.718282, 301.763826] | 279.252647 | 347.540801 | 286.095473 | -2.270% |
| 1 changed source | direct_ms | 20 | 309.607591 | 288.741060 | 44.650708 | [288.710657, 330.504525] | 274.373980 | 412.398615 | 294.818480 | -4.777% |
| 1 changed source | doc_ms | 20 | 0.349742 | 0.329531 | 0.040853 | [0.330622, 0.368861] | 0.319373 | 0.457766 | 0.334745 | -4.288% |
| 8 changed sources | direct_ms | 20 | 297.049457 | 287.639962 | 29.699189 | [283.149968, 310.948945] | 276.030036 | 410.510359 | 290.561904 | -2.184% |
| 8 changed sources | doc_ms | 20 | 1.357903 | 1.255768 | 0.229287 | [1.250595, 1.465212] | 1.213864 | 2.052019 | 1.266982 | -6.696% |
| 64 changed sources | direct_ms | 20 | 330.318181 | 295.041023 | 98.253076 | [284.334854, 376.301508] | 276.070002 | 644.199491 | 294.942571 | -10.710% |
| 64 changed sources | doc_ms | 20 | 9.174572 | 8.709807 | 1.374970 | [8.531074, 9.818070] | 8.279585 | 14.459734 | 8.867390 | -3.348% |
| 512 changed sources | direct_ms | 20 | 294.623199 | 286.471419 | 28.739987 | [281.172626, 308.073773] | 278.025677 | 408.853281 | 286.756730 | -2.670% |
| 512 changed sources | doc_ms | 20 | 73.310017 | 72.320490 | 5.191487 | [70.880355, 75.739680] | 67.841699 | 91.815923 | 72.080774 | -1.677% |
| 2,048 changed sources | direct_ms | 20 | 292.589087 | 281.487932 | 30.524505 | [278.303343, 306.874831] | 273.575127 | 403.768139 | 282.153309 | -3.567% |
| 2,048 changed sources | doc_ms | 20 | 303.647928 | 282.851111 | 71.876895 | [270.008892, 337.286964] | 276.618858 | 604.387213 | 283.681869 | -6.575% |
| Exact equality cutoff | elapsed_ms | 20 | 0.002128 | 0.002017 | 0.000590 | [0.001851, 0.002404] | 0.001245 | 0.003309 | 0.002128 | +0.000% |
| Dense cheap negative control | direct_ms | 20 | 0.227308 | 0.224475 | 0.035211 | [0.210829, 0.243787] | 0.195335 | 0.353301 | 0.218975 | -3.666% |
| Dense cheap negative control | doc_ms | 20 | 43.697902 | 35.677979 | 21.517300 | [33.627611, 53.768192] | 33.051903 | 121.126148 | 36.197347 | -17.165% |
| 1 participant | elapsed_ms | 20 | 239.533697 | 221.903355 | 39.208366 | [221.183828, 257.883567] | 213.406344 | 356.193024 | 224.491868 | -6.280% |
| 2 participants | elapsed_ms | 20 | 136.679465 | 129.642137 | 32.728318 | [121.362317, 151.996613] | 107.412334 | 227.667157 | 127.354575 | -6.822% |
| 3 participants | elapsed_ms | 20 | 130.477816 | 109.861007 | 85.543619 | [90.442630, 170.513002] | 74.376404 | 466.044721 | 112.816400 | -13.536% |
| 4 participants | elapsed_ms | 20 | 91.113979 | 83.745869 | 26.800650 | [78.571033, 103.656925] | 74.224142 | 195.069242 | 85.642649 | -6.005% |
| 1 changed business unit | cached_ms | 20 | 0.001332 | 0.001288 | 0.000129 | [0.001272, 0.001392] | 0.001181 | 0.001585 | 0.001296 | -2.696% |
| 1 changed business unit | direct_ms | 20 | 5.315847 | 4.705027 | 1.564801 | [4.583505, 6.048188] | 4.410345 | 9.605768 | 4.695942 | -11.661% |
| 1 changed business unit | doc_ms | 20 | 2.355978 | 1.963343 | 1.072975 | [1.853817, 2.858140] | 1.737803 | 5.796905 | 1.924928 | -18.296% |
| 64 changed business units | cached_ms | 20 | 0.074718 | 0.074172 | 0.002573 | [0.073513, 0.075922] | 0.071968 | 0.084812 | 0.074257 | -0.616% |
| 64 changed business units | direct_ms | 20 | 4.778584 | 4.587407 | 0.563026 | [4.515082, 5.042085] | 4.412728 | 6.979831 | 4.680037 | -2.062% |
| 64 changed business units | doc_ms | 20 | 1.941784 | 1.890211 | 0.131418 | [1.880279, 2.003289] | 1.797593 | 2.258519 | 1.922077 | -1.015% |
| 1,024 changed business units | cached_ms | 20 | 1.234868 | 1.203562 | 0.088678 | [1.193366, 1.276370] | 1.173816 | 1.571766 | 1.211325 | -1.907% |
| 1,024 changed business units | direct_ms | 20 | 5.213841 | 4.705363 | 1.084690 | [4.706196, 5.721486] | 4.502955 | 8.347369 | 4.836498 | -7.237% |
| 1,024 changed business units | doc_ms | 20 | 4.063995 | 3.323616 | 1.874509 | [3.186707, 4.941282] | 3.100060 | 11.413075 | 3.418937 | -15.872% |
| 1 changed input | direct_cold_ms | 20 | 0.418247 | 0.309043 | 0.274206 | [0.289916, 0.546578] | 0.294632 | 1.419129 | 0.430591 | +2.951% |
| 1 changed input | direct_update_ms | 20 | 0.048067 | 0.047546 | 0.004879 | [0.045784, 0.050351] | 0.042933 | 0.065692 | 0.047181 | -1.843% |
| 1 changed input | doc_cold_ms | 20 | 11.362574 | 9.166440 | 7.097785 | [8.040747, 14.684402] | 8.425899 | 40.813449 | 9.756206 | -14.137% |
| 1 changed input | doc_update_ms | 20 | 9.835272 | 9.020846 | 3.030808 | [8.416826, 11.253718] | 7.929456 | 21.976848 | 9.099246 | -7.484% |
| 8 changed inputs | direct_cold_ms | 20 | 0.360991 | 0.306586 | 0.105383 | [0.311671, 0.410311] | 0.294151 | 0.723031 | 0.367856 | +1.902% |
| 8 changed inputs | direct_update_ms | 20 | 0.047587 | 0.047643 | 0.001870 | [0.046712, 0.048462] | 0.044062 | 0.051624 | 0.047390 | -0.414% |
| 8 changed inputs | doc_cold_ms | 20 | 9.530898 | 9.037299 | 1.490880 | [8.833153, 10.228643] | 8.648711 | 14.647351 | 9.582676 | +0.543% |
| 8 changed inputs | doc_update_ms | 20 | 9.959071 | 8.864566 | 2.987188 | [8.561041, 11.357102] | 8.180247 | 19.120554 | 8.848260 | -11.154% |
| 64 changed inputs | direct_cold_ms | 20 | 0.319458 | 0.308924 | 0.023604 | [0.308412, 0.330505] | 0.295986 | 0.369069 | 0.313052 | -2.006% |
| 64 changed inputs | direct_update_ms | 20 | 0.085284 | 0.046843 | 0.166782 | [0.007228, 0.163339] | 0.042818 | 0.793565 | 0.046390 | -45.605% |
| 64 changed inputs | doc_cold_ms | 20 | 10.339955 | 9.174348 | 3.228667 | [8.828910, 11.851001] | 8.403667 | 22.022519 | 9.388899 | -9.198% |
| 64 changed inputs | doc_update_ms | 20 | 10.306106 | 9.215597 | 2.850982 | [8.971821, 11.640391] | 8.259255 | 19.077403 | 8.987333 | -12.796% |
| 256 changed inputs | direct_cold_ms | 20 | 0.328047 | 0.310429 | 0.050792 | [0.304276, 0.351818] | 0.291988 | 0.493907 | 0.320357 | -2.344% |
| 256 changed inputs | direct_update_ms | 20 | 0.041380 | 0.039025 | 0.009783 | [0.036802, 0.045959] | 0.036995 | 0.082401 | 0.038982 | -5.797% |
| 256 changed inputs | doc_cold_ms | 20 | 10.184211 | 9.133697 | 2.914482 | [8.820207, 11.548215] | 8.376659 | 20.457075 | 9.302713 | -8.656% |
| 256 changed inputs | doc_update_ms | 20 | 10.333907 | 9.043530 | 3.393245 | [8.745838, 11.921976] | 8.255088 | 22.345125 | 9.239995 | -10.586% |
| 512 changed inputs | direct_cold_ms | 20 | 0.338170 | 0.311343 | 0.086821 | [0.297537, 0.378803] | 0.293750 | 0.691533 | 0.320910 | -5.104% |
| 512 changed inputs | direct_update_ms | 20 | 0.033057 | 0.031391 | 0.008033 | [0.029297, 0.036816] | 0.030417 | 0.067130 | 0.031304 | -5.302% |
| 512 changed inputs | doc_cold_ms | 20 | 10.733911 | 9.372919 | 3.857755 | [8.928447, 12.539375] | 8.591611 | 25.703325 | 9.732125 | -9.333% |
| 512 changed inputs | doc_update_ms | 20 | 10.163706 | 9.095434 | 2.606242 | [8.943961, 11.383451] | 8.673367 | 18.018271 | 9.129710 | -10.173% |

## Outlier accounting

Recorded measurements: **400**. Excluded measurements: **67**. No result is removed merely for showing a smaller speedup; exclusion depends only on the same declared symmetric timing bounds.

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
