"""WebGPU-only physical device evidence tests: no platform graphics API."""
import ast
from pathlib import Path
import re
import unittest

template=Path(__file__).with_name("doc_kaggle_gpu.py").read_text()
tree=ast.parse(template.replace("__DOC_KAGGLE_RUN_SPEC__","{}"))
candidate=next(node for node in tree.body
    if isinstance(node,ast.FunctionDef)
    and node.name=="selected_physical_webgpu_adapter")
namespace={"re":re}
exec(compile(ast.Module(body=[candidate],type_ignores=[]),
             "<webgpu-device-classification>","exec"),namespace)
check=namespace["selected_physical_webgpu_adapter"]

def record(name="PhysicalAdapter",kind="DiscreteGpu",vendor=4318,device=1):
    return (f"DOC_GPU_SELECTED_DEVICE: name={name} type={kind} "
            f"vendor={vendor} device={device}\n")

class WebGpuDeviceAdmission(unittest.TestCase):
    def test_discrete_and_integrated_adapters_are_admitted(self):
        self.assertEqual(check(record()),("PhysicalAdapter","DiscreteGpu","4318","1"))
        self.assertEqual(check(record("Integrated","IntegratedGpu",32902,2)),
                         ("Integrated","IntegratedGpu","32902","2"))
    def test_cpu_or_unknown_device_cannot_certify_hardware(self):
        for kind in ("Cpu","Other","VirtualGpu",""):
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):
                check(record(kind=kind))
        with self.assertRaises(RuntimeError):
            check("")
    def test_reject_software_marker_even_with_physical_device_record(self):
        with self.assertRaises(RuntimeError):
            check(record()+"DOC_GPU_SOFTWARE_TEST_ONLY: test adapter\n")
    def test_reject_conflicting_multiple_device_records(self):
        with self.assertRaises(RuntimeError):
            check(record()+record("AnotherGpu","IntegratedGpu",32902,3))
    def test_reject_driver_vendor_or_request_only_claims(self):
        for candidate in (
            "vendor=4318 device=1 kind=DiscreteGpu",
            "GPU requested: NvidiaTeslaT4",
            "deviceName: physical GPU",
            "DOC_GPU_SELECTED_DEVICE: name=Device type=Cpu vendor=4318 device=1",
        ):
            with self.subTest(candidate=candidate),self.assertRaises(RuntimeError):
                check(candidate)
    def test_no_native_api_probe_is_used(self):
        source=Path(__file__).with_name("doc_kaggle_gpu.py").read_text()
        for forbidden in ("vulkaninfo","VK_DRIVER_FILES","VK_ICD_FILENAMES",
                          "WGPU_BACKEND","all_vulkan_adapters_are_physical_nvidia"):
            self.assertNotIn(forbidden,source)

if __name__=="__main__":
    unittest.main()
