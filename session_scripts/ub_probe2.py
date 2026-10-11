import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
for i in range(NF+1):
    pcm = o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n)))
def rms(v): return (sum(x*x for x in v)/len(v))**0.5
import math
def corr(a,b):
    ma=sum(a)/len(a); mb=sum(b)/len(b)
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
A32=fl(o.r32(o32+0x38),640); B32=fl(o.r32(o32+0x3c),640)
A16=fl(o.r32(o16+0x38),320); B16=fl(o.r32(o16+0x3c),320)
ring32=fl(o.r32(o32+0x28),640)          # o32 scratch base
o32_2c=fl(o.r32(o32+0x2c),320)
o16_2c=fl(o.r32(o16+0x2c),160)
o8_30=fl(o.r32(o8+0x30),160)
o16_34=fl(o.r32(o16+0x34),160)
o32_34=fl(o.r32(o32+0x34),320)
exc32=fl(o.r32(o32+0x48),320)
exc16=fl(o.r32(o16+0x48),160)
pcm=[x for x in pcm]
print("RMS: pcm=%.1f A32=%.1f B32=%.1f A16=%.1f B16=%.1f"%(rms(pcm),rms(A32),rms(B32),rms(A16),rms(B16)))
comb32=[max(-32768.0,min(32767.0,2.0*(a-b))) for a,b in zip(A32,B32)]
print("corr(pcm, clamp(2*(A32-B32)))=%.6f"%corr(pcm,comb32))
comb16=[max(-32768.0,min(32767.0,2.0*(a-b))) for a,b in zip(A16,B16)]
print("corr(o32[+0x2c], clamp(2*(A16-B16)))=%.6f  rms=%.1f vs %.1f"%(corr(o32_2c,comb16),rms(o32_2c),rms(comb16)))
print("corr(o32[+0x2c], A16)=%.6f"%corr(o32_2c,A16))
print("corr(o16[+0x2c], o8[+0x30])=%.6f rms %.1f %.1f"%(corr(o16_2c,o8_30),rms(o16_2c),rms(o8_30)))
print("RMS exc32=%.1f exc16=%.1f o16_34=%.1f o32_34=%.1f"%(rms(exc32),rms(exc16),rms(o16_34),rms(o32_34)))
print("exc32[:8]=",["%.3f"%x for x in exc32[:8]])
print("exc16[:8]=",["%.3f"%x for x in exc16[:8]])
print("o32_34[:8]=",["%.3f"%x for x in o32_34[:8]])
print("o16_34[:8]=",["%.3f"%x for x in o16_34[:8]])
print("o32[+0x60]:",[("%.6g"%x) for x in fl(o.r32(o32+0x60),4)])
print("o16[+0x60]:",[("%.6g"%x) for x in fl(o.r32(o16+0x60),4)])
print("o32[+0x58] lpc:",["%.6g"%x for x in fl(o.r32(o32+0x58),8)])
print("o16[+0x58] lpc:",["%.6g"%x for x in fl(o.r32(o16+0x58),8)])
print("o32[+0x5c] state:",["%.6g"%x for x in fl(o.r32(o32+0x5c),16)])
print("o16[+0x5c] state:",["%.6g"%x for x in fl(o.r32(o16+0x5c),16)])
print("o32[+0x4c] lsf:",["%.6g"%x for x in fl(o.r32(o32+0x4c),8)])
print("o16[+0x4c] lsf:",["%.6g"%x for x in fl(o.r32(o16+0x4c),8)])
print("o32[+0x50] prevlsf:",["%.6g"%x for x in fl(o.r32(o32+0x50),8)])
print("o16[+0x50] prevlsf:",["%.6g"%x for x in fl(o.r32(o16+0x50),8)])
print("o32[+0x54]:",["%.6g"%x for x in fl(o.r32(o32+0x54),8)])
