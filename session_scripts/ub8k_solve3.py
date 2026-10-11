"""Correct (3-tap) triangular solve for the DLL's tap values inside the current sub-frame."""
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
N=int(sys.argv[1]) if len(sys.argv)>1 else 118
dec=P.Codec210()
for i in range(N):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
blk=d[150+N*110:150+(N+1)*110]
f=dec.parse_frame(blk,0x6D)
pre=list(dec.buf)
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
buf=list(pre); buf[0:P.HIST]=buf[160:160+P.HIST]
print("=== frame %d g8=%d"%(N,f["energy8"]))
for sf in range(4):
    lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
    tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
    stale=list(buf[p:p+40]); buf_pre=list(buf)
    for k in range(40): buf[p+k]=0.0
    w0=p-(lag+1)
    out=[P._f32(g[2]*buf[w0+i]+g[1]*buf[w0+i+1]+g[0]*buf[w0+i+2]) for i in range(40)]
    D=L[sf]
    if any(x is None for x in D):
        # advance the state anyway
        gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        for i in range(40):
            buf[p+i]=P._f32(P._f32(out[i]+P._f32(gg*cb1[i]))+P._f32(g2v*cb2[i]))
        continue
    # solve v[q] for q=0..39 (positions p+q)
    v=[None]*40
    for i in range(40):
        q1=i-(lag+1)      # position of the g[2] tap relative to p
        delta=D[i]-out[i]
        acc=0.0; unk=None
        for coef,q in ((g[2],q1),(g[1],q1+1),(g[0],q1+2)):
            if 0<=q<40:
                if v[q] is None: unk=(coef,q)
                else: acc+=coef*v[q]
        if unk:
            v[unk[1]]=(delta-acc)/unk[0]
    # the DLL's own LTP outputs (their tap value if read live) - approximate
    gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
    cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
    print(" sf%d lag=%d idx=%d g=%s"%(sf,lag,idx,["%.5f"%x for x in g]))
    print("    q : dll_tap_value   stale(prev frame)   port_ltp_out   dll_ltp_out   exc_final")
    for q in range(min(40,41-lag+2)):
        if v[q] is None: continue
        print("   %2d : %14.5f %14.5f %14.5f %14.5f %12.5f"%(
            q,v[q],stale[q],out[q],D[q],
            P._f32(P._f32(out[q]+P._f32(gg*cb1[q]))+P._f32(g2v*cb2[q]))))
    for i in range(40):
        buf[p+i]=D[i]
