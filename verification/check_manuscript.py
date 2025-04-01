#!/usr/bin/env python3
"""Publication checks for the DOC manuscript and retained evidence."""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "dependency-oriented-computation.typ"
BIB = ROOT / "paper" / "references.bib"
STATS = ROOT / "runtime" / "results" / "revision-2026-09-29" / "statistics.csv"

errors: list[str] = []
notes: list[str] = []
source = PAPER.read_text(encoding="utf-8")


def fail(message: str) -> None:
    errors.append(message)


def require(text: str, why: str) -> None:
    if text not in source:
        fail(f"missing {why}: {text!r}")


# Native Typst graphics only.
if re.search(r"(?<![A-Za-z0-9_])image\s*\(", source):
    fail("paper source contains image(...); diagrams/charts must remain native Typst vectors")
diagram_count = len(re.findall(r"#diagram\s*\(", source))
if diagram_count < 7:
    fail(f"expected at least 7 native conceptual diagrams, found {diagram_count}")
for primitive in ("#line(", "#polygon(", "#rect("):
    if primitive not in source:
        fail(f"missing native Typst drawing primitive {primitive}")
if 'kind: "diagram"' in source:
    fail('custom diagram figure kind would restart visible Figure numbering')

# Cross-reference integrity.
labels = re.findall(r"<([A-Za-z0-9:_-]+)>", source)
refs = set(re.findall(r"(?<!\\)@([A-Za-z0-9:_-]+)", source))
seen: set[str] = set()
for label in labels:
    if label in seen:
        fail(f"duplicate label: {label}")
    seen.add(label)

for prefix in ("fig:", "tab:", "alg:"):
    for label in (x for x in labels if x.startswith(prefix)):
        if label not in refs:
            fail(f"unreferenced {prefix[:-1]} label: {label}")

visual_labels = [x for x in labels if x.startswith("fig:")]
if len(visual_labels) != 9:
    fail(f"expected 9 visual figure labels, found {len(visual_labels)}")
if source.count('kind: "figure"') != 3:
    fail('expected shared kind: "figure" on the diagram macro and two benchmark charts')
if re.search(r"\b(?:Section|Table|Figure)\s+\d+(?:\.\d+)*\b", source):
    fail("hard-coded numbered Section/Table/Figure reference remains")

# Bibliography integrity.
bib_text = BIB.read_text(encoding="utf-8")
bib_keys = set(re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", bib_text))
structural = ("fig:", "tab:", "alg:", "eq:", "sec:", "thm:", "lem:", "cor:", "def:", "app:")
citations = {r for r in refs if not r.startswith(structural) and r != "gmail"}
missing = sorted(citations - bib_keys)
unused = sorted(bib_keys - citations)
if missing:
    fail(f"citation keys missing from references.bib: {missing}")
if unused:
    fail(f"unused bibliography entries: {unused}")
if "10.1145/2594291.2594324" not in bib_text:
    fail("verified Adapton DOI is missing")

# Reviewer-targeted semantics and scope.
for token, why in [
    ("<eq:program>", "program graph equation label"),
    ("P_d", "explicit premise sequence notation"),
    ("<alg:finite-stabilization>", "finite stabilization algorithm"),
    ("semantic key", "graph-version semantic-key discussion"),
    ("arbitrary function equivalence", "compatibility caveat"),
    ("repair-admissible", "finite theorem precondition"),
    ("pure, total, deterministic", "finite kernel assumptions"),
    ("specialized", "specialized-baseline performance discussion"),
    ("four-CPU quota", "parallel capacity boundary"),
    ("runtime/results/revision-2026-09-29/", "stable evidence path"),
]:
    require(token, why)

# Benchmark values printed in the article must match the retained campaign.
rows: dict[tuple[str, str, str], dict[str, str]] = {}
with STATS.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        rows[(row["name"], row["metric"], row["population"])] = row


def stat(name: str, metric: str, field: str = "mean", population: str = "raw") -> float:
    key = (name, metric, population)
    if key not in rows:
        fail(f"missing statistics row {key}")
        return float("nan")
    return float(rows[key][field])


def require_number(text: str, why: str) -> None:
    if text not in source:
        fail(f"manuscript does not contain expected {why}: {text}")

for name in ("cold", "density-1", "density-8", "density-64", "density-512", "density-2048", "dense-cheap"):
    require_number(f"{stat(name, 'direct_ms'):.3f} ms", f"{name} direct mean")
    require_number(f"{stat(name, 'doc_ms'):.3f} ms", f"{name} DOC mean")

p1 = stat("parallel-1", "elapsed_ms")
for n in range(1, 5):
    name = f"parallel-{n}"
    mean = stat(name, "elapsed_ms")
    lo = stat(name, "elapsed_ms", "ci95_low")
    hi = stat(name, "elapsed_ms", "ci95_high")
    require_number(f"{mean:.3f} ms ({lo:.3f}--{hi:.3f})", f"{name} mean/CI")
    require_number(f"{p1 / mean:.3f}$times$", f"{name} speedup")

for changed in (1, 64, 1024):
    name = f"financial-{changed}"
    require_number(f"{stat(name, 'direct_ms'):.3f} ms", f"{name} full mean")
    digits = 5 if changed == 1 else (4 if changed == 64 else 3)
    require_number(f"{stat(name, 'cached_ms'):.{digits}f} ms", f"{name} cached mean")
    require_number(f"{stat(name, 'doc_ms'):.3f} ms", f"{name} DOC mean")

bitonic = ["bitonic-1", "bitonic-8", "bitonic-64", "bitonic-256", "bitonic-512"]
direct = [stat(x, "direct_update_ms") for x in bitonic]
doc = [stat(x, "doc_update_ms") for x in bitonic]
ratios = [q / d for q, d in zip(doc, direct)]
require_number(f"{min(doc):.2f} to {max(doc):.2f} ms", "bitonic DOC range")
require_number(f"{min(direct):.4f} to {max(direct):.4f} ms", "bitonic direct range")
require_number(f"{min(ratios):.0f} times", "bitonic minimum overhead")
require_number(f"{max(ratios):.0f} times", "bitonic maximum overhead")

for stale in ("Intel(R) Xeon", "Section 9.2", "142.589", "3.847"):
    if stale in source:
        fail(f"stale pre-revision text remains: {stale}")

if errors:
    print("MANUSCRIPT CHECK: FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("MANUSCRIPT CHECK: PASS")
print(f"- {len(labels)} unique Typst labels")
print(f"- {len(citations)} bibliography citations resolve with no unused entry")
print(f"- {len(visual_labels)} visual figures share the native Typst figure counter")
print("- displayed benchmark statistics agree with the retained revision campaign")
print("- reviewer-targeted notation, assumptions, compatibility, and performance boundaries are present")
