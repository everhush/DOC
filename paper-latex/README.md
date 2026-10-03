# Journal-neutral LaTeX manuscript

This folder contains the single-column LaTeX form of **Dependency-Oriented Computation: Persistent-Graph Semantics for Incremental Repair**.

## Source structure

The scientific manuscript is kept in publisher-neutral files. Publisher classes are thin adapters; the shared scientific body is the canonical source:

- `manuscript-body.tex`: abstract, sections, proofs, figures, tables, limitations, conclusion;
- `manuscript-preamble.tex`: standard packages, theorem environments, and notation;
- `references.bib`: bibliography.

Two thin wrappers compile the same body:

- `dependency-oriented-computation.tex` — neutral A4 `article` review manuscript, 11 pt, balanced 22 mm side margins and 20 mm top/bottom margins;
- `dependency-oriented-computation-computing.tex` — Computing submission adapter using the required one-column Springer `svjour3` `smallextended` class.

The neutral manuscript restores reviewer-useful diagrams and performance charts from the finalized Typst paper. The Computing adapter suppresses only those supplemental visuals that would push the mandatory Springer-formatted manuscript beyond Computing's 25-page limit; all theorem text, evidence tables, benchmark numbers, negative results, limitations, and references remain shared.

No geometry override or other space-saving modification is applied to the Computing wrapper.

The large right and bottom whitespace in the Computing PDF is intentional and comes from Springer's `smallextended` class itself: the class sets an approximately 119 mm by 194 mm single-column text area on the A4 submission sheet. Do not recenter or expand that area with `geometry`; Computing evaluates the 25-page limit in the mandated template and explicitly forbids space-saving layout changes.

## Intended submission use

**Computing is the first target.** Its current author instructions require the one-column `smallextended` LaTeX template and a maximum of 25 template-formatted pages. Submit the Computing PDF/source bundle for that journal.

The neutral A4 `article` wrapper is retained for reviewer-readable initial submissions to journals that permit flexible initial formatting, including the planned Elsevier fallbacks. It uses 11 pt text and ordinary A4 margins; no publisher class is required. A venue-specific wrapper can later be added without modifying the scientific body.

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

Computing's current author instructions request a professional or institutional author email and state that submissions using a private email address will be sent back. The Computing wrapper uses the author's professional-domain correspondence address, `rituraj@riturajbasak.tech`.

## Computing declaration checklist

Computing currently requires a Data Availability Statement and a competing-interest disclosure in the manuscript; the Computing wrapper includes both. Computing also requires funding information to be disclosed in the submission and summarized in the declarations section when applicable. The repository does not invent a funding statement: add the truthful funding/no-funding wording before submission if it is not already supplied through your final author metadata. The journal also states that submissions using a private email address will be returned; the Computing wrapper therefore uses `rituraj@riturajbasak.tech`.
