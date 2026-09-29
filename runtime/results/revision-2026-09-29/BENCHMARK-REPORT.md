# DOC complete benchmark report

Generated at `2026-09-29T10:39:28.859122+00:00` from `20` fresh processes per row.
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
| Platform | Linux-6.18.44-x86_64-with-glibc2.41 |
| Compiler | c++ (Debian 14.2.0-19) 14.2.0 |
| Build mode | Release |
| CPU | AMD EPYC 9V74 80-Core Processor |
| Kernel | Linux 6.18.44 #1 SMP Sat Sep 26 20:02:31 UTC 2026 GNU/Linux |
| External limit | DOC_MAX_WORKERS environment variable; affinity/cgroup limits are recorded separately |
| Affinity CPUs | 5 |
| Cgroup CPU quota | 4.0 |
| Samples per row | 20 |
| Warmups per row | 1 |
| Benchmark SHA-256 | `8c4f9d20da82192203fe800da5310a7ae5c3f9a94cd2171ced9a77b08fc66323` |
| Driver SHA-256 | `2755857a06f6c34c63d32d27f9c3d34620f34807fac8463369125086a79d4b58` |

## Initial evaluation, update density, and negative control

| Scenario | Direct mean | DOC mean | Evaluations | Retained |
|---|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | 194.647782 ms | 195.766821 ms | 4,095 | 20/20 |
| 1 changed source | 192.469761 ms | 0.369425 ms | 12 | 18/20 |
| 8 changed sources | 192.690092 ms | 1.029775 ms | 23 | 19/20 |
| 64 changed sources | 192.349459 ms | 6.028953 ms | 132 | 20/20 |
| 512 changed sources | 192.519038 ms | 48.370088 ms | 1,007 | 19/20 |
| 2,048 changed sources | 187.542642 ms | 188.819979 ms | 4,038 | 18/20 |
| Dense cheap negative control | 0.214460 ms | 33.511879 ms | 245,730 | 17/20 |

Exact cutoff: 0.002607 ms, 1 evaluation, 1 equality cutoff, retained 20/20. Its sub-millisecond timing is structural evidence, not a stable speed claim.

## Ready-frontier scaling

| Participants | Filtered mean | Filtered speedup | Raw mean | Raw speedup | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 149.251759 ms | 1.000x | 150.221381 ms | 1.000x | 19/20 |
| 2 | 76.717431 ms | 1.945x | 82.266653 ms | 1.826x | 17/20 |
| 3 | 60.325490 ms | 2.474x | 60.325490 ms | 2.490x | 20/20 |
| 4 | 45.171660 ms | 3.304x | 46.411673 ms | 3.237x | 19/20 |

## Incremental financial projection workload

This workload models 4,096 business units, each with four input cells and a 360-period fixed-point projection, followed by a balanced consolidation tree. It compares complete serial reevaluation, a conventional serial cached repair using a segment tree, and DOC repair; all three outputs must agree.

| Changed units | Full raw mean | Cached raw mean | DOC raw mean | DOC filtered mean | DOC evaluations | Retained |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.822968 ms | 0.001343 ms | 1.256094 ms | 1.254395 ms | 13 | 18/20 |
| 64 | 4.991274 ms | 0.079473 ms | 1.397398 ms | 1.278481 ms | 133 | 13/20 |
| 1,024 | 4.964799 ms | 1.296315 ms | 2.681944 ms | 2.688490 ms | 2,049 | 19/20 |

## Complete graph-expressed bitonic network

| Changed inputs | Direct mean | DOC mean | Evaluations | Cutoffs | Retained |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.036783 ms | 5.713350 ms | 1,986 | 691 | 16/20 |
| 8 | 0.036772 ms | 5.781619 ms | 2,830 | 763 | 18/20 |
| 64 | 0.036819 ms | 6.288978 ms | 8,828 | 994 | 17/20 |
| 256 | 0.031021 ms | 6.430691 ms | 13,808 | 256 | 17/20 |
| 512 | 0.024635 ms | 6.353267 ms | 23,040 | 0 | 18/20 |

The network has 11,520 compare-exchanges and 23,552 total states. Every run checks DOC output against both direct execution of the same Batcher network and `std::sort`.

## Full timing distributions

The table below reports every timing metric in the matrix. Confidence intervals use a two-sided 95% Student-t interval for up to 31 observations and the normal approximation above that; no interval is reported for a single observation. Filter sensitivity is the percentage change from the raw mean to the filtered mean.

