import sys, struct, math
sys.path.insert(0,'/tmp'); sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
from ub_port import Full
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
def corr(a,b):
    n=len(a); ma=sum(a)/n; mb=sum(b)/n
    num=sum((x-ma)*(y-mb) for x,y in zip(a,b))
    da=math.sqrt(sum((x-ma)**2 for x in a)); db=math.sqrt(sum((y-mb)**2 for y in b))
    return num/(da*db) if da*db else 0.0
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")
d,info=C.read_container(DEFAULT)
for N in (0,1,37,120):
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    blk=d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE]
    pcm=o.decode(ctx, blk)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    R=dict(exc8=fl(o.r32(o8+0x3c),160), sig8=fl(o.r32(o8+0x30),160), tilt8=fl(0x30012a20,4),
           exc16=fl(o.r32(o16+0x48),160), syn16=fl(o.r32(o16+0x34),160),
           exc32=fl(o.r32(o32+0x48),320), syn32=fl(o.r32(o32+0x34),320),
           A32=fl(o.r32(o32+0x38),640), B32=fl(o.r32(o32+0x3c),640))
    dec=Full()
    for i in range(N+1):
        b=d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]
        m=dec.decode_frame(b,key=info['key'])
    M=dict(exc8=dec.buf[C.HIST:C.HIST+160], sig8=dec.sig8_last, tilt8=dec.tilt8,
           exc16=dec.exc16_pre, syn16=dec.b34_16, exc32=dec.exc32_pre, syn32=dec.b34_32,
           A32=dec.ub_A32, B32=dec.ub_B32)
    print("frame %3d"%N, " ".join("%s=%.6f"%(k,corr(M[k],R[k])) for k in M), "pcm=%.6f"%corr(m,pcm))
