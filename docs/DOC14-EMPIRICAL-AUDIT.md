# Retained physical evidence re-audit — DOC14 empirical pass

This is a derived audit record, not a replacement raw archive or a new benchmark. It concerns only the qualified DOC production run 46052437755, original source ed0cc865dbb0c416b903062c8869e6956635929e. Physical artifact 15227957875, ZIP SHA-256 aeaf10e30d72c2cee5aaa5c2a09316586923a7eb1ad5d1a17f4dd20e10399f91. Archived run provenance agrees with the manifest and remote summary. The original returned ZIP was independently reopened; all 884 member names are unique, CRCs pass, and all 880 regular-file members of its inner tar match the separately returned bytes. The retained physical archive is not itself the original build archive: this pass does not claim a new independent executable reconstruction or fresh GPU dispatch.

## Recomputed numerical evidence

Independent numerical oracles for addition, polynomial, affine modular composition, sorting input checksum and reduction were evaluated for every recorded sample. CSV records were checked against raw process stdout; unique process and sample identities, recorded admitted capacity, actual device adapter trace and dispatch geometry were checked against raw stderr. All recorded summary means and medians were recomputed.

| Evidence | Families | Staged algorithms | Total |
|---|---:|---:|---:|
| Numerical observations | 1,260 | 567 | 1,827 |
| Distinct processes | 210 | 189 | 399 |
| Verified physical dispatch traces | 360 | 4,014 | 4,374 |
| Physical process sessions | 60 | 54 | 114 |
| Measurement groups | 70 | 63 | 133 |

The hardware record is Tesla T4 (driver 580.178.04), four affinity CPUs, cgroup quota 400000/100000. Two devices were listed, not used as a combined accelerator. All 133 medians in the DOC-only manuscript supplement were compared to the recomputed values with a tolerance of 0.0000051 ms for five-decimal rounding; no discrepancy. All 19 automatic CPU groups record a four-worker capacity/maximum as measured by the corresponding family/algorithm harness; this does not imply four active workers at every stage.

## Timing boundaries and tail observations

For each measurement group, use the epoch or epoch-sum time in nanoseconds divided by 1e6. Warm samples exclude ordinal zero. p50 is the sample median; p95 and p99 use nearest rank (ceil(q*n)). Cold p50 uses ordinal zero only; process and device-opening p50 deduplicate the three fresh processes. These small samples are descriptive observations, not reliable population tail estimates or independent per-epoch confidence intervals. The p95 and p99 often coincide with the observed maximum. Sample count is 15 for families, 12 for the modular map and 3 for staged sort/reduction.

| Workload | Mode | Warm n | p50 ms | p95 ms | p99 ms | Cold p50 ms | Device open p50 ms | Fresh process p50 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Add 64 | CPU 1 | 15 | 0.004086 | 0.007908 | 0.007908 | 0.018582 | 0 | 2.009067 |
| Add 64 | Auto backend | 15 | 0.283740 | 0.533156 | 0.533156 | 3.662232 | 343.798285 | 440.974222 |
| Polynomial 4,194,304 | CPU 1 | 15 | 410.561122 | 417.671581 | 417.671581 | 412.725750 | 0 | 4669.629903 |
| Polynomial 4,194,304 | Auto backend | 15 | 208.757275 | 237.987511 | 237.987511 | 228.900264 | 383.868394 | 4042.090609 |
| Modular map 65,536 | CPU 1 | 12 | 30.521596 | 31.209289 | 31.209289 | 31.607791 | 0 | 234.073981 |
| Modular map 65,536 | Auto backend | 12 | 2.204562 | 3.426000 | 3.426000 | 6.941072 | 356.633950 | 550.316111 |
| Reduction 65,536 | CPU 1 | 3 | 4.253024 | 4.304986 | 4.304986 | 4.287694 | 0 | 23.588905 |
| Reduction 65,536 | Auto backend | 3 | 5.208001 | 5.551192 | 5.551192 | 9.118371 | 325.461657 | 440.707673 |

Family process median RSS (KiB)/peak owned-region bytes: add 64 CPU 1 26564/2800, auto 291600/2240; polynomial 4,194,304 CPU 1 176968/167772400, auto 507852/134217920. RSS includes the process/device provider and is distinct from DOC region accounting; it is not GPU VRAM occupancy. Algorithm RSS is absent from this CSV and is not imputed. These figures reinforce the negative startup/granularity cases. In particular, 65,536-lane modular work has a large warm speedup while its measured short fresh process is slower. No extrapolation to population p99, arbitrary automatic placement or universal memory efficiency is justified.

The existing source-level offline verifier is `runtime-doc/tests/verify_autonomous_evidence.py`; it additionally requires the exact build directory for executable/source/WGSL byte checks. Retain that requirement for the final release evidence audit. This retained-archive re-audit establishes the empirical matrix and descriptive timing boundaries, not durable distribution rights, a fresh release-root rebuild, or physical qualification of the new curated candidate.

## Candidate caller review

The first source export contains optional mesh/scene host and compiler sources even though the game is not bundled. A static include/import inspection of the exact 85-file archive identified the six generated policy headers (intentionally regenerated), the separately emitted GPU header, and optional scene generated inputs (scene_generated.c, scene_shader.h and xdg-shell-client-protocol.h). The latter are not part of the clean CPU path. Legacy standalone frontend stage sources also remain in this broad preliminary allowlist. Prune or justify and test these caller paths before R4/R9; a successful source export is not final minimal curation.
