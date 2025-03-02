# Verification report

Verification date: 2026-07-30.

Transient absolute paths in preserved command logs were normalized to relative build paths; command outputs and pass/fail results were otherwise left unchanged.

## Scope and change boundary

The supplied runtime implementation, CMake definition, tests, bounded checkers, benchmark source, examples, and campaign driver were copied without source changes. A byte-for-byte comparison of those directories passed. No runtime defect or manuscript/runtime contradiction was found, so no runtime correction or regression test was introduced.

No mathematical claim, formal state component, operational rule, theorem conclusion, or realization contract was changed. Submission-facing changes were limited to author/declaration metadata, reference metadata, contents-page layout, artifact cleanup, and restoration of Section 9.2 to the scaling table and wording in the supplied master manuscript.

## Optimized Release verification

GCC 14.2.0, CMake 3.31.6, Ninja 1.12.1, and Python 3.13.5 were used on Debian GNU/Linux 13.

A clean out-of-tree Release configuration and build completed. The complete registered CTest suite passed:

| Registered test | Result | Elapsed time |
|---|---:|---:|
| `doc_tests` | pass | 0.28 s |
| `doc_benchmark_generator` | pass | 0.34 s |
| `doc_bounded_model_check` | pass | 3.49 s |
| `doc_repair_model_check` | pass | 9.20 s |
| `doc_graph_version_model_check` | pass | 0.65 s |
| `doc_duplicate_premise_model_check` | pass | 0.61 s |
| `doc_demand_recurrence_model_check` | pass | 0.73 s |

CTest result: **7/7 passed in 15.30 seconds**.

Direct execution additionally confirmed:

- 36 named native conformance suites passed;
- the native suite's 9,600 randomized differential epochs passed;
- randomized frontier-subset schedule agreement and sequential/parallel agreement passed;
- benchmark-generator/direct/bitonic equivalence passed.

## Bounded checker results

Direct checker executions completed with these reported spaces:

- finite checker: 2,520 graphs and 40,320 source epochs, all legal frontier subsets, exact and conservative cutoff profiles;
- repair checker: 512 graphs, 59,904 admissible seeds, 521,584 explored configurations, and 239,616 continued source updates;
- graph-version checker: 64 graphs and 15,360 commits, including source/derived authority transitions;
- duplicate-premise checker: 84 graphs and 2,592 admissible configurations;
- demand/recurrence checker: 364 demand graphs, 21,840 demanded subsets, 364 recurrence templates, 17,472 finite prefixes, 2,912 stopping cases, and 364 duplicate-carry rejection cases.

These are bounded-exhaustive checks of their encoded finite spaces, not unbounded proofs.

## Compiler and sanitizer checks

- Clang 17.0.0 Release build: completed; registered suite **7/7 passed** in 12.08 seconds.
- GCC AddressSanitizer plus UndefinedBehaviorSanitizer Debug build: completed; registered suite **7/7 passed** in 19.63 seconds with leak detection and halt-on-error enabled.
- GCC ThreadSanitizer Debug build: completed; the two instrumented native test executables **2/2 passed** in 14.75 seconds with halt-on-error enabled.

An initial optimized ASan/UBSan build exceeded the five-minute execution-wrapper limit before compilation finished; the Debug sanitizer build was then completed and tested successfully. An attempted full TSan CTest command passed both instrumented native executables, then exceeded the wrapper limit after entering the non-instrumented Python checker portion. The native TSan subset was rerun explicitly and completed. Both interrupted attempts are preserved rather than reported as passes.

## Benchmark integrity and correctness

The headline timing campaigns were not regenerated because the runtime did not change and no benchmark defect was found. Their raw numeric evidence was preserved.

Every manuscript value was checked against the supplied benchmark evidence. The sparse/dense, financial, and negative-control table agrees with the preserved primary campaign. The restored Section 9.2 table matches the supplied master manuscript and its local-machine scaling series: median times are 142.589, 72.274, 49.605, and 37.527 ms, and median paired speedups are 1.000x, 1.959x, 2.853x, and 3.847x. The raw scaling measurements remain preserved unchanged in `runtime/results/scaling/raw.csv`.

Fresh single-process correctness smoke checks completed for cold evaluation, sparse and complete-density updates, cutoff, four-participant parallel evaluation, the dense-cheap negative control, two financial sizes, and two sorting-network densities. Every executable returned success after checking its output oracle. Their fresh timings are retained only as smoke-check logs and are not substituted for the preserved campaigns.

## Manuscript and PDF checks

The supplied Typst 0.15.1 binary compiled the final source. The result is a 28-page A4, unencrypted, text-based PDF with embedded Unicode fonts. Structural preflight passed. Recompilation produced identical extracted text and pixel-identical rendering on all 28 pages at 100 DPI.

Every final page was rendered at 200 DPI. The restored Section 9.2, the contents page, and every page affected by reflow were visually inspected; all remaining pages were pixel-identical to the previously inspected manuscript. The inspection covered numbering, tables, appendices, declarations, bibliography, clipping, overflow, malformed glyphs, whitespace, and final-page balance. No visible defect remains.

## Citation verification

All sixteen references were checked against primary or official records. Author names, titles, venue metadata, year, page ranges where applicable, and DOI or stable identifier were reconciled. Every reference is cited, every scholarly citation resolves, and the related-work sentence supported by each reference is recorded in `CITATION-VERIFICATION-LEDGER.md`.

## Verification boundary

The paper's formal results remain human mathematical arguments rather than proof-assistant-checked theorems. Bounded checkers establish only their encoded finite spaces. The placed runtime remains a bounded single-coordinator witness rather than a production consensus or partition-tolerant multi-host platform. Timing results remain host- and workload-specific. These limitations are already disclosed in the manuscript.
