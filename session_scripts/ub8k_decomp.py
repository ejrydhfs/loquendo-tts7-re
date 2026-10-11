"""Reconstruct the per-sub-frame excitation decomposition from the DLL's write timeline.

Watches writes to the 8 kHz excitation buffer (0x30012364, 160 floats) and attributes each
written value to the code address that produced it, then compares the LTP / CB1 / CB2
increments with the port's own per-sub-frame components.
"""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_EBX
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
EXC=0x30012364

class Probe(P.Codec210):
    """Records the port's own components per sub-frame."""
    def ltp(self, p, lag, idx):
        r=P.Codec210.ltp(self,p,lag,idx)
        self.c_ltp=list(r); self.c_win=list(self.buf[max(0,p-lag-1):max(0,p-lag-1)+42])
        return r
    def decode_frame(self, block, key=0x6D, trace=None):
        self.comps=[]
        # replicate the port's loop to capture cb1/cb2
        f=self.parse_frame(block,key)
        self.buf[0:P.HIST]=self.buf[160:160+P.HIST]
        g8=f["energy8"]
        for sf in range(4):
            lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf
            gain=self.exc_gain(g8,b3)
            for i in range(40): self.buf[p+i]=0.0
            ltp=self.ltp(p,lag_d+17,idx)
            cb1=self.codebook(cbi[0:8],0); cb2=self.codebook(cbi[8:16],0)
            g1=gain; g2=P._f32(g1*P.CB2_RATIO)
            self.comps.append(dict(sf=sf,lag=lag_d+17,idx=idx,b3=b3,g1=g1,g2=g2,
                                   ltp=list(ltp),cb1=list(cb1),cb2=list(cb2)))
            for i in range(40):
                v=P._f32(ltp[i]+P._f32(g1*cb1[i]))
                self.buf[p+i]=P._f32(v+P._f32(g2*cb2[i]))
        return P.Codec210.decode_frame(self,block,key,trace)

dec=Probe()
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i,(idx,blk) in enumerate(P.iter_blocks(*P.read_container(DEFAULT))):
    if i>118: break
    ev=[]
    if i==118:
        last=[0]
        def hc(uc,a,s,u): last[0]=a
        def hw(uc,acc,addr,size,val,u):
            if EXC<=addr<EXC+640:
                ev.append((last[0],(addr-EXC)//4,struct.unpack("<f",struct.pack("<I",val))[0]))
        o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
        o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
    pcm=o.decode(ctx, blk)
    m=dec.decode_frame(blk,key=0x6D)
    if i==118:
        from collections import Counter
        print("write pcs:",Counter(p for p,_,_ in ev))
        # group events per sub-frame by position (sample index // 40)
        import math
        for sf in range(4):
            ltp=[None]*40; cb1=[0.0]*40; cb2=[0.0]*40
            state=[0.0]*40
            for pc,pos,val in [e for e in ev if 40*sf<=e[1]<40*sf+40]:
                k=pos-40*sf
                if pc in (0x10009b6f,):           # clear
                    state[k]=0.0
                elif pc in (0x10009c0d,0x10009c35,0x10007210):  # LTP output
                    state[k]=val; ltp[k]=val
                elif pc in (0x10009f3e,0x10009f44):            # CB1 accumulate
                    cb1[k]=val-state[k]; state[k]=val
                elif pc in (0x10009ff1,):                      # CB2 accumulate
                    cb2[k]=val-state[k]; state[k]=val
            c=dec.comps[sf]
            print("  sf%d lag=%d idx=%d g1=%.6g g2=%.6g"%(sf,c["lag"],c["idx"],c["g1"],c["g2"]))
            mcb1=[c["g1"]*x for x in c["cb1"]]; mcb2=[c["g2"]*x for x in c["cb2"]]
            print("     dll ltp  = %s"%["%.6g"%x for x in ltp[:6]])
            print("     my  ltp  = %s"%["%.6g"%x for x in c["ltp"][:6]])
            print("     dll cb1* = %s"%["%.6g"%x for x in cb1[:6]])
            print("     my  cb1* = %s"%["%.6g"%x for x in mcb1[:6]])
            print("     dll cb2* = %s"%["%.6g"%x for x in cb2[:6]])
            print("     my  cb2* = %s"%["%.6g"%x for x in mcb2[:6]])
