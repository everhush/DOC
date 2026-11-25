#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
mkdir -p validation-logs/aot
out="$root/validation-logs/aot"
rm -f "$out/repair.c" "$out/repair.ir" "$out/repair-native"
compiler=runtime-rust/target/release/doc-compile
reference=runtime-rust/target/release/doc
source=runtime-rust/examples/repair.doc
cc --version > "$out/cc-version.txt"
# Record actual process costs, not inferred optimizer speed.
/usr/bin/time -f 'build_elapsed_s=%e build_peak_rss_kib=%M' -o "$out/build-time.txt" \
  "$compiler" "$source" --emit-c "$out/repair.c" --emit-ir "$out/repair.ir" --out "$out/repair-native" | tee "$out/compile.txt"
file "$out/repair-native" | tee "$out/file.txt"
readelf -h "$out/repair-native" > "$out/elf-header.txt"
ldd "$out/repair-native" | tee "$out/linkage.txt"
! grep -E 'libdoc|libRust|libgoose' "$out/linkage.txt"
"$reference" "$source" a=4 b=1 > "$out/reference.txt"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT
cp "$out/repair-native" "$scratch/native"
(cd "$scratch"; env -i /usr/bin/time -f 'native_elapsed_s=%e native_peak_rss_kib=%M' -o "$out/run-time.txt" ./native a=4 b=1) > "$out/native.txt"
diff -u "$out/reference.txt" "$out/native.txt"
grep -Fx 'chosen: 10' "$out/native.txt"
echo DOC_AOT_STAGE0_NATIVE_SMOKE_PASS

# Exercise the real generated C, including UTF-8, big naturals and owned
# buffers, under native sanitizers. No Rust interpreter linked into target.
cat > "$out/memory.doc" <<'DOC'
source n: nat = 9999999999999999999999999999999999999999
source xs: ints = [1,2]
source label: text = "世界"
derive next: nat (n) = add(n,nat(1))
derive result: nat (n) = mul(n,nat(99))
derive more: ints (xs) = append(xs,1)
derive joined: text (label) = concat(label,text("🙂"))
DOC
rm -f "$out/memory.c" "$out/memory-native" "$out/memory-sanitized"
"$compiler" "$out/memory.doc" --emit-c "$out/memory.c" --out "$out/memory-native"
cc -std=c11 -O1 -g -fno-omit-frame-pointer -fno-pie -no-pie \
  -fsanitize=address,undefined -pthread "$out/memory.c" -o "$out/memory-sanitized"
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
 DOC_AOT_MEMORY_TRACE=1 DOC_WORKERS=1 "$out/memory-sanitized" \
 --through=1000 n=next > "$out/memory-sanitized.txt" 2> "$out/memory-sanitized.log"
grep -F 'DOC_AOT_MEMORY: phase=exit live=0 ' "$out/memory-sanitized.log"
DOC_AOT_MEMORY_TRACE=1 DOC_WORKERS=1 "$out/memory-native" --through=1000 n=next \
 > "$out/memory-native.txt" 2> "$out/memory-native.log"
diff -u "$out/memory-native.txt" "$out/memory-sanitized.txt"
echo DOC_AOT_NATIVE_SANITIZER_RECLAMATION_PASS
