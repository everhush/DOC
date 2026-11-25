"""Verify actual WebGPU dispatch/frontier/epoch accounting, not shader presence."""
import re

def trace(raw):
    """Count actual completed device dispatches and committed recurrence epochs."""
    epochs=[];current=[];dispatches=0;pending=[]
    for line in raw.splitlines():
        if line.startswith(b'DOC11_GPU_DISPATCH:'):
            m=re.fullmatch(rb'DOC11_GPU_DISPATCH: lanes=(\d+) workgroups=(\d+)',line)
            if not m:raise ValueError('malformed device trace')
            lanes,groups=map(int,m.groups())
            if not lanes or groups!=(lanes+63)//64:raise ValueError('invalid workgroup accounting')
            dispatches+=1;pending.append((dispatches,lanes))
        elif line.startswith(b'DOC11_GPU_FRONTIER:'):
            m=re.fullmatch(rb'DOC11_GPU_FRONTIER: cpu=(\d+) gpu=(\d+) concurrent=([01])',line)
            if not m:raise ValueError('malformed frontier trace')
            cpu,gpu,concurrent=map(int,m.groups())
            if not pending or pending[0][1]!=gpu or (concurrent and not cpu):raise ValueError('dispatch/frontier mismatch')
            ordinal,_=pending.pop(0);current.append((ordinal,cpu,gpu,concurrent))
        elif line.startswith(b'DOC11_RECURRENCE_EPOCH:'):
            m=re.fullmatch(rb'DOC11_RECURRENCE_EPOCH: (\d+) evaluations=(\d+) frontiers=(\d+) parallel=(\d+)',line)
            if not m:raise ValueError('malformed epoch trace')
            ep,ev,frontiers,parallel=map(int,m.groups())
            if ep!=len(epochs) or pending or len(current)>frontiers or sum(c+g for _,c,g,_ in current)>ev or parallel>frontiers:raise ValueError('invalid epoch accounting')
            epochs.append({'epoch':ep,'evaluations':ev,'frontiers':frontiers,'parallel':parallel,'gpu_lanes':sum(g for _,_,g,_ in current),'mixed_frontiers':sum(bool(c and g) for _,c,g,_ in current),'concurrent_frontiers':sum(k for _,_,_,k in current),'dispatches':[n for n,_,_,_ in current]});current=[]
    if pending or current:raise ValueError('uncommitted device trace in successful execution')
    return epochs

def first_successor_dispatch(epochs):
    for e in epochs[1:]:
        if e['dispatches']:return e['epoch'],e['dispatches'][0]
    raise ValueError('no successor GPU work')

def self_test():
    raw=b'DOC11_GPU_DISPATCH: lanes=64 workgroups=1\nDOC11_GPU_FRONTIER: cpu=32 gpu=64 concurrent=1\nDOC11_RECURRENCE_EPOCH: 0 evaluations=96 frontiers=1 parallel=1\nDOC11_GPU_DISPATCH: lanes=65 workgroups=2\nDOC11_GPU_FRONTIER: cpu=1 gpu=65 concurrent=1\nDOC11_RECURRENCE_EPOCH: 1 evaluations=66 frontiers=1 parallel=0\n'
    e=trace(raw);assert first_successor_dispatch(e)==(1,2) and e[1]['gpu_lanes']==65 and e[1]['mixed_frontiers']==1
    for broken in [raw.replace(b'workgroups=2',b'workgroups=1'),raw.replace(b'gpu=65',b'gpu=64'),raw.replace(b'EPOCH: 1',b'EPOCH: 2'),raw.rsplit(b'DOC11_RECURRENCE_EPOCH:',1)[0],raw.replace(b'evaluations=66',b'evaluations=65')]:
        try:trace(broken)
        except ValueError:continue
        raise AssertionError('bad trace admitted')
    print('DOC11_GPU_TRACE_PASS: 1 positive, 5 malformed traces rejected')

if __name__=='__main__':self_test()
