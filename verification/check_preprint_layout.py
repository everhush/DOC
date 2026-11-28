#!/usr/bin/env python3
"""Fail closed on structural PDF preflight; visual inspection is a separate gate."""
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/1999/xhtml}"
ROOT = Path(sys.argv[1])
for name in ("preprint-model",):
    pdf = ROOT / (name + ".pdf")
    if not pdf.is_file() or not pdf.stat().st_size:
        raise ValueError(f"{name}: missing PDF")
    info = Path(str(pdf) + ".info").read_text()
    count = int(re.search(r"^Pages:\s+(\d+)", info, re.M).group(1))
    if count < 1:
        raise ValueError(f"{name}: no pages")
    fonts = Path(str(pdf) + ".fonts").read_text().splitlines()[2:]
    fonts = [row.split() for row in fonts if row.strip()]
    if not fonts or any(len(row) < 6 or row[-5] != "yes" for row in fonts):
        raise ValueError(f"{name}: font embedding check failed")
    if "\ufffd" in Path(str(pdf) + ".txt").read_text():
        raise ValueError(f"{name}: replacement glyph in extracted text")
    pages = list(ET.parse(str(pdf) + ".bbox.html").getroot().iter(NS + "page"))
    if len(pages) != count:
        raise ValueError(f"{name}: page inventory mismatch")
    images = list((ROOT / (name + "-pages")).glob("page-*.png"))
    if len(images) != count or any(not f.stat().st_size for f in images):
        raise ValueError(f"{name}: missing page render")
    words_total = 0
    min_margin = float("inf")
    for i, page in enumerate(pages, 1):
        w, h = float(page.attrib["width"]), float(page.attrib["height"])
        if abs(w - 595.276) > 1 or abs(h - 841.890) > 1:
            raise ValueError(f"{name}: page {i} not A4")
        words = list(page.iter(NS + "word"))
        if not words:
            raise ValueError(f"{name}: empty extracted page {i}")
        for word in words:
            x0, y0, x1, y1 = (float(word.attrib[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
            if (not all(math.isfinite(v) for v in (x0,y0,x1,y1))
                or x0 < -1 or y0 < -1 or x1 > w+1 or y1 > h+1 or x1 < x0 or y1 < y0
                or "\ufffd" in (word.text or "")):
                raise ValueError(f"{name}: page {i} invalid text geometry: {word.attrib}")
            min_margin = min(min_margin, x0, y0, w-x1, h-y1)
            words_total += 1
    print(f"{name}: PASS; {count} A4 pages; {words_total} words; {len(fonts)} embedded font entries; minimum text-to-page-edge margin {min_margin:.2f} pt")
print("Automated preflight only: inspect all rendered pages for overlap, overflow, legibility, figures, equations, captions, and consistency; record the exact reviewed PDF digests in issue #14.")
