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

The final hosted-CI artifact check is recorded separately after the corresponding GitHub Actions run completes.
