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
    def test_cli_read_retry_and_write_fail_closed(self):
        from unittest.mock import patch
        from subprocess import CompletedProcess, TimeoutExpired
        failure = CompletedProcess([], 1, "", "HTTP status 503 SECRET_TOKEN")
        success = CompletedProcess([], 0, "RUNNING", "")
        with patch.object(module.subprocess, "run", side_effect=[failure, success]) as run, \
             patch.object(module.time, "sleep") as sleep:
            self.assertEqual(module.kaggle(["kernels", "status", "private/name"], {}), "RUNNING")
            self.assertEqual(run.call_count, 2)
            sleep.assert_called_once_with(1)
        for error in (failure, TimeoutExpired(["secret"], 1)):
            with patch.object(module.subprocess, "run") as run:
                if isinstance(error, Exception):
                    run.side_effect = error
                else:
                    run.return_value = error
                with self.assertRaisesRegex(RuntimeError, r"^Kaggle CLI operation failed: kernels-push category=(http-503|network)$"):
                    module.kaggle(["kernels", "push", "SECRET_TOKEN"], {})
                self.assertEqual(run.call_count, 1)
        denied = CompletedProcess([], 1, "", "HTTP status 403 SECRET_TOKEN")
        with patch.object(module.subprocess, "run", return_value=denied) as run:
            with self.assertRaisesRegex(RuntimeError, r"^Kaggle CLI operation failed: kernels-status category=http-403$"):
                module.kaggle(["kernels", "status", "private/name"], {})
            self.assertEqual(run.call_count, 1)
        with patch.object(module.subprocess, "run", return_value=failure) as run, \
             patch.object(module.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "category=http-503"):
                module.kaggle(["quota", "--format", "json"], {})
            self.assertEqual(run.call_count, 3)

    def test_only_exact_matching_private_mount_error_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            spec={"sha":"a"*40,"run_id":"123","bundle_dataset":"owner/one"}
            good={"sha":"a"*40,"run_id":"123","bundle_dataset":"owner/one",
                  "result":"failed","hardware":False,
                  "failure":"INFRA_BLOCKED: precompiled native GPU dataset not mounted"}
            file=root/"doc-kaggle-summary.json"
            file.write_text(json.dumps(good))
            self.assertTrue(module.missing_private_mount(root,spec))
            for key,value in [("sha","b"*40),("run_id","456"),
                ("bundle_dataset","owner/other"),("result","pass"),
                ("hardware",True),("failure","compute GPU fault")]:
                file.write_text(json.dumps(dict(good,**{key:value})))
                self.assertFalse(module.missing_private_mount(root,spec))
            file.write_text("not-json")
            self.assertFalse(module.missing_private_mount(root,spec))

    def test_no_doc_usage_caps_or_duplicate_prohibitions(self):
        self.assertFalse(hasattr(module, "MAX_WEEKLY_RUNS"))
        self.assertFalse(hasattr(module, "MAX_SESSION_MINUTES"))
        self.assertFalse(hasattr(module, "MIN_QUOTA_RESERVE_HOURS"))
        self.assertFalse(hasattr(module, "DUPLICATE_LOOKBACK_DAYS"))
        self.assertFalse(hasattr(module, "github_duplicate_work"))
        self.assertFalse(hasattr(module, "duplicate_gpu_submission"))

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
    def test_session_duration_left_to_kaggle(self):
        self.assertFalse(hasattr(module, "MAX_SESSION_MINUTES"))
        self.assertFalse(hasattr(module, "MIN_QUOTA_RESERVE_HOURS"))
        self.assertEqual(module.DEFAULT_ACCELERATOR, "NvidiaTeslaT4")
    def test_private_legacy_json_and_raw_token(self):
        with tempfile.TemporaryDirectory() as temp:
            env,owner=module.auth_environment('{"username":"Tester","key":"FAKE"}',
                Path(temp)/"config","")
            self.assertEqual(owner,"tester")
            f=Path(env["KAGGLE_CONFIG_DIR"])/"kaggle.json"
            self.assertEqual(f.stat().st_mode & 0o777,0o600)
            self.assertEqual(json.loads(f.read_text())["key"],"FAKE")
        with tempfile.TemporaryDirectory() as temp:
            legacy_key="a"*32
            env,owner=module.auth_environment(legacy_key,Path(temp),"tester")
            self.assertEqual(owner,"tester")
            config=Path(temp)/"kaggle.json"
            self.assertEqual(config.stat().st_mode & 0o777,0o600)
            self.assertEqual(json.loads(config.read_text()),
                             {"username":"tester","key":legacy_key})
            self.assertNotIn("KAGGLE_API_TOKEN",env)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"DOC_KAGGLE_USERNAME"):
                module.auth_environment("b"*32,Path(temp),"")
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
        fields={"repo":"rtu0/DOC","sha":"a"*40,"run_id":"123",
                "attempt":"1","accelerator":"NvidiaTeslaT4"}
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
            frames="\n".join("DOC_GAME_FRAME: tick="+str(i) for i in range(16) if i!=13)+"\n"+"DOC_GAME_FRAME: tick=13 player=(6,4) score=2 paused=false won=true coin=(6,4)\n"
            radar={"adapter":"GPU","device_type":"DiscreteGpu","cpu_nodes":930,
                   "gpu_nodes":2010,"mixed_frontiers":15,"gpu_frontiers":15,
                   "complete_replay_parity":True,"failure_rollback":True}
            # Synthetic records exercise only the offline validator contract.
            scene_frames="".join(f"DOC_SCENE_FRAME: epoch={i} next_won={'true' if i==14 else 'false'} next_elevation={24 if i==1 else 0}\n" for i in range(17))
            scene_pixels="".join(f"DOC_SCENE_PIXELS: epoch={i} distinct=6 digest={i:016x}\n" for i in range(17))
            scene_result={"frames":17,"mixed_frontiers":16,"adapter":"GPU","device_type":"DiscreteGpu","complete_replay_parity":True}
            with tarfile.open(out/"doc-kaggle-logs.tar.gz","w:gz") as archive:
                evidence={
                    "report/rust-gpu-conformance.log":
                        "DOC_RUST_NATIVE_PHYSICAL_GPU_PASS: 42 signed GPU episodes",
                    "report/webgpu-device-admission.log":
                        "DOC_WEBGPU_HARDWARE_ADMISSION_PASS: 62 executed DOC source cases\n"+
                        ("DOC_GPU_SELECTED_DEVICE: name=GPU type=DiscreteGpu vendor=4318 device=1\n"*62),
                    "report/doc-selected-gpu-equivalence.log":
                        "DOC_SELECTED_RUST_DOC_GPU_PARITY_PASS: 62 real GPU-selected executions",
                    "report/radar-auto-result.log":"DOC_RADAR_PHYSICAL_AUTO_PASS: fixture",
                    "report/radar-auto-physical.log":frames+
                        "DOC_GPU_SELECTED_DEVICE: name=GPU type=DiscreteGpu vendor=4318 device=1\n"+
                        "DOC_AUTO_GPU_SESSION_CREATED: gpu_kind=physical\n"+
                        "DOC_AUTO_GPU_SESSION_REUSED: gpu_kind=physical\n"*14+
                        "DOC_AUTO_FRONTIER: cpu=8 gpu=134 gpu_kind=physical placement=typed-independent\n"*15+
                        "DOC_RUST_GPU_FRONTIER_DISPATCH: states=134 workgroups=3 workgroup_size=64\n"*15+
                        "DOC_AUTO_SUMMARY: gpu_kind=physical cpu_nodes=930 gpu_nodes=2010 cpu_parallel_frontiers=0 cpu_only_frontiers=135 gpu_frontiers=15 mixed_frontiers=15\n",
                    "report/radar-auto-cpu.log":frames+"DOC_AUTO_SUMMARY: gpu_kind=none cpu_nodes=2940 gpu_nodes=0\n",
                    "report/radar-auto-fault.log":"DOC_GAME_FRAME: tick=0\nDOC_GPU_INJECTED_STAGE_FAILURE: stage=0\n",
                    "report/scene3d-cpu.log":scene_frames+"DOC_SCENE_REPLAY_PASS: mode=headless actions=16 frames=17\n",
                    "report/scene3d-physical.log":scene_frames+scene_pixels+
                        "DOC_SCENE_RENDER_DEVICE: name=GPU type=DiscreteGpu\n"+
                        "DOC_SCENE_GENERATED_PIPELINE: source_bytes=123\n"+
                        "DOC_GPU_GENERATED_PIPELINE_CREATED: lanes=134 source_bytes=456\n"+
                        "DOC_GPU_GENERATED_PIPELINE_REUSED: lanes=134\n"+
                        "DOC_AUTO_FRONTIER: cpu=8 gpu=134 gpu_kind=physical placement=typed-independent\n"*16+
                        "DOC_RUST_GPU_FRONTIER_DISPATCH: states=134 workgroups=3 workgroup_size=64\n"*16+
                        "DOC_SCENE_REPLAY_PASS: mode=offscreen actions=16 frames=17\n",
                    "report/scene3d-result.log":"DOC_SCENE3D_PHYSICAL_PASS: offline fixture",
                    # Offline validator unit fixture only; never a hardware result.
                    "report/dependency-family.log":
                        "DOC_GPU_SELECTED_DEVICE: name=GPU type=DiscreteGpu vendor=4318 device=1\n"+
                        "DOC_FAMILY_EPISODE: lanes=128 gpu_lanes=128\nDOC_FAMILY_EPISODE: lanes=0 gpu_lanes=0\n"+
                        "DOC_FAMILY_EPISODE: lanes=256 gpu_lanes=256\nDOC_FAMILY_EPISODE: lanes=3 gpu_lanes=0\n"+
                        "DOC_FAMILY_EPISODE: lanes=128 gpu_lanes=128\n"+
                        "DOC_RUST_GPU_FRONTIER_DISPATCH: states=128 workgroups=2 workgroup_size=64\n"*2+
                        "DOC_RUST_GPU_FRONTIER_DISPATCH: states=256 workgroups=4 workgroup_size=64\n"+
                        "DOC_GPU_GENERATED_PIPELINE_REUSED: lanes=128\n"+
                        "DOC_FAMILY_PROOF_PASS: device=physical gpu_lanes=512 episodes=5 rollback=true\n",
                    "report/scene3d-pixel-proof.log":"DOC_SCENE_RENDER_DEVICE: name=GPU type=DiscreteGpu\nDOC_SCENE_GPU_PROOF_PASS: covered=1000 mutated=2000 lighting=3 depth_orders=2 jump=24 landed=0 repeats=16 rejected=2\n",
                    "report/scene3d-fault.log":"DOC_SCENE_FRAME: epoch=0\nDOC_GPU_INJECTED_STAGE_FAILURE: stage=0\n",
                }
                for name,content in evidence.items():
                    path=Path(temp)/name
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(content)
                    archive.add(path,arcname=name)
            result={"sha":"b"*40,"run_id":"123","result":"pass",
                    "hardware":True,"backend":"webgpu",
                    "accelerator":"NvidiaTeslaT4",
                    "rust_gpu_episodes":42,
                "selected_rust_doc_gpu_cases":62,"radar_auto_physical":radar,"scene3d_physical":scene_result}
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)
            result["sha"]="a"*40
            (out/"doc-kaggle-summary.json").write_text(json.dumps(result))
            self.assertEqual(module.verify_result(out,fields),result)
            # Neither a claimed radar result nor older standalone physical evidence
            # can substitute for actual physical game logs and dispatch counts.
            for bad in ("DOC_GPU_SOFTWARE_TEST_ONLY: software adapter\n",
                        "DOC_GPU_SELECTED_DEVICE: name=CPU type=Cpu vendor=0 device=0\n"):
                with tarfile.open(out/"doc-kaggle-logs.tar.gz","w:gz") as archive:
                    for name,content in evidence.items():
                        path=Path(temp)/name
                        path.write_text(content+(bad if name=="report/radar-auto-physical.log" else ""))
                        archive.add(path,arcname=name)
                with self.assertRaises(AssertionError):
                    module.verify_result(out,fields)
            # A software WebGPU adapter must never certify physical hardware.
            with tarfile.open(out/"doc-kaggle-logs.tar.gz","w:gz") as archive:
                for name,content in evidence.items():
                    if name == "report/webgpu-device-admission.log":
                        content = ("DOC_WEBGPU_HARDWARE_ADMISSION_PASS: 62 executed DOC source cases\n"
                                   + "DOC_GPU_SELECTED_DEVICE: name=CPU type=Cpu vendor=0 device=0\n"*62)
                    path = Path(temp)/name
                    path.write_text(content)
                    archive.add(path,arcname=name)
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)
            (out/"doc-kaggle-logs.tar.gz").write_bytes(b"x")
            with self.assertRaises(AssertionError):
                module.verify_result(out,fields)

if __name__=="__main__":
    unittest.main()
