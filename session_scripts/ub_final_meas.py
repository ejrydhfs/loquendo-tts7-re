import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def run(NF,label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    ev=[]
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP)
        if a==0x10002ec0:
            ev.append(('ec0', hex(o.r32(esp)), hex(o.r32(esp+4)), o.r32(esp+8)))
        if a==0x1000e695:
            ev.append(('energy', f32(esp+0x28), f32(esp+0x20), f32(esp+0x10), f32(esp+0x24)))
        if a==0x1000e623:
            ev.append(('noise', f32(esp+0x1c), f32(esp+0x20), o.r32(esp+0x18), o.r32(esp+0x34), o.r32(esp+0x30)))
        if a==0x1000e7bb:
            ev.append(('exc16', fl(uc.reg_read(UC_X86_REG_EBX),4)))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002ec0,end=0x10002ec2)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e695,end=0x1000e696)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e623,end=0x1000e624)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e7bb,end=0x1000e7bc)
    pcm=o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print("=== %s pcm=%.2f"%(label,(sum(x*x for x in pcm)/640)**0.5))
    for e in ev: print("   ",e)
run(38,"frame 38")
run(0,"frame 0")
