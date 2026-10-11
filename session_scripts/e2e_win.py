import sys, json, math
sys.path.insert(0,'/tmp')
import codec210_ring as P
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=P.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
dec=P.Codec210(); per=[]
for i,(idx,blk) in enumerate(list(P.iter_blocks(d,info))[:300]):
    per.append(dec.decode_frame(blk,key=info['key']))
import collections
for lo in range(0,300,10):
    hi=min(lo+9,299)
    A=[x for f in per[lo:hi+1] for x in f]; B=[x for f in oracle[lo:hi+1] for x in f]
    c=corr(A,B)
    if lo>=100 and c<0.999 or lo in (0,110,120,130,160,170,180,230,240,250,260,270,280,290):
        print("  %3d-%3d corr=%.6f"%(lo,hi,c))
