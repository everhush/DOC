# Journal-neutral LaTeX manuscript

This folder contains the compact LaTeX form of **Dependency-Oriented Computation: Persistent-Graph Semantics for Incremental Repair**.

## Intended submission use

The manuscript uses Springer's one-column `svjour3` class with the `smallextended` option because **Computing** currently requires that format and limits submissions to 25 pages. The resulting single-column reviewer PDF is also suitable for regular initial submission to **Journal of Systems and Software**, **Future Generation Computer Systems**, and **Information and Software Technology**, whose regular Elsevier initial-submission workflows accept reviewer-readable manuscripts without requiring this source to be rewritten. A special issue may impose its own template or page limit.

The scientific content follows the finalized Typst manuscript. Space was saved by consolidating redundant explanatory graphics into text/tables, not by shrinking fonts, margins, proofs, or negative results.

The source deliberately omits repository URLs, checksums, AI-related declarations, and submission-internal provenance. A source/reference archive is supplied separately with the journal submission.

## Build

Keep every file in this directory together and run:

```sh
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
bibtex dependency-oriented-computation
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
pdflatex -interaction=nonstopmode -halt-on-error -file-line-error dependency-oriented-computation.tex
```

The repository CI performs the same build and validates the PDF page count, word-count ceiling, references, PDF structure, and embedded fonts.

## Submission note for Computing

Computing's current author instructions request a professional or institutional author email. The manuscript currently contains the author's existing Gmail address. Replace it with a professional/institutional address before submitting to Computing if one is available; the scientific manuscript does not otherwise require a journal-specific rewrite.
