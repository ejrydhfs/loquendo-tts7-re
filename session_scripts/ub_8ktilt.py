import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
for i in range(38): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
ev=[]
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x100030e0:
        p1,p2,p3,p4,p5,p6=o.r32(esp+4),o.r32(esp+8),o.r32(esp+0xc),o.r32(esp+0x10),o.r32(esp+0x14),o.r32(esp+0x18)
        if True:
            lpc=fl(p2,10); t=1.0
            for i in range(0,9,2): t+=lpc[i]+lpc[i+1]
            ev.append((p4,hex(p2),["%.6g"%x for x in lpc],t))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x100030e0,end=0x100030e1)
o.decode(ctx, d[BLOCK_OFFSET+38*BLOCK_SIZE:BLOCK_OFFSET+39*BLOCK_SIZE])
print("LPC calls:")
for e in ev: print("  ",e)
print("o8 tilt array (0x30012a20):",["%.6g"%x for x in fl(0x30012a20,4)])
