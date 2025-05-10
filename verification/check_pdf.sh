#!/usr/bin/env bash
set -euo pipefail

PDF=${1:-paper/dependency-oriented-computation.pdf}
if [[ ! -s "$PDF" ]]; then
  echo "PDF preflight failed: missing or empty $PDF" >&2
  exit 1
fi

if command -v qpdf >/dev/null 2>&1; then
  qpdf --check "$PDF"
elif [[ "${REQUIRE_QPDF:-0}" == "1" ]]; then
  echo "PDF preflight failed: qpdf is required" >&2
  exit 1
fi

if ! command -v pdfinfo >/dev/null 2>&1; then
  echo "PDF preflight failed: pdfinfo is required" >&2
  exit 1
fi
INFO=$(pdfinfo "$PDF")
PAGES=$(printf '%s\n' "$INFO" | awk '/^Pages:/ {print $2}')
SIZE=$(printf '%s\n' "$INFO" | awk -F: '/^Page size:/ {sub(/^[[:space:]]+/,"",$2); print $2}')
[[ "$PAGES" =~ ^[0-9]+$ ]] || { echo "PDF preflight failed: invalid page count" >&2; exit 1; }
(( PAGES >= 20 )) || { echo "PDF preflight failed: unexpectedly short manuscript ($PAGES pages)" >&2; exit 1; }
printf '%s\n' "$SIZE" | grep -qi 'A4' || {
  echo "PDF preflight failed: expected A4 page size, got: $SIZE" >&2
  exit 1
}

if command -v pdffonts >/dev/null 2>&1; then
  FONTS=$(pdffonts "$PDF" | tail -n +3 || true)
  if [[ -z "$FONTS" ]]; then
    echo "PDF preflight failed: no fonts detected" >&2
    exit 1
  fi
  # The final five whitespace fields are: emb, sub, uni, object, ID.
  # Parsing from the right is robust to font-type names such as
  # "CID Type 0C" and "CID TrueType", which occupy different field counts.
  if printf '%s\n' "$FONTS" | awk 'NF >= 6 && $(NF-4) != "yes" {bad=1} END {exit bad ? 0 : 1}'; then
    echo "PDF preflight failed: one or more fonts are not embedded" >&2
    exit 1
  fi
fi

# Paper graphics are required to remain native Typst vectors. A raster page render
# is a CI inspection artifact; the PDF itself must not embed image XObjects.
if command -v pdfimages >/dev/null 2>&1; then
  if pdfimages -list "$PDF" 2>/dev/null | tail -n +3 | grep -Eq '^[[:space:]]*[0-9]+'; then
    echo "PDF preflight failed: embedded image XObjects detected" >&2
    exit 1
  fi
fi

printf 'PDF PREFLIGHT: PASS\n'
printf -- '- pages: %s\n' "$PAGES"
printf -- '- page size: %s\n' "$SIZE"
printf -- '- no embedded raster/image XObjects detected\n'