| Scenario | Metric | n | Raw mean | Median | SD | 95% CI | Min | Max | Filtered mean | Sensitivity |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cold 2,048-leaf reduction | direct_ms | 20 | 194.647782 | 192.191408 | 9.207702 | [190.338494, 198.957069] | 182.278979 | 214.688593 | 194.647782 | +0.000% |
| Cold 2,048-leaf reduction | doc_ms | 20 | 195.766821 | 193.975548 | 7.997670 | [192.023840, 199.509803] | 185.176805 | 210.851448 | 195.766821 | +0.000% |
| 1 changed source | direct_ms | 20 | 193.008513 | 191.966884 | 5.259355 | [190.547087, 195.469938] | 186.159426 | 203.172289 | 192.469761 | -0.279% |
| 1 changed source | doc_ms | 20 | 0.384299 | 0.365119 | 0.055592 | [0.358281, 0.410316] | 0.340752 | 0.562516 | 0.369425 | -3.870% |
| 8 changed sources | direct_ms | 20 | 192.774047 | 191.713437 | 5.612293 | [190.147443, 195.400651] | 183.742529 | 203.803111 | 192.690092 | -0.044% |
| 8 changed sources | doc_ms | 20 | 1.045359 | 0.970464 | 0.127457 | [0.985708, 1.105010] | 0.928356 | 1.341467 | 1.029775 | -1.491% |
| 64 changed sources | direct_ms | 20 | 192.349459 | 192.698870 | 4.746238 | [190.128177, 194.570741] | 183.185360 | 201.571276 | 192.349459 | +0.000% |
| 64 changed sources | doc_ms | 20 | 6.028953 | 5.967386 | 0.198388 | [5.936106, 6.121801] | 5.719979 | 6.383287 | 6.028953 | +0.000% |
| 512 changed sources | direct_ms | 20 | 193.580265 | 191.853885 | 7.297523 | [190.164959, 196.995572] | 184.471263 | 213.743592 | 192.519038 | -0.548% |
| 512 changed sources | doc_ms | 20 | 48.241971 | 47.533705 | 2.150416 | [47.235557, 49.248386] | 45.807757 | 52.553441 | 48.370088 | +0.266% |
| 2,048 changed sources | direct_ms | 20 | 189.051856 | 187.057593 | 5.971146 | [186.257305, 191.846406] | 182.706671 | 204.275872 | 187.542642 | -0.798% |
| 2,048 changed sources | doc_ms | 20 | 189.988561 | 188.516447 | 4.617640 | [187.827464, 192.149658] | 183.685377 | 203.114903 | 188.819979 | -0.615% |
| Exact equality cutoff | elapsed_ms | 20 | 0.002607 | 0.002519 | 0.000664 | [0.002297, 0.002918] | 0.001603 | 0.004066 | 0.002607 | +0.000% |
| Dense cheap negative control | direct_ms | 20 | 0.223340 | 0.211663 | 0.024394 | [0.211924, 0.234757] | 0.210657 | 0.305720 | 0.214460 | -3.976% |
| Dense cheap negative control | doc_ms | 20 | 33.886862 | 33.160637 | 2.739094 | [32.604942, 35.168783] | 31.497604 | 43.372259 | 33.511879 | -1.107% |
| 1 participant | elapsed_ms | 20 | 150.221381 | 149.798885 | 6.264457 | [147.289558, 153.153203] | 143.180762 | 168.644189 | 149.251759 | -0.645% |
| 2 participants | elapsed_ms | 20 | 82.266653 | 75.803928 | 14.957741 | [75.266295, 89.267011] | 72.955393 | 130.582241 | 76.717431 | -6.745% |
| 3 participants | elapsed_ms | 20 | 60.325490 | 55.781528 | 10.125080 | [55.586861, 65.064119] | 49.961342 | 76.956670 | 60.325490 | +0.000% |
| 4 participants | elapsed_ms | 20 | 46.411673 | 47.593368 | 7.799817 | [42.761288, 50.062058] | 36.851383 | 69.971908 | 45.171660 | -2.672% |
| 1 changed business unit | cached_ms | 20 | 0.001343 | 0.001277 | 0.000136 | [0.001279, 0.001407] | 0.001181 | 0.001602 | 0.001332 | -0.820% |
| 1 changed business unit | direct_ms | 20 | 4.822968 | 4.715896 | 0.427332 | [4.622973, 5.022963] | 4.519754 | 6.509596 | 4.707026 | -2.404% |
| 1 changed business unit | doc_ms | 20 | 1.256094 | 1.228562 | 0.129042 | [1.195701, 1.316486] | 1.095176 | 1.556069 | 1.254395 | -0.135% |
| 64 changed business units | cached_ms | 20 | 0.079473 | 0.074171 | 0.020962 | [0.069662, 0.089283] | 0.073841 | 0.168063 | 0.074044 | -6.831% |
| 64 changed business units | direct_ms | 20 | 4.991274 | 4.838223 | 0.554427 | [4.731797, 5.250751] | 4.601877 | 7.087225 | 4.791169 | -4.009% |
| 64 changed business units | doc_ms | 20 | 1.397398 | 1.288196 | 0.466768 | [1.178947, 1.615850] | 1.186414 | 3.348194 | 1.278481 | -8.510% |
| 1,024 changed business units | cached_ms | 20 | 1.296315 | 1.240580 | 0.101209 | [1.248949, 1.343682] | 1.203650 | 1.507287 | 1.300460 | +0.320% |
| 1,024 changed business units | direct_ms | 20 | 4.964799 | 4.873352 | 0.336449 | [4.807338, 5.122260] | 4.595069 | 5.840150 | 4.918728 | -0.928% |
| 1,024 changed business units | doc_ms | 20 | 2.681944 | 2.597780 | 0.170345 | [2.602221, 2.761667] | 2.450554 | 3.010626 | 2.688490 | +0.244% |
| 1 changed input | direct_cold_ms | 20 | 0.296621 | 0.276896 | 0.047192 | [0.274535, 0.318708] | 0.253842 | 0.427543 | 0.298827 | +0.743% |
| 1 changed input | direct_update_ms | 20 | 0.039191 | 0.037035 | 0.007825 | [0.035529, 0.042853] | 0.035494 | 0.069564 | 0.036783 | -6.145% |
| 1 changed input | doc_cold_ms | 20 | 6.688666 | 6.703162 | 0.594050 | [6.410645, 6.966687] | 5.910585 | 8.256633 | 6.614350 | -1.111% |
| 1 changed input | doc_update_ms | 20 | 5.884749 | 5.676354 | 0.625468 | [5.592024, 6.177474] | 5.359897 | 7.594938 | 5.713350 | -2.913% |
| 8 changed inputs | direct_cold_ms | 20 | 0.296747 | 0.276270 | 0.044865 | [0.275749, 0.317744] | 0.257207 | 0.412880 | 0.298804 | +0.693% |
| 8 changed inputs | direct_update_ms | 20 | 0.041275 | 0.036746 | 0.019720 | [0.032046, 0.050503] | 0.035724 | 0.125008 | 0.036772 | -10.908% |
| 8 changed inputs | doc_cold_ms | 20 | 6.473965 | 6.237742 | 0.550871 | [6.216152, 6.731777] | 5.971357 | 7.992215 | 6.383090 | -1.404% |
| 8 changed inputs | doc_update_ms | 20 | 5.851336 | 5.689844 | 0.402987 | [5.662734, 6.039937] | 5.457906 | 6.744308 | 5.781619 | -1.191% |
| 64 changed inputs | direct_cold_ms | 20 | 0.319702 | 0.264518 | 0.194071 | [0.228874, 0.410529] | 0.258438 | 1.135658 | 0.277963 | -13.055% |
| 64 changed inputs | direct_update_ms | 20 | 0.037766 | 0.036861 | 0.003602 | [0.036081, 0.039452] | 0.036004 | 0.052639 | 0.036819 | -2.508% |
| 64 changed inputs | doc_cold_ms | 20 | 6.388263 | 6.308994 | 0.323081 | [6.237059, 6.539468] | 5.889224 | 7.030409 | 6.343956 | -0.694% |
| 64 changed inputs | doc_update_ms | 20 | 6.351289 | 6.159600 | 0.704178 | [6.021727, 6.680850] | 5.656594 | 8.592708 | 6.288978 | -0.981% |
| 256 changed inputs | direct_cold_ms | 20 | 0.272785 | 0.268153 | 0.016848 | [0.264900, 0.280670] | 0.257787 | 0.320862 | 0.273219 | +0.159% |
| 256 changed inputs | direct_update_ms | 20 | 0.031218 | 0.031072 | 0.001199 | [0.030657, 0.031779] | 0.029815 | 0.035934 | 0.031021 | -0.632% |
| 256 changed inputs | doc_cold_ms | 20 | 6.431490 | 6.367624 | 0.435962 | [6.227456, 6.635524] | 5.859889 | 7.469609 | 6.418566 | -0.201% |
| 256 changed inputs | doc_update_ms | 20 | 6.482317 | 6.391094 | 0.566929 | [6.216989, 6.747645] | 5.787781 | 8.306468 | 6.430691 | -0.796% |
| 512 changed inputs | direct_cold_ms | 20 | 0.270593 | 0.266541 | 0.016588 | [0.262829, 0.278356] | 0.254863 | 0.322645 | 0.270347 | -0.091% |
| 512 changed inputs | direct_update_ms | 20 | 0.024651 | 0.024702 | 0.000261 | [0.024529, 0.024773] | 0.024216 | 0.025017 | 0.024635 | -0.064% |
| 512 changed inputs | doc_cold_ms | 20 | 6.441815 | 6.421083 | 0.417580 | [6.246384, 6.637246] | 5.847651 | 7.466504 | 6.376070 | -1.021% |
| 512 changed inputs | doc_update_ms | 20 | 6.480147 | 6.310467 | 0.453361 | [6.267970, 6.692324] | 6.083045 | 7.740507 | 6.353267 | -1.958% |

## Outlier accounting

Recorded measurements: **400**. Excluded measurements: **38**. No result is removed merely for showing a smaller speedup; exclusion depends only on the same declared symmetric timing bounds.

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
