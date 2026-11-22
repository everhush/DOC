"""Synthetic end-to-end evidence fixtures; never hardware validation."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "evidence", Path(__file__).with_name("verify-local-gpu-evidence.py"))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

class EvidenceIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for directory in ("parity", "rust", "goose/goose-sdl3"):
            (self.root / directory).mkdir(parents=True)
        with (self.root / "parity/native-gpu-equivalence.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(("operation", "lanes", "epoch", "equal_or_true_count"))
            for mode in evidence.MODES:
                for width in evidence.WIDTHS:
                    for epoch in (0, 1):
                        writer.writerow((mode, width, epoch, width // 2 + epoch))
                    (self.root / f"rust/rust-{mode}-{width}.log").write_text(
                        "DOC_SIGNED_WEBGPU_ADAPTER: AMD Radeon 860M Graphics (RADV KRACKAN1) type=IntegratedGpu backend=Vulkan\n"
                        + "".join(f"DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch={epoch} lanes={width} equals={width // 2 + epoch}\nDOC_SIGNED_WEBGPU_HOST_MS: epoch={epoch} elapsed_ms={epoch + 1}.125\n" for epoch in (0, 1)))
                    (self.root / f"goose/goose-sdl3/sdl3-{mode}-{width}.log").write_text(
                        "DOC_GOOSE_SDL3_DEVICE: vulkan\n"
                        + "".join(f"DOC_GOOSE_SDL3_GPU_PASS: op={mode} epoch={epoch} lanes={width} count={width // 2 + epoch} backend=vulkan\n" for epoch in (0, 1)))
        (self.root / "parity/native-gpu-equivalence.log").write_text(
            "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes\n")
        (self.root / "vulkan-adapter.log").write_text(
            "GPU0:\n"
            "\tvendorID           = 0x1002\n"
            "\tdeviceID           = 0x1114\n"
            "\tdeviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
            "\tdeviceName         = AMD Radeon 860M Graphics (RADV KRACKAN1)\n")

    def test_inventory_identity_cannot_be_borrowed_from_cpu(self):
        path = self.root / "vulkan-adapter.log"
        path.write_text(
            "GPU0:\n\tdeviceType         = PHYSICAL_DEVICE_TYPE_CPU\n"
            "\tdeviceName         = AMD Radeon 860M Graphics (RADV KRACKAN1)\n"
            "\tvendorID           = 0x1002\n\tdeviceID           = 0x1114\n"
            "GPU1:\n\tdeviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
            "\tdeviceName         = llvmpipe\n"
            "\tvendorID           = 0x10005\n\tdeviceID           = 0x0000\n")
        with self.assertRaisesRegex(ValueError, "identity, type and PCI IDs"):
            evidence.main(self.root)

    def test_inventory_wrong_pci_device_rejected(self):
        path = self.root / "vulkan-adapter.log"
        path.write_text(path.read_text().replace("0x1114", "0x9999"))
        with self.assertRaisesRegex(ValueError, "identity, type and PCI IDs"):
            evidence.main(self.root)

    def test_duplicate_vendor_identity_in_one_stanza_rejected(self):
        path = self.root / "vulkan-adapter.log"
        path.write_text(path.read_text() + "\tvendorID = 0x10005\n")
        with self.assertRaisesRegex(ValueError, "identity, type and PCI IDs"):
            evidence.main(self.root)

    def test_duplicate_device_type_in_one_stanza_rejected(self):
        path = self.root / "vulkan-adapter.log"
        path.write_text(path.read_text() +
                        "\tdeviceType = PHYSICAL_DEVICE_TYPE_CPU\n")
        with self.assertRaisesRegex(ValueError, "identity, type and PCI IDs"):
            evidence.main(self.root)

    def test_missing_rust_host_timing_rejected(self):
        path = self.root / "rust/rust-eq-1.log"
        path.write_text("\n".join(line for line in path.read_text().splitlines()
                                  if "DOC_SIGNED_WEBGPU_HOST_MS: epoch=1" not in line) + "\n")
        with self.assertRaisesRegex(ValueError, "missing host timings"):
            evidence.main(self.root)

    def test_nonfinite_rust_host_timing_rejected(self):
        path = self.root / "rust/rust-lt-63.log"
        path.write_text(path.read_text().replace("elapsed_ms=1.125", "elapsed_ms=nan"))
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            evidence.main(self.root)

    def test_duplicate_rust_host_timing_rejected(self):
        path = self.root / "rust/rust-le-64.log"
        path.write_text(path.read_text() + "DOC_SIGNED_WEBGPU_HOST_MS: epoch=0 elapsed_ms=3.0\n")
        with self.assertRaisesRegex(ValueError, "duplicate host timing"):
            evidence.main(self.root)

    def test_negative_rust_host_timing_rejected(self):
        path = self.root / "rust/rust-eq-65.log"
        path.write_text(path.read_text().replace("elapsed_ms=2.125", "elapsed_ms=-0.5"))
        with self.assertRaisesRegex(ValueError, "negative"):
            evidence.main(self.root)

    def test_complete_fixture(self):
        self.assertEqual(evidence.main(self.root), 0)

    def test_corrupted_csv_row(self):
        path = self.root / "parity/native-gpu-equivalence.csv"
        path.write_text(path.read_text().replace("eq,1,0,0", "eq,1,0,1", 1))
        with self.assertRaises(ValueError):
            evidence.main(self.root)

    def test_extra_csv_column_rejected(self):
        path = self.root / "parity/native-gpu-equivalence.csv"
        path.write_text(path.read_text().replace("eq,1,0,0", "eq,1,0,0,unexpected", 1))
        with self.assertRaises(ValueError):
            evidence.main(self.root)

    def test_missing_csv_column_rejected(self):
        path = self.root / "parity/native-gpu-equivalence.csv"
        path.write_text(path.read_text().replace("eq,1,0,0", "eq,1,0", 1))
        with self.assertRaises(ValueError):
            evidence.main(self.root)

    def test_non_integer_csv_rejected(self):
        path = self.root / "parity/native-gpu-equivalence.csv"
        path.write_text(path.read_text().replace("eq,1,0,0", "eq,1,0,NaN", 1))
        with self.assertRaises(ValueError):
            evidence.main(self.root)

    def test_rust_adapter_not_in_inventory_rejected(self):
        path = self.root / "rust/rust-eq-1.log"
        path.write_text(path.read_text().replace(
            "AMD Radeon 860M Graphics (RADV KRACKAN1)", "Other Physical GPU"))
        with self.assertRaisesRegex(ValueError, "adapter differs"):
            evidence.main(self.root)

    def test_rust_adapter_inconsistent_across_episodes_rejected(self):
        path = self.root / "rust/rust-lt-65.log"
        path.write_text(path.read_text().replace(
            "AMD Radeon 860M Graphics (RADV KRACKAN1)", "Other Physical GPU"))
        with self.assertRaisesRegex(ValueError, "adapter differs"):
            evidence.main(self.root)

    def test_missing_log(self):
        (self.root / "goose/goose-sdl3/sdl3-lt-65.log").unlink()
        with self.assertRaises(OSError):
            evidence.main(self.root)

    def test_duplicate_csv_row(self):
        path = self.root / "parity/native-gpu-equivalence.csv"
        with path.open("a") as f:
            f.write("le,1024,1,513\n")
        with self.assertRaises(ValueError):
            evidence.main(self.root)

    def test_mismatched_goose_episode(self):
        path = self.root / "goose/goose-sdl3/sdl3-le-257.log"
        path.write_text(path.read_text().replace("count=129", "count=128"))
        with self.assertRaises(ValueError):
            evidence.main(self.root)

if __name__ == "__main__":
    unittest.main()
