import sys, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full, tilt_vals
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
dec=Full()
for i,(idx,blk) in enumerate(C.iter_blocks(d,info)):
    if i>38: break
    f=dec.parse_frame(blk,info['key'])
    if i<38:
        # advance the 8k state only (needed for prev LSF)
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
        dec.synth8_tilt(f["lsf10"])
        continue
    prev=dec.lsf8_prev
    for sf in range(4):
        lsf_i=C.lsf_stabilise(C.lsf_interp(prev,f["lsf10"],10,sf,4),0.05)
        a=C.lsf_to_lpc(lsf_i)
        s,dd=tilt_vals(a,10)
        print("sf%d  s=%.6g  d=%.6g   (oracle tilt8 = %.6g)"%(sf,s,dd,[2.74864,2.67832,2.60797,2.5377][sf]))
