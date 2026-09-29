#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

BUILD_DIR=${BUILD_DIR:-build/release}
TYPST=${TYPST:-typst}
GENERATOR=()
if command -v ninja >/dev/null 2>&1; then
  GENERATOR=(-G Ninja)
fi

cmake -S runtime -B "$BUILD_DIR" "${GENERATOR[@]}" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR"
ctest --test-dir "$BUILD_DIR" --output-on-failure
python3 -m compileall -q runtime/formal runtime/scripts verification
python3 verification/check_manuscript.py
"$TYPST" compile paper/dependency-oriented-computation.typ paper/dependency-oriented-computation.pdf
verification/check_pdf.sh paper/dependency-oriented-computation.pdf
printf 'REVISION VERIFICATION: PASS\n'
