import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
log=[]; cur=0
def h(uc,a,s,u):
    esp=uc.reg_read(UC_X86_REG_ESP)
    global cur
    if a==0x100029c0:
        a1,a2,a3,a4,a5=o.r32(esp+4),o.r32(esp+8),o.r32(esp+0xc),o.r32(esp+0x10),o.r32(esp+0x14)
        if a2==0x10023a5c:
            cur=a1; log.append(('CB16 out=%s scratch=%s before'%(hex(a1),hex(a5)),["%.4g"%x for x in fl(a1,8)]))
    if a==0x1000e6f9 and cur:
        log.append(('CB16 after_call',["%.4g"%x for x in fl(cur,8)]))
    if a==0x10002da0 and o.r32(esp+4)==cur:
        log.append(('CB16 scale',f32(esp+0xc),o.r32(esp+0x10)))
    if a==0x1000e70f and cur:
        log.append(('CB16 after_scale',["%.4g"%x for x in fl(cur,8)]))
        cur=0
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x100029c0,end=0x100029c1)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e6f9,end=0x1000e6fa)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002da0,end=0x10002da1)
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e70f,end=0x1000e710)
o.decode(ctx, d[BLOCK_OFFSET:BLOCK_OFFSET+BLOCK_SIZE])
for e in log[:24]: print(e)
