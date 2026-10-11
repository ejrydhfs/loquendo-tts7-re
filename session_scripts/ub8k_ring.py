"""Verify the lag-periodic ring rule for the 8 kHz LTP tap window.

Measured (frame 118 sf1, lag=20, w0=h-(lag+1)=p-21): the DLL's tap window is
  S[0] = buf[w0] ;  S[k] = buf[w0 + 1 + ((k-1) mod lag)]  for k >= 1
i.e. the window is a cyclic read of the lag-sample ring that ends just before the current
sub-frame, with the one sample before the ring in front.  The current sub-frame is never read.
"""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
EXC=0x30012364
PCS={0x10009b6f:'clear',0x10009c0d:'ltp',0x10009f3e:'cb1',0x10009ff1:'cb2'}
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=(sum((x-ma)**2 for x in a))**.5; db=(sum((y-mb)**2 for y in b))**.5
    return num/(da*db) if da*db else 0.0
def ring(buf,w0,lag,n=120):
    out=[buf[w0]]
    for k in range(1,n):
        out.append(buf[w0+1+((k-1)%lag)])
    return out
for N in (int(x) for x in sys.argv[1:]):
    dec=P.Codec210(); snap=[]
    for i in range(N+1):
        dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D); snap.append(list(dec.buf))
    pre=snap[N-1]
    f=dec.parse_frame(d[150+N*110:150+(N+1)*110],0x6D)
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N): o.decode(ctx, d[150+i*110:150+(i+1)*110])
    ev=[]; last=[0]
    def hc(uc,a,s,u): last[0]=a
    def hw(uc,acc,addr,size,val,u):
        if EXC<=addr<EXC+640:
            ev.append((PCS.get(last[0],hex(last[0])),(addr-EXC)//4,
                       struct.unpack("<f",struct.pack("<I",val))[0]))
    o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
    o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
    o.decode(ctx, d[150+N*110:150+(N+1)*110])
    L=[[None]*40 for _ in range(4)]
    for pc,pos,val in ev:
        if pc=='ltp': L[pos//40][pos%40]=val
    b=list(pre); b[0:P.HIST]=b[160:160+P.HIST]
    print("=== frame %d g8=%d"%(N,f["energy8"]))
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
        tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        for k in range(40): b[p+k]=0.0
        w0=p-(lag+1)
        old=[P._f32(g[2]*b[w0+i]+g[1]*b[w0+i+1]+g[0]*b[w0+i+2]) for i in range(40)]
        S=ring(b,w0,lag,120)
        new=[P._f32(g[2]*S[i]+g[1]*S[40+i]+g[0]*S[80+i]) for i in range(40)]
        R=L[sf]
        if any(x is None for x in R): print("  sf%d nodata"%sf); continue
        print("  sf%d lag=%3d idx=%3d  port(old)=%.6f  ring(new)=%.6f   (dll rms %.5g)"%(
            sf,lag,idx,corr(R,old),corr(R,new),(sum(x*x for x in R)/40)**.5))
        # advance the port state with the ring rule so later sub-frames stay exact
        gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        for i in range(40):
            v=P._f32(new[i]+P._f32(gg*cb1[i])); b[p+i]=P._f32(v+P._f32(g2v*cb2[i]))
