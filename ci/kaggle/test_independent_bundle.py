"""Offline regression gate for private exact-build artifact transport."""
import ast,io,json,tarfile,tempfile,unittest
from pathlib import Path
from independent_bundle import pack,unpack,digest
from independent_micro_evidence import MICRO_GRAPHS,MICRO_EXECUTABLES,validate_micro_evidence,validate_destroy,DESTROY_QUEUE,DESTROY_CONFIRMED,ABANDON_QUEUE,LOSS_PROBE

from dispatch import prepare_kernel,render_kernel_template
from independent_dispatch import INDEPENDENT_SPEC_MARKER,write_template

class NotebookTemplateTests(unittest.TestCase):
    def test_actual_independent_template(self):
        spec={'sha':'a'*40,'run_id':'12345','attempt':'1','accelerator':'NvidiaTeslaT4',
              'bundle_sha256':'b'*64,'bundle_dataset':'tester/private-bundle','executables':['bin/program']}
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);template=root/'template.py';write_template(template)
            rendered=render_kernel_template(template,spec,placeholder=INDEPENDENT_SPEC_MARKER)
            folder=root/'kernel'
            self.assertEqual(prepare_kernel(folder,template,spec,'tester',placeholder=INDEPENDENT_SPEC_MARKER),'tester/doc-gpu-12345-1')
            code=(folder/'doc_kaggle_gpu.py').read_text()
            self.assertEqual(code,rendered)
            self.assertNotIn(INDEPENDENT_SPEC_MARKER,code)
            tree=ast.parse(code)
            assignments=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SPEC' for t in n.targets)]
            self.assertEqual(len(assignments),1)
            self.assertEqual(ast.literal_eval(assignments[0].value),spec)
            calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='runpy' and n.func.attr=='run_path']
            self.assertEqual(len(calls),1)
            globals_arg=next(k.value for k in calls[0].keywords if k.arg=='init_globals')
            self.assertEqual([ast.literal_eval(k) for k in globals_arg.keys],['__DOC_KAGGLE_RUN_SPEC__'])
            self.assertEqual(globals_arg.values[0].id,'SPEC')
            metadata=json.loads((folder/'kernel-metadata.json').read_text())
            self.assertEqual(metadata['dataset_sources'],[spec['bundle_dataset']])
            self.assertEqual(metadata['is_private'],'true')
            self.assertEqual(metadata['enable_gpu'],'true')
    def test_template_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            template=Path(td)/'template.py'
            for source in ('SPEC=None','SPEC='+INDEPENDENT_SPEC_MARKER+'\nOTHER='+INDEPENDENT_SPEC_MARKER,'SPEC='+INDEPENDENT_SPEC_MARKER+'\nif'):
                template.write_text(source)
                with self.subTest(source=source),self.assertRaises((ValueError,SyntaxError)):
                    render_kernel_template(template,{},placeholder=INDEPENDENT_SPEC_MARKER)

