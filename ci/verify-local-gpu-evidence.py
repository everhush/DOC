#!/usr/bin/env python3
"""Verify committed local physical-host logs without pretending to re-run a GPU.

Checks all 42 paired observations against raw independent host logs and
the committed summary CSV. Rust identifies a physical Vulkan adapter; Goose
reports only the Vulkan backend, so its exact GPU selection remains OPEN.
"""
import csv
import re
import sys
from pathlib import Path

MODES = ("eq", "lt", "le")
WIDTHS = (1, 63, 64, 65, 129, 257, 1024)
EXPECTED = {(mode, lanes, epoch) for mode in MODES
            for lanes in WIDTHS for epoch in (0, 1)}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def parse_rust(content, mode, width, expected_adapter=None):
    lines = content.splitlines()
    adapter = [s for s in lines if s.startswith("DOC_SIGNED_WEBGPU_ADAPTER:")]
    require(len(adapter) == 1, f"Rust {mode}/{width}: no unique wgpu adapter")
    require(re.search(r"\btype=(IntegratedGpu|DiscreteGpu)\b", adapter[0]),
            f"Rust {mode}/{width}: not a physical GPU")
    if expected_adapter is not None:
        require(adapter[0].startswith("DOC_SIGNED_WEBGPU_ADAPTER: " + expected_adapter + " "),
                f"Rust {mode}/{width}: adapter differs from inventoried hardware")
    require("backend=Vulkan" in adapter[0],
            f"Rust {mode}/{width}: not Vulkan")
    require("llvmpipe" not in adapter[0].lower(),
            f"Rust {mode}/{width}: software Vulkan")
    result = {}
    pat = re.compile(
        r"^DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=([01]) lanes=(\d+) equals=(\d+)$")
    for line in lines:
        m = pat.fullmatch(line)
        if line.startswith("DOC_SIGNED_WEBGPU_COMPUTE_PASS:"):
            require(m is not None, f"Rust {mode}/{width}: malformed compute record")
            epoch, size, value = map(int, m.groups())
            require(size == width and epoch not in result,
                    f"Rust {mode}/{width}: invalid/duplicate episode")
            require(0 <= value <= width, f"Rust {mode}/{width}: impossible count")
            result[epoch] = value
    require(set(result) == {0, 1}, f"Rust {mode}/{width}: incomplete observations")
    return result

def parse_goose(content, mode, width):
    lines = content.splitlines()
    require(lines.count("DOC_GOOSE_SDL3_DEVICE: vulkan") == 1,
            f"Goose {mode}/{width}: Vulkan backend not identified")
    pat = re.compile(
        r"^DOC_GOOSE_SDL3_GPU_PASS: op=(eq|lt|le) epoch=([01]) "
        r"lanes=(\d+) count=(\d+) backend=vulkan$")
    result = {}
    for line in lines:
        m = pat.fullmatch(line)
        if line.startswith("DOC_GOOSE_SDL3_GPU_PASS:"):
            require(m is not None, f"Goose {mode}/{width}: malformed GPU record")
            operation, episode, size, value = m.groups()
            epoch = int(episode)
            require(operation == mode and int(size) == width and epoch not in result,
                    f"Goose {mode}/{width}: invalid/duplicate episode")
            require(0 <= int(value) <= width, f"Goose {mode}/{width}: impossible count")
            result[epoch] = int(value)
    require(set(result) == {0, 1}, f"Goose {mode}/{width}: incomplete observations")
    return result

def main(root):
    root = Path(root)
    table = root / "parity/native-gpu-equivalence.csv"
    with table.open(newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames ==
                ["operation", "lanes", "epoch", "equal_or_true_count"],
                "Unexpected parity CSV columns")
        rows = {}
        for record in reader:
            require(None not in record and all(record.get(c) is not None for c in reader.fieldnames),
                    "Malformed parity CSV column count")
            mode = record["operation"]
            try:
                width, epoch, value = (int(record[c]) for c in
                                        ("lanes", "epoch", "equal_or_true_count"))
            except (TypeError, ValueError) as exc:
                raise ValueError("Non-integer parity CSV field") from exc
            key = (mode, width, epoch)
            require(key in EXPECTED and key not in rows,
                    f"Unknown or duplicated CSV row: {key}")
            require(0 <= value <= width, f"Impossible result count: {key}")
            rows[key] = value
    require(set(rows) == EXPECTED,
            f"Parity CSV missing/extra {len(EXPECTED) - len(rows)} rows")
    physical = (root / "vulkan-adapter.log").read_text(errors="replace")
    expected_adapter = "AMD Radeon 860M Graphics (RADV KRACKAN1)"
    # vulkaninfo can list software and hardware adapters together. All identity
    # fields must belong to the SAME GPU stanza, not separate devices.
    devices = re.split(r"(?m)^GPU\d+:\s*$", physical)[1:]
    # A single device stanza must have exactly one of each identity field.
    # Duplicate contradictory keys must never manufacture a matching adapter.
    def physical_amd(device):
        fields = {}
        for key in ("deviceName", "deviceType", "vendorID", "deviceID"):
            matches = re.findall(
                r"(?m)^\s*" + key + r"\s*=\s*(.*?)\s*$", device)
            if len(matches) != 1:
                return False
            fields[key] = matches[0]
        return (fields["deviceName"] == expected_adapter
                and fields["deviceType"] in (
                    "PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU",
                    "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")
                and fields["vendorID"] == "0x1002"
                and fields["deviceID"] == "0x1114")

    require(any(physical_amd(device) for device in devices),
        "Inventoried AMD GPU identity, type and PCI IDs do not match one physical device")
    for mode in MODES:
        for width in WIDTHS:
            rust_file = root / f"rust/rust-{mode}-{width}.log"
            goose_file = root / f"goose/goose-sdl3/sdl3-{mode}-{width}.log"
            rust = parse_rust(rust_file.read_text(), mode, width, expected_adapter)
            goose = parse_goose(goose_file.read_text(), mode, width)
            for epoch in (0, 1):
                key = (mode, width, epoch)
                require(rust[epoch] == goose[epoch] == rows[key],
                        f"Rust/Goose/CSV mismatch for {key}")
    marker = (root / "parity/native-gpu-equivalence.log").read_text().strip()
    require(marker ==
            "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes",
            "Independent parity tool summary does not match")
    print("DOC_COMMITTED_LOCAL_GPU_LOG_PARITY_PASS: 42 raw episodes")
    print("DOC_GOOSE_PHYSICAL_DEVICE_IDENTITY_PENDING: SDL3 logs identify only Vulkan backend")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else "local-evidence"))
    except (OSError, ValueError) as exc:
        print(f"DOC_COMMITTED_GPU_EVIDENCE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
