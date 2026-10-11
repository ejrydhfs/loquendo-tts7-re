"""Test the in-place (live-read) LTP hypothesis on the drift frames.

Hypothesis: the DLL's LTP reads the adaptive-codebook buffer *live* while writing its
outputs, so a tap that lands in the current sub-frame reads the already written LTP
output of that position (not the cleared zero the materialised-window port reads).
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

def dll_components(N):
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
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    o.decode(ctx, blk)
    ltp=[[None]*40 for _ in range(4)]
    for pc,pos,val in ev:
        if pc=='ltp': ltp[pos//40][pos%40]=val
    return ltp

def corr(a,b):
    a=[x for x in a if x is not None]
    n=len(a); ma=sum(a)/n; mb=sum(b[:n])/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=(sum((x-ma)**2 for x in a))**.5; db=(sum((y-mb)**2 for y in b[:n]))**.5
    return num/(da*db) if da*db else 0.0

for N in (int(x) for x in sys.argv[1:]):
    dec=P.Codec210()
    for i in range(N):
        dec.decode_frame(d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE],key=0x6D)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    f=dec.parse_frame(blk,0x6D)
    dltp=dll_components(N)
    buf=list(dec.buf)
    buf[0:P.HIST]=buf[160:160+P.HIST]
    print("=== frame %d g8=%d"%(N,f["energy8"]))
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
        tbl=dec.pitch_tbl; g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
        for k in range(40): buf[p+k]=0.0
        w0=p-(lag+1)
        # (1) materialised window (current port)
        S=[buf[w0+k] for k in range(120)]
        mat=[P._f32(g[2]*S[i]+g[1]*S[40+i]+g[0]*S[80+i]) for i in range(40)]
        # (2) live in-place read
        for k in range(40): buf[p+k]=0.0
        live=[]
        for i in range(40):
            a1=w0+i; a2=a1+1; a3=a1+2
            v=P._f32(g[2]*buf[a1]+g[1]*buf[a2]+g[0]*buf[a3])
            buf[p+i]=v
            live.append(v)
        # restore for the next sub-frame with (2) (the hypothesis under test)
        R=dltp[sf]
        if any(x is None for x in R): print("  sf%d no data"%sf); continue
        print("  sf%d lag=%d idx=%d  materialised corr=%.6f   live corr=%.6f  (rms dll=%.5g mat=%.5g live=%.5g)"%(
            sf,lag,idx,corr(R,mat),corr(R,live),
            (sum(x*x for x in R)/40)**.5,(sum(x*x for x in mat)/40)**.5,(sum(x*x for x in live)/40)**.5))
