# Issue #14 release-readiness register — development, not release approval

Canonical master base: 4f0e8e6b33f9fcb9843be3104a5969ddbccf856c. Exact #11 accepted native implementation, frozen reference and actual engine/game validation are recorded in issue #11 comment 7216772969; #9 final qualified runtime/compiler trees and physical results remain unchanged. Master manuscript render 46104609751 PASS; source artifact 15246867071 digest 6afc75c954d30c9f92d1796f90f86a936b14af7de89bbcbe0e5387ba75f2f1c6. Reviewed source-only candidate is an intermediate stage, not final R0–R11 acceptance.

| Gate | Present evidence / remaining requirement |
|---|---|
| R0 | Accepted development reference and #9 actual native physical and CPU evidence. Final curated-source conformance still required. |
| R1 | #11 byte-identical Stage2/3 and native tools; clean candidate requalification initiated. |
| R2 | Development native source/graph/epoch/ownership/rollback tests passed; candidate CPU regression required. |
| R3 | Development physical T4 and independent numerical parity passed. Candidate GPU build and physical validation not yet executed. |
| R4 | Candidate excludes retired evaluators, old CI, generated headers and historical evidence; caller/dependency audit and native install still required. |
| R5 | Separate native bootstrap and clean-source requalification initiated. Final signed/hash-pinned bootstrap, install and full physical qualification pending. |
| R6 | Editable papers retained; license selection, permissions, third-party notices and paper/asset rights remain open. |
| R7 | DOC-only supplement and archived exact-run evidence. Durable artifact publication, independent raw distributions/build/size and pinned CI audit pending. |
| R8 | Development #11 actual game validation passed. Initial candidate omits optional game distribution to limit footprint; final choice remains a release decision. |
| R9 | Source-only manifest/curation candidate first gate; complete caller, dependency, rights, secrets and exact release-root audit pending. |
| R10 | Revised accessible development README drafted; actual curated install instructions and release status must be verified before publication. |
| R11 | Dynamic generation and finite-family conditional proofs, historical/current empirical separation, source diff and master render verified. Full independent PDF/editorial/attribution and publisher page-limit review still pending. |

## Rights and publication stop gate

Existing LICENSE and NOTICE explicitly grant Apache-2.0 for original software and CC BY 4.0 for research/documentation, preserving prior grants. No new terms can retroactively cancel those grants. Before selecting the future source-available terms, establish copyright and contributor rights, review third-party WebGPU/native dependencies (including external downloaded binaries), publisher class and style terms, paper and game-asset rights, and choose exact license text/version plus scope. No final license has been authorized or applied. No new public repository, package, tag, binary or paper submission has been created. A separate fresh root and publication require all gates and explicit final approval. Historical commits and existing licenses remain immutable.

## Curation procedure

The first candidate is generated into a fresh workspace from an explicit source SHA using release/curate.py and a path allowlist, with a per-file original blob/byte digest/mode manifest outside the candidate. It excludes generated headers and regenerates policy macros using a separate native bootstrap for CPU validation. It is intentionally a narrow core candidate, not a claim that every retained source has a proven live caller or that every required final file is already included. Build outputs remain artifacts. Review the exact candidate inventory, full dependency graph, complete independent tests and actual physical validation before accepting a release tree.

## First candidate export audit

Run 46105142921, source 9491ca31303579b2ce223e344dee9b8b5354214f: source export passed; artifact 15247725787, ZIP SHA-256 `27dc610f44d59108d2921292fae7be117387a44d09dbd0f186abdff93a85d054`. Independently verified ZIP CRC and digest, inner tar hash, exact manifest of 85 files, every SHA-256 and Git blob identity and UTF-8 decoding, no generated headers, binary data or symlinks. Four relative references from copied development documentation were absent in the candidate; replaced them in development source by explicit canonical links for the next export. This first export is not final curation. Bootstrap is still in progress at the time of this check. The source candidate is a development CI artifact; no new release repository or distribution license was created. The canonical development repository is already public according to repository metadata; do not confuse its visibility with #14's planned separately curated release.

## Retained empirical and caller re-audit

Independent archive re-audit of the original physical result completed; see [DOC14 empirical audit](DOC14-EMPIRICAL-AUDIT.md). All 1,827 checksum observations, 399 process identities, 4,374 physical dispatch traces, 880 inner archive files and 133 warm medians match; descriptive tail and cold/process timing observations added without changing manuscript numbers. Candidate static caller scan identified optional scene/mesh source and legacy standalone frontend footprint for further curation. No new physical measurement or final R7/R9 clearance claimed.

## Independent candidate bootstrap and bounded native resource checks

