# Revision decision log

This file records publication-affecting decisions made during the 2026-09-29 reviewer revision.

| Decision | Reason | Enforcement / evidence |
|---|---|---|
| Treat the finite acyclic kernel as the proved semantic core. | Reviewer 2 requested separation between proved properties, conditional extensions, and runtime evidence. | Manuscript claim map, finite theorem assumptions, `CLAIM-EVIDENCE-MAP.md`, manuscript checker. |
| Define all finite-kernel notation before use, including `S`, `D`, `P_d`, the valuation, active set, and ready frontier. | Reviewer 1 identified undefined/late-defined symbols. | Numbered definitions/equations and `verification/check_manuscript.py`. |
| Add an explicit finite-stabilization algorithm. | Reviewer 1 requested a stepwise flow across semantic layers. | Algorithm label and cross-reference gate. |
| Compare DOC by representation/repair/guarantee rather than claiming dependency tracking is new. | Both reviewers requested assessable novelty positioning. | Related-work comparison and bounded novelty language. |
| Treat graph-version semantic keys as external compatibility certificates; do not claim arbitrary function equivalence is decidable. | Reviewer 2 requested an operational compatibility account. | Graph-version example and explicit caveat checked by the manuscript gate. |
| Present specialized cached baselines and fine-grained negative cases prominently. | Reviewer 2 requested stronger interpretation of performance limits. | Revised evaluation text and retained raw campaign. |
| Bound the parallel claim to one host and externally granted capacity. | Reviewer 2 warned against distributed-scalability extrapolation. | Four-participant wording and CI/retained evidence. |
| Keep all manuscript diagrams/charts native to Typst. | The revised article must remain editable, consistent, and vector-native. | Source checker rejects `image(...)`; PDF preflight rejects embedded image XObjects. |
| Use one Typst figure counter for all nine visual figures. | Separate custom kinds can restart visible numbering. | Shared `kind: "figure"` plus checker. |
| Pin Typst 0.15.1 in CI and build the PDF there. | The paper must compile without a user-supplied binary. | Manuscript CI job downloads the pinned upstream release and uploads the PDF/renders. |
| Use GitHub Actions artifacts rather than GitHub Releases for generated evidence. | Releases are persistent while the requested evidence-retention window is one day. | Every `upload-artifact` step has `retention-days: 1`; no release credentials are needed. |
| Give CI read-only repository permission and require no secrets. | Validation should run on push/PR without manual credential setup. | Workflow `permissions: contents: read`; policy checker rejects `secrets.*` and write permissions. |
| Retain one authoritative reproduced benchmark campaign in the repository. | Multiple stale campaigns can contradict revised manuscript numbers. | `runtime/results/revision-2026-09-29/` is retained; older primary/scaling snapshots are removed. |
| Increase global heading separation rather than adding page-specific whitespace. | The technically revised PDF had become visually congested around level-2/3 subtopics compared with the submitted article. | Typst heading rules now use larger above/below spacing and sticky headings; every page is re-rendered for inspection. |
| Give level-3 headings additional local separation in the final submission pass. | Dense formal and appendix pages still placed sub-subtopics too close to following prose. | Only the level-3 above/below spacing was increased; all 33 pages were re-rendered and independently reinspected. |
| Keep the 100-sample bare-metal campaign as independent follow-up evidence rather than replacing article timings. | The campaign corroborates scaling on a different host, but it uses a different machine/toolchain and statistical campaign size from the retained article evidence. | Manuscript and repository documentation explicitly separate the `independent-dedicated-100/` campaign from `revision-2026-09-29/`. |
| Add a compact reading guide but do not restore the report-style contents page. | The original paper was easier to navigate, while a contents page made the revision look like a technical report. | The Introduction now explains the paper sequence in one compact callout. |
| Reject the unbreakable six-item realization-contract experiment. | Keeping the list together produced a visibly under-filled preceding page and worse page balance. | The tested experiment was reverted; the balanced split is retained and documented in `verification/FINAL-LAYOUT-AUDIT.md`. |

## Validation history

The first GitHub Actions run established that the manuscript job compiled, preflighted, rendered, and uploaded correctly; it was superseded when a citation-scanner false-positive fix was committed. Run 2 (commit `b569982186c6546f78161d7b1b4500a438b90b21`) completed successfully across GCC, Clang, ASan/UBSan, ThreadSanitizer, Typst/PDF validation, the full benchmark campaign, CI policy, and the final publication gate.

The manuscript artifact from that run was downloaded and visually inspected page by page. That pre-spacing article contained 31 A4 pages and nine sequentially numbered native-vector figures; no clipping, overlap, broken glyph, or raster-diagram regression was observed.

A later independent readability cycle compared that render against the originally submitted paper. Global heading rhythm and paragraph leading were relaxed, a compact Introduction reading guide was added, two duplicated automatic-reference supplements were corrected, and a pagination experiment that created a half-empty page was explicitly rejected. The resulting local article is 33 A4 pages. Four independent passes—visual hierarchy, pagination/compiled text, implementation/evidence, and 200-DPI page inspection—found no remaining actionable defect before the final hosted-CI rebuild.


## Final publication-hardening pass (2026-09-30)

- Hosted publication-validation run 36583157931 completed successfully for revision `d2e9edb4f962f132e96d7e342bd14f48ff8446cc` and produced the 33-page manuscript artifact.
- A later evidence audit found a brittle fixed-field `pdffonts` parser and piped commands without an explicit pipefail shell. Direct inspection confirmed every detected font in the submitted PDF is embedded.
- The repository now parses the embedding field relative to the end of each `pdffonts` row and sets the workflow run shell explicitly to bash, so `tee` cannot mask a failing validation command.
- Stale `runtime/results/primary` and `runtime/results/scaling` documentation was replaced with the single authoritative `runtime/results/revision-2026-09-29/` campaign.
- Performance-optimization experiments were not retained: input-preparation parallelization showed a non-stable apparent gain, while atomic-index and targeted-wakeup scheduler variants regressed; statistics-counter aggregation reproduced the retained four-participant speedup within run noise. The simpler reviewed runtime therefore remains the final implementation.
