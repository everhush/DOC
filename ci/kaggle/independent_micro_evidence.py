"""Validate returned physical micrograph evidence independently of notebook summary."""
import re
MICRO_GRAPHS=('scalar','arithmetic','wide','mixed')
MICRO_EXECUTABLES=(*MICRO_GRAPHS,'device_loss','gpu_epoch_authority','gpu_graph_generation')
ADAPTER=re.compile(rb'(?m)^DOC11_GPU_ADAPTER: [^\n]* physical=1 ')

POOL=re.compile(rb'(?m)^DOC11_GPU_POOL_METRICS: event=(created|grown|reused|closed) admitted=(\d+) released=(\d+) live=(\d+) peak=(\d+)$')

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


DESTROY_QUEUE=b'DOC11_WGPU_QUEUE_RETIRED: destroy=1'
DESTROY_CONFIRMED=b'DOC11_WGPU_DESTROY_CONFIRMED: provider invalidation after queue retirement'
LOSS_PROBE=(b'DOC11_WGPU_LOSS_PROBE: status=success type=validation',b'Validation Error',b'',b'Caused by:',b'  In wgpuDeviceCreateBuffer',b'    Parent device is lost')
ABANDON_QUEUE=b'DOC11_WGPU_QUEUE_RETIRED: destroy=0'


def validate_destroy(log,callback_prefix):
    lines=log.splitlines()
    try:
        queue=lines.index(DESTROY_QUEUE)
        confirmed=lines.index(DESTROY_CONFIRMED)
    except ValueError as exc:
        raise ValueError('missing destroy queue acknowledgement or confirmation') from exc
    callbacks=[i for i,line in enumerate(lines) if re.fullmatch(re.escape(callback_prefix)+rb': reason=\d+',line)]
    probe=any(tuple(lines[i:i+len(LOSS_PROBE)])==LOSS_PROBE and i+len(LOSS_PROBE)<=confirmed for i in range(queue+1,confirmed))
    if not queue<confirmed or not (any(i<confirmed for i in callbacks) or probe):
        raise ValueError('destroy confirmation precedes queue acknowledgement or actual provider invalidation')
    return lines,confirmed


def validate_compute_retirement(log,submitted):
    lines,confirmed=validate_destroy(log,b'DOC11_GPU_LOST_CALLBACK')
    if submitted:
        try:
            abandoned=lines.index(ABANDON_QUEUE)
            completed=lines.index(b'DOC11_GPU_RETIRED: outcome=queue-complete')
            lost=lines.index(b'DOC11_GPU_RETIRED: outcome=device-lost')
        except ValueError as exc:
            raise ValueError('missing failed-submission queue/loss evidence') from exc
        if not abandoned<completed<confirmed<lost:
            raise ValueError('failed submission retirement ordering')


def validate_micro_evidence(root,expected):
    for name in MICRO_EXECUTABLES:
        log=(root/(name+'.stderr')).read_bytes()
        adapters=[line for line in log.splitlines() if line.startswith(b'DOC11_GPU_ADAPTER:')]
        if not adapters or not all(ADAPTER.search(line) for line in adapters):raise ValueError('nonphysical or missing micro adapter: '+name)
        if name in MICRO_GRAPHS:
            if (root/(name+'.actual')).read_bytes()!=(expected/(name+'.expected')).read_bytes():raise ValueError('physical micro parity: '+name)
            if b'DOC11_GPU_DISPATCH:' not in log or b'DOC11_REGIONS: live=0 ' not in log:raise ValueError('missing dispatch/lifetime evidence: '+name)
        elif name=='gpu_graph_generation':
            output=(root/(name+'.stdout')).read_bytes()
            closed=[tuple(map(int,row[1:])) for row in POOL.findall(log) if row[0]==b'closed']
            if b'DOC11_GPU_GRAPH_GENERATION_PASS:' not in output or len(adapters)!=4 or log.count(b'DOC11_GPU_DISPATCH:')<6 or len(closed)!=4 or not all(a==r and l==0 and 0<p<=a for a,r,l,p in closed) or b'DOC11_GPU_INJECTED_FAILURE: dispatch=1' not in log:
                raise ValueError('missing graph replacement, dispatch or retired pool evidence')
        else:
            output=(root/(name+'.stdout')).read_bytes()
            marker=b'DOC11_GPU_DEVICE_LOSS_PASS:' if name=='device_loss' else b'DOC11_GPU_EPOCH_AUTHORITY_PASS:'
            if marker not in output:raise ValueError('missing authority result: '+name)
            validate_compute_retirement(log,name=='gpu_epoch_authority')
            if name=='gpu_epoch_authority' and any(m not in log for m in (b'DOC11_GPU_RETIRED: outcome=queue-complete',b'DOC11_GPU_RETIRED: outcome=device-lost',b'DOC11_GPU_BUFFER_POOL: action=reused',b'DOC11_GPU_DISPATCH: lanes=96 workgroups=2')):
                raise ValueError('missing submitted-work retirement or reuse evidence')
            if name=='gpu_epoch_authority':validate_pool(log)
