import sys, json, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
dec=Full()
low=[]
modes={}
for i,(idx,blk) in enumerate(list(C.iter_blocks(d,info))[:300]):
    f=dec.parse_frame(blk,info['key'])
    modes[i]=(f['mode8'],f['f16'],f['mode16'],f['f32'],f['mode32'])
    pcm=dec.decode_frame(blk,key=info['key'])
    c=corr(pcm,oracle[i])
    if c<0.99: low.append((i,round(c,4),modes[i]))
print("frames with corr<0.99:",low[:40])
print("distinct mode tuples:",set(modes.values()))
