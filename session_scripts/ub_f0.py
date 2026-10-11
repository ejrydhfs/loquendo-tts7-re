import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
last=[0]; log=[]
def hc(uc,a,s,u):
    last[0]=a
    esp=uc.reg_read(UC_X86_REG_ESP)
    if a==0x10002da0:
        ret=o.r32(esp)
        n=o.r32(esp+0x14); g=f32(esp+0x10); src=o.r32(esp+8); dst=o.r32(esp+4)
        if n==40 and 0x30000000<=dst<0x30020000:
            log.append(('da0',hex(ret),hex(dst),hex(src),g))
    if a==0x1000e7ca:
        log.append(('copy',hex(uc.reg_read(UC_X86_REG_EBX)),hex(o.r32(esp+0x24))))
def hw(uc,acc,addr,size,val,u):
    if 0x30014030<=addr<0x30014030+640 and last[0] in (0x1000e65b,0x1000e5bc,0x1000e354,0x1000e7ab,0x1000e78c):
        log.append(('w',hex(last[0]),hex(addr),val))
o.uc.hook_add(UC_HOOK_CODE,hc,begin=0x10000000,end=0x10040000)
o.uc.hook_add(UC_HOOK_MEM_WRITE,hw,begin=0x30014030,end=0x300142b0)
o.decode(ctx, d[BLOCK_OFFSET:BLOCK_OFFSET+BLOCK_SIZE])
for e in log[:40]: print(e)
print("...")
print("exc16 first 40:", ["%.4g"%x for x in struct.unpack("<40f", bytes(o.uc.mem_read(o.r32(o16+0x48),160)))])
