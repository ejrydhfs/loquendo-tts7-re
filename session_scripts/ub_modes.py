import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
import json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
import codec210 as C
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
dec=C.Codec210()
rows=[]
for i in range(45):
    blk=d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE]
    f=dec.parse_frame(blk,0x6D)
    pcm=o.decode(ctx, blk)
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    rms=(sum(x*x for x in pcm)/640)**0.5
    rows.append((i,f['wb_flag'],f['mode8'],f['f16'],f['mode16'],f['f32'],f['mode32'],
                 o.r32(o8+0x70),o.r32(o16+0x70),o.r32(o32+0x70),rms))
print("fr wb m8 f16 m16 f32 m32 | o8m o16m o32m  rms")
for r in rows:
    print("%2d  %d  %d   %d  %d   %d  %d   |  %d   %d   %d   %.1f"%r)
