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
                        + "".join(f"DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch={epoch} lanes={width} equals={width // 2 + epoch}\n" for epoch in (0, 1)))
                    (self.root / f"goose/goose-sdl3/sdl3-{mode}-{width}.log").write_text(
                        "DOC_GOOSE_SDL3_DEVICE: vulkan\n"
                        + "".join(f"DOC_GOOSE_SDL3_GPU_PASS: op={mode} epoch={epoch} lanes={width} count={width // 2 + epoch} backend=vulkan\n" for epoch in (0, 1)))
        (self.root / "parity/native-gpu-equivalence.log").write_text(
            "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes\n")
        (self.root / "vulkan-adapter.log").write_text(
            "deviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU\n"
            "deviceName         = AMD Radeon 860M Graphics (RADV KRACKAN1)\n")

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
