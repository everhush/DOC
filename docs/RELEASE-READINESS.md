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
