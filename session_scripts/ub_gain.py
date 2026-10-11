import sys, struct, json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_EBP
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def fl(o,a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
def run(NF, label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    gains=[]; noise=[]
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP)
        if a==0x10002da0:
            p4=o.r32(esp+0x14)
            if p4 in (40,80):
                g=struct.unpack("<f", bytes(uc.mem_read(esp+0x10,4)))[0]
                gains.append((p4,g))
        if a==0x1000e65b:
            gains.append(('noise', o.r32(0x30016d80+0)))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002da0,end=0x10002da1)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e65b,end=0x1000e65c)
    pcm=o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print("=== %s"%label)
    print("  FUN_10002da0 gains:",[("n=%d"%n,"%.6g"%g) for n,g in gains if n!='noise'])
    print("  exc16:",["%.5g"%x for x in fl(o,o.r32(o16+0x48),8)])
    print("  exc32:",["%.5g"%x for x in fl(o,o.r32(o32+0x48),8)])
    print("  tilt16:",["%.6g"%x for x in fl(o,o.r32(o16+0x60),4)])
    print("  tilt32:",["%.6g"%x for x in fl(o,o.r32(o32+0x60),4)])
    print("  lpc16:",["%.6g"%x for x in fl(o,o.r32(o16+0x58),8)])
    print("  lpc32:",["%.6g"%x for x in fl(o,o.r32(o32+0x58),8)])
    return gains
run(38,"frame 38")
run(0,"frame 0")
