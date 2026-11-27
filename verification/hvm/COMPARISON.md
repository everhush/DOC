# Issue #9 — private HVM2 comparison (interim)
 
This extension uses published HVM2 2.0.22 and Bend 0.2.38. It does not modify the accepted production DOC runtime/compiler or the manuscripts. The canonical issue is [imxade/DOC #9](https://github.com/imxade/DOC/issues/9). All evidence is retained, including failed harness attempts. No software GPU is accepted.

## Method

The two implementations execute on the same runner with the same CPU affinity. HVM's pure one-shot native compiled computation and DOC's persistent reactive computation are distinct; process medians and amortized DOC round times must not be presented as identical semantic/measurement boundaries. Source generation and compilation are outside measured process time. HVM uses 24-bit arithmetic; modular multiplication and the exact 32-bit LCG are implemented with split arithmetic, with independent numerical oracles. Smaller maps and sorting retain full HVM vectors; larger maps use exact two-limb checksums, not proof of elementwise equality at every large size. The reduction uses exact two-limb results. DOC keeps its native per-lane and independent oracle validation. No stable HVM rendering or DOC-specific reactive publication, rollback, versioning, protected observation or retained-state equivalence is assumed.

| Run | Status / artifact |
|---|---|
| [46060067697](https://github.com/xad3play/DOC/actions/runs/46060067697) | Rejected HVM source tokenization; all 57 DOC samples passed. 15228411930, SHA256 b4a12d2e1ea9af7e52c2c3dd613426136bc94820c6fd23580833b5e7085a9eb2 |
| [46060344285](https://github.com/xad3play/DOC/actions/runs/46060344285) | Partial: all 18 complete sorting outputs and 57 DOC samples verified; 41 other HVM codegen failures (recursive tuple typing). 15229220857, SHA256 3427627a8bb1a9c9176ddae3f01937e980ebfb7fef92e7eff11e6319fab934e8 |
| [46060534794](https://github.com/xad3play/DOC/actions/runs/46060534794) | Rejected CUDA source typing, no physical execution. Artifact 15228158544 |
| [46060598044](https://github.com/xad3play/DOC/actions/runs/46060598044) | PASS integrated prime. 15228228738, SHA256 501b01a38cb653a122470b855cb4125319f195c2848f2b675b37a8b20eb93f93 |
| [46060776985](https://github.com/xad3play/DOC/actions/runs/46060776985) | PASS all 19 sizes, 47 native HVM programs, 198 process samples; artifact 15228373526, SHA256 7120e6032fb1f7a26f2384fafe48b93593899f42f7466e738a5a4565d2f1cccb |
| [46060777040](https://github.com/xad3play/DOC/actions/runs/46060777040) | Running at record creation, physical Tesla T4 comparison |

## Verified CPU comparisons so far

Two exposed CPU affinity threads; three repetitions per epoch/round, full sorted outputs equal to the independently regenerated LCG sequence. HVM uses two generated C workers; DOC uses two auto workers. Medians in ms, process wall for HVM and DOC amortized process per round:

| Work | HVM | DOC |
|---|---:|---:|
| bitonic sort 1024 | 56.633 | 7.236 |
| bitonic sort 16384 | 1076.283 | 134.755 |
| bitonic sort 65536 | 5317.855 | 697.520 |
| integrated prime (fresh process, exact 40 shifted intervals) | 24990.120 | 1207.203 |

Prime expected 76216; all 3 HVM and 9 DOC outputs passed. DOC single-worker median 2105.303 ms, explicit two workers 1205.297 ms. HVM is compiled to native C; DOC retains the production independent compiler and integrated recurrence graph. Timings are workload-specific and not a general performance ranking.

Current decision: DOC original production acceptance is green. Comparison extension remains OPEN until the corrected runs finish and raw artifacts are verified. Do not infer external runtime GPU compatibility from its codegen or DOC's GPU success.

## Final matched CPU matrix — PASS

Run 46060776985 at 382f1eebfabe222f688dd536c50adced4bd082f3. Independent verification of all 779 manifest files, all 198 successful processes (141 HVM + 57 DOC), all 47 source/generated C/native binary identities and worker bounds. No failed or missing case. HVM full vectors verified at smaller map sizes and all sort sizes; two-limb checksums verified at larger sizes and for reduction. All DOC rounds verified by independently regenerated oracles (closed-form polynomial and modular affine recurrence, exact LCG and reduction). Both use two CPU workers on the same runner. All values below median; HVM fresh process and DOC amortized per round; peak RSS KiB measured per process, not per round.

| Work | Size | HVM ms | DOC ms | HVM RSS KiB | DOC RSS KiB |
|---|---:|---:|---:|---:|---:|
| add | 64 | 6.143 | 2.308 | 2484 | 3656 |
| add | 4096 | 12.466 | 1.734 | 3588 | 3872 |
| add | 65536 | 79.405 | 11.467 | 20848 | 6444 |
| add | 1048576 | 1199.399 | 78.166 | 621414 | 50296 |
| add | 4194304 | 4761.746 | 326.120 | 2476984 | 190580 |
| poly | 64 | 6.312 | 1.361 | 2540 | 3620 |
| poly | 4096 | 20.752 | 1.764 | 5634 | 3912 |
| poly | 65536 | 137.120 | 8.323 | 52780 | 6252 |
| poly | 1048576 | 2254.405 | 109.876 | 1133470 | 47032 |
| poly | 4194304 | 9107.654 | 452.950 | 4524978 | 177440 |
| stress | 4096 | 137.610 | 2.711 | 63148 | 3984 |
| stress | 65536 | 1883.815 | 30.070 | 968496 | 8032 |
| stress | 262144 | 7548.504 | 118.106 | 3948416 | 21432 |
| sort | 1024 | 56.956 | 10.381 | 21504 | 3740 |
| sort | 16384 | 1054.931 | 150.020 | 519914 | 5100 |
| sort | 65536 | 5340.957 | 753.185 | 2609718 | 9388 |
| reduce | 1024 | 7.189 | 2.221 | 2936 | 3764 |
| reduce | 16384 | 53.145 | 3.259 | 11148 | 4088 |
| reduce | 65536 | 86.112 | 7.005 | 36148 | 5940 |

DOC lower measured process/round times across all 19 tested combinations; small HVM maps can use less resident memory. Timing boundaries and HVM's narrow integer representation differ, so these are scoped workload measurements rather than universal speed or equivalent semantic guarantees. No evidence supports changing qualified DOC CPU production code solely to chase this external baseline. Physical comparison remains pending.
