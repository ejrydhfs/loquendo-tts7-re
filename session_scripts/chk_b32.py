import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
class Patched(P.Codec210):
    def band32(self,f,exc16,tilt16):
        self.norms=[]
        lsf_cur=f["lsf32"]; prev=lsf_cur if self.lsf32_prev is None else self.lsf32_prev
        # replicate to grab norms
        import codec210_patched as Q
        ps=[]
        for sf in range(4):
            li=Q.lsf_stabilise(Q.lsf_interp(prev,lsf_cur,8,sf,4),0.05); a=Q.lsf_to_lpc(li)
            ps.append((a,)+Q._tilt_pair(a))
        for sf in range(4):
            a,s,d32=ps[sf]; self.norms.append((s+0.01)/(0.01+d32))
        r=P.Codec210.band32(self,f,exc16,tilt16)
        self.st32=list(r); return r
    def decode_frame(self,*a,**k):
        pcm=P.Codec210.decode_frame(self,*a,**k); self.st_pcm=pcm; return pcm
o=Oracle(); ctx=o.open_decoder(32000,0x6D); dec=Patched()
for i in range(39):
    blk=d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]
    pcm=o.decode(ctx,blk); m=dec.decode_frame(blk,key=0x6D)
o32=o.r32(ctx+0x28)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
print("patched norm32 (uses s32) =",["%.5g"%x for x in dec.norms])
print("oracle  norm32            = [6.51323, 6.83571, 7.10934, 7.3074]")
r32=fl(o.r32(o32+0x34),320)
m32=dec.st32
num=sum(x*y for x,y in zip(m32,r32)); dd=math.sqrt(sum(x*x for x in m32)*sum(y*y for y in r32))
print("corr(my syn32, oracle syn32)=%.6f  rms %.4f/%.4f"%(num/dd,(sum(x*x for x in m32)/320)**.5,(sum(y*y for y in r32)/320)**.5))
