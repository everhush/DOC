# Reviewer response matrix

This matrix maps the two initial reviews to concrete repository/manuscript changes.

| Reviewer concern | Revision | Status |
|---|---|---|
| Problem and DOC terminology are too abstract. | Introduction now starts from a running repair example before general terminology; persistent logical state, retained valuation, activation, frontier selection, cutoff, and publication are explained concretely.  Addressed |
| Novelty is not assessable against incremental computation. | Related work now compares program representation, graph mutability, repair state/rule, cutoff, demand, and guarantees without claiming dependency tracking itself is new.  Addressed |
| Tables/figures are not labelled or referenced. | Tables, algorithms, equations, theorem-family results, and all nine figures have labels/cross-references; CI rejects unreferenced figures/tables/algorithms.  Addressed |
| Core-semantics purpose is unclear. | The section now states its role and is organized around definitions, transition rules, and Algorithm 1.  Addressed |
| Symbols such as `S` and `P_d` are undefined/ambiguous. | Finite-program and local-definition notation is defined explicitly before use; premise-sequence evaluation is written out.  Addressed |
| Need a stepwise algorithm. | Added finite-stabilization pseudocode with source update, active set, dependency-minimal frontier, evaluate, cutoff/publish, user activation, and termination.  Addressed |
| Lemmas/theorems/corollaries/equations need labels. | Formal results and proof-relevant equations are numbered and cross-referenced.  Addressed |
| Validation/runtime-conformance organization overlaps. | Experimental validation is organized by semantic conformance versus performance/reproducibility.  Addressed |
| Results do not establish universal performance superiority. | Claims are explicitly workload/host specific; specialized cached and fine-grained negative controls remain prominent.  Addressed |
| Formal assumptions are demanding for build/compiler settings. | The paper states pure/total/deterministic finite-kernel assumptions and explains that failures/effects/external observations must be values/contracts or remain outside the kernel.  Addressed |
| Broader claims may be mistaken for consequences of the finite theorem. | Claim/evidence mapping separates finite theorem, conditional recurrence/versioning results, realization contracts, runtime evidence, and empirical evidence.  Addressed |
| Semantic-key compatibility is underspecified. | Added an operational graph-version example and states that arbitrary function equivalence is not decided by DOC.  Addressed |
| Parallel result could be overgeneralized. | The article reports one-host, four-CPU-quota evidence only and explicitly rejects distributed-scalability inference.  Addressed |
| Reproducibility details need to be in the article and stable. | Retained campaign includes machine/config/raw/statistical files; CI regenerates benchmarks, PDF, renders, and validation logs on every push/PR.  Addressed |
