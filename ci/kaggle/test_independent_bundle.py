"""Offline regression gate for private exact-build artifact transport."""
import io,json,tarfile,tempfile,unittest
from pathlib import Path
from independent_bundle import pack,unpack,digest
from independent_micro_evidence import MICRO_GRAPHS,MICRO_EXECUTABLES,validate_micro_evidence

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
            (self.actual/(name+'.stderr')).write_bytes(b'DOC11_GPU_ADAPTER: type=2 backend=6 physical=1 description=test\nDOC11_GPU_DISPATCH: lanes=96 workgroups=2\nDOC11_REGIONS: live=0 peak=8\nDOC11_GPU_BUFFER_POOL: action=reused\nDOC11_GPU_RETIRED: outcome=queue-complete\nDOC11_GPU_RETIRED: outcome=device-lost\n')
            if name in MICRO_GRAPHS:
                (self.expected/(name+'.expected')).write_bytes(name.encode())
                (self.actual/(name+'.actual')).write_bytes(name.encode())
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
    def test_output_parity(self):
        (self.actual/'wide.actual').write_bytes(b'different')
        with self.assertRaises(ValueError):self.validate()
    def test_required_retirement_traces(self):
        p=self.actual/'gpu_epoch_authority.stderr';original=p.read_bytes()
        for marker in (b'DOC11_GPU_RETIRED: outcome=queue-complete',b'DOC11_GPU_RETIRED: outcome=device-lost',b'DOC11_GPU_BUFFER_POOL: action=reused',b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2'):
            p.write_bytes(original.replace(marker,b'absent'))
            with self.subTest(marker=marker),self.assertRaises(ValueError):self.validate()
    def test_missing_result(self):
        (self.actual/'device_loss.stdout').write_bytes(b'')
        with self.assertRaises(ValueError):self.validate()
if __name__=='__main__':unittest.main()
