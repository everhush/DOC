# Verification report

Verification date: 2026-09-30.

## Scope and revision boundary

The manuscript was substantially revised in response to both reviewers: the problem statement and running example were rewritten; notation was made explicit; tables, diagrams, formal statements, equations, and algorithms were numbered and cross-referenced; the finite-kernel assumptions and claim/evidence boundaries were clarified; related work was rewritten around direct technical distinctions; graph-version compatibility received an operational semantic-key example; and the evaluation was rebuilt around a reproduced campaign with explicit negative cases and host limits.

The C++20 runtime implementation, CMake definition, tests, bounded checkers, benchmark source, examples, and benchmark driver remain byte-for-byte identical to the supplied archive, excluding generated results and Python cache files. A fresh extraction of the supplied archive was compared against the revised tree and produced no runtime source/test difference. No runtime defect requiring a source correction was found.

## Clean Release verification

A clean out-of-tree Release build with GCC 14.2.0, CMake 3.31.6, Ninja 1.12.1, and Python 3.13.5 completed successfully on Debian GNU/Linux 13. The full registered CTest suite passed:

| Registered test | Result |
|---|---:|
| `doc_tests` | pass |
| `doc_benchmark_generator` | pass |
| `doc_bounded_model_check` | pass |
| `doc_repair_model_check` | pass |
| `doc_graph_version_model_check` | pass |
| `doc_duplicate_premise_model_check` | pass |
| `doc_demand_recurrence_model_check` | pass |

CTest result: **7/7 passed**. The final post-layout clean Release run completed in 13.79 seconds.

Direct native execution additionally confirmed **36 named conformance suites**, including 9,600 randomized differential epochs, randomized frontier-subset schedule agreement, sequential/parallel agreement, graph-version commits, recurrence, transport, placement, recovery, effects, typed publication, eviction/reconstruction, and benchmark-generator/direct/bitonic equivalence.

## Bounded checker results

Fresh direct checker executions completed with the following encoded state spaces:

- finite checker: 2,520 graphs and 40,320 source epochs, all legal frontier subsets, exact and conservative cutoff profiles;
- repair checker: 512 graphs, 59,904 admissible seeds, 521,584 base-seed explored configurations, 239,616 continued source updates, and 119,808 unique start/profile checks;
- graph-version checker: 64 graphs and 15,360 commits, including source/derived authority transitions;
- duplicate-premise checker: 84 graphs and 2,592 admissible configurations;
- demand/recurrence checker: 364 demand graphs, 1,456 source valuations, 21,840 demanded subsets, 364 recurrence templates, 17,472 finite prefixes, 2,912 stopping cases, and 364 duplicate-carry rejection cases.

These are bounded-exhaustive checks of their encoded finite spaces, not unbounded proofs.

## Independent compiler and sanitizer passes

- GCC Release with `-Wall -Wextra -Wpedantic -Werror` plus the runtime's `-Wconversion -Wshadow`: full registered suite **7/7 passed** in 13.45 seconds.
- Clang 17.0.0 Release build: full registered suite **7/7 passed** in 13.81 seconds.
- GCC AddressSanitizer + UndefinedBehaviorSanitizer build: the native runtime executable and benchmark-generator oracle both passed in the final post-layout pass; the earlier named-suite run also completed all 36 native suites with halt-on-error enabled.
- GCC ThreadSanitizer build: the same two native executables passed again in the final post-layout pass with halt-on-error enabled.

One combined sanitizer wrapper was interrupted by the outer execution time limit while entering the ASan benchmark-generator test. The test was immediately rerun directly under ASan/UBSan and passed, so the interrupted wrapper is not reported as a pass. The transient wrapper logs are retained in Git history rather than in the final publication tree.

## Benchmark evidence and correctness

The final article uses the complete campaign in `runtime/results/independent-dedicated-100/`, generated from 100 fresh processes per row after three warmups. The recorded environment is Linux 6.18.53 x86-64 with glibc 2.42, GCC 15.3.0 in Release mode, Python 3.14.7, CMake 4.4.2, and an AMD Ryzen AI 7 350 w/ Radeon 860M on bare metal; eight physical cores / 16 logical CPUs were visible and no cgroup CPU quota was recorded. Participant limits were deliberately capped at four. Every benchmark process checks its output oracle and exits nonzero on disagreement.

