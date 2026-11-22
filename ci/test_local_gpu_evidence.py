"""Adversarial offline tests; synthetic logs are not physical GPU evidence."""
import importlib.util
import unittest
from pathlib import Path

source = Path(__file__).with_name("verify-local-gpu-evidence.py")
spec = importlib.util.spec_from_file_location("gpu_evidence", source)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

RUST = ("DOC_SIGNED_WEBGPU_ADAPTER: name=AMD Radeon 860M Graphics type=IntegratedGpu backend=Vulkan\n"
        "DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=0 lanes=65 equals=32\n"
        "DOC_SIGNED_WEBGPU_COMPUTE_PASS: epoch=1 lanes=65 equals=31\n")
GOOSE = ("DOC_GOOSE_SDL3_DEVICE: vulkan\n"
         "DOC_GOOSE_SDL3_GPU_PASS: op=lt epoch=0 lanes=65 count=32 backend=vulkan\n"
         "DOC_GOOSE_SDL3_GPU_PASS: op=lt epoch=1 lanes=65 count=31 backend=vulkan\n")

class LogParserAdversarialTests(unittest.TestCase):
    def test_valid_pair(self):
        self.assertEqual(verifier.parse_rust(RUST, "lt", 65), {0: 32, 1: 31})
        self.assertEqual(verifier.parse_goose(GOOSE, "lt", 65), {0: 32, 1: 31})

    def test_rust_software_adapter_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_rust(RUST.replace("IntegratedGpu", "Cpu"), "lt", 65)

    def test_rust_llvmpipe_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_rust(RUST.replace("AMD Radeon 860M Graphics", "llvmpipe"), "lt", 65)

    def test_rust_duplicate_episode_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_rust(RUST + RUST.splitlines()[-1] + "\n", "lt", 65)

    def test_rust_missing_episode_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_rust("\n".join(RUST.splitlines()[:-1]), "lt", 65)

    def test_goose_wrong_operation_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_goose(GOOSE.replace("op=lt", "op=le"), "lt", 65)

    def test_goose_duplicate_episode_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_goose(GOOSE + GOOSE.splitlines()[-1] + "\n", "lt", 65)

    def test_goose_wrong_width_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_goose(GOOSE.replace("lanes=65", "lanes=64"), "lt", 65)

    def test_goose_no_backend_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_goose(GOOSE.replace("DOC_GOOSE_SDL3_DEVICE: vulkan\n", ""), "lt", 65)

    def test_goose_duplicate_backend_rejected(self):
        with self.assertRaises(ValueError):
            verifier.parse_goose("DOC_GOOSE_SDL3_DEVICE: vulkan\n" + GOOSE, "lt", 65)

if __name__ == "__main__":
    unittest.main()
