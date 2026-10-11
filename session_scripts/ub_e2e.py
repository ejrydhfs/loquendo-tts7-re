import sys, json, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from ub_port import Full
import codec210 as C
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
dec=Full()
A=[];B=[]
blocks=list(C.iter_blocks(d,info))[:300]
for i,(idx,blk) in enumerate(blocks):
    pcm=dec.decode_frame(blk,key=info['key'])
    ref=oracle[i]
    if i%40==0 or i in (37,38,39):
        print("frame %3d rms mine=%9.2f ref=%9.2f corr=%.6f"%(i,rms(pcm),rms(ref),corr(pcm,ref)))
    A+=pcm; B+=ref
print("OVERALL frames 0..299 corr=%.6f  rms %.4f / %.4f  ratio=%.4f"%(corr(A,B),rms(A),rms(B),rms(A)/rms(B)))
