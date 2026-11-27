# Issue #9 — private HVM2 comparison (final)
 
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
| [46060777040](https://github.com/xad3play/DOC/actions/runs/46060777040) | DOC physical PASS; unmodified HVM2 CUDA launch FAIL on all 47 cases (T4 shared-memory limit). Artifact 15230256132, SHA256 a98d0197ffd230cbe00efc5ea761bd44f154af16b7c35e455398b713d75b4206 |
| [46062395091](https://github.com/xad3play/DOC/actions/runs/46062395091) | PASS one/two-worker controls, 144 processes; artifact 15228589955, SHA256 25860e0b2e3b4ddc5906b2cc5938785e424e3c8e9ed2a91b16421ff514a526bb |

## Verified CPU comparisons so far

Two exposed CPU affinity threads; three repetitions per epoch/round, full sorted outputs equal to the independently regenerated LCG sequence. HVM uses two generated C workers; DOC uses two auto workers. Medians in ms, process wall for HVM and DOC amortized process per round:

| Work | HVM | DOC |
|---|---:|---:|
| bitonic sort 1024 | 56.633 | 7.236 |
| bitonic sort 16384 | 1076.283 | 134.755 |
| bitonic sort 65536 | 5317.855 | 697.520 |
| integrated prime (fresh process, exact 40 shifted intervals) | 24990.120 | 1207.203 |

Prime expected 76216; all 3 HVM and 9 DOC outputs passed. DOC single-worker median 2105.303 ms, explicit two workers 1205.297 ms. HVM is compiled to native C; DOC retains the production independent compiler and integrated recurrence graph. Timings are workload-specific and not a general performance ranking.

Interim decision (superseded by final decision below): DOC original production acceptance was green; external comparison awaited returned artifacts.

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

DOC lower measured process/round times across all 19 tested combinations; small HVM maps can use less resident memory. Timing boundaries and HVM's narrow integer representation differ, so these are scoped workload measurements rather than universal speed or equivalent semantic guarantees. No evidence supports changing qualified DOC CPU production code solely to chase this external baseline. Physical comparison completed with the documented compatibility limitation below.

## Final matched worker controls — PASS

Run [46062395091](https://github.com/xad3play/DOC/actions/runs/46062395091), source e20b1ecec87975ed9f45516e5fd3eb109da4cf74; [artifact 15228589955](https://github.com/xad3play/DOC/actions/runs/46062395091/artifacts/15228589955). ZIP SHA-256 25860e0b2e3b4ddc5906b2cc5938785e424e3c8e9ed2a91b16421ff514a526bb. Independent recheck: all 375 manifest entries, all 144 successful processes (102 HVM2, 42 DOC), 34 HVM build identity records matched to qualified source/C hashes, all numerical results and summary medians; DOC worker traces and both CPU affinity controls. No failure. HVM native C with its existing TPC_L2 configuration; DOC with explicit 1/2-worker controls, identical affinity for each configuration. The original automatic production policy is unchanged.

Median process ms (HVM fresh process; DOC amortized per round); ratios are within-engine one-worker/two-worker speedup, not cross-engine speed ratios.

| Work | Size | HVM 1 | HVM 2 | HVM speedup | DOC 1 | DOC 2 | DOC speedup |
|---|---:|---:|---:|---:|---:|---:|---:|
| add | 4096 | 7.631 | 36.752 | 0.208x | 2.244 | 2.467 | 0.910x |
| add | 4194304 | 5395.217 | 4931.117 | 1.094x | 304.101 | 292.680 | 1.039x |
| poly | 65536 | 128.060 | 122.960 | 1.041x | 6.568 | 6.534 | 1.005x |
| poly | 4194304 | 9936.012 | 8678.457 | 1.145x | 371.513 | 363.144 | 1.023x |
| stress | 262144 | 8052.857 | 7257.804 | 1.110x | 82.696 | 84.889 | 0.974x |
| sort | 65536 | 5479.701 | 5249.344 | 1.044x | 773.201 | 683.482 | 1.131x |
| reduce | 65536 | 80.940 | 81.101 | 0.998x | 5.411 | 5.400 | 1.002x |

Neither runtime scales proportionally on these controls; small-work overhead, saturation, and DOC modular-map negative scaling are retained, not hidden. DOC is faster in absolute measured process/round time in every tested pair. This shared runner is not a physical-core efficiency experiment. The earlier integrated DOC prime 1.74x scaling and original physical modular acceleration remain separate evidence.

## Final physical comparison — DOC PASS; stable HVM2 unsupported on tested T4

Run [46060777040](https://github.com/xad3play/DOC/actions/runs/46060777040), source 382f1eebfabe222f688dd536c50adced4bd082f3. [Artifact 15230256132](https://github.com/xad3play/DOC/actions/runs/46060777040/artifacts/15230256132), ZIP SHA-256 a98d0197ffd230cbe00efc5ea761bd44f154af16b7c35e455398b713d75b4206. Private transported bundle SHA-256 e5d0f8de5adc0967b47101f3ee24c00fa51b188fe340619569c3e201e3812e78. Verified 310 raw tar members against the extracted ZIP contents, all 47 Bend sources byte-for-byte against accepted CPU sources, all 47 CUDA generated source hashes against cases and bundle manifest, report identity, 104 process records and independent numerical/dispatch evidence. Host listed two Tesla T4 devices, 15360 MiB each, driver 580.178.04; CUDA compiler 13.0.88. HVM restricted to CUDA-visible device 0; DOC selected a physical WebGPU adapter on the same host. No assertion that the individual device UUIDs match, and no multi-GPU execution claimed.

All 57 DOC processes (three per 19 workload sizes) succeeded; 141 numerical rounds independently checked, 2121 physical dispatches, real adapter trace, and pool closure. All 47 unmodified HVM2 CUDA sources compiled for sm_75, but each fresh executable exited 1, with empty stdout and identical stderr: `Failed to launch kernels. Error code: invalid argument.` The remote notebook correctly returned failure, and CI correctly failed its HVM/DOC all-pass criterion. No valid HVM GPU timing, no CPU fallback, no software GPU, no fabricated comparison or green override.

The generated runtime declares L_NODE_LEN = L_VARS_LEN = 0x2000; LNet contains 8192 eight-byte Pair entries and 8192 four-byte Port entries, i.e. 98304 bytes (96 KiB) dynamic shared memory per evaluator block. It attempts cudaFuncSetAttribute(evaluator, cudaFuncAttributeMaxDynamicSharedMemorySize, sizeof(LNet)) and launches evaluator with that same size. [NVIDIA Turing tuning guide](https://docs.nvidia.com/cuda/turing-tuning-guide/index.html) specifies at most 64 KiB shared memory for a Turing block. This resource mismatch alone precludes the unmodified HVM2 evaluator on T4 irrespective of workload. Upstream [HVM2 README](https://github.com/HigherOrderCO/HVM2) also specifies CUDA 12.x; the tested CUDA 13 environment is an additional compatibility caveat, so the exact failing CUDA API call is not independently isolated. CUDA 12 would not remove the documented shared-memory limit. No change to HVM's runtime or device selection is appropriate for an unmodified stable-release, same-environment comparison. A different capable GPU with matching supported CUDA would be a separate experiment.

DOC medians on that same Kaggle session (process wall amortized per round / warm epoch or epoch-sum, ms):

| Largest workload | DOC process/round | DOC warm epoch |
|---|---:|---:|
| add 4194304 | 802.897 | 230.042 |
| poly 4194304 | 756.595 | 204.397 |
| stress 262144 | 145.946 | 7.394 |
| sort 65536 | 1383.972 | 380.693 |
| reduce 65536 | 196.329 | 5.085 |

Device opening and other host costs are reflected in process measurements; warm epoch-sum is a distinct measurement. HVM CUDA is unsupported on this tested configuration, not a timing loss. Graphical 2D/3D external comparison intentionally excluded; DOC game/physical correctness already qualified. DOC-specific reactive/safety semantics are not attributed to HVM.

## Final issue #9 disposition

Original binding DOC acceptance completed: [46052437755](https://github.com/xad3play/DOC/actions/runs/46052437755) all six jobs passed at ed0cc865dbb0c416b903062c8869e6956635929e; prior source/resource, original-paper CPU and returned-evidence checks also passed. The requested external computational comparison is complete for what the stable HVM release can execute in this environment. CPU matrix, integrated prime and worker controls passed; the physical experiment established an explicit HVM hardware incompatibility while DOC passed on the same host. The comparison workflow failure remains a real and preserved negative result, not a DOC correctness failure. Further DOC optimization is not warranted by this scoped comparison; no further CI submission or artificial HVM patch required for this milestone. Keep negative scaling and workload/timing/representation limitations visible. Production runtime a7fe0554abea1a2b218929b33ad2f8f66f632f94, compiler 9120f50dde55af7c0a656d43ece6acf824cbcab0, frozen reference a95a38bc6e9300aae815f83b570db5f99d32f221 and engine 4d6044ac566fa8374f44e3f32f153d63b95f2b9f remain unchanged. Close #9 as completed, not as HVM GPU pass. No public release or manuscript edits; #14 remains separate. No scheduled automation.
