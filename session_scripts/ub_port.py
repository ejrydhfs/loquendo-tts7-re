"""Prototype: full codec210 chain incl. the 16k coded band and the 32k noise band."""
import sys, json, struct, os, math
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C

DLL="/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/bin/LTTS7Codec210.dll"
def load_table(va, n):
    import pefile
    pe=pefile.PE(DLL); data=open(DLL,'rb').read(); rva=va-0x10000000
    for s in pe.sections:
        if s.VirtualAddress<=rva<s.VirtualAddress+max(s.SizeOfRawData,s.Misc_VirtualSize):
            off=s.PointerToRawData+(rva-s.VirtualAddress)
            return list(struct.unpack("<%db"%n, data[off:off+n]))
    raise ValueError
CB16 = load_table(0x10022470, 1024)        # 128 x 8 int8

SCALE=1.0/32.0
def codebook(pairs, dim, table):
    out=[0.0]*(dim*len(pairs))
    for k,(s,idx) in enumerate(pairs):
        f=(-1.0 if s else 1.0)*SCALE
        b=idx*dim
        for j in range(dim):
            out[k*dim+j]+=table[b+j]*f
    return out

def tilt_vals(lpc, order):
    s=1.0; d=1.0
    for i in range(0,order-1,2):
        d+=lpc[i+1]-lpc[i]; s+=lpc[i]+lpc[i+1]
    return s,d

def ec0(p, n):
    """FUN_10002ec0: sqrt(sum(p[i]^2)/n + 0.1)"""
    s=0.0
    for x in p: s+=x*x
    return math.sqrt(s/n + 0.1)

