"""Offline Kaggle bootstrap tests. Zero Kaggle API and GPU quota usage."""
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest

SOURCE = Path(__file__).with_name("doc_kaggle_gpu.py").read_text()
TREE = ast.parse(SOURCE.replace("__DOC_KAGGLE_RUN_SPEC__", "{}"))
FUNCTIONS = {node.name: node for node in TREE.body if isinstance(node, ast.FunctionDef)}

def load_function(name, namespace):
    tree = ast.Module(body=[FUNCTIONS[name]], type_ignores=[])
    exec(compile(tree, "<doc-kaggle-bootstrap>", "exec"), namespace)
    return namespace[name]

class KaggleBootstrapSafety(unittest.TestCase):
    def test_installed_packages_does_not_use_apt_or_network(self):
        def fake_query(argv, **kwargs):
            self.assertEqual(argv[:2], ["dpkg-query","-W"])
            self.assertTrue(argv[2].startswith("-f="))
            return subprocess.CompletedProcess(argv,0 if argv[-1]!="missing" else 1,
                "install ok installed\n" if argv[-1]!="missing" else "", "")
        scope={"subprocess":types.SimpleNamespace(run=fake_query)}
        fn=load_function("installed_packages",scope)
        self.assertEqual(fn(["cmake","vulkan-tools"]),[])
        self.assertEqual(fn(["cmake","missing"]),["missing"])

    def namespace(self, tmp, missing, outcomes):
        events=[]
        def run(name, argv, **kwargs):
            events.append((name,argv,kwargs))
            if name=="nvidia-smi":
                return "GPU 0: Tesla T4"
            if name in outcomes and outcomes[name]:
                raise RuntimeError("fake bounded package failure")
            return ""
        scope={
            "run":run,"installed_packages":lambda packages:list(missing),
            "LOGS":Path(tmp),"ROOT":Path(tmp),"json":json,
            "os":types.SimpleNamespace(geteuid=lambda:0,pathsep=":"),
            "shutil":types.SimpleNamespace(which=lambda name:"/usr/bin/cargo"),
            "preflight_hardware":lambda:events.append(("preflight",[],{})),
            "subprocess":subprocess,
        }
        fn=load_function("install_dependencies",scope)
        return fn,events

    def test_warm_image_skips_apt_update_entirely(self):
        with tempfile.TemporaryDirectory() as temp:
            fn,events=self.namespace(temp,[],{})
            fn()
            self.assertEqual([n for n,_,_ in events],["nvidia-smi","preflight"])
            data=json.loads((Path(temp)/"kaggle-packages-required.json").read_text())
            self.assertEqual(data["missing"],[])

    def test_missing_package_installs_without_unconditional_update(self):
        with tempfile.TemporaryDirectory() as temp:
            fn,events=self.namespace(temp,["vulkan-tools"],{})
            with self.assertRaisesRegex(RuntimeError,"missing native"):
                fn()
            self.assertEqual([n for n,_,_ in events],
                             ["nvidia-smi","apt-install-missing"])
            self.assertLessEqual(events[1][2]["max_seconds"],105)

    def test_retry_is_bounded_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            fn,events=self.namespace(temp,["libvulkan-dev"],
                {"apt-install-missing":True})
            with self.assertRaisesRegex(RuntimeError,"INFRA_BLOCKED"):
                fn()
            names=[n for n,_,_ in events]
            self.assertEqual(names,["nvidia-smi","apt-install-missing",
                                    "apt-update-bounded","apt-install-missing"])
            self.assertLessEqual(events[2][2]["max_seconds"],50)

    def test_no_cuda_gpu_never_touches_apt(self):
        with tempfile.TemporaryDirectory() as temp:
            scope = {"run":lambda name,argv,**kwargs:"no accelerator",
                "installed_packages":lambda x:[],
                "LOGS":Path(temp),"ROOT":Path(temp),"json":json,
                "os":types.SimpleNamespace(geteuid=lambda:0,pathsep=":"),
                "shutil":types.SimpleNamespace(which=lambda n:"/bin/cargo"),
                "preflight_hardware":lambda:None,
                "subprocess":subprocess}
            reject=load_function("install_dependencies",scope)
            with self.assertRaisesRegex(RuntimeError,"INFRA_BLOCKED"):
                reject()

if __name__=="__main__":
    unittest.main()
