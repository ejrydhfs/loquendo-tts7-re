import sys, math, json
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from ub_port import Full
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=P.read_container(DEFAULT)
a=P.Codec210(); b=Full()
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(x,y):
    n=len(x); mx=sum(x)/n; my=sum(y)/n
    num=sum((p-mx)*(q-my) for p,q in zip(x,y))
    dx=math.sqrt(sum((p-mx)**2 for p in x)); dy=math.sqrt(sum((q-my)**2 for q in y))
    return num/(dx*dy) if dx*dy else 0.0
for i,(idx,blk) in enumerate(list(P.iter_blocks(d,info))[:40]):
    p1=a.decode_frame(blk,key=info['key']); p2=b.decode_frame(blk,key=info['key'])
    if i in (0,37,38,39):
        print("frame %2d patched=%.6f subclass=%.6f p-vs-s=%.6f nzdiff=%d"%(
            i,corr(p1,oracle[i]),corr(p2,oracle[i]),corr(p1,p2),sum(1 for x,y in zip(p1,p2) if x!=y)))
