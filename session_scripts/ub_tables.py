import sys, math, struct
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full, CB16, codebook, tilt_vals, ec0
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
dec=Full()
for i,(idx,blk) in enumerate(list(C.iter_blocks(d,info))[:39]):
    m=dec.decode_frame(blk,key=info['key'])
    if i in (37,38):
        f=dec.parse_frame(blk,info['key'])
        print("frame %d  mode16=%d mode32=%d  lsf16_idx=%s lsf32_idx=%s"%(i,f['mode16'],f['mode32'],f['lsf16_idx'],f['lsf32_idx']))
        print("   g4=%s ref32(5bit)=%s"%([f['sub16'][s][0] for s in range(4)],f['ref32']))
# redo frame 38 with a detailed printout
dec=Full()
for i,(idx,blk) in enumerate(list(C.iter_blocks(d,info))[:37]):
    dec.decode_frame(blk,key=info['key'])
blk=d[150+38*110:150+39*110]
f=dec.parse_frame(blk,info['key'])
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
exc16,ps16=dec.band16(f,exc8)
print("frame 38 16k table (mine):")
for sf in range(4):
    a,s,dd=ps16[sf]
    print("  sf%d energy=%.6f gg=%.6f norm=%.6f gain=%.6f  (oracle gain: %s)"%(
        sf, ec0(exc8[40*sf:40*sf+40],40), math.exp(f['sub16'][sf][0]*0.27027027027-0.15556),
        (dec.tilt8[sf]+0.01)/(0.01+dd), (ec0(exc8[40*sf:40*sf+40],40)+1.0)*(math.exp(f['sub16'][sf][0]*0.27027027027-0.15556)/((dec.tilt8[sf]+0.01)/(0.01+dd))),
        [432.573,122.42,432.02,66.6155][sf]))
print("frame 38 32k table (mine): idx5=%s"%f['ref32'])
src=[0.0]*320
for k in range(160): src[2*k]=2.0*dec.exc16_pre[k]
for sf in range(4):
    a,s,dd=ps16[sf]
    norm=(s+0.01)/(0.01+tilt_vals(C.lsf_to_lpc(C.lsf_stabilise(C.lsf_interp(dec.lsf32_prev if dec.lsf32_prev else f['lsf32'],f['lsf32'],8,sf,4),0.05)),8)[1])
    g5=math.exp((f['ref32'][sf]-10)*0.125)
    print("  sf%d gain5=%.6f norm=%.6f amp=%.6f  (oracle gain5: %s)"%(sf,g5,norm,g5/norm,[1.13315,5.7546,0.367879,7.38906][sf]))
