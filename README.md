# DOC — Dependency-Oriented Computation

DOC investigates a simple question: when the inputs to a long-lived computation change, why repeat work whose results are still justified? A DOC program describes typed values and the relationships between them. The realization determines which conclusions need repair, which independent work is ready, and how to use available computation resources. The same dependency structure governs initial evaluation and subsequent updates.

For example, if two numbers change but their sum does not, downstream work that depends only on the sum can retain its previous result. Input-dependent finite computation families can also determine the amount of independent work at runtime. The research model distinguishes that construction from changing values in a fixed graph, recurrence across epochs and physical scheduling.

## What has been demonstrated

The finite acyclic model gives conditional mathematical arguments for stabilization, agreement with complete reevaluation, schedule independence and sound equality cutoff. These results have explicit typing, totality, determinism and graph assumptions; they are not proof-assistant mechanized.

The independent DOC-authored compiler and runtime in `runtime-doc/` compile supported DOC programs into native executables without the original evaluator at execution. Linux x86_64 is the qualified host. The bounded implementation supports typed incremental repair, demand, recurrence, runtime-sized independent work, private graph replacement, automatic CPU worker admission and selected physical WebGPU execution. CPU is the default; strict GPU selection rejects unsupported operations or unavailable devices. Automatic heterogeneous placement uses heuristics, not an optimality guarantee.

In the final production campaign, all six validation jobs passed, including actual Tesla T4 execution. Automatic two-worker CPU prime-counting achieved 1.741-fold speedup (87.0% efficiency); representative same-session warm modular work achieved 13.85-fold automatic-backend speedup over one CPU worker. Cheap work, small reductions and device startup can be slower. See the [DOC-only reproducibility supplement](paper/REPRODUCIBILITY-NATIVE.md) for the complete matrix, methods, source identities and limitations. No universal acceleration, distributed scalability or unbounded memory claim follows.

## Explore the research

- [Computation-model preprint source](paper/dependency-oriented-computation.typ) — semantics, metatheory, conditional dynamic dependency generation and empirical evaluation.
- [Finite calculus source](paper-calculus/dependency-oriented-calculus.typ) — typed expressions and finite-family elaboration.
- [Independent implementation](https://github.com/everhush/DOC/blob/9491ca31303579b2ce223e344dee9b8b5354214f/runtime-doc/README.md), [current execution contract](BACKEND-EXECUTION-CONTRACT.md), [claim/evidence map](https://github.com/everhush/DOC/blob/9491ca31303579b2ce223e344dee9b8b5354214f/CLAIM-EVIDENCE-MAP.md).
- [Native compiler validation](https://github.com/everhush/DOC/issues/11), [performance evidence](https://github.com/everhush/DOC/issues/9), [release readiness](https://github.com/everhush/DOC/issues/14).

## Development and release status

This is the canonical development repository, not the separately curated release specified in #14. Master retains the immutable reference/bootstrap implementation and historical evidence; the retired Goose implementation is not part of the planned product. Native compiler/source-only release-candidate work is tracked in [the release readiness register](https://github.com/everhush/DOC/blob/master/docs/RELEASE-READINESS.md). The development bootstrap may use the frozen reference; a distributed release must instead use a separately trusted native bootstrap and rebuild its DOC-authored compiler. No public installable compiler release or production support promise is implied.

The source-level [candidate validation guide](release/README.md) describes the clean-source build being qualified. Its artifact is a development review candidate, not a released distribution.

## Rights and collaboration

The existing [LICENSE](LICENSE), [Apache 2.0 text](LICENSE-APACHE) and [NOTICE](NOTICE) remain in force for their stated scope. A future source-available distribution requires specific reviewed license terms and third-party rights; previous grants are not revoked. Paper versions and historical results are preserved. Research questions and reproducibility findings can be discussed through the repository issue tracker. No sponsorship arrangement or commercial permission beyond the actual license is implied.