class Full(C.Codec210):
    def reset(self):
        super().reset()
        self.lsf8_first=True
        self.lsf16_prev=None; self.lsf32_prev=None
        self.mem16=[0.0]*8; self.mem32=[0.0]*8
        self.b34_16=[0.0]*160
        self.tilt8=[0.0]*4
        self.tail_b16=[0.0]*64; self.tail_b32=[0.0]*64

    def synth8_tilt(self, lsf_cur):
        out=[]; mem=list(self.lpc_mem8); prev=self.lsf8_prev; first=self.lsf8_first
        if first: prev=lsf_cur
        for sf in range(4):
            lsf_i=C.lsf_stabilise(C.lsf_interp(prev,lsf_cur,10,sf,4),0.05)
            a=C.lsf_to_lpc(lsf_i)
            _t,d8=tilt_vals(a,10); self.tilt8[sf]=d8
            x=self.buf[C.HIST+40*sf:C.HIST+40*sf+40]
            y,mem=C.lpc_synth(a,mem,x); out.extend(y)
        self.lpc_mem8=mem; self.lsf8_prev=lsf_cur; self.lsf8_first=False
        return out

    def band16(self, f, exc8):
        lsf_cur=f["lsf16"]
        ps=[]
        prev=self.lsf16_prev if self.lsf16_prev is not None else lsf_cur
        for sf in range(4):
            lsf_i=C.lsf_stabilise(C.lsf_interp(prev,lsf_cur,8,sf,4),0.05)
            a=C.lsf_to_lpc(lsf_i); ps.append((a,)+tilt_vals(a,8))
        block2=list(exc8)
        exc=[0.0]*160
        for sf in range(4):
            a,t,d=ps[sf]
            norm=(self.tilt8[sf]+0.01)/(0.01+d)
            energy=ec0(block2[40*sf:40*sf+40],40)
            g4=f["sub16"][sf][0]
            gg=math.exp(g4*0.27027027027-0.15556)
            gain=(energy+1.0)*(gg/norm)
            pr=f["sub16"][sf][1]
            v1=codebook(pr[0:5],8,CB16); v2=codebook(pr[5:10],8,CB16)
            exc[40*sf:40*sf+40]=[v1[i]*gain+v2[i]*(gain*0.4) for i in range(40)]
        self.exc16_pre=list(exc)          # obj16+0x48 (the excitation, fed to the 32 kHz level)
        mem=list(self.mem16)
        for sf in range(4):
            y,mem=C.lpc_synth(ps[sf][0],mem,exc[40*sf:40*sf+40])
            exc[40*sf:40*sf+40]=y
        self.mem16=mem; self.lsf16_prev=lsf_cur
        self.b34_16=list(exc); self.ub_exc16=list(exc)
        return exc,ps

    def band32(self, f, exc16, ps16):
        lsf_cur=f["lsf32"]
        ps=[]
        prev=self.lsf32_prev if self.lsf32_prev is not None else lsf_cur
        for sf in range(4):
            lsf_i=C.lsf_stabilise(C.lsf_interp(prev,lsf_cur,8,sf,4),0.05)
            a=C.lsf_to_lpc(lsf_i); ps.append((a,)+tilt_vals(a,8))
        tilt_child=[ps16[sf][1] for sf in range(4)]
        src=[0.0]*320
        for i in range(160): src[2*i]=2.0*exc16[i]
        exc=[0.0]*320
        for sf in range(4):
            a,t,d=ps[sf]
            norm=(tilt_child[sf]+0.01)/(0.01+d)
            gain5=math.exp((f["ref32"][sf]-10)*0.125)
            amp=gain5/norm
            ramp=1.0
            for i in range(80):
                exc[80*sf+i]=((ramp*amp)*0.7)*src[80*sf+i]
                ramp*=(-1.0)
        self.exc32_pre=list(exc)
        mem=list(self.mem32)
        for sf in range(4):
            y,mem=C.lpc_synth(ps[sf][0],mem,exc[80*sf:80*sf+80])
            exc[80*sf:80*sf+80]=y
        self.mem32=mem; self.lsf32_prev=lsf_cur
        self.b34_32=list(exc)
        return exc

    def decode_frame(self, block, key=0x6D, trace=None):
        f=self.parse_frame(block,key)
        self.buf[0:C.HIST]=self.buf[160:160+C.HIST]
        g8=f["energy8"]
        for sf in range(4):
            lag_d,idx,b3,cbi=f["sub8"][sf]
            p=C.HIST+40*sf
            gain=self.exc_gain(g8,b3)
            for i in range(40): self.buf[p+i]=0.0
            ltp=self.ltp(p,lag_d+17,idx)
            cb1=self.codebook(cbi[0:8],0); cb2=self.codebook(cbi[8:16],0)
            g1=gain; g2=C._f32(g1*C.CB2_RATIO)
            for i in range(40):
                v=C._f32(ltp[i]+C._f32(g1*cb1[i]))
                self.buf[p+i]=C._f32(v+C._f32(g2*cb2[i]))
        exc8=self.buf[C.HIST:C.HIST+160]
        sig8=self.synth8_tilt(f["lsf10"]); self.sig8_last=sig8
        exc16,ps16=self.band16(f,exc8)
        a16=C.band_filter(sig8,self.cf_a,320,64,self.tail_a16,[0.0]*1088)
        b16=C.band_filter(exc16,self.cf_b,320,64,self.tail_b16,[0.0]*1088)
        ring32=[max(-32768.0,min(32767.0,2.0*(x-y))) for x,y in zip(a16,b16)]
        exc32=self.band32(f,self.exc16_pre,ps16)
        a32=C.band_filter(ring32,self.cf_a,640,64,self.tail_a32,[0.0]*2048); self.ub_A32=a32
        b32=C.band_filter(exc32,self.cf_b,640,64,self.tail_b32,[0.0]*2048); self.ub_B32=b32
        pcm=[C.clamp_int16(2.0*(x-y)) for x,y in zip(a32,b32)]
        if trace is not None:
            trace.update(f); trace['stages']={'upper':'ported'}
        return pcm
