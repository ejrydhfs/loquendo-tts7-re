"""Read the DLL's LTP tap scratch (120 floats) for the drift frames and compare with the
port's linearised window S = buf[w0 : w0+120]."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
SCRATCH=0x3000e0a4

def analyse(N):
    dec=P.Codec210()
    for i in range(N):
        dec.decode_frame(d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE],key=0x6D)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    f=dec.parse_frame(blk,0x6D)
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    ev=[]; last=[0]
    def hc(uc,a,s,u): last[0]=a
    def hw(uc,acc,addr,size,val,u):
        if SCRATCH<=addr<SCRATCH+120*4:
            ev.append((last[0],(addr-SCRATCH)//4,struct.unpack("<f",struct.pack("<I",val))[0]))
    o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
    o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=SCRATCH,end=SCRATCH+120*4)
    o.decode(ctx, blk)
    # port: single pass, capture S per sub-frame
    dec.buf[0:P.HIST]=dec.buf[160:160+P.HIST]
    print("=== frame %d  scratch writes: %d (pcs %s)"%(
        N,len(ev),sorted(set(hex(p) for p,_,_ in ev))))
    mine=[]
    for sf in range(4):
        lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf
        gain=dec.exc_gain(f["energy8"],b3)
        for i in range(40): dec.buf[p+i]=0.0
        w0=p-(lag_d+17+1)
        S=dec.buf[w0:w0+120] if w0>=0 else [0.0]*(-w0)+dec.buf[0:w0+120]
        mine.append(S)
        dec.buf[p:p+40]=[0.0]*40
    # reconstruct the DLL scratch per sub-frame from the write events (in order)
    from collections import defaultdict
    sub=defaultdict(list)
    for pc,pos,val in ev: sub[pos//40].append((pos,val))
    for sf in range(4):
        got={pos:val for pos,val in sub.get(sf,[])}
        if not got: continue
        dll=[got.get(k) for k in range(120)]
        my=mine[sf]
        # compare where both known
        ks=[k for k in range(120) if dll[k] is not None]
        diff=[(k,dll[k],my[k]) for k in ks if abs(dll[k]-my[k])>1e-3*max(1e-9,abs(dll[k]))]
        print("  sf%d lag=%d: scratch known slots %d, mismatches %d"%(sf,lag_d+17,len(ks),len(diff)))
        if diff: print("      first mismatches (k,dll,port):",[("%d"%k,"%.6g"%a,"%.6g"%b) for k,a,b in diff[:6]])
for N in (int(x) for x in sys.argv[1:]):
    analyse(N)
