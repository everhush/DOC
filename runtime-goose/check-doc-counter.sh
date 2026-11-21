#!/usr/bin/env bash
set -euo pipefail
goose=$1
rust=$2
logs=$3
mkdir -p "$logs"
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
"$goose" check runtime-goose/doc_counter.goose > "$logs/counter-goose-check.log" 2>&1
"$goose" build runtime-goose/doc_counter.goose --offline -o "$tmp/doc-counter-goose" \
  > "$logs/counter-goose-build.log" 2>&1
python3 runtime-goose/check-counter-oracle.py "$rust" "$tmp/doc-counter-goose" "$logs"
