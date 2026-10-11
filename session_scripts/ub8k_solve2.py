"""Solve the LTP tap-input (Delta) values on the drift frames.

For each output sample i the DLL/port difference is
    d_i = g2*D[w0+i] + g1*D[w0+1+i] + g0*D[w0+2+i]
with D = DLL buffer - port buffer (0 inside the history).  The system is triangular in the
current sub-frame's positions, so D[0..39] can be recovered exactly and compared with
  * the port's pre-clear content (previous frame's excitation),
  * the port's own LTP output at that position (in-place recursion hypothesis),
  * the port's accumulated excitation (ltp + cb) at that position.
"""
import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
EXC=0x30012364
PCS={0x10009b6f:'clear',0x10009c0d:'ltp',0x10009f3e:'cb1',0x10009ff1:'cb2'}

def run(N):
    dec=P.Codec210()
    for i in range(N):
        dec.decode_frame(d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE],key=0x6D)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    f=dec.parse_frame(blk,0x6D)
    pre=list(dec.buf)
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    ev=[]; last=[0]
    def hc(uc,a,s,u): last[0]=a
    def hw(uc,acc,addr,size,val,u):
        if EXC<=addr<EXC+640:
            ev.append((PCS.get(last[0],hex(last[0])),(addr-EXC)//4,
                       struct.unpack("<f",struct.pack("<I",val))[0]))
    o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
    o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
    o.decode(ctx, blk)
    dll_ltp=[[None]*40 for _ in range(4)]
    for pc,pos,val in ev:
        if pc=='ltp': dll_ltp[pos//40][pos%40]=val
    buf=list(pre); buf[0:P.HIST]=buf[160:160+P.HIST]
    print("=== frame %d g8=%d"%(N,f["energy8"]))
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
        tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        stale=list(buf[p:p+40])
        for k in range(40): buf[p+k]=0.0
        w0=p-(lag+1)
        S=[buf[w0+k] for k in range(120)]
        port=[P._f32(g[2]*S[i]+g[1]*S[40+i]+g[0]*S[80+i]) for i in range(40)]
        dll=dll_ltp[sf]
        if any(x is None for x in dll): continue
        # triangular solve for D[0..39] (coefficients g2,g1,g0 for k1=k1, k1+1, k1+2)
        D=[None]*40
        ok=True
        for i in range(40):
            k1=w0+i-p               # position of the g2 tap in the current sub-frame (-1 = history)
            di=dll[i]-port[i]
            acc=0.0
            for coef,kk in ((g[2],k1),(g[1],k1+1),(g[0],k1+2)):
                if 0<=kk<40:
                    if D[kk] is not None: acc+=coef*D[kk]
            # the only unknown is the largest kk with D None
            unk=[(coef,kk) for coef,kk in ((g[2],k1),(g[1],k1+1),(g[0],k1+2)) if 0<=kk<40 and D[kk] is None]
            if unk:
                coef,kk=unk[-1]
                if abs(coef)<1e-9 or len(unk)>1: ok=False; continue
                D[kk]=(di-acc)/coef
        if not ok: print("  sf%d: singular"%sf); continue
        # write the port's outputs into buf for the next sub-frame, then compute the excitation
        for i in range(40): buf[p+i]=port[i]
        g1v=dec.exc_gain(f["energy8"],b3); g2v=P._f32(g1v*P.CB2_RATIO)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        exc=[P._f32(P._f32(port[i]+P._f32(g1v*cb1[i]))+P._f32(g2v*cb2[i])) for i in range(40)]
        # cb increments are exact (established), so the DLL buffer after the LTP = port + D
        dll_after_ltp=[port[i]+(D[i] if D[i] is not None else 0.0) for i in range(40)]
        def rms(v): return (sum(x*x for x in v)/len(v))**0.5
        print("  sf%d lag=%d idx=%d  D rms=%.4g  stale rms=%.4g  portltp rms=%.4g  exc rms=%.4g"%(
            sf,lag,idx,rms([x or 0 for x in D]),rms(stale),rms(port),rms(exc)))
        print("      k :   D        stale      port_ltp     exc(ltp+cb)   D-stale     D-portltp")
        for k in range(40):
            dd=D[k] if D[k] is not None else float('nan')
            print("     %2d : %9.4f %9.4f %10.4f %12.4f %10.4f %10.4f"%(
                k,dd,stale[k],port[k],exc[k],dd-stale[k],dd-port[k]))
            if k>=9: break
for N in (int(x) for x in sys.argv[1:]):
    run(N)
