"""Clean single-pass decomposition of the 8 kHz excitation for the drift frames.

Frames 0..N-1 use the (patched) port; frame N is re-implemented once in this script so the
LTP / CB1 / CB2 components can be compared, sample by sample, with the DLL's own writes to
0x30012364 (attributed by code address).
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

def analyse(N):
    dec=P.Codec210()
    for i in range(N):
        dec.decode_frame(d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE],key=0x6D)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    f=dec.parse_frame(blk,0x6D)
    # --- oracle: capture the DLL's component writes for frame N ---
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
    # --- port: single pass of the 8k loop on the same starting state ---
    dec.buf[0:P.HIST]=dec.buf[160:160+P.HIST]
    g8=f["energy8"]
    mine=[]
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf
        gain=dec.exc_gain(g8,b3)
        for i in range(40): dec.buf[p+i]=0.0
        ltp=dec.ltp(p,lag_d+17,idx)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        g1=gain; g2=P._f32(g1*P.CB2_RATIO)
        mine.append(dict(sf=sf,lag=lag_d+17,idx=idx,g1=g1,g2=g2,ltp=list(ltp),cb1=list(cb1),cb2=list(cb2)))
        for i in range(40):
            v=P._f32(ltp[i]+P._f32(g1*cb1[i])); dec.buf[p+i]=P._f32(v+P._f32(g2*cb2[i]))
    # --- compare ---
    print("=== frame %d  g8=%d"%(N,g8))
    for sf in range(4):
        dltp=[None]*40; dcb1=[0.0]*40; dcb2=[0.0]*40; st=[0.0]*40
        for pc,pos,val in [e for e in ev if 40*sf<=e[1]<40*sf+40]:
            k=pos-40*sf
            if pc=='clear': st[k]=0.0
            elif pc=='ltp': st[k]=val; dltp[k]=val
            elif pc=='cb1': dcb1[k]=val-st[k]; st[k]=val
            elif pc=='cb2': dcb2[k]=val-st[k]; st[k]=val
        m=mine[sf]
        dltp=[(x if x is not None else 0.0) for x in dltp]
        def rms(v): return (sum(x*x for x in v)/40)**0.5
        # alignment check: ratio of DLL ltp to port ltp should be constant 1 if identical
        rat=[(b/a if a else float('nan')) for a,b in zip(m["ltp"],dltp)]
        print(" sf%d lag=%d idx=%d  rms: dll_ltp=%.6g my_ltp=%.6g | dll_cb1=%.6g my_cb1=%.6g | dll_cb2=%.6g my_cb2=%.6g"
              %(sf,m["lag"],m["idx"],rms(dltp),rms(m["ltp"]),
                rms(dcb1),rms([m["g1"]*x for x in m["cb1"]]),
                rms(dcb2),rms([m["g2"]*x for x in m["cb2"]])))
        if rms(dltp):
            print("    ltp dll[:5]=%s  my[:5]=%s  ratio[:5]=%s"%(
                ["%.6g"%x for x in dltp[:5]],["%.6g"%x for x in m["ltp"][:5]],
                ["%.4f"%x for x in rat[:5]]))
            imm=min(range(40), key=lambda k: abs(rat[k]-1) if rat[k]==rat[k] else 9)
            print("    max |ratio-1| at sample %d (dll %.6g my %.6g)"%(
                max(range(40), key=lambda k: abs(rat[k]-1) if rat[k]==rat[k] else 0),
                dltp[max(range(40), key=lambda k: abs(rat[k]-1) if rat[k]==rat[k] else 0)],
                m["ltp"][max(range(40), key=lambda k: abs(rat[k]-1) if rat[k]==rat[k] else 0)]))
for N in (int(x) for x in sys.argv[1:]):
    analyse(N)
