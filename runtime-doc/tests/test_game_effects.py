#!/usr/bin/env python3
"""Independent compiled game: checkpoint restore, typed reload, committed PCM."""
import argparse,hashlib,math,os,re,shutil,struct,subprocess,tempfile,wave
from pathlib import Path
from test_stage2_games import CARRIES,ACTIONS
from test_epoch_authority import emit
ROOT=Path(__file__).resolve().parent.parent
REPLAY='edsssxwddddsspr'
def epochs(raw):
    starts=list(re.finditer(rb'(?m)^epoch: (\d+)\n',raw))
    assert starts and starts[0].start()==0
    return [raw[m.end():starts[i+1].start() if i+1<len(starts) else len(raw)] for i,m in enumerate(starts)]
def fnv(raw):
    h=0xcbf29ce484222325
    for x in raw:h=((h^x)*0x100000001b3)&0xffffffffffffffff
    return h
def fix_checksum(raw):return raw[:-8]+struct.pack('<Q',fnv(raw[:-8]))
def main():
    p=argparse.ArgumentParser();p.add_argument('--games',required=True,type=Path);p.add_argument('--reference',required=True,type=Path);p.add_argument('--managed',required=True,type=Path);p.add_argument('--evidence',required=True,type=Path);a=p.parse_args()
    games=a.games.resolve();reference=a.reference.resolve();out=a.evidence.resolve();out.mkdir(parents=True,exist_ok=True);engine=ROOT.parent/'engine'
    expected=(games/'radar_chase-reference.txt').read_bytes();expected_epochs=epochs(expected)
    carry=[x.replace(':','=') for x in CARRIES.split(',')];action=dict(x.split(':') for x in ACTIONS.split(','))
    with tempfile.TemporaryDirectory() as td:
        base=Path(td);assets=base/'assets';shutil.copytree(engine/'levels',assets/'levels');output=base/'output';output.mkdir();(output/'wav').mkdir()
        # Portable effect admission must be actual native DOC output.
        source=(ROOT/'runtime/effects_policy.doc').read_text()+'source marker:int=0\n'
        generated=[x for x in emit(a.managed.resolve(),source,base).splitlines() if x.startswith('#define F_effect_')]
        checked=[x for x in (ROOT/'runtime/effects_policy_generated.h').read_text().splitlines() if x.startswith('#define F_effect_')]
        assert len(generated)==3 and generated==checked
        env={**os.environ,'DOC_WORKERS':'4','DOC_REGION_METRICS':'1'}
        def invoke(seq,extra=(),carries=carry,add=(),require=True):
            args=['--through='+str(len(seq)),*carries,*[f'--fact={i}:action={action[c]}' for i,c in enumerate(seq,1)],*add,*extra]
            r=subprocess.run([str(games/'radar_chase'),'--asset-root='+str(assets),'--output-root='+str(output),'--backend=cpu',*args],cwd=assets,env={**env,'PATH':''},capture_output=True,timeout=180)
            if require:assert r.returncode==0 and b'DOC11_REGIONS: live=0 ' in r.stderr,r.stderr
            else:assert r.returncode!=0 and b'DOC11_REGIONS: live=0 ' in r.stderr,r.stderr
            return r
        full=invoke(REPLAY,['--save=full.chk','--audio-dir=wav'])
        assert full.stdout==expected
        cue_epochs=[]
        for ep,body in enumerate(expected_epochs[1:],1):
            hz=int(re.search(rb'(?m)^audio_hz: (\d+)$',body)[1]);ms=int(re.search(rb'(?m)^audio_ms: (\d+)$',body)[1])
            if not hz and not ms:continue
            cue_epochs.append(ep);path=output/'wav'/f'cue_{ep}.wav'
            with wave.open(str(path),'rb') as wav:
                n=44100*ms//1000
                assert wav.getparams()[:4]==(1,2,44100,n)
                samples=struct.unpack('<'+'h'*n,wav.readframes(n))
                oracle=[int(math.copysign(math.floor(abs(math.sin(math.tau*hz*k/44100)*7200)+0.5),math.sin(math.tau*hz*k/44100))) for k in range(n)]
                assert samples==tuple(oracle),'PCM differs from independent cue oracle'
        assert cue_epochs and sorted(p.name for p in (output/'wav').iterdir())==sorted(f'cue_{e}.wav' for e in cue_epochs)
        for split in (1,8,len(REPLAY)-1):
            prefix=invoke(REPLAY[:split],['--save=split.chk']);assert epochs(prefix.stdout)==expected_epochs[:split+1]
            resumed=invoke(REPLAY[split:],['--load=split.chk']);assert epochs(resumed.stdout)==expected_epochs[split:]
            assert f'DOC11_CHECKPOINT_RESTORED: saved_epoch={split} new_epoch=0'.encode() in resumed.stderr
        checkpoint=(output/'split.chk').read_bytes();assert checkpoint.startswith(b'DOC11CP1')
        assert len(checkpoint)>96 and struct.unpack('<Q',checkpoint[-8:])[0]==fnv(checkpoint[:-8])
        def changed(offset,value):
            b=bytearray(checkpoint);b[offset:offset+8]=struct.pack('<Q',value);return fix_checksum(bytes(b))
        bad=[checkpoint[:95],checkpoint[:-1],checkpoint+b'x',checkpoint[:100]+bytes([checkpoint[100]^1])+checkpoint[101:],fix_checksum(checkpoint[:8]+b'0'*64+checkpoint[72:]),changed(80,0),changed(88,2**64-1),changed(96,255),changed(104,2**64-1),changed(112,2**64-1)]
        for raw in bad:
            (output/'bad.chk').write_bytes(raw)
            rejected=invoke('', ['--load=bad.chk'],require=False);assert rejected.stdout==b''
        rejected=invoke('', ['--load=split.chk'],carries=['frame=frame',*carry[1:]],require=False);assert rejected.stdout==b''
        outside=base/'outside';outside.write_bytes(b'untouched');(output/'link.chk').symlink_to(outside);(output/'linkdir').symlink_to(base,target_is_directory=True);os.mkfifo(output/'fifo')
        for name in ('../outside','link.chk','linkdir/outside','fifo'):
            rejected=invoke('', ['--load='+name],require=False);assert rejected.stdout==b''
        for name in ('../outside','link.chk','linkdir/outside','fifo'):
            invoke('', ['--save='+name],require=False)
        assert outside.read_bytes()==b'untouched'
        good=['--fact=1:reload=true','--fact=1:replacement_xs=[2,3]','--fact=1:replacement_ys=[1,2]']
        reload=invoke('e',add=good)
        ref=subprocess.run([str(reference),str(engine/'radar_chase.doc'),'--through=1',*carry,'--fact=1:action=7',*good],cwd=assets,env=env,capture_output=True,timeout=180)
        assert ref.returncode==0 and reload.stdout==ref.stdout and b'template_next_xs: [2,3]\n' in reload.stdout
        preserved=(output/'full.chk').read_bytes()
        rejected=invoke('e',['--save=full.chk','--audio-dir=wav'],add=[*good[:2],'--fact=1:replacement_ys=[1]'],require=False)
        assert epochs(rejected.stdout)==expected_epochs[:1] and (output/'full.chk').read_bytes()==preserved
        assert sorted(p.name for p in (output/'wav').iterdir())==sorted(f'cue_{e}.wav' for e in cue_epochs)
        # The source-free executable still requires explicitly admitted assets.
        (assets/'levels/showcase_xs.txt').unlink()
        (assets/'levels/showcase_xs.txt').symlink_to(outside)
        rejected=invoke('',require=False);assert rejected.stdout==b''
        assert not list(output.rglob('.doc-tmp-*'))
        shutil.copy2(output/'full.chk',out/'full.chk')
        for f in (output/'wav').iterdir():shutil.copy2(f,out/f.name)
        print(f'DOC11_GAME_EFFECTS_PASS: {len(expected_epochs)} typed epochs, 3 checkpoint splits, {len(bad)+9} malformed/authority rejections, typed reload parity and rollback, {len(cue_epochs)} exact PCM cues; no Rust evaluator in native executable')
if __name__=='__main__':main()
