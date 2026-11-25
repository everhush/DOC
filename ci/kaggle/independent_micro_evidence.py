"""Validate returned physical micrograph evidence independently of notebook summary."""
import re
MICRO_GRAPHS=('scalar','arithmetic','wide','mixed')
MICRO_EXECUTABLES=(*MICRO_GRAPHS,'device_loss','gpu_epoch_authority')
ADAPTER=re.compile(rb'(?m)^DOC11_GPU_ADAPTER: [^\n]* physical=1 ')

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
