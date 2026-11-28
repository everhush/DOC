# DOC14 rights and external-dependency review register

Review checkpoint: master 43b6f05c1f070b16824beb289bab78914701f41b; 2026-11-28. **Internal review, not legal clearance, license selection or publication authorization.** Scope is the proposed core candidate (without optional graphics/game, original evaluator or publisher class). A source inventory and public license declaration are evidence, not a certification of ownership.

## Existing grant and future distribution

The current [LICENSE](../LICENSE), [Apache text](../LICENSE-APACHE) and [NOTICE](../NOTICE) remain binding in their stated scope: CC BY 4.0 research/documentation, original software additionally Apache-2.0, third-party terms preserved. The future source-available decision in [issue 14](https://github.com/everhush/DOC/issues/14) is not a selected license. Prior grants cannot be withdrawn from already licensed copies by changing a future license. Do not claim that previously granted Apache permissions have been extinguished, that all sources can be relicensed, or that the future distribution is OSI-approved.

Before any release, the rights holder must identify exact files and new contributions eligible for future licensing, agree exact written terms/version (use, modification, redistribution, commercial use, hosted services, patent/trademark, termination and sublicensing provisions), retain existing notices and applicable third-party permissions, and approve the final license map. No new license text was selected or installed by this review.

## Source provenance and rights evidence

| Scope | Evidence inspected | Disposition |
|---|---|---|
| DOC compiler/runtime | Git commit history filtered to runtime-doc: 84 returned commits, 65 linked to one GitHub account and 19 not linked to an account | Confirm author identities and rights for all material, including incorporated/adapted code; commit author fields are not assignments |
| Main paper | 16 path-history commits, 15 linked and one unresolved | Verify original/submitted-version rights and any publisher agreement |
| Calculus paper | 3 path-history commits, all linked | Verify authorship and version-specific release permission |
| LaTeX paper | 32 path-history commits, all linked | Neutral wrapper only; publisher template remains excluded |
| Release tooling | 12 path-history commits, all linked | Review generated/assisted contributions and ownership under applicable terms |
| Optional game/graphics | Not in core inventory | No asset/engine distribution clearance inferred; separate review if included |

Counts are the returned path histories at the checkpoint (each below the 100-result page limit), not unique individuals, complete attribution or proof of copyright ownership. Multiple paths may overlap in history. The author account link being absent does not establish an unrelated contributor.

Independently inspected the exact earlier corrected source artifact 15248985274 (88 entries; see readiness register). Current comparison shows no changes to manuscripts or root license files. Typst main source contains 15 figure constructs, LaTeX body 10 figure environments, calculus no figure constructs; no external image includes/imports in the inspected paper sources. Bibliographies each contain 16 entries. These are source inventory observations, not a declaration that every claim, figure design, quotation, adaptation or historic dataset is independently owned. Check citations and figure/data provenance against originals; do not remove necessary attribution. The Computing wrapper is 28 pages against the recorded 25-page constraint: defer any resubmission until publisher decision. Existing submissions remain untouched.

## External dependencies and distribution boundary

| Component | Exact evidence / declared terms | Required action |
|---|---|---|
| Native WebGPU provider | [wgpu-native v27.0.4.1](https://github.com/gfx-rs/wgpu-native/releases/tag/v27.0.4.1), annotated tag 4d41e7c8f4a1c76c6e1c15134175f7b2adc61e67 points to f16f716698899ebfcc3f703722fabd85543318a7; GitHub reports tag signature valid. Manifest declares MIT OR Apache-2.0; [MIT](https://github.com/gfx-rs/wgpu-native/blob/f16f716698899ebfcc3f703722fabd85543318a7/LICENSE.MIT), [Apache](https://github.com/gfx-rs/wgpu-native/blob/f16f716698899ebfcc3f703722fabd85543318a7/LICENSE.APACHE). Linux archive asset 391870975, 15,925,192 bytes, SHA-256 9385b8a9e4e6f0b00264757577511097104fedf6db7819aa3e34a106c3dc0a42 agrees with pinned CI value | External download, not vendored. Audit actual archive contents and compiled transitive dependencies, preserve applicable notices before distribution of binaries or headers |
| WebGPU ABI headers | Provider tree references submodule 7d3186c3dd2c708703524027b46b8703534ab3cc; [license](https://github.com/webgpu-native/webgpu-headers/blob/7d3186c3dd2c708703524027b46b8703534ab3cc/LICENSE) is BSD-3-Clause | Keep copyright, conditions and disclaimer in source/binary distributions as applicable; no implied endorsement |
| Internal bootstrap | Frozen Rust reference tree a95a38bc6e9300aae815f83b570db5f99d32f221; Cargo manifest declares CC-BY-4.0 and default normal dependency libc with version range 0.2. Optional GPU/window and dev dependencies present in manifest but not intended for this CPU bootstrap | Obtain actual successful Cargo.lock, review resolved normal dependency versions and licenses, preserve immutable lock for subsequent build; check actual ELF linkage and applicable notices. Do not distribute the retired evaluator |
| Native host | Linux x86-64 C compiler, binutils, libc/POSIX/pthread/math, system graphics provider and device driver | System prerequisites, not source vendoring; inventory exact versions/linked components and check obligations of any redistributed binary |
| Validation infrastructure | Pinned GitHub actions, Rust toolchain 1.100.1, Python, private Kaggle CLI and host graphics provisioning | Internal CI only. Review action/CLI transitive versions and licenses, preserve exact tool records; credentials never distributed |
| Scientific rendering | Typst, LaTeX packages and fonts; neutral source uses system packages and locally supplied bibliographies | Verify applicable font/package redistribution terms if shipped; no class files, fonts or rendered PDFs in tracked candidate |

No exact reviewed Cargo.lock was accessible at this checkpoint: the active corrected run's bootstrap stage was still in progress, with only its source artifact visible. Do not fabricate a lockfile from manifest version ranges or claim a lock generated afresh is a reproducible pin. The eventual lock must come from verified build evidence and be checked against the frozen manifest, not modify frozen runtime-rust source.

## Required approvals / release boundary

- [ ] Resolve author identity/ownership and third-party provenance; document file-level exceptions and permissions.
- [ ] Review actual WebGPU archive transitive notices and native bootstrap dependency lock; inventory external host and validation dependencies.
- [ ] Confirm exact future source-available text and file scopes, preserving prior grants.
- [ ] Confirm permission for revised research artifacts, publisher version/page constraints and any third-party source/figure/data reuse.
- [ ] Complete fresh signed candidate and physical qualification with durable evidence; preserve negative results.
- [ ] Obtain explicit final authorization before new repository, tag, release or manuscript publication.

This register is a review input only. No permissions or publication approval are inferred.

## Recovered and pinned bootstrap lock — verification checkpoint

Run 46106999905 stage 140866704983 completed successfully. Independently retrieved bootstrap artifact 15249125386, ZIP SHA-256 `feccf548a5a0b5db3708f319dc7663e4f3ee08dd4cf0656887f481c51be522e7`; CRC passed, all six recorded subject checksums matched, embedded source SHA 2a251298e0f8bf9bdc62f51645a3441ade716531. Both native executable SHA-256 values are unchanged from the first verified bootstrap (managed db17fecb3d0588993fe7700d47a2c623400d25431ba41ee3201dc9ad357c104c; module_scan ebaf0b1b6c1da606aee00528979858548f961aa04155f0da8a7517f71bbca25b). Independently inspected the actual ELF headers and dynamic dependency lists: x86-64, libc.so.6 only. Cargo.lock format 4, 57,000 bytes, Git blob 619049d06ad88cae1c97dc6ca6c70f2313e6dff5, SHA-256 `e1b60aca7f477425698a7247d50c2575cfffe39a592ebda664e43952c400407e`. TOML parsed successfully: 234 unique package identities, 233 crates.io registry entries each with a 64-hex checksum, one local root. The actual recorded normal dependency tree is doc-runtime 0.1.0 -> libc 0.2.191 (lock checksum 65cd87c9a6d60536580b316ad985726104730a5151c99845f2490428ef91240a). The [upstream exact-version manifest](https://github.com/rust-lang/libc/blob/0.2.191/Cargo.toml) declares MIT OR Apache-2.0. Full optional/development registry inventory is not evidence of compiled or distributed dependencies; no complete transitive license clearance inferred.

Future internal bootstrap CI retrieves the exact successful prior run artifact using actions:read, verifies its ID/name/source/run/digest and non-expiry, then verifies the exact lock bytes before and after a --locked --no-default-features build. The lock origin record is included in the signed checksum manifest. No fresh lock resolution or mutation of the frozen tracked reference tree is allowed. This pins a verified input, but remains dependent on artifact retention until an immutable long-term copy of the actual lock is placed in a suitable internal store; expired/unavailable artifact must fail closed, never regenerate a different lock. This is not a completed fresh locked build or signed provenance run. Current corrected clean CPU job 140867563020 is in progress; full signed run 46108605003 is queued. The new revision skips CI to preserve both; its lock-reuse configuration still requires execution.

## Permanent exact bootstrap lock retention

The previously verified 57,000-byte Cargo.lock is now tracked as `ci/bootstrap/doc14.Cargo.lock` (Git blob `619049d06ad88cae1c97dc6ca6c70f2313e6dff5`, SHA-256 `e1b60aca7f477425698a7247d50c2575cfffe39a592ebda664e43952c400407e`). The original verified artifact, source, job, frozen reference tree and lock identities are recorded in `ci/bootstrap/doc14-lock-origin.json`. The CI job verifies the tracked lock Git object and SHA-256, copies the exact bytes into the untracked bootstrap build location, builds with --locked --no-default-features, and checks the digest again. This supersedes retrieval from the expiring GitHub Actions artifact: no live artifact download, actions:read permission or fresh dependency resolution is needed. The lock and provenance are internal development build inputs, excluded by the existing explicit curated source allowlist; the frozen tracked reference tree remains unchanged. Exact lock storage and workflow wiring are complete; a fresh locked build and signed physical qualification still require successful CI execution. Existing run snapshots are preserved.
