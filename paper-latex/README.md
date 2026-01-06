# Journal-neutral LaTeX manuscript

This folder contains the single-column LaTeX form of **Dependency-Oriented Computation: Persistent-Graph Semantics for Incremental Repair**.

## Source structure

The scientific manuscript is kept in publisher-neutral files:

- `manuscript-body.tex`: abstract, sections, proofs, figures, tables, limitations, conclusion;
- `manuscript-preamble.tex`: standard packages, theorem environments, and notation;
- `references.bib`: bibliography.

Two thin wrappers compile the same body:

- `dependency-oriented-computation.tex` — neutral A4 `article` review manuscript, 11 pt, balanced 22 mm side margins and 20 mm top/bottom margins;
- `dependency-oriented-computation-computing.tex` — Computing submission adapter using the required one-column Springer `svjour3` `smallextended` class.

The neutral manuscript restores reviewer-useful diagrams and performance charts from the finalized Typst paper. The Computing adapter suppresses only those supplemental visuals that would push the mandatory Springer-formatted manuscript beyond Computing's 25-page limit; all theorem text, evidence tables, benchmark numbers, negative results, limitations, and references remain shared.

No geometry override or other space-saving modification is applied to the Computing wrapper.

## Intended submission use

**Computing is the first target.** Its current author instructions require the one-column `smallextended` LaTeX template and a maximum of 25 template-formatted pages. Submit the Computing PDF/source bundle for that journal.

The neutral A4 wrapper is retained for reviewer-readable initial submissions to journals that permit flexible initial formatting, including the planned Elsevier fallbacks. A venue-specific wrapper can later be added without modifying the scientific body.

The source deliberately omits repository URLs, checksums, and submission-internal provenance. A source/reference archive is supplied separately with the submission.

## Build

Neutral manuscript:

```sh
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
bibtex dependency-oriented-computation
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
```

Computing manuscript:

```sh
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation-computing.tex
bibtex dependency-oriented-computation-computing
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation-computing.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation-computing.tex
```

Repository CI builds and validates both PDFs, including page count, word-count ceiling, unresolved references, layout overflow, PDF structure, and font embedding.

## Computing submission note

Computing's current author instructions request a professional or institutional author email and state that submissions using a private email address will be sent back. The manuscript currently contains the author's existing Gmail address. Replace it with a professional/institutional address before submitting to Computing if one is available.
