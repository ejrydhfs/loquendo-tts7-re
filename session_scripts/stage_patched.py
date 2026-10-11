import sys, struct, math
sys.path.insert(0,'/tmp')
import codec210_patched as P
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
class Patched(P.Codec210):
    def band32(self, f, exc16):
        r=P.Codec210.band32(self,f,exc16); self.st_exc32=list(r); return r
    def decode_frame(self, *a, **k):
        pcm=P.Codec210.decode_frame(self,*a,**k); self.st_pcm=pcm; return pcm
for N in (37,38,39):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    dec=Patched()
    for i in range(N+1):
        blk=d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]
        pcm=o.decode(ctx, blk)
        m=dec.decode_frame(blk,key=0x6D)
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    R=dict(exc16=fl(o.r32(o16+0x48),160), syn16=fl(o.r32(o16+0x34),160),
           exc32=fl(o.r32(o32+0x48),320), syn32=fl(o.r32(o32+0x34),320),
           B32=fl(o.r32(o32+0x3c),640), pcm=pcm)
    M=dict(exc16=dec._exc16_pre, syn16=[0.0], exc32=dec.st_exc32, syn32=[0.0], B32=[0.0], pcm=dec.st_pcm)
    print("frame %d"%N, " ".join("%s=%.6f"%(k,corr(M[k],R[k])) for k in ('exc16','exc32','pcm')))
