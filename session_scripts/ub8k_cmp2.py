"""Compare the port's ltp() with a hand-rolled materialised window on the same state."""
import sys, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210_patched as P
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d=open(DEFAULT,'rb').read()
N=117
dec=P.Codec210()
for i in range(N):
    dec.decode_frame(d[150+i*110:150+(i+1)*110],key=0x6D)
blk=d[150+N*110:150+(N+1)*110]
f=dec.parse_frame(blk,0x6D)
buf=list(dec.buf); buf[0:P.HIST]=buf[160:160+P.HIST]
dec.buf[0:P.HIST]=dec.buf[160:160+P.HIST]
for sf in range(2):
    lag_d,idx,b3,cbi=f["sub8"][sf]; p=P.HIST+40*sf; lag=lag_d+17
    for k in range(40): buf[p+k]=0.0
    for k in range(40): dec.buf[p+k]=0.0
    hand=[]
    w0=p-(lag+1)
    tbl=dec.pitch_tbl
    g=[tbl[idx*3+k]/64.0+0.5 for k in range(3)]
    for i in range(40):
        a=w0+i
        hand.append(P._f32(g[2]*buf[a]+g[1]*buf[a+1]+g[0]*buf[a+2]))
    port=dec.ltp(p,lag,idx)
    print("sf%d lag=%d w0=%d  hand[:4]=%s port[:4]=%s  maxdiff=%.3g"%(
        sf,lag,w0,["%.6g"%x for x in hand[:4]],["%.6g"%x for x in port[:4]],
        max(abs(a-b) for a,b in zip(hand,port))))
    # advance both the same way (port-style: write the excitation, but here just ltp+0)
    for k in range(40):
        buf[p+k]=port[k]; dec.buf[p+k]=port[k]
