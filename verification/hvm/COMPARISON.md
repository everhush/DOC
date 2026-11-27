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
| [46060776985](https://github.com/xad3play/DOC/actions/runs/46060776985) | Running at record creation, corrected balanced static-depth tree source |
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
