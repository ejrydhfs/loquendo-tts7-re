import sys, math, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full, CB16, codebook, tilt_vals, ec0
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
dec=Full()
for i,(idx,blk) in enumerate(C.iter_blocks(d,info)):
    if i>38: break
    if i<38:
        dec.decode_frame(blk,key=info['key']); continue
    # frame 38 detailed
    f=dec.parse_frame(blk,info['key'])
    dec.buf[0:C.HIST]=dec.buf[160:160+C.HIST]
    g8=f["energy8"]
    for sf in range(4):
        lag_d,ix,b3,cbi=f["sub8"][sf]
        p=C.HIST+40*sf
        gain=dec.exc_gain(g8,b3)
        for k in range(40): dec.buf[p+k]=0.0
        ltp=dec.ltp(p,lag_d+17,ix)
        cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
        dec.buf[p:p+40]=[ltp[k]+gain*cb1[k]+(gain/2.2)*cb2[k] for k in range(40)]
    exc8=dec.buf[C.HIST:C.HIST+160]
    print("my exc8 rms per sf:",["%.4g"%(sum(x*x for x in exc8[40*k:40*k+40])/40)**0.5 for k in range(4)])
    sig8=dec.synth8_tilt(f["lsf10"])
    print("my tilt8:",["%.6g"%x for x in dec.tilt8])
    lsf_cur=f["lsf16"]
    prev=dec.lsf16_prev
    block2=[0.0]*320
    for k in range(160): block2[2*k]=2.0*exc8[k]
    for sf in range(4):
        lsf_i=C.lsf_stabilise(C.lsf_interp(prev,lsf_cur,8,sf,4),0.05)
        a=C.lsf_to_lpc(lsf_i); t,dd=tilt_vals(a,8)
        norm=(dec.tilt8[sf]+0.01)/(0.01+dd)
        energy=ec0(block2[40*sf:40*sf+40],40)
        g4=f["sub16"][sf][0]
        gg=math.exp(g4*0.27027027027-0.15556)
        gain=(energy+1.0)*(gg/norm)
        print(" sf%d lpc=%s t=%.6g dd=%.6g norm=%.6g energy=%.6g g4=%d gg=%.6g gain=%.6g"%(sf,["%.4g"%x for x in a],t,dd,norm,energy,g4,gg,gain))
        print("      pairs:",f["sub16"][sf][1])
