"""Solve for the DLL's LTP tap-input values on the drift frames.

The DLL's LTP output (= the excitation write at the LTP site) minus the port's LTP output
gives the contribution of the tap positions that fall inside the *current* sub-frame
(the port has zeros there after the clear).  Solving those equations yields, per position,
the value the DLL's tap copy actually read, which is then compared with
  (a) the port's pre-clear buffer content (= the previous frame's excitation), and
  (b) the DLL's / the port's own LTP output at that position (the "in-place recursion").
"""
import sys, struct, json
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
    pre=list(dec.buf)                     # the state at the start of frame N (post frame N-1)
    # ---- DLL: the LTP write values per sub-frame ----
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
    o.uc_hook=o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=EXC,end=EXC+640)
    o.decode(ctx, blk)
    dll_ltp=[[None]*40 for _ in range(4)]
    for pc,pos,val in ev:
        if pc=='ltp': dll_ltp[pos//40][pos%40]=val
    # ---- port: single pass on the same state ----
    buf=list(pre)
    buf[0:P.HIST]=buf[160:160+P.HIST]            # the frame memmove
    out=[]
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf
        lag=lag_d+17
        tbl=dec.pitch_tbl
        g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        w0=p-(lag+1)
        S=[(buf[w0+k] if 0<=w0+k<len(buf) else 0.0) for k in range(120)]
        my_ltp=[P._f32(g[2]*S[i]+g[1]*S[40+i]+g[0]*S[80+i]) for i in range(40)]
        for k in range(40): buf[p+k]=0.0
        for i in range(40): buf[p+i]=my_ltp[i]
        out.append(dict(sf=sf,lag=lag,idx=idx,g=g,w0=w0,p=p,
                        my=my_ltp,dll=dll_ltp[sf],
                        stale=[pre[buf_idx] if 0<=(buf_idx:=p+k)<len(pre) else 0.0 for k in range(40)]))
    print("=== frame %d  g8=%d"%(N,f["energy8"]))
    for e in out:
        dll=e["dll"]
        if any(x is None for x in dll): print("  sf%d: incomplete dll data"%e["sf"]); continue
        g=e["g"]; lag=e["lag"]; p=e["p"]; my=e["my"]
        print("  sf%d lag=%d idx=%d g=%s"%(e["sf"],lag,e["idx"],["%.4f"%x for x in g]))
        print("     sample  dll        port       stale(prev frame)  dll_ltp_out")
        for i in range(40):
            if abs(dll[i]-my[i])>1e-3*max(1.0,abs(dll[i])):
                print("      %2d   %10.5f %10.5f %12.5f %12.5f"%(i,dll[i],my[i],
                      e["stale"][i],dll[i]))
                if i>12: break
for N in (int(x) for x in sys.argv[1:]):
    run(N)
