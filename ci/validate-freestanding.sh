#!/usr/bin/env bash
# Actual bare-metal guest, not a hosted no-libc Linux process.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
mkdir -p validation-logs
logs=$root/validation-logs
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
compiler="$root/runtime-rust/target/release/doc-compile"
test -x "$compiler"
"$compiler" runtime-rust/examples/native_boot.doc --object boot \
  --allow-native-region scratch --allow-native-import x86_out8 \
  --emit-c "$scratch/boot.c" --emit-header "$scratch/boot.h" \
  --emit-ir "$scratch/boot.ir" --out "$scratch/host.o"
flags=(-m64 -std=c11 -O2 -ffreestanding -fno-builtin -fno-pie -fno-stack-protector -mno-red-zone -mno-sse -mno-mmx -fno-asynchronous-unwind-tables)
cc "${flags[@]}" -c "$scratch/boot.c" -o "$scratch/boot.o"
cc "${flags[@]}" -I"$scratch" -c ci/freestanding/verify.c -o "$scratch/verify.o"
cc -m64 -c ci/freestanding/entry.S -o "$scratch/entry.o"
ld -m elf_x86_64 -nostdlib -T ci/freestanding/layout.ld \
  "$scratch/entry.o" "$scratch/boot.o" "$scratch/verify.o" -o "$scratch/kernel64.elf"
test -z "$(nm -u "$scratch/kernel64.elf")"
readelf -h -l -d "$scratch/kernel64.elf" > "$logs/freestanding-elf.txt"
grep -F 'Advanced Micro Devices X86-64' "$logs/freestanding-elf.txt"
! grep -E 'INTERP|\(NEEDED\)' "$logs/freestanding-elf.txt"
# Multiboot loader consumes a 32-bit ELF container; the entry switches the
# processor to long mode before calling any generated 64-bit DOC code.
objcopy -O elf32-i386 "$scratch/kernel64.elf" "$scratch/kernel.elf"
cp "$scratch/boot.ir" "$scratch/boot.c" "$scratch/boot.h" "$logs/"
readelf -h -l "$scratch/kernel.elf" > "$logs/freestanding-loader.txt"
qemu-system-x86_64 --version > "$logs/freestanding-qemu-version.txt"
# isa-debug-exit requests guest shutdown with the encoded result status.
# Do not use -no-shutdown: that pauses the VM instead of returning the status.
set +e
timeout 30s qemu-system-x86_64 -machine pc -cpu qemu64 -m 64M \
  -display none -serial none -monitor none -no-reboot \
  -d int,cpu_reset,guest_errors -D "$logs/freestanding-qemu-trace.txt" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -debugcon "file:$logs/freestanding-device.txt" \
  -global isa-debugcon.iobase=0xe9 -kernel "$scratch/kernel.elf" \
  > "$logs/freestanding-qemu.stdout" 2> "$logs/freestanding-qemu.stderr"
status=$?
set -e
if [[ "$status" -ne 33 ]]; then
  echo "Unexpected QEMU exit status: $status" >&2
  cat "$logs/freestanding-qemu.stderr" >&2
  tail -n 100 "$logs/freestanding-qemu-trace.txt" >&2
  od -An -tx1 "$logs/freestanding-device.txt" >&2
  exit 1
fi
printf AB > "$scratch/expected"
cmp "$scratch/expected" "$logs/freestanding-device.txt"
echo 'DOC_FREESTANDING_X86_64_BOOT_MEMORY_DEVICE_PASS: bytes=AB negative_bounds=pass'
