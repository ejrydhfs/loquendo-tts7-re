import sys, json, math
sys.path.insert(0,'/tmp')
import codec210_patchedB as P
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=P.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
dec=P.Codec210(); A=[];B=[]
for i,(idx,blk) in enumerate(list(P.iter_blocks(d,info))[:300]):
    pcm=dec.decode_frame(blk,key=info['key']); A+=pcm; B+=oracle[i]
    if i in (37,38,39,120): print("frame %3d corr=%.6f"%(i,corr(pcm,oracle[i])))
print("variantB OVERALL 0..299 corr=%.6f ratio=%.4f"%(corr(A,B),rms(A)/rms(B)))