Run [46105142921](https://github.com/everhush/DOC/actions/runs/46105142921), exact candidate revision `9491ca31303579b2ce223e344dee9b8b5354214f`. Independently downloaded source artifact 15247725787 and internal bootstrap artifact 15247027700. Both ZIP digests matched GitHub metadata and every ZIP entry passed CRC; source tar digest `1cc4009ff73c82f2a493b0de780b8f1402dc3515c247aa21151f1d15c633cd0c`; all 85 source file sizes, SHA-256 values, Git blob identities, modes and UTF-8 decoding match the manifest. No nonregular tar members other than directories were found. Bootstrap ZIP SHA-256 `ba6ccd431b313b2d658f80f2e2c789837312a27942226ec268ca41c31a12439b`; embedded source SHA matches the candidate. Independent ELF inspection:
 
| Binary | SHA-256 | Size (bytes) | Declared shared-library dependency |
|---|---|---:|---|
| managed | `db17fecb3d0588993fe7700d47a2c623400d25431ba41ee3201dc9ad357c104c` | 832376 | libc.so.6 |
| module_scan | `ebaf0b1b6c1da606aee00528979858548f961aa04155f0da8a7517f71bbca25b` | 97760 | libc.so.6 |

Both are x86-64 ELF executables and both binary hashes agree with the embedded SHA256SUMS. This is artifact integrity and declared dynamic linkage verification, not signed bootstrap provenance, a complete runtime dependency audit or independent compiler reconstruction.

An independent clean extraction of the same candidate, with the two native bootstrap binaries outside the source tree and without a reference evaluator checkout, generated all six policy headers. Local GCC builds with AddressSanitizer and UndefinedBehaviorSanitizer (nonrecovering) passed the three candidate C regressions:
- `DOC9_SCRATCH_PASS`: 65 fault ordinals, 1000 repeated scopes, peak 1712, 7259 allocations, live 0.
- `DOC9_NAME_INDEX_PASS`: seven size classes, 64 independent index lifetimes, length/prefix/duplicate/hole checks, live 0.
- `DOC9_RESOURCE_BOUNDARY_PASS`: exact signed parsing, malformed rejection, million-lane list, resource overflow and zero live bytes.

The local full self-reproduction attempt was time-bounded and did not return a result; it is not accepted as a pass. The GitHub clean-cpu job state at this observation was in_progress (no conclusion). No CI jobs were cancelled. The current workflow has only stage and clean-cpu jobs; GPU release-candidate qualification is not covered. Its CI uses mutable action/toolchain tags and must undergo immutable pinning and dependency review before final R7 acceptance. Existing rights grants, separate release approval, complete curation, signed bootstrap, physical GPU qualification, durable evidence and publisher constraints remain open. No production runtime/compiler or manuscript source changed in this checkpoint.

## Fail-closed candidate manifest verification

The candidate workflow previously checked only the transported tar checksum before extraction. The new independent `release/verify_candidate.py` checks the source commit, unique canonical relative paths, exact file inventory, byte counts, SHA-256, Git blob SHA-1 identities, regular file modes, UTF-8 text, and capacity limits before writing any source file. It rejects links and unexpected members. The exporter now checks the original tar before upload; the clean job verifies it again and writes its own fresh source tree, rather than invoking unrestricted tar extraction. The verifier is transported as a separate stage-produced file and is also included in the curated source. This checks consistency and safe extraction, not cryptographic publisher identity or signed bootstrap provenance.

Local test: the genuine source artifact 15247725787 at 9491ca31303579b2ce223e344dee9b8b5354214f passed all 85 file entries (696919 bytes). Sixteen negative cases were rejected without creating an output directory: wrong commit, duplicate manifest entry, unsafe manifest path, mismatched SHA-256, Git blob, mode, and size, missing manifest entry, extra tar file, traversal, absolute path, duplicate member, symbolic link, hard link, omitted file, and modified bytes. The revised workflow is not yet accepted as a successful new CI run. No qualified compiler/runtime or manuscript sources are changed by this validation patch.

## Latest manuscript render — independent visual and PDF preflight

Run [46105142888](https://github.com/everhush/DOC/actions/runs/46105142888), artifact 15247700465, source `9491ca31303579b2ce223e344dee9b8b5354214f`. Downloaded ZIP SHA-256 `292793fd471f5519625a2e7e8ee939fdfb4e38d6aba568c00030c329d2dabee0` matches GitHub metadata; all 24 unique ZIP entries passed CRC and the embedded source SHA agrees. GitHub comparison against master 8c879a5ff58b53aecd8007ffd55426c5fbda88f7 lists no changes to manuscript, bibliography or publisher wrapper sources.

| PDF | Pages | SHA-256 | Embedded font entries |
|---|---:|---|---:|
| Preprint | 36 | `1390cde3a31a2cce5ded94454f543ed0284b09e64f65118149e25bfc18bf1977` | 7/7 |
| Finite calculus | 5 | `81338b8bc574a8326e893cbd3306d2122defe2a3b34a4bef291546fd8d9e8341` | 3/3 |
| Neutral LaTeX | 24 | `badfc01d2f8d4d6a55cf7fc9c97582ba976fca527cf3885645bb26d3b6609e09` | 27/27 |
| Computing wrapper | 28 | `b5487a22addf757f1909ad6703dfd1d6e6d28bee329cc9ae6605621f042d1fdb` | 24/24 |

Rendered and visually inspected contact sheets covering all 93 pages (nine sheets). No obvious page-scale clipping, blank pages, missing figures or broken layout observed. Programmatic text-block bounds check found zero blocks outside the page by more than 1 pt. All pages have extractable text; zero replacement characters, zero unresolved bracketed citation/numbered-reference markers detected, and zero matches for the excluded named comparative engines in extracted text. All fonts are embedded per pdffonts. This is a rendering/layout preflight, not a line-by-line proof validation, external-link availability check, copyright clearance or acceptance by the publisher.

The Computing wrapper still exceeds its recorded 25-page limit by three pages; its log reports one 2.74968 pt overfull horizontal box at lines 535–536. The neutral LaTeX log has no matching overfull/undefined-reference/missing-character warnings. Retain the synchronized full-length neutral and Typst sources and defer venue-specific shortening until the version/editorial decision; do not alter margins or font sizes to force compliance. No submitted version replaced and no paper or runtime source edited.

At this observation the original clean-cpu job (run 46105142921) remained in progress. The updated manifest-verification run [46106120875](https://github.com/everhush/DOC/actions/runs/46106120875) was pending with no job records. No new candidate build, physical GPU acceptance, or publication approval claimed. This documentation-only checkpoint avoids replacing an already pending CI run.
