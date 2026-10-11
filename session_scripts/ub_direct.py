import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn.x86_const import UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
o.decode(ctx, d[BLOCK_OFFSET:BLOCK_OFFSET+BLOCK_SIZE])
print("desc mem:",[hex(o.r32(0x10023a5c+4*i)) for i in range(8)])
print("table 0x10022470:",[x for x in struct.unpack("<16b", bytes(o.uc.mem_read(0x10022470,16)))])
# controlled bit reader: 40 bits for one codebook call (5 x (1 sign + 7 idx))
bits=''.join('%08d'%1 if False else format(v,'08b') for v in [0b11111111,0b11111111,0,0,0])
buf=o.malloc(16)
data=bytearray(5); data[0]=0xFF; data[1]=0xFF
o.uc.mem_write(buf, bytes(data))
o.call(0x10001020,[ctx])
o.call(0x10001040,[ctx, buf, 5])
dst=o.malloc(160); o.uc.mem_write(dst,b"\x00"*160)
scratch=o.malloc(256)
o.call(0x100029c0,[dst,0x10023a5c,40,ctx,scratch])
print("out with bits FFFF..:",["%.5g"%x for x in struct.unpack("<8f", bytes(o.uc.mem_read(dst,32)))])
# zero bits
o.uc.mem_write(buf, b"\x00"*5)
o.uc.mem_write(dst,b"\x00"*160)
o.call(0x10001020,[ctx]); o.call(0x10001040,[ctx,buf,5])
o.call(0x100029c0,[dst,0x10023a5c,40,ctx,scratch])
print("out with zero bits:",["%.5g"%x for x in struct.unpack("<8f", bytes(o.uc.mem_read(dst,32)))])
# check ctx bit-reader state after
print("ctx+4 total=%d +8 byte=%d +0xc bit=%d +0x14 err=%d"%(o.r32(ctx+4),o.r32(ctx+8),o.r32(ctx+0xc),o.r32(ctx+0x14)))
