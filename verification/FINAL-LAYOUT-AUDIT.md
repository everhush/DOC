# Final layout and readability audit

Audit date: 2026-09-29.

This audit records the final post-review visual/readability iterations applied after the technical revision had already passed its semantic and implementation checks. The manuscript source remains Typst-native; no raster diagrams were introduced.

## Iteration 1 - hierarchy and reading flow

- Compared the revised 31-page PDF against the originally submitted article page by page.
- Increased paragraph leading slightly and expanded level-1/2/3 heading separation globally rather than inserting manual page-specific gaps.
- Kept the established navy/green/warm visual language, but changed level-3 headings to a quieter semibold blue-gray so dense formal pages have a clearer hierarchy.
- Added a compact reading guide at the end of the Introduction instead of restoring the report-style contents page.
- Recompiled and inspected the full document. The initial reading-guide wording incorrectly said “next three sections”; the following audit caught and corrected it to “next four sections.”

## Iteration 2 - independent pagination and compiled-text audit

- Audited headings near page bottoms and confirmed that each retained low-page heading has meaningful following content rather than an orphaned title.
- Scanned the compiled PDF text for duplicated automatic supplements and found two genuine editorial defects: “Equation Equation 1” and “Equations Equation 16 and Equation 17.” Both were corrected at source by relying on Typst's automatic reference supplement.
- Tested an unbreakable six-item safe-realization contract. The resulting render produced an unattractive half-empty page, so that experiment was reverted and the visually better balanced split was retained.
- Recompiled and re-rendered after the reversion.

## Iteration 3 - independent implementation and evidence pass

- Clean Release build: 7/7 registered CTest targets passed, including all five bounded model checkers.
- Manuscript checker: 73 unique labels, all figure/table/algorithm labels referenced, 16/16 bibliography keys resolved, benchmark values consistent with the retained campaign, and no `image(...)` calls.
- PDF preflight: tagged A4, openable, unencrypted, embedded fonts, zero embedded image XObjects, 33 pages.
- ASan/UBSan: native runtime suite and benchmark-generator oracle passed.
- ThreadSanitizer: native runtime suite and benchmark-generator oracle passed.

## Iteration 4 - independent final visual pass

- Rendered all 33 pages at 200 DPI.
- Inspected the title/abstract page, introductory running example and reading flow, dense finite-semantics pages, theorem/proof pages, recurrence and realization sections, placement diagrams, benchmark tables/charts, appendices, declarations, and references.
- Checked for content within eight pixels of the physical page edge: none.
- Checked every conceptual diagram/chart remains vector-native Typst content.
- No clipping, overlap, broken glyphs, caption collisions, table overflow, malformed equations, inconsistent figure numbering, or actionable spacing defect remained in the local final render.

The hosted build at revision `d2e9edb4f962f132e96d7e342bd14f48ff8446cc` completed and produced the 33-page reviewer-revision manuscript artifact. A subsequent 2026-09-30 publication-readiness pass hardened the repository PDF-preflight/pipefail logic; the later final evidence pass then adopted the completed 100-sample bare-metal campaign and repeated manuscript compilation, structure/font/vector checks, and page inspection.


## Final submission pass - 2026-09-30

- Increased only level-3 heading separation from `above: 0.92em, below: 0.38em` to `above: 1.05em, below: 0.55em`; level-1/2 rules and paragraph leading were left unchanged.
- Recompiled with Typst 0.15.1 with zero diagnostics and rendered all 33 pages again.
- Inspected every page individually and then repeated the review from six whole-document contact sheets; two consecutive visual passes produced no conflicting finding.
- Rechecked the title/abstract, all formal blocks and equations, nine labeled figures, eleven labeled tables, performance/limitations pages, related-work table, appendices, declarations, and all reference pages.
- A clean-room rebuild from only the final `.typ` and `.bib` files produced the same 33-page A4 geometry and byte-identical extracted text.
- Final PDF preflight again found all detected fonts embedded and no raster/image XObjects.
- No clipping, overlap, broken glyph, caption collision, table overflow, orphaned level-3 heading, malformed equation, or inconsistent hierarchy remains.


## 100-sample evidence adoption - 2026-09-30

- Replaced all article performance numbers derived from the 20-sample EPYC campaign with the generated raw statistics from `runtime/results/independent-dedicated-100/`.
- Updated the benchmark host/method description, reduction table, parallel means/confidence intervals/speedups, parallel chart labels, financial table and derived ratios, sorting-network ranges, limitations, and code/data availability statement.
- Recompiled and re-rendered the full manuscript after the numerical substitution; page count remains 33 and the level-3 spacing/layout treatment remains intact.
- The manuscript checker now reads the 100-sample statistics file, so stale 20-sample article numbers fail validation.
- Post-substitution PDF preflight reports 33 A4 pages, all detected fonts embedded, and zero raster/image XObjects.
- Modified pages 1, 26, 27, 28, and 32 were inspected individually at rendered resolution; a second whole-document pass used six contact sheets covering all 33 pages. No clipping, overlap, chart-label collision, table overflow, malformed line wrap, or new pagination defect was found.

## Submission declaration simplification - 2026-09-30

- Replaced the detailed private-repository/data-availability paragraph with the single sentence: “A source and reference archive is provided with this submission.”
- Removed the Generative-AI disclosure from the manuscript at the author's request.
- Recompiled the manuscript with Typst 0.15.1; it remains 33 A4 pages with zero compiler diagnostics and all detected fonts embedded.
- Re-rendered and inspected pages 32-33 after the declaration changes. The Declarations/References transition is clean, with no clipping, overlap, orphaning, or pagination defect.
