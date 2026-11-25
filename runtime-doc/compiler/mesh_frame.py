"""Bounded host transport for already-admitted DOC mesh shader and frame values.
No DOC evaluation, geometry generation, lighting or projection in this module.
"""
import ast
from dataclasses import dataclass
import struct

MAX_BYTES=64*1024*1024
MAGIC=b'DOCMSH01'

@dataclass(frozen=True)
class Frame:
    vertices: tuple
    indices: tuple
    draws: tuple
    clear: tuple
    width: int=640
    height: int=480


def ints(raw):
    data=ast.literal_eval(raw)
    if type(data) is not list or any(type(x) is not int for x in data):
        raise ValueError('expected DOC ints value')
    return tuple(data)


def rows(data,n):
    if len(data)%n:raise ValueError('invalid scene column size')
    return tuple(tuple(data[i:i+n]) for i in range(0,len(data),n))


def snapshots(raw):
    """Read only the typed render values from the native CLI's epoch output."""
    keys={'render_vertices','render_indices','render_draws','render_clear'}
    result=[];values={};epoch=None
    def finish():
        if set(values)!=keys:raise ValueError('incomplete render observation')
        result.append(Frame(rows(values['render_vertices'],12),values['render_indices'],rows(values['render_draws'],10),values['render_clear']))
    if len(raw)>MAX_BYTES:raise ValueError('render observation capacity')
    for line in raw.decode('utf-8').splitlines():
        if line.startswith('epoch: '):
            if epoch is not None:finish()
            elif values:raise ValueError('mixed epoch and non-epoch observations')
            current=int(line[7:]);expected=0 if epoch is None else epoch+1
            if current!=expected:raise ValueError('nonconsecutive render epoch')
            epoch=current;values={}
        else:
            key,sep,value=line.partition(': ')
            if sep and key in keys:
                if key in values:raise ValueError('duplicate render observation')
                values[key]=ints(value)
    finish()
    return tuple(result)


def validate(plan,frame):
    if type(frame.width) is not int or type(frame.height) is not int or not 1<=frame.width<=4096 or not 1<=frame.height<=4096:raise ValueError('framebuffer dimensions')
    if len(frame.clear)!=4 or any(type(x) is not int or not 0<=x<=255 for x in frame.clear):raise ValueError('clear RGBA')
    if not 0<len(frame.draws)<=128:raise ValueError('draw count')
    for d in frame.draws:
        if len(d)!=10 or any(type(x) is not int for x in d):raise ValueError('draw ABI')
        first,count=d[:2]
        if not 0<=first<=len(frame.indices) or not 0<count<=len(frame.indices)-first or count%3:raise ValueError('draw span')
    plan.validate(frame.vertices,[d[2:] for d in frame.draws],frame.indices)


def pack(plan,frames):
    if not 0<len(frames)<=32 or not 0<len(plan.wgsl)<=65536 or any(c not in (9,10,13) and not 32<=c<=126 for c in plan.wgsl):raise ValueError('shader or frame capacity')
    if len(plan.vertex)!=12 or len(plan.draw)!=8:raise ValueError('domain ABI')
    parts=[MAGIC,struct.pack('<II',len(plan.wgsl),len(frames))]
    for d in (*plan.vertex,*plan.draw):
        if d is None:parts.append(struct.pack('<Iii',0,0,0))
        else:
            if len(d)!=2 or any(type(x) is not int for x in d) or not -2147483648<=d[0]<=d[1]<=2147483647:raise ValueError('domain ABI')
            parts.append(struct.pack('<Iii',1,*d))
    parts.append(plan.wgsl);input_bytes=sum(map(len,parts));output_bytes=0
    for f in frames:
        validate(plan,f)
        input_bytes+=24+48*len(f.vertices)+4*len(f.indices)+40*len(f.draws)
        output_bytes+=f.width*f.height*4
        if input_bytes>MAX_BYTES or output_bytes>MAX_BYTES:raise ValueError('batch byte capacity')
        parts.append(struct.pack('<5I4B',f.width,f.height,len(f.vertices),len(f.indices),len(f.draws),*f.clear))
        parts.extend(struct.pack('<12i',*r) for r in f.vertices)
        parts.append(struct.pack('<'+'I'*len(f.indices),*f.indices))
        parts.extend(struct.pack('<II8i',*r) for r in f.draws)
    return b''.join(parts)


def unpack_pixels(raw,frames):
    if len(raw)!=sum(f.width*f.height*4 for f in frames):raise ValueError('incomplete pixel publication')
    out=[];at=0
    for f in frames:
        n=f.width*f.height*4;out.append(raw[at:at+n]);at+=n
    return tuple(out)
