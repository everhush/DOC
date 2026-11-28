# DOC-only manuscript reproducibility supplement (revision candidate)

Historical witness: code 27a0139643237bfcaf05c71155fd137f297f6a53, data 8d3d647ea913732a39ad4cb83d17b9f7f3e20d17. Preserve the original submission and archive unchanged. Independent native source: ed0cc865dbb0c416b903062c8869e6956635929e; runtime tree a7fe0554abea1a2b218929b33ad2f8f66f632f94; compiler tree 9120f50dde55af7c0a656d43ece6acf824cbcab0. Reference tree a95a38bc6e9300aae815f83b570db5f99d32f221 is frozen. Final source acceptance six jobs passed; see issue #9 DOC-only production sections 2–5, not the separate external comparison.

| Campaign | Run / artifact | Digest (SHA-256) |
|---|---|---|
| Native integrated prime earlier four-worker | 46032762791 / 15215840294 | see preserved original evidence |
| Final native two-worker prime | 46053929420 / 15225438430 | 52ea07cf37b2f09ef76a2d2296b1d21c65143ff0127c4460d0b6515210479c84 |
| Physical preflight | 46053188589 / 15226800551 | 50a6b7c5da1cb7d11e7ceb484237c523daf1fb196aab709fcda8e8ce7e2b4e16 |
| Final physical | 46052437755 / 15227957875 | aeaf10e30d72c2cee5aaa5c2a09316586923a7eb1ad5d1a17f4dd20e10399f91 |
| Returned-evidence audit | 46056113923 / 15227225064 | a719e435495cdd73c4e4711c41880aac8a516760fc50172567ab88b2bbf00c55 |

Previous development repository migration may make historic artifact URLs unavailable. IDs and digests identify existing evidence, not a promise of public download. A durable DOC-only source/data artifact with rights and access verified remains a release requirement; do not link the private comparative ledger in a manuscript supplement.

Harness: runtime-doc/tests/build_autonomous_scale.py, runtime-doc/tests/verify_autonomous_evidence.py and production compiler/runtime at the pinned revision. Workloads: addition and polynomial maps (64–4,194,304 lanes), modular map (4,096–262,144 lanes; 32 modular recurrence steps per lane), staged bitonic sort and balanced reduction (1,024–65,536). Exact inputs, generated sources/shaders, independent numeric oracles and raw process/epoch/dispatch records are in the retained archives. The 40-leaf prime workload tests 1,000,000 candidate occurrences and returns 76,216. The earlier four-worker source campaign uses means, final two-worker regression uses medians; do not pool them. Historical C++20 timings retain their original meaning.

Final physical host: four affinity CPUs/four-CPU quota, one selected Tesla T4, NVIDIA driver 580.178.04, 15,360 MiB per listed device; no multi-GPU or software GPU timing. Three processes per setting; warm epoch/epoch-sum excludes initial round, device initialization, input construction and oracle, includes source ingress, evaluation and publication. Staged sort/reduction host orchestration is separately measured. Strict GPU and automatic backend are distinct. Complete final 19-size matrix (ms, rounded to five decimals), selected directly from final production ledger:

| Workload | Lanes | CPU1 | CPU2 | CPU3 | CPU4 | Auto CPU | Strict GPU | Auto backend |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Add | 64 | 0.00409 | 0.07561 | 0.15114 | 0.16125 | 0.15761 | 0.22441 | 0.28374 |
| Add | 4096 | 0.14344 | 0.25275 | 0.26768 | 0.30368 | 0.29437 | 0.41473 | 0.35149 |
| Add | 65536 | 2.53700 | 2.59149 | 2.52994 | 2.42632 | 2.52748 | 2.28825 | 2.31912 |
| Add | 1048576 | 45.35861 | 39.16488 | 39.24297 | 38.35427 | 36.85006 | 38.92947 | 38.85462 |
| Add | 4194304 | 253.15394 | 217.35398 | 212.83606 | 206.04628 | 205.16905 | 245.43165 | 243.25715 |
| Polynomial | 64 | 0.00880 | 0.08659 | 0.14097 | 0.16200 | 0.15478 | 0.19825 | 0.23660 |
| Polynomial | 4096 | 0.31582 | 0.30985 | 0.37500 | 0.36205 | 0.36842 | 0.35567 | 0.32811 |
| Polynomial | 65536 | 5.32841 | 3.66648 | 4.09227 | 3.54379 | 3.46739 | 1.74326 | 1.76032 |
| Polynomial | 1048576 | 87.98424 | 55.03114 | 61.63511 | 51.98587 | 52.34220 | 29.17105 | 30.26459 |
| Polynomial | 4194304 | 410.56112 | 279.87115 | 280.20124 | 268.79162 | 268.75041 | 210.03561 | 208.75727 |
| Modular map | 4096 | 1.93319 | 1.17391 | 1.62078 | 1.31083 | 1.28119 | 0.34978 | 0.49791 |
| Modular map | 65536 | 30.52160 | 16.75332 | 23.56098 | 18.16074 | 18.00772 | 2.17121 | 2.20456 |
| Modular map | 262144 | 123.54715 | 65.92424 | 79.22456 | 71.82497 | 72.14711 | 8.61394 | 8.98091 |
| Sort | 1024 | 6.46817 | 9.88449 | 12.14756 | 13.41061 | 12.39897 | 13.18498 | 17.80696 |
| Sort | 16384 | 191.79795 | 137.16108 | 139.86148 | 129.94398 | 127.28260 | 95.55063 | 107.83809 |
| Sort | 65536 | 1008.12463 | 706.93630 | 693.74458 | 619.39650 | 620.76296 | 428.98019 | 411.51223 |
| Reduction | 1024 | 0.09656 | 0.43254 | 0.71744 | 0.78664 | 0.78225 | 2.33494 | 1.33382 |
| Reduction | 16384 | 1.15360 | 1.52911 | 1.89206 | 2.04532 | 1.98962 | 3.41719 | 2.97854 |
| Reduction | 65536 | 4.25302 | 4.21547 | 4.28371 | 4.52024 | 4.65237 | 5.87272 | 5.20800 |

Auto CPU used four participants. CPU speedup T1/Tp; efficiency 100*T1/(p*Tp). GPU acceleration T1/Tgpu is not a per-core efficiency. Preflight polynomial 64→4096: epoch throughput growth 40.26×, dispatch-wall throughput 47.65×, 62.9%/74.5% proportional scaling. Negative cases retained. No unmeasured contention assumption. Final 2D/3D mixed replay fresh-process medians 492.303900/432.969566 ms versus CPU 7.085858/7.655349 ms; device-open median 383.995982/333.876383 ms, warm dispatch 0.210565/0.220327 ms, not FPS. Same-source typed outputs and injected failure isolation passed.

Scope: source-emitted partitioned profiles and historical callback witnesses are separate from ordinary integrated native source; no unrestricted monolithic compiler capacity claim. No raw binary or log is committed by this supplement. Publication, licensing, and release are not authorized by these edits.
