import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
print("ctx=%08x" % ctx)
d=open(BIN,'rb').read()
# decode a few frames so objects exist
for i in range(40):
    o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
def dumpobj(name, a):
    print("== %s @ %08x  vtbl=%08x" % (name, a, o.r32(a)))
    for off in range(0,0x74,4):
        v=o.r32(a+off)
        print("   +%02x = %08x (%d)" % (off, v, v-0x100000000 if v>=0x80000000 else v))
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
print("o32=%08x o16=%08x o8=%08x"%(o32,o16,o8))
dumpobj("o32",o32); dumpobj("o16",o16); dumpobj("o8",o8)
