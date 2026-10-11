"""Test the 'clear happens after the LTP tap copy' hypothesis:
out[i] = g2*PRE[w0+i] + g1*PRE[w0+i+1] + g0*PRE[w0+i+2] with PRE = the buffer before the clear.
Compare with (i) the cleared-buffer port formula and (ii) the DLL's measured LTP output."""
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
for N in (int(x) for x in sys.argv[1:]):
    dec=P.Codec210()
    for i in range(N):
        dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
    blk=d[150+N*110:150+(N+1)*110]
    f=dec.parse_frame(blk,0x6D)
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[150+i*110:150+(i+1)*110])
    ev=[]; last=[0]
    def hc(uc,a,s,u): last[0]=a
    def hw(uc,acc,addr,size,val,u):
        if EXC<=addr<EXC+640:
            ev.append((PCS.get(last[0],hex(last[0])),(addr-EXC)//4,
                       struct.unpack("<f",struct.pack("<I",val))[0]))
    o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
    o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
    o.decode(ctx, blk)
    L=[[None]*40 for _ in range(4)]
    for pc,pos,val in ev:
        if pc=='ltp': L[pos//40][pos%40]=val
    buf=list(dec.buf)
    print("=== frame %d"%(N))
    for memmove in (True,False):
        b=list(buf)
        if memmove: b[0:P.HIST]=b[160:160+P.HIST]
        one=[]
        for sf in range(4):
            lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
            tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
            pre=list(b)
            cleared=list(b); 
            for k in range(40): cleared[p+k]=0.0
            w0=p-(lag+1)
            # (a) cleared-buffer 3-tap (the port)
            a_=[P._f32(g[2]*cleared[w0+i]+g[1]*cleared[w0+i+1]+g[0]*cleared[w0+i+2]) for i in range(40)]
            # (b) pre-clear 3-tap
            b_=[P._f32(g[2]*pre[w0+i]+g[1]*pre[w0+i+1]+g[0]*pre[w0+i+2]) for i in range(40)]
            one.append((sf,lag,a_,b_))
            gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
            cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
            for i in range(40):
                v=P._f32(a_[i]+P._f32(gg*cb1[i])); b[p+i]=P._f32(v+P._f32(g2v*cb2[i]))
        print("  memmove=%s: %s"%(memmove," ".join(
            "sf%d(lag=%d) port=%.6f preclear=%.6f"%(sf,lag,corr(L[sf],a_),corr(L[sf],b_))
            for sf,lag,a_,b_ in one)))
