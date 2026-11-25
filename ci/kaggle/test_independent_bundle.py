"""Offline regression gate for private exact-build artifact transport."""
import io,json,tarfile,tempfile,unittest
from pathlib import Path
from independent_bundle import pack,unpack,digest

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
if __name__=='__main__':unittest.main()
