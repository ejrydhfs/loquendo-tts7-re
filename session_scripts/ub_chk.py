import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
def rms(v): return (sum(float(x)*x for x in v)/len(v))**0.5
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
for N in (0,37,120,38):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    pcm=o.decode(ctx, blk)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    r_exc8=fl(o.r32(o8+0x3c),160); r_exc16=fl(o.r32(o16+0x48),160); r_syn32=fl(o.r32(o32+0x34),320)
    r_A32=fl(o.r32(o32+0x38),640); r_B32=fl(o.r32(o32+0x3c),640); r_t8=fl(0x30012a20,4)
    dec=Full()
    for i in range(N+1):
        b=d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]
        m=dec.decode_frame(b,key=info['key'])
    print("frame %d: corr mine/ref:"%N,
          "exc8=%.6f sig8=%.6f tilt8=%.6f exc16=%.6f syn16=%.6f syn32=%.6f B32=%.6f pcm=%.6f"%(
        corr(dec.buf[C.HIST:C.HIST+160],r_exc8), corr(dec.sig8_last,r_exc8), corr(dec.tilt8,r_t8),
        corr(dec.ub_exc16,r_exc16), corr(dec.b34_16,fl(o.r32(o16+0x34),160)),
        corr(dec.b34_32,r_syn32), corr(dec.ub_B32,r_B32), corr(m,pcm)))