`verification/check_manuscript.py` mechanically checks every timing value, confidence interval, speedup, range, graph dimension, and evaluation count printed in the article against `statistics.csv`. This check passes. The article intentionally reports raw means for its displayed timing tables and explicitly distinguishes those from filtered sensitivity summaries in the retained benchmark report.

Fresh post-revision smoke executions also completed successfully for cold evaluation, sparse and complete-density repair, equality cutoff, four-participant parallel evaluation, the dense-cheap negative control, a 64-unit financial update, and a 64-input sorting-network update. Their timings are validation-only and are not substituted for the 20-process campaign.

## Manuscript structure and evidence checks

The final manuscript checker passes with:

- **73 unique Typst labels**;
- every figure, table, and algorithm label referenced from the text;
- no hard-coded numbered Section/Table/Figure references;
- **16 scholarly citation keys**, all resolved and no unused bibliography entry;
- explicit notation for `S`, `P_d`, `users(x)`, premise tuples, initialization, and the finite-stabilization algorithm;
- the graph-version semantic-key example and explicit statement that arbitrary function equivalence is not decided by the runtime;
- all displayed benchmark statistics matching the authoritative 100-sample campaign.

## Native Typst graphics and PDF checks

All conceptual diagrams and benchmark charts are native Typst vector content. The manuscript contains **no `image(...)` call**. Seven conceptual diagrams use Typst rectangles, lines, polygons, placement, text, and math primitives; the two performance charts are also drawn directly with Typst vector primitives.

The supplied Typst 0.15.1 binary compiled the final source to a **33-page**, tagged, A4, unencrypted, text-based PDF. `pdfimages -list` reports **zero embedded image XObjects**, confirming that manuscript diagrams/charts are not raster images. Structural preflight reports the PDF as openable and non-scanned.

Every final page was rendered at 200 DPI and visually inspected after the spacing revision. The inspection covered title/abstract balance, headings, numbered equations, formal boxes, algorithm layout, all tables, all seven conceptual diagrams, both benchmark charts, appendices, declarations, references, clipping, overlap, broken glyphs, whitespace, and page balance. No visible defect remains.

## Citation verification

All sixteen references have a citation-verification entry in `verification/CITATION-VERIFICATION-LEDGER.md`, recording the publication metadata and the manuscript claim each source supports. The manuscript's related-work language is deliberately comparative rather than claiming that dependency tracking, caching, demand, or parallel incremental execution originated with DOC.

## Verification boundary

The paper's formal results remain human mathematical arguments rather than proof-assistant-checked theorems. Bounded checkers establish only their encoded finite spaces. The placed runtime remains a bounded single-coordinator witness rather than a production consensus or partition-tolerant multi-host platform. Timing results are host- and workload-specific. The manuscript states these limitations explicitly.

## Final evidence-tree cleanup

The final working tree uses `runtime/results/independent-dedicated-100/` as the authoritative article timing campaign. The earlier `runtime/results/revision-2026-09-29/` campaign remains as historical reviewer-revision evidence, while superseded pre-revision `primary` and `scaling` timing directories and transient local verification logs remain removed. Fresh local runs are ignored under `runtime/results/runs/`; fresh GitHub-hosted campaigns are uploaded only as one-day Actions artifacts.

## Continuous publication gate

The revised repository now includes `.github/workflows/publication-validation.yml`. It is configured to run clean GCC/Clang Release validation, separate ASan/UBSan and ThreadSanitizer jobs, a pinned Typst 0.15.1 build with PDF preflight and page rendering, and a fresh 20-sample benchmark campaign. Generated PDF/source/renders, benchmark evidence, and compiler/sanitizer logs are one-day GitHub Actions artifacts. A final `Publication gate` status requires every job to succeed. The workflow is read-only, persists no checkout credentials, creates no releases, and needs no user-managed secrets or tokens.

The workflow definition and its component commands were validated locally in the revision environment: the local release gate passes, the retained 20-sample campaign passes the benchmark-artifact validator, and a fresh one-sample/all-scenario campaign also passes it. Hosted run 36583157931 at revision `d2e9edb4f962f132e96d7e342bd14f48ff8446cc` completed the publication gate successfully and produced the final 33-page manuscript artifact. A later audit found that the historical PDF font-preflight script parsed a fixed `pdffonts` field and that piped validation commands did not explicitly request bash pipefail semantics; the submitted PDF itself had all fonts embedded. The current repository corrects the parser and requires explicit bash run-shell semantics so future piped failures propagate. These post-run hardening edits were validated locally because the Actions artifact quota was exhausted; no new hosted run is claimed for them.
