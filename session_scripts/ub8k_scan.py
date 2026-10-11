"""For the small-lag (drifting) sub-frames, scan tap-base offsets and tap patterns to find
which geometry reproduces the DLL's LTP output exactly."""
import sys, struct, itertools
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
targets=[(118,1),(118,3),(119,1),(119,2),(121,0)]
for N,SF in targets:
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
    # advance the port's buf to sub-frame SF (using the port formulas)
    buf=list(dec.buf); buf[0:P.HIST]=buf[160:160+P.HIST]
    for sf in range(SF):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
        tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        for k in range(40): buf[p+k]=0.0
        w0=p-(lag+1)
        o_=[P._f32(g[2]*buf[w0+i]+g[1]*buf[w0+i+1]+g[0]*buf[w0+i+2]) for i in range(40)]
        gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        for i in range(40):
            v=P._f32(o_[i]+P._f32(gg*cb1[i])); buf[p+i]=P._f32(v+P._f32(g2v*cb2[i]))
    sf=SF; lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
    tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
    for k in range(40): buf[p+k]=0.0
    w0=p-(lag+1); R=L[sf]
    best=[]
    for dlt in range(-160,161):
        a_=[P._f32(g[2]*buf[w0+dlt+i]+g[1]*buf[w0+dlt+i+1]+g[0]*buf[w0+dlt+i+2]) for i in range(40)]
        best.append((corr(R,a_),dlt))
    best.sort(reverse=True)
    print("frame %d sf%d lag=%d: best offsets %s"%(N,sf,lag,[(round(c,5),d2) for c,d2 in best[:4]]))