SHA='a'*40
RUN='12345'
class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.src=self.root/'src';self.src.write_bytes(b'compiled\0bytes')
        self.tar=self.root/'bundle.tgz';self.dest=self.root/'dest'
        self.hash,self.manifest=pack({'bin/program':self.src},self.tar,SHA,RUN)
    def load(self,sha=SHA,run=RUN,checksum=None):
        return unpack(self.tar,self.dest,checksum or digest(self.tar),sha,run)
    def archive(self,rows,manifest=None):
        with tarfile.open(self.tar,'w:gz') as tar:
            if manifest is not None:
                rows=[('manifest.json',json.dumps(manifest).encode(),tarfile.REGTYPE)]+rows
            for name,data,kind in rows:
                m=tarfile.TarInfo(name);m.type=kind;m.size=len(data) if kind==tarfile.REGTYPE else 0
                if kind==tarfile.SYMTYPE:m.linkname='../../outside'
                tar.addfile(m,io.BytesIO(data) if m.isfile() else None)
    def test_roundtrip(self):
        self.assertEqual(self.load(),self.manifest)
        self.assertEqual((self.dest/'bin/program').read_bytes(),self.src.read_bytes())
        with self.assertRaises(ValueError):self.load()
    def test_provenance(self):
        for kwargs in ({'sha':'b'*40},{'run':'9'},{'checksum':'0'*64}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.load(**kwargs)
            self.assertFalse(self.dest.exists())
    def test_unsafe_paths_and_links(self):
        for name,kind in (('../outside',tarfile.REGTYPE),('/tmp/outside',tarfile.REGTYPE),('a/../outside',tarfile.REGTYPE),('a//b',tarfile.REGTYPE),('a\\b',tarfile.REGTYPE),('bin/program',tarfile.SYMTYPE),('bin/program',tarfile.LNKTYPE)):
            self.archive([(name,b'bad',kind)],self.manifest)
            with self.subTest(name=name,kind=kind),self.assertRaises(ValueError):self.load()
            self.assertFalse(self.dest.exists())
    def test_duplicate_and_missing(self):
        row=('bin/program',self.src.read_bytes(),tarfile.REGTYPE)
        for rows,manifest in (([row,row],self.manifest),([],self.manifest),([row],None)):
            self.archive(rows,manifest)
            with self.assertRaises(ValueError):self.load()
            self.assertFalse(self.dest.exists())
    def test_hash_and_size_rollback(self):
        for data in (b'bad',b'x'*len(self.src.read_bytes())):
            self.archive([('bin/program',data,tarfile.REGTYPE)],self.manifest)
            with self.assertRaises(ValueError):self.load()
            self.assertFalse(self.dest.exists())
    def test_pack_authority(self):
        link=self.root/'link';link.symlink_to(self.src)
        for files in ({'../bad':self.src},{'bin/program':link},{'manifest.json':self.src},{}):
            with self.subTest(files=files),self.assertRaises(ValueError):pack(files,self.tar,SHA,RUN)
class PhysicalMicroEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        self.actual=root/'actual';self.actual.mkdir();self.expected=root/'expected';self.expected.mkdir()
        for name in MICRO_EXECUTABLES:
            (self.actual/(name+'.stderr')).write_bytes(b'DOC11_GPU_ADAPTER: type=2 backend=6 physical=1 description=test\nDOC11_GPU_DISPATCH: lanes=96 workgroups=2\nDOC11_REGIONS: live=0 peak=8\nDOC11_GPU_BUFFER_POOL: action=reused\nDOC11_WGPU_QUEUE_RETIRED: destroy=0\nDOC11_GPU_RETIRED: outcome=queue-complete\nDOC11_WGPU_QUEUE_RETIRED: destroy=1\nDOC11_GPU_LOST_CALLBACK: reason=2\nDOC11_WGPU_DESTROY_CONFIRMED: provider invalidation after queue retirement\nDOC11_GPU_RETIRED: outcome=device-lost\nDOC11_GPU_POOL_METRICS: event=created admitted=420 released=0 live=420 peak=420\nDOC11_GPU_POOL_METRICS: event=grown admitted=2320 released=20 live=2300 peak=2320\nDOC11_GPU_POOL_METRICS: event=reused admitted=2320 released=20 live=2300 peak=2320\nDOC11_GPU_POOL_METRICS: event=closed admitted=2320 released=2320 live=0 peak=2320\n')
            if name in MICRO_GRAPHS:
                (self.expected/(name+'.expected')).write_bytes(name.encode())
                (self.actual/(name+'.actual')).write_bytes(name.encode())
                if name=='family':
                    p=self.actual/(name+'.stderr')
                    p.write_bytes(p.read_bytes()+b''.join(b'DOC11_GPU_FAMILY: state=3 lanes='+n+b'\nDOC11_GPU_FRONTIER: cpu=1 gpu=1 concurrent=1\n' for n in (b'128',b'256',b'128')))
                    adapter=b'DOC11_GPU_ADAPTER: type=2 backend=6 physical=1 description=test\nDOC11_REGIONS: live=0 peak=8\n'
                    for label,data in [('family-overflow',b'family'),('family-injected',b'epoch: 0\nepoch: 1\n'),('family-strict',b'ys: [6,7,8]\n'),('family-empty',b'ys: []\n'),('family-rejected',b'')]:
                        (self.actual/(label+'.stdout')).write_bytes(data)
                        (self.actual/(label+'.stderr')).write_bytes(adapter+(b'DOC11_GPU_INJECTED_FAILURE: dispatch=2\n' if label=='family-injected' else b''))
            elif name=='gpu_graph_generation':
                adapter=b'DOC11_GPU_ADAPTER: type=2 backend=6 physical=1 description=test\n'
                dispatch=b'DOC11_GPU_DISPATCH: lanes=2 workgroups=1\n'
                closed=b'DOC11_GPU_POOL_METRICS: event=closed admitted=100 released=100 live=0 peak=100\n'
                (self.actual/(name+'.stderr')).write_bytes((adapter+dispatch*2+closed)*4+b'DOC11_GPU_INJECTED_FAILURE: dispatch=1\n')
                (self.actual/(name+'.stdout')).write_bytes(b'DOC11_GPU_GRAPH_GENERATION_PASS:')
            else:
                marker=b'DOC11_GPU_DEVICE_LOSS_PASS:' if name=='device_loss' else b'DOC11_GPU_EPOCH_AUTHORITY_PASS:'
                (self.actual/(name+'.stdout')).write_bytes(marker)
    def validate(self):validate_micro_evidence(self.actual,self.expected)
    def test_complete_evidence(self):self.validate()
    def test_missing_or_software_adapter(self):
        p=self.actual/'gpu_epoch_authority.stderr';p.write_bytes(p.read_bytes().replace(b'physical=1',b'physical=0'))
        with self.assertRaises(ValueError):self.validate()
        p.unlink()
        with self.assertRaises(FileNotFoundError):self.validate()
    def test_gpu_graph_generation_evidence(self):
        p=self.actual/'gpu_graph_generation.stderr';original=p.read_bytes()
        for changed in (original.replace(b'physical=1',b'physical=0',1),original.replace(b'live=0',b'live=1',1),original.replace(b'event=closed',b'event=absent',1),original.replace(b'DOC11_GPU_DISPATCH:',b'absent'),original.replace(b'DOC11_GPU_INJECTED_FAILURE:',b'absent')):
            p.write_bytes(changed)
            with self.assertRaises(ValueError):self.validate()
    def test_family_evidence(self):
        p=self.actual/'family.stderr';original=p.read_bytes()
        for changed in (original.replace(b'lanes=256',b'lanes=128'),original.replace(b'concurrent=1',b'concurrent=0',1)):
            p.write_bytes(changed)
            with self.assertRaises(ValueError):self.validate()
        p.write_bytes(original)
        (self.actual/'family-injected.stdout').write_bytes(b'epoch: 2\n')
        with self.assertRaises(ValueError):self.validate()
    def test_output_parity(self):
        (self.actual/'wide.actual').write_bytes(b'different')
        with self.assertRaises(ValueError):self.validate()
    def test_required_retirement_traces(self):
        p=self.actual/'gpu_epoch_authority.stderr';original=p.read_bytes()
        for marker in (b'DOC11_GPU_RETIRED: outcome=queue-complete',b'DOC11_GPU_RETIRED: outcome=device-lost',b'DOC11_GPU_BUFFER_POOL: action=reused',b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2'):
            p.write_bytes(original.replace(marker,b'absent'))
            with self.subTest(marker=marker),self.assertRaises(ValueError):self.validate()
    def test_pool_accounting(self):
        p=self.actual/'gpu_epoch_authority.stderr';original=p.read_bytes()
        for old,new in ((b'live=2300',b'live=2301'),(b'peak=2320',b'peak=2300'),(b'event=grown',b'event=absent'),(b'event=reused',b'event=absent'),(b'event=closed',b'event=absent'),(b'released=2320 live=0',b'released=2319 live=1')):
            p.write_bytes(original.replace(old,new))
            with self.subTest(old=old),self.assertRaises(ValueError):self.validate()
    def test_destroy_evidence(self):
        for name in ('device_loss','gpu_epoch_authority'):
            p=self.actual/(name+'.stderr');original=p.read_bytes()
            for marker in (DESTROY_QUEUE,DESTROY_CONFIRMED,b'DOC11_GPU_LOST_CALLBACK: reason=2'):
                p.write_bytes(original.replace(marker,b'absent'))
                with self.subTest(name=name,marker=marker),self.assertRaises(ValueError):self.validate()
            p.write_bytes(original.replace(DESTROY_QUEUE,b'placeholder').replace(DESTROY_CONFIRMED,DESTROY_QUEUE).replace(b'placeholder',DESTROY_CONFIRMED))
            with self.subTest(name=name,order='reversed'),self.assertRaises(ValueError):self.validate()
            p.write_bytes(original)
        p=self.actual/'gpu_epoch_authority.stderr';original=p.read_bytes()
        p.write_bytes(original.replace(ABANDON_QUEUE,b'absent'))
        with self.assertRaises(ValueError):self.validate()
    def test_mesh_destroy_order(self):
        callback=b'DOC11_MESH_LOST_CALLBACK: reason=2'
        for lines in ((DESTROY_QUEUE,callback,DESTROY_CONFIRMED),(callback,DESTROY_QUEUE,DESTROY_CONFIRMED)):
            validate_destroy(b'\n'.join(lines),b'DOC11_MESH_LOST_CALLBACK')
        with self.assertRaises(ValueError):validate_destroy(b'\n'.join((DESTROY_QUEUE,DESTROY_CONFIRMED,callback)),b'DOC11_MESH_LOST_CALLBACK')
    def test_scoped_provider_invalidation(self):
        for name in ('device_loss','gpu_epoch_authority'):
            p=self.actual/(name+'.stderr')
            p.write_bytes(p.read_bytes().replace(b'DOC11_GPU_LOST_CALLBACK: reason=2',b'\n'.join(LOSS_PROBE)))
        self.validate()
        p=self.actual/'gpu_epoch_authority.stderr';original=p.read_bytes()
        for old,new in ((b'Parent device is lost',b'Invalid buffer size'),(b'type=validation',b'type=out-of-memory'),(b'In wgpuDeviceCreateBuffer',b'In another operation')):
            p.write_bytes(original.replace(old,new))
            with self.subTest(old=old),self.assertRaises(ValueError):self.validate()
        p.write_bytes(original)
        validate_destroy(b'\n'.join((DESTROY_QUEUE,*LOSS_PROBE,DESTROY_CONFIRMED)),b'DOC11_MESH_LOST_CALLBACK')
        with self.assertRaises(ValueError):
            validate_destroy(b'\n'.join((*LOSS_PROBE,DESTROY_QUEUE,DESTROY_CONFIRMED)),b'DOC11_MESH_LOST_CALLBACK')
    def test_missing_result(self):
        (self.actual/'device_loss.stdout').write_bytes(b'')
        with self.assertRaises(ValueError):self.validate()
if __name__=='__main__':unittest.main()
