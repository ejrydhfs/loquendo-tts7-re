import sys, math, json
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
import codec210_patched as P
d,info=P.read_container(DEFAULT)
blocks=list(P.iter_blocks(d,info))[:300]
dec=P.Codec210(); A=[];B=[]
for i,(idx,blk) in enumerate(blocks):
    A+=dec.decode_frame(blk,key=info['key']); B+=oracle[i]
print("patched   : corr=%.6f ratio=%.4f"%(corr(A,B),rms(A)/rms(B)))
from ub_port import Full
dec2=Full(); A=[];B=[]
for i,(idx,blk) in enumerate(blocks):
    A+=dec2.decode_frame(blk,key=info['key']); B+=oracle[i]
print("subclass  : corr=%.6f ratio=%.4f"%(corr(A,B),rms(A)/rms(B)))
