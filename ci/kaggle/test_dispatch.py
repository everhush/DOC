"""Offline tests: no GitHub/Kaggle tokens and NO accelerator usage."""
import datetime as dt
import importlib.util
import json
import tempfile
import tarfile
from pathlib import Path
import unittest

path = Path(__file__).with_name("dispatch.py")
spec = importlib.util.spec_from_file_location("doc_kaggle_dispatch", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class KaggleDispatchPolicy(unittest.TestCase):
    def test_count_actual_notebook_pushes_not_cpu_preflight(self):
        ts = "2026-11-21T21:43:52.6962854Z "
        first = ts + "DOC_KAGGLE_DISPATCH: notebook=person/doc-gpu-123-1 sha=" + "a"*40 + " minutes=30"
        blocked = ts + "DOC_KAGGLE_DISPATCH_FAILURE: RuntimeError: Kaggle private binary dataset status unavailable"
        skipped = ts + "DOC_KAGGLE_QUOTA_SKIP: maximum 2 attempts"
        sha="a"*40
        self.assertTrue(module.duplicate_gpu_submission(first,sha,"NvidiaTeslaT4"))
        self.assertFalse(module.duplicate_gpu_submission(blocked,sha,"NvidiaTeslaT4"))
        self.assertFalse(module.duplicate_gpu_submission(skipped,sha,"NvidiaTeslaT4"))
        self.assertFalse(module.duplicate_gpu_submission("",sha,"NvidiaTeslaT4"))
        tagged=first+" accelerator=NvidiaTeslaT4"
        self.assertTrue(module.duplicate_gpu_submission(tagged,sha,"NvidiaTeslaT4"))
        self.assertFalse(module.duplicate_gpu_submission(tagged,sha,"NvidiaL4"))
        self.assertFalse(module.duplicate_gpu_submission(
            tagged.replace(sha,"b"*40),sha,"NvidiaTeslaT4"))
        self.assertFalse(hasattr(module,"MAX_WEEKLY_RUNS"))
        self.assertEqual(module.MIN_QUOTA_RESERVE_HOURS,0.0)

    def test_live_quota_units_and_gpu_tpu_separation(self):
        q = [{"resource":"GPU","remaining":"25.50h","total":"30h"},
             {"resource":"TPU","remaining":"100h"}]
        self.assertEqual(module.gpu_remaining_hours(json.dumps(q)),25.5)
        self.assertEqual(module.gpu_remaining_hours('[{"resource":"GPU","remaining":1.25}]'),1.25)
    def test_unknown_quota_must_block_submission(self):
        for value in ("{}", "[]", '[{"resource":"TPU","remaining":"5h"}]',
                      '[{"resource":"GPU","remaining":"unknown"}]',
                      '[{"resource":"GPU","remaining":"5m"}]',
                      '[{"resource":"GPU","remaining":-1}]',
                      '[{"resource":"GPU","remaining":true}]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.gpu_remaining_hours(value)
    def test_exact_remote_status(self):
        self.assertEqual(module.status_from_cli("KernelWorkerStatus.COMPLETE"),"COMPLETE")
        self.assertEqual(module.status_from_cli("KernelWorkerStatus.ERROR"),"FAILED")
        self.assertEqual(module.status_from_cli("KernelWorkerStatus.RUNNING"),"RUNNING")
        self.assertEqual(module.status_from_cli("INCOMPLETE"),"UNKNOWN")
        self.assertEqual(module.status_from_cli("unknown"),"UNKNOWN")
    def test_no_weekly_quota_cap_and_session_timeout(self):
        self.assertEqual(module.MIN_QUOTA_RESERVE_HOURS,0.0)
        self.assertEqual(module.DUPLICATE_LOOKBACK_DAYS,7)
        self.assertFalse(hasattr(module,"MAX_WEEKLY_RUNS"))
        self.assertEqual(module.MAX_SESSION_MINUTES,30)
    def test_private_legacy_json_and_raw_token(self):
        with tempfile.TemporaryDirectory() as temp:
            env,owner=module.auth_environment('{"username":"Tester","key":"FAKE"}',
                Path(temp)/"config","")
            self.assertEqual(owner,"tester")
            f=Path(env["KAGGLE_CONFIG_DIR"])/"kaggle.json"
            self.assertEqual(f.stat().st_mode & 0o777,0o600)
            self.assertEqual(json.loads(f.read_text())["key"],"FAKE")
        with tempfile.TemporaryDirectory() as temp:
            env,owner=module.auth_environment("FAKE_TOKEN",Path(temp),"tester")
            self.assertEqual(owner,"tester")
            self.assertEqual(env["KAGGLE_API_TOKEN"],"FAKE_TOKEN")
            self.assertFalse((Path(temp)/"kaggle.json").exists())
        with tempfile.TemporaryDirectory() as temp:
            from unittest.mock import patch
            from subprocess import CompletedProcess
            fake = CompletedProcess(["kaggle","config","view"],0,
                "- username: TestOwner\n", "")
            with patch.object(module.subprocess,"run",return_value=fake):
                env,owner=module.auth_environment("FAKE_TOKEN",Path(temp),"")
            self.assertEqual(owner,"testowner")
    def test_exact_sha_and_no_stale_parity(self):
        fields={"repo":"x0796666-ui/DOC","sha":"a"*40,"run_id":"123",
                "attempt":"1","minutes":30,"accelerator":"NvidiaTeslaT4"}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"kernel"
            name=module.prepare_kernel(folder,
                Path(__file__).with_name("doc_kaggle_gpu.py"),fields,"tester")
            self.assertEqual(name,"tester/doc-gpu-123-1")
            metadata=json.loads((folder/"kernel-metadata.json").read_text())
            self.assertEqual(metadata["title"],"doc-gpu-123-1")
            self.assertEqual(metadata["is_private"],"true")
            self.assertEqual(metadata["enable_gpu"],"true")
            self.assertEqual(metadata["enable_internet"],"true")
            compile((folder/"doc_kaggle_gpu.py").read_text(),"<notebook>","exec")
            out=Path(temp)/"remote"
            out.mkdir()
            with tarfile.open(out/"doc-kaggle-logs.tar.gz","w:gz") as archive:
                evidence={
                    "report/native-gpu-equivalence.log":
                        "DOC_RUST_WGPU_GOOSE_SDL3_PARITY_PASS: 42 observed GPU episodes",
                    "goose/goose-sdl3/doc-goose-sdl3-summary.log":
                        "DOC_GOOSE_SDL3_NATIVE_PARITY_PASS: 77 checks",
                    "physical-vulkan.log":"deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU",
                    "nvidia-smi.log":"GPU 0: Tesla T4",
                }
                for name,content in evidence.items():
                    path=Path(temp)/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(content)
                    archive.add(path,arcname=name)
            result={"sha":"b"*40,"run_id":"123","result":"pass",
                    "hardware":True,"backend":"vulkan",
                    "accelerator":"NvidiaTeslaT4","max_gpu_minutes":30,
                    "goose_sdl3_checks":77,"dual_backend_episodes":42}
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)
            result["sha"]="a"*40
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            self.assertEqual(module.verify_result(out,fields),result)
            (out/"doc-kaggle-logs.tar.gz").write_bytes(b"x")
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)

if __name__=="__main__":
    unittest.main()
