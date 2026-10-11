import sys, json, math
sys.path.insert(0,'/tmp')
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
oracle=json.load(open('/tmp/oracle_pcm_0_299.json'))
def run(modname,cls=None):
    M=__import__(modname)
    d,info=M.read_container(DEFAULT)
    dec=M.Codec210()
    per=[]
    for i,(idx,blk) in enumerate(list(M.iter_blocks(d,info))[:300]):
        per.append(dec.decode_frame(blk,key=info['key']))
    for lo,hi in ((0,299),(37,299),(40,299),(100,299)):
        A=[x for f in per[lo:hi+1] for x in f]; B=[x for f in oracle[lo:hi+1] for x in f]
        print("  %s frames %d..%d: corr=%.6f ratio=%.4f"%(modname,lo,hi,corr(A,B),rms(A)/rms(B)))
run('codec210_patched')
run('codec210_patchedB')
