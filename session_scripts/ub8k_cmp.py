"""Per-frame divergence finder for the 8 kHz chain (drift frames).

For frames N the DLL's post-frame 8 kHz work arrays are compared with the port's state:
  0x300128a0 = the 5-stage VQ accumulator (frame's LSF), 0x30012870 = the LPC (last sf),
  0x30012930 = the LPC synthesis state, 0x30011ea0 = sig8, 0x30012364 = the excitation,
  0x30012a20 = the tilt array, 0x300128d0 / 0x30012900 = interp work arrays.
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
    """Records the 8 kHz state after each frame."""
    def synth8(self, lsf_cur):
        self.p_lsf = list(lsf_cur)
        # replicate the per-sub-frame LPC so we can compare with the DLL's obj8+0x50
        self.p_lpc = []
        prev = lsf_cur if self.lsf8_first else self.lsf8_prev
        for sf in range(4):
            li = P.lsf_stabilise(P.lsf_interp(prev, lsf_cur, 10, sf, 4), 0.05)
            self.p_lpc.append(P.lsf_to_lpc(li))
        r = P.Codec210.synth8(self, lsf_cur)
        self.p_sig8 = list(r)
        return r
    def decode_frame(self,*a,**k):
        pcm=P.Codec210.decode_frame(self,*a,**k)
        self.p_state=list(self.lpc_mem8[:10])
        self.p_exc=list(self.buf[P.HIST:P.HIST+160])
        return pcm

ORACLES={}
def oracle_state(N):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N+1):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    return dict(lsf=fl(0x300128a0,10), lpc=fl(0x30012870,10), state=fl(0x30012930,10),
                sig8=fl(0x30011ea0,160), exc=fl(0x30012364,160), tilt=fl(0x30012a20,4),
                w1=fl(0x300128d0,10), w2=fl(0x30012900,10))

frames=list(range(116,131))+[170,171,172,173,174,175,176,177,178,179,37,38]
dec=Probe()
N=0
for i,(idx,blk) in enumerate(P.iter_blocks(*P.read_container(DEFAULT))):
    if i>max(frames): break
    dec.decode_frame(blk,key=0x6D)
    if i in frames:
        R=oracle_state(i)
        M=dict(lsf=dec.p_lsf, lpc=dec.p_lpc[3], state=dec.p_state, sig8=dec.p_sig8,
               exc=dec.p_exc, tilt=dec.tilt8)
        print("frame %3d  " % i + "  ".join(
            "%s=%.6f"%({ 'lsf':'lsf','lpc':'lpc','state':'state','sig8':'sig8','exc':'exc','tilt':'tilt'}[k],
                       corr(M[k],R[k])) for k in ('lsf','lpc','state','sig8','exc','tilt')))
