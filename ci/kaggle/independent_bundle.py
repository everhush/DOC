"""Bounded private physical-validation bundle: exact source/run and member hashes."""
import hashlib,json,re,tarfile,tempfile,shutil
from pathlib import Path,PurePosixPath
MAX_FILES=160
MAX_MEMBER=128*1024*1024
MAX_TOTAL=512*1024*1024
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def valid_name(name):
    p=PurePosixPath(name)
    return bool(name and not p.is_absolute() and p.as_posix()==name and all(x not in ('','.','..') for x in name.split('/')) and '\\' not in name and not any(ord(c)<32 for c in name))
def pack(files,output,sha,run_id):
    if not re.fullmatch(r'[0-9a-f]{40}',sha) or not re.fullmatch(r'[1-9][0-9]{0,19}',str(run_id)):raise ValueError('invalid build provenance')
    if not files or len(files)>MAX_FILES-1 or 'manifest.json' in files:raise ValueError('bundle file count')
    records={};total=0
    for name,p in sorted(files.items()):
        p=Path(p)
        if not valid_name(name) or p.is_symlink() or not p.is_file():raise ValueError('unsafe bundle source')
        n=p.stat().st_size;total+=n
        if not 0<n<=MAX_MEMBER or total>MAX_TOTAL:raise ValueError('bundle size')
        records[name]={'sha256':digest(p),'bytes':n}
    manifest={'schema':1,'sha':sha,'run_id':str(run_id),'files':records}
    with tempfile.TemporaryDirectory() as td:
        mf=Path(td)/'manifest.json';mf.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        with tarfile.open(output,'w:gz') as tar:
            for name,p in sorted({**files,'manifest.json':mf}.items()):
                item=tar.gettarinfo(str(p),arcname=name);item.uid=item.gid=0;item.uname=item.gname='';item.mode=0o600
                with Path(p).open('rb') as f:tar.addfile(item,f)
    return digest(output),manifest
def unpack(archive,destination,expected,sha,run_id):
    archive=Path(archive);destination=Path(destination)
    if digest(archive)!=expected:raise ValueError('bundle digest mismatch')
    if destination.exists():raise ValueError('destination already exists')
    with tarfile.open(archive,'r:gz') as tar:
        names=set();total=0;members=[]
        for m in tar:
            total+=m.size
            if not m.isfile() or not valid_name(m.name) or m.name in names or not 0<m.size<=MAX_MEMBER or total>MAX_TOTAL or len(members)>=MAX_FILES:raise ValueError('unsafe bundle member')
            names.add(m.name);members.append(m)
        if 'manifest.json' not in names:raise ValueError('missing manifest')
        manifest=json.load(tar.extractfile('manifest.json'))
        if manifest.get('schema')!=1 or manifest.get('sha')!=sha or manifest.get('run_id')!=str(run_id) or set(manifest['files'])!=names-{'manifest.json'}:raise ValueError('stale or incomplete manifest')
        destination.mkdir()
        try:
            for m in members:
                if m.name=='manifest.json':continue
                rec=manifest['files'][m.name]
                if rec['bytes']!=m.size:raise ValueError('member size mismatch')
                target=destination/m.name;target.parent.mkdir(parents=True,exist_ok=True)
                h=hashlib.sha256()
                with tar.extractfile(m) as source,target.open('xb') as sink:
                    for b in iter(lambda:source.read(1024*1024),b''):h.update(b);sink.write(b)
                if h.hexdigest()!=rec['sha256']:raise ValueError('member digest mismatch')
        except BaseException:
            shutil.rmtree(destination);raise
    return manifest
