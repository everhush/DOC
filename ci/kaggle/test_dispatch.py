"""Offline tests: no GitHub/Kaggle tokens and NO accelerator usage."""
import datetime as dt
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest

path = Path(__file__).with_name("dispatch.py")
spec = importlib.util.spec_from_file_location("doc_kaggle_dispatch", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class KaggleDispatchPolicy(unittest.TestCase):
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
    def test_weekly_limit_counts_cancelled_and_failed(self):
        now=dt.datetime(2026,11,22,tzinfo=dt.timezone.utc)
        data={"workflow_runs":[
            {"id":1,"created_at":"2026-11-22T00:00:00Z"},
            {"id":2,"created_at":"2026-11-21T10:00:00Z","conclusion":"cancelled"},
            {"id":3,"created_at":"2026-11-16T10:00:00Z","conclusion":"failure"},
            {"id":4,"created_at":"2026-11-01T00:00:00Z"}]}
        self.assertEqual(module.github_recent_attempts(data,1,now),2)
        self.assertEqual(module.MAX_WEEKLY_RUNS,2)
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
            with self.assertRaises(ValueError):
                module.auth_environment("FAKE_TOKEN",Path(temp),"")
    def test_exact_sha_and_no_stale_parity(self):
        fields={"repo":"x0796666-ui/DOC","sha":"a"*40,"run_id":"123",
                "attempt":"1","minutes":30,"accelerator":"NvidiaTeslaT4"}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"kernel"
            name=module.prepare_kernel(folder,
                Path(__file__).with_name("doc_kaggle_gpu.py"),fields,"tester")
            self.assertEqual(name,"tester/doc-gpu-123-1")
            metadata=json.loads((folder/"kernel-metadata.json").read_text())
            self.assertEqual(metadata["is_private"],"true")
            self.assertEqual(metadata["enable_gpu"],"true")
            self.assertEqual(metadata["enable_internet"],"true")
            compile((folder/"doc_kaggle_gpu.py").read_text(),"<notebook>","exec")
            out=Path(temp)/"remote"
            out.mkdir()
            (out/"doc-kaggle-logs.tar.gz").write_bytes(b"x")
            result={"sha":"b"*40,"run_id":"123","result":"pass",
                    "hardware":True,"backend":"vulkan",
                    "goose_sdl3_checks":77,"dual_backend_episodes":42}
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)
            result["sha"]="a"*40
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            self.assertEqual(module.verify_result(out,fields),result)

if __name__=="__main__":
    unittest.main()
