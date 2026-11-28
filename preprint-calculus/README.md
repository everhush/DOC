# DOC calculus preprint

This is an independent draft manuscript, not a modification of the submitted Computing paper. It defines a small, pure, first-order expression fragment as an instance of DOC's finite acyclic graph semantics and states the corresponding reduction rules and proof obligations.

Source: dependency-oriented-calculus.typ (Typst). Build from the repository root with `typst compile --root . preprint-calculus/dependency-oriented-calculus.typ preprint-calculus/dependency-oriented-calculus.pdf`. Generated PDFs are not committed. See the root README and manuscript review workflow for build and validation instructions.

The current Rust crate supports only the declared finite fragment; later recurrence, graph-version replacement, physical realization, and distributed extensions remain separate work.
