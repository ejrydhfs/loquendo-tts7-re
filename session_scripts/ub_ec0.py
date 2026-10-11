import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EAX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def probe(NF,label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    print("=== %s  o8=%08x o16=%08x o32=%08x  o8[+3c]=%08x o16[+34]=%08x o32[+34]=%08x"%(label,o8,o16,o32,o.r32(o8+0x3c),o.r32(o16+0x34),o.r32(o32+0x34)))
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    def rms(v): return (sum(x*x for x in v)/len(v))**0.5
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP)
        ret=o.r32(esp)
        if ret==0x1000e691 or ret==0x1000e681:
            p=o.r32(esp+4); n=o.r32(esp+8)
            try:
                r=rms(fl(p,n)); print("  EC0 ret=%08x p=%08x n=%d rms=%.6g  p[:4]=%s"%(ret,p,n,r,["%.6g"%x for x in fl(p,4)]))
            except Exception as e: print("  EC0 bad",hex(p),n)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002ec0,end=0x10002ec1)
    o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    for nm,base in (('o8exc',o.r32(o8+0x3c)),('o16_34',o.r32(o16+0x34)),('o32_34',o.r32(o32+0x34))):
        print("   %s rmsS=[%s]"%(nm,", ".join("%.4g"%rms(fl(base+40*k,40)) for k in range(4))))
probe(38,"frame 38")
probe(0,"frame 0")
