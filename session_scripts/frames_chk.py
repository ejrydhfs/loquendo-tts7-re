import sys, json, math
sys.path.insert(0,'/tmp')
import codec210_patched as P
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=P.read_container(DEFAULT)
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
dec=P.Codec210(); cs=[]
for i,(idx,blk) in enumerate(list(P.iter_blocks(d,info))[:299]):
    pcm=dec.decode_frame(blk,key=info['key'])
    cs.append(corr(pcm,oracle[i]))
print("frames 36..50:",["%.4f"%c for c in cs[36:51]])
bad=[(i,round(c,4)) for i,c in enumerate(cs) if c<0.99]
print("n_bad=%d  max_bad_index=%d"%(len(bad),max(i for i,_ in bad)))
print("bad beyond 36:",[b for b in bad if b[0]>36])
print("mean corr 37..298 = %.6f"% (sum(cs[37:])/len(cs[37:])))
