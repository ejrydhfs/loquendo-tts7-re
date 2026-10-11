import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
o=Oracle(); ctx=o.open_decoder(32000,0x6D)
for i in range(39): pcm=o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
r_exc8=list(struct.unpack("<160f", bytes(o.uc.mem_read(o.r32(o8+0x3c),640))))
dec=Full()
for i in range(39):
    m=dec.decode_frame(d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE],key=info['key'])
my=dec.buf[C.HIST:C.HIST+160]
print("exc8 rms  mine=%.4f oracle=%.4f ratio=%.6f"%(rms(my),rms(r_exc8),rms(my)/rms(r_exc8)))
n=len(my); ma=sum(my)/n; mb=sum(r_exc8)/n
print("best scale = %.6f"%(sum((a)*(b) for a,b in zip(my,r_exc8))/sum(b*b for b in r_exc8)))
print("my per-sf rms:",["%.5g"%rms(my[40*k:40*k+40]) for k in range(4)])
print("or per-sf rms:",["%.5g"%rms(r_exc8[40*k:40*k+40]) for k in range(4)])
print("tilt8 mine:",["%.6g"%x for x in dec.tilt8])
print("my exc16 rms=%.5g oracle=%.5g"%(rms(dec.exc16_pre), rms(struct.unpack("<160f",bytes(o.uc.mem_read(o.r32(o16+0x48),640))))))
