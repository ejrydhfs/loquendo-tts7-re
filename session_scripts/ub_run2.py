import sys, json, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from ub_port import Full
import codec210 as C
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_38.json'))
dec=Full()
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
tot_a=[]; tot_b=[]
for i,(idx,blk) in enumerate(C.iter_blocks(d,info)):
    if i>38: break
    pcm=dec.decode_frame(blk,key=info['key'])
    ref=oracle[i]
    if i in (0,1,2,36,37,38):
        print("frame %2d  mine=%8.2f ref=%8.2f corr=%.4f | exc16=%.4g exc32=%.4g syn16=%.4g syn32=%.4g"%(
            i,rms(pcm),rms(ref),corr(pcm,ref),rms(dec.b34_16),rms(dec.b34_32),rms(dec.b34_16),rms(dec.b34_32)))
    tot_a+=pcm; tot_b+=ref
print("OVERALL corr=%.4f"%corr(tot_a,tot_b))
