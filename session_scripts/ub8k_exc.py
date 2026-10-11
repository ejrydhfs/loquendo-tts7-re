"""Drill into the 8 kHz excitation drift (frames 116..126).

Dumps: per-sub-frame excitation correlation, the history window (0x30012120) and the ±1
CB scratch buffers (0x300125f0 = CB1, 0x3000e0a4 = CB2) vs the port's, plus pitch fields.
"""
import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()

def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0

class Probe(P.Codec210):
    def decode_frame(self, block, key=0x6D, trace=None):
        pcm=P.Codec210.decode_frame(self,block,key,trace)
        self.p_exc=list(self.buf[P.HIST:P.HIST+160])
        self.p_hist=list(self.buf[P.HIST-145:P.HIST])
        return pcm

frames=list(range(116,127))
dec=Probe()
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
o8=None
prev_hist=None
for i,(idx,blk) in enumerate(P.iter_blocks(*P.read_container(DEFAULT))):
    if i>max(frames): break
    o8=o.r32(o.r32(o.r32(ctx+0x28)+4)+4)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    hist_before=fl(0x30012120,145) if i in frames else None
    exc8_before=fl(0x30012364,160) if i in frames else None
    pcm=o.decode(ctx, blk)
    m=dec.decode_frame(blk,key=0x6D)
    if i in frames:
        f=dec.parse_frame(blk)
        R=fl(o.r32(o8+0x3c),160)
        persf=[corr(dec.p_exc[40*s:40*s+40],R[40*s:40*s+40]) for s in range(4)]
        hb=corr(dec.p_hist,hist_before)
        print("frame %3d exc=%.6f  per-sf=[%s]  hist_before_corr=%.6f  g8=%d  sub8(lag_d,idx,b3)=%s"%(
            i, corr(dec.p_exc,R), ", ".join("%.4f"%c for c in persf), hb, f["energy8"],
            [(a,b,c) for a,b,c,_ in f["sub8"]]))
