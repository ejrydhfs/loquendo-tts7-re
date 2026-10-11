"""Read the DLL's actual tap values inside the current sub-frame from the tap scratch.

Scratch layout (proved: window w = S[40w : 40w+40], containing buf[w0+w+0 ... +40)).
The position p+m (current sub-frame sample m) sits in window w at index lag+1+m-w, so the
DLL's tap value V(m) is read directly.
"""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
def run(N,sf_want):
    dec=P.Codec210(); snap=[]
    for i in range(N+1):
        dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D); snap.append(list(dec.buf))
    pre=snap[N-1]
    f=dec.parse_frame(d[150+N*110:150+(N+1)*110],0x6D)
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N): o.decode(ctx, d[150+i*110:150+(i+1)*110])
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    snaps=[]; pend=None
    def h(uc,a,s,u):
        global pend
        esp=uc.reg_read(UC_X86_REG_ESP)
        if a==0x10009c0d: pend=[o.r32(esp+4*k) for k in range(14)]
        elif a==0x10009c12 and pend: snaps.append(fl(pend[9],120)); pend=None
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
    o.decode(ctx, d[150+N*110:150+(N+1)*110])
    b=list(pre); b[0:P.HIST]=b[160:160+P.HIST]
    # advance the port's buffer to sf_want using the port formulas (state matches DLL up to divergence)
    for sf in range(sf_want):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
        tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        for k in range(40): b[p+k]=0.0
        w0=p-(lag+1)
        o_=[P._f32(g[2]*b[w0+i]+g[1]*b[w0+i+1]+g[0]*b[w0+i+2]) for i in range(40)]
        gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        for i in range(40):
            v=P._f32(o_[i]+P._f32(gg*cb1[i])); b[p+i]=P._f32(v+P._f32(g2v*cb2[i]))
    sf=sf_want; lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
    w0=p-(lag+1); S=snaps[sf]
    stale=list(pre[p:p+40]); prenow=list(b[p:p+40])
    tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
    gg=dec.exc_gain(f["energy8"],b3); g2v=P._f32(gg*P.CB2_RATIO)
    cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
    print("=== frame %d sf%d lag=%d idx=%d (window start w0=%d)"%(N,sf,lag,idx,w0))
    print(" m : DLL tap value | stale(prev frame) | my3tap(cleared) | DLL_ltp_out | exc(ltp+cb)")
    # the DLL's LTP outputs for this sub-frame come from the excitation writes; approximate by
    # recomputing with the DLL's taps (below) is circular, so just dump the taps + candidates.
    for m in range(0, min(40-lag+2, 20)):
        k=lag+1+m                     # index inside window 0 for this position
        v=(S[k] if k<40 else (S[40+(k-40)] if k<80 else None))
        print("  %2d: %12.5f | %16.5f | %15.5f |"%(m, v if v is not None else float('nan'),
                                                  stale[m], prenow[m]))
run(int(sys.argv[1]) if len(sys.argv)>1 else 118, int(sys.argv[2]) if len(sys.argv)>2 else 1)
