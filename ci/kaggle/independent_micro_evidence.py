"""Validate returned physical micrograph evidence independently of notebook summary."""
import re
MICRO_GRAPHS=('scalar','arithmetic','wide','mixed')
MICRO_EXECUTABLES=(*MICRO_GRAPHS,'device_loss','gpu_epoch_authority')
ADAPTER=re.compile(rb'(?m)^DOC11_GPU_ADAPTER: [^\n]* physical=1 ')

POOL=re.compile(rb'(?m)^DOC11_GPU_POOL_METRICS: event=(created|grown|reused|closed) admitted=(\d+) released=(\d+) live=(\d+) peak=(\d+)(root,expected):
    for name in MICRO_EXECUTABLES:
        log=(root/(name+'.stderr')).read_bytes()
        if not ADAPTER.search(log):raise ValueError('nonphysical or missing micro adapter: '+name)
        if name in MICRO_GRAPHS:
            if (root/(name+'.actual')).read_bytes()!=(expected/(name+'.expected')).read_bytes():raise ValueError('physical micro parity: '+name)
            if b'DOC11_GPU_DISPATCH:' not in log or b'DOC11_REGIONS: live=0 ' not in log:raise ValueError('missing dispatch/lifetime evidence: '+name)
        else:
            output=(root/(name+'.stdout')).read_bytes()
            marker=b'DOC11_GPU_DEVICE_LOSS_PASS:' if name=='device_loss' else b'DOC11_GPU_EPOCH_AUTHORITY_PASS:'
            if marker not in output:raise ValueError('missing authority result: '+name)
            if name=='gpu_epoch_authority' and any(m not in log for m in (b'DOC11_GPU_RETIRED: outcome=queue-complete',b'DOC11_GPU_RETIRED: outcome=device-lost',b'DOC11_GPU_BUFFER_POOL: action=reused',b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2')):
                raise ValueError('missing submitted-work retirement or reuse evidence')
)

def validate_pool(log):
    rows=POOL.findall(log)
    if not rows or rows[0][0]!=b'created' or rows[-1][0]!=b'closed':
        raise ValueError('missing pool creation or closure evidence')
    previous=(0,0,0,0);growth=False;reuse=False
    for i,(event,*fields) in enumerate(rows):
        a,r,l,p=map(int,fields)
        if max(a,r,l,p)>=2**64 or a-r!=l or p<l or p>a or a<previous[0] or r<previous[1] or p<previous[3]:
            raise ValueError('invalid pool byte accounting')
        if event==b'created' and (i!=0 or not l or r):
            raise ValueError('invalid initial pool')
        if event==b'grown':
            if not (a>previous[0] and r>previous[1] and l>previous[2] and p>l):
                raise ValueError('missing growth overlap or retirement')
            growth=True
        if event==b'reused':
            if (a,r,l,p)!=previous or not l:raise ValueError('reuse changed pool accounting')
            reuse=True
        if event==b'closed' and (i!=len(rows)-1 or l or a!=previous[0] or p!=previous[3]):
            raise ValueError('invalid pool closure')
        previous=(a,r,l,p)
    if not growth or not reuse:raise ValueError('missing actual pool growth or reuse')


def validate_micro_evidence(root,expected):
    for name in MICRO_EXECUTABLES:
        log=(root/(name+'.stderr')).read_bytes()
        if not ADAPTER.search(log):raise ValueError('nonphysical or missing micro adapter: '+name)
        if name in MICRO_GRAPHS:
            if (root/(name+'.actual')).read_bytes()!=(expected/(name+'.expected')).read_bytes():raise ValueError('physical micro parity: '+name)
            if b'DOC11_GPU_DISPATCH:' not in log or b'DOC11_REGIONS: live=0 ' not in log:raise ValueError('missing dispatch/lifetime evidence: '+name)
        else:
            output=(root/(name+'.stdout')).read_bytes()
            marker=b'DOC11_GPU_DEVICE_LOSS_PASS:' if name=='device_loss' else b'DOC11_GPU_EPOCH_AUTHORITY_PASS:'
            if marker not in output:raise ValueError('missing authority result: '+name)
            if name=='gpu_epoch_authority' and any(m not in log for m in (b'DOC11_GPU_RETIRED: outcome=queue-complete',b'DOC11_GPU_RETIRED: outcome=device-lost',b'DOC11_GPU_BUFFER_POOL: action=reused',b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2')):
                raise ValueError('missing submitted-work retirement or reuse evidence')
            if name=='gpu_epoch_authority':validate_pool(log)
