"""Offline integrity, provenance and no-GPU-usage tests for private native bundle."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

location=Path(__file__).with_name("bundle.py")
loader=importlib.util.spec_from_file_location("doc_native_gpu_bundle",location)
bundle=importlib.util.module_from_spec(loader)
loader.loader.exec_module(bundle)

class NativeGpuBundle(unittest.TestCase):
    def fixtures(self,folder):
        root=Path(folder)
        checkout=root/"checkout"
        sources={}
        for path in bundle.SOURCE_FILES:
            target=checkout/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text("fixture "+path+"\n")
            sources[path]=target
        artifacts=root/"artifacts"
        for name,(kind,source) in bundle.GPU_EXECUTABLES.items():
            target=artifacts/kind/source
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(("native "+kind+" "+name).encode())
        return checkout,artifacts

    def test_exact_sha_native_bundle_contains_both_hosts_and_oracles(self):
        with tempfile.TemporaryDirectory() as td:
            checkout,artifacts=self.fixtures(td)
            sha="a"*40
            archive,digest,manifest=bundle.bundle_source(
                "x0796666-ui/DOC",sha,"123",checkout,artifacts,
                Path(td)/"output")
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),digest)
            with tarfile.open(archive) as f:
                names=set(f.getnames())
                self.assertIn("bin/doc-goose-sdl3",names)
                self.assertIn("bin/webgpu_bool",names)
                self.assertIn("bin/webgpu_integer_eq",names)
                self.assertIn("bin/Xvfb",names)
                self.assertIn("lib/libvulkan.so.1",names)
                self.assertIn("DOC/runtime-goose/check-dual-gpu-parity.py",names)
                contents=json.loads(f.extractfile("manifest.json").read())
                self.assertEqual(contents["sha"],sha)
                self.assertEqual(contents["standard_ci_run_id"],"123")
                self.assertEqual(set(contents["files"]),set(names)-{"manifest.json"})
            self.assertGreater(len(manifest["files"]),10)

    def test_missing_compiled_gpu_binary_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            checkout,artifacts=self.fixtures(td)
            (artifacts/"goose/doc-goose-sdl3").unlink()
            with self.assertRaisesRegex(RuntimeError,"binary missing"):
                bundle.bundle_source("x0796666-ui/DOC","a"*40,
                                     "123",checkout,artifacts,Path(td)/"output")

    def test_only_exact_successful_ci_provides_native_artifacts(self):
        with patch.object(bundle,"github_json") as api:
            api.return_value={
                "id":456,"head_sha":"a"*40,"conclusion":"success",
                "name":"DOC dual-runtime validation"}
            self.assertEqual(
                bundle.find_native_run("x0796666-ui/DOC","FAKE","a"*40,456),
                "456")
            api.return_value["head_sha"]="b"*40
            with self.assertRaisesRegex(RuntimeError,"successful exact-SHA"):
                bundle.find_native_run("x0796666-ui/DOC","FAKE","a"*40,456)
            api.return_value["head_sha"]="a"*40
            api.return_value["conclusion"]="failure"
            with self.assertRaisesRegex(RuntimeError,"successful exact-SHA"):
                bundle.find_native_run("x0796666-ui/DOC","FAKE","a"*40,456)

    def test_private_dataset_metadata_ready_before_gpu_submission(self):
        class Completed:
            def __init__(self,code,text=""):
                self.returncode=code
                self.stdout=text
                self.stderr=""
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            (folder/"doc-gpu-bundle.tar.gz").write_bytes(b"test bundle")
            with patch.object(bundle.subprocess,"run",
                side_effect=[Completed(0),Completed(0,'{"status":"COMPLETE"}')]) as invoke:
                name=bundle.create_private_dataset(folder,"owner","123","1",
                    {"KAGGLE_API_TOKEN":"FAKE"})
            self.assertEqual(name,"owner/doc-gpu-123-1-bundle")
            meta=json.loads((folder/"dataset-metadata.json").read_text())
            self.assertEqual(meta["id"],name)
            self.assertEqual(meta["licenses"],[{"name":"other"}])
            self.assertEqual(invoke.call_count,2)
            self.assertEqual(invoke.call_args_list[0].args[0][:3],
                             ["kaggle","datasets","create"])

    def test_delayed_private_dataset_status_retries_without_gpu(self):
        class Completed:
            def __init__(self,rc,output=""):
                self.returncode=rc
                self.stdout=output
                self.stderr=""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"doc-gpu-bundle.tar.gz").write_bytes(b"test")
            with patch.object(bundle.subprocess,"run",side_effect=[
                Completed(0),Completed(1),Completed(0,'{"status":"COMPLETE"}')
            ]) as invoke, patch.object(bundle.time,"sleep",return_value=None):
                value=bundle.create_private_dataset(root,"owner","77","1",{})
            self.assertEqual(value,"owner/doc-gpu-77-1-bundle")
            self.assertEqual(invoke.call_count,3)
            self.assertEqual(invoke.call_args_list[1].args[0][:3],
                             ["kaggle","datasets","status"])

    def test_no_dataset_upload_after_api_failure(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(bundle.subprocess,"run",return_value=
                subprocess.CompletedProcess(["kaggle"],1,"","")):
                with self.assertRaisesRegex(RuntimeError,"upload failed"):
                    bundle.create_private_dataset(Path(td),"owner","123","1",{})

if __name__=="__main__":
    unittest.main()
