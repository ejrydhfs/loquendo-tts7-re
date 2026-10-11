import sys, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full, ec0, tilt_vals
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
dec=Full()
blocks=list(C.iter_blocks(d,info))
for i in range(38):
    dec.decode_frame(blocks[i][1],key=info['key'])
f=dec.parse_frame(blocks[38][1],info['key'])
# manual single-frame trace using the class internals
dec.buf[0:C.HIST]=dec.buf[160:160+C.HIST]
g8=f["energy8"]
for sf in range(4):
    lag_d,ix,b3,cbi=f["sub8"][sf]; p=C.HIST+40*sf
    gain=dec.exc_gain(g8,b3)
    for k in range(40): dec.buf[p+k]=0.0
    ltp=dec.ltp(p,lag_d+17,ix); cb1=dec.codebook(cbi[0:8],0); cb2=dec.codebook(cbi[8:16],0)
    g2=C._f32(gain*C.CB2_RATIO)
    for k in range(40):
        v=C._f32(ltp[k]+C._f32(gain*cb1[k])); dec.buf[p+k]=C._f32(v+C._f32(g2*cb2[k]))
exc8=dec.buf[C.HIST:C.HIST+160]
sig8=dec.synth8_tilt(f["lsf10"])
lpc_ps=[]
prev=dec.lsf16_prev if dec.lsf16_prev else f["lsf16"]
for sf in range(4):
    li=C.lsf_stabilise(C.lsf_interp(prev,f["lsf16"],8,sf,4),0.05)
    a=C.lsf_to_lpc(li); lpc_ps.append((a,)+tilt_vals(a,8))
print("== frame 38 : 16 kHz coded band ==")
print(" sf  g4  energy      gg         norm16      gain      (oracle gain)")
og=[432.573,122.42,432.02,66.6155]
for sf in range(4):
    a,s,dd=lpc_ps[sf]
    e=ec0(exc8[40*sf:40*sf+40],40); gg=math.exp(f['sub16'][sf][0]*0.27027027027-0.15556)
    n=(dec.tilt8[sf]+0.01)/(0.01+dd)
    print(" %d   %d   %-10.6g  %-10.6g  %-10.6g  %-9.6g  %.6g"%(sf,f['sub16'][sf][0],e,gg,n,(e+1.0)*(gg/n),og[sf]))
print(" tilt8(=1+Sum(lpc8[i+1]-lpc8[i])):",["%.6g"%x for x in dec.tilt8])
print("== frame 38 : 32 kHz noise band ==")
print(" sf  idx5 ln(g5)   g5          norm32      amp       noise[:3]")
on=[6.51323,6.83571,7.10934,7.3074]
for sf in range(4):
    li=C.lsf_stabilise(C.lsf_interp(dec.lsf32_prev if dec.lsf32_prev else f["lsf32"],f["lsf32"],8,sf,4),0.05)
    s2,d2=tilt_vals(C.lsf_to_lpc(li),8)
    n=(lpc_ps[sf][1]+0.01)/(0.01+d2)
    g5=math.exp((f['ref32'][sf]-10)*0.125)
    print(" %d   %2d  %-8.3g %-11.6g %-11.6g %-9.6g (oracle norm %.5g)"%(sf,f['ref32'][sf],(f['ref32'][sf]-10)*0.125,g5,n,g5/n,on[sf]))
print(" 0.7 factor (float @0x10023ca8+0x24) = 0.699999988079071 ; ramp = (-1)^i")
