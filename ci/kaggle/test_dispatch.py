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
        self.assertTrue(module.gpu_session_attempted(first))
        self.assertFalse(module.gpu_session_attempted(blocked))
        self.assertFalse(module.gpu_session_attempted(skipped))
        self.assertTrue(module.gpu_session_attempted(""))
        self.assertTrue(module.gpu_session_attempted("Kaggle kernel was launched, but log truncated"))
        self.assertTrue(module.gpu_session_attempted(
            first + "\\n" + blocked))
        history={"workflow_runs":[
            {"id":1,"created_at":"2026-11-22T00:00:00Z"},
            {"id":2,"created_at":"2026-11-21T21:00:00Z","conclusion":"failure"},
            {"id":3,"created_at":"2026-11-21T20:00:00Z","conclusion":"failure"}]}
        log_by_run={"2": first,"3":blocked}
        self.assertEqual(module.github_recent_attempts(history,1,
            dt.datetime(2026,11,22,tzinfo=dt.timezone.utc),
            lambda run_id: module.gpu_session_attempted(log_by_run[run_id])),1)

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
