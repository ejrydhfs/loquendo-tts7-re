import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def probe(NF,label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    tmp={}
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP); obj=uc.reg_read(UC_X86_REG_ESI)
        if obj!=o16: return
        if a==0x1000e691: tmp['addr']=esp+0x28
        if a==0x1000e695:
            ad=tmp.get('addr')
            print("  energy stored at %08x = %.6g"%(ad, f32(ad) if ad else 0))
        if a==0x1000e68c:
            ptr=o.r32(esp+4); n=o.r32(esp+8)
            print("  EC0(ptr=%08x, n=%d) ptr[:4]=%s"%(ptr,n,["%.6g"%x for x in fl(ptr,4)]))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e691,end=0x1000e692)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e695,end=0x1000e696)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e68c,end=0x1000e68d)
    pcm=o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print("=== %s pcm=%.2f"%(label,(sum(x*x for x in pcm)/640)**0.5))
probe(38,"frame 38")
probe(0,"frame 0")
