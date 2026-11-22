"""Offline NVIDIA Vulkan adapter certification tests; never uses a GPU."""
import ast
from pathlib import Path
import re
import unittest

template = Path(__file__).with_name("doc_kaggle_gpu.py").read_text()
tree = ast.parse(template.replace("__DOC_KAGGLE_RUN_SPEC__", "{}"))
fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
          and node.name == "all_vulkan_adapters_are_physical_nvidia")
namespace = {"re": re}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gpu-device-check>", "exec"),
     namespace)
valid = namespace["all_vulkan_adapters_are_physical_nvidia"]

def device(index, vendor, kind):
    return ("GPU{}:\n".format(index) +
            "  vendorID = {}\n".format(vendor) +
            "  deviceType = {}\n".format(kind))

class PhysicalNvidiaVulkanTest(unittest.TestCase):
    def test_real_nvidia_discrete(self):
        self.assertTrue(valid("Vulkan Instance Version: 1.3\n" +
            device(0, "0x10de", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")))
    def test_two_nvidia_cards(self):
        self.assertTrue(valid(device(0, "0x10de", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU") +
                              device(1, "0x10DE", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")))
    def test_missing_device_or_vendor(self):
        self.assertFalse(valid(""))
        self.assertFalse(valid(device(0, "0x10005", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")))
        self.assertFalse(valid("GPU0:\n  deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU\n"))
    def test_software_only_or_mixed_software_adapter(self):
        nvidia = device(0, "0x10de", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")
        software = device(1, "0x10005", "PHYSICAL_DEVICE_TYPE_CPU")
        self.assertFalse(valid(software))
        self.assertFalse(valid(nvidia + software))
    def test_disallow_spoofed_cross_device_identity(self):
        amd = device(0, "0x1002", "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU")
        nvidia_software = device(1, "0x10de", "PHYSICAL_DEVICE_TYPE_CPU")
        self.assertFalse(valid(amd + nvidia_software))

if __name__ == "__main__":
    unittest.main()
