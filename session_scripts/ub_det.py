import sys, struct, json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def probe(NF,label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    ev=[]
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP); obj=uc.reg_read(UC_X86_REG_ESI)
        if a==0x1000e6ce and obj==o16:
            ev.append(('cb', f32(esp+0x1c), f32(esp+0x10), f32(esp+0x28)))
        if a==0x1000e623 and obj==o32:
            ev.append(('nz', f32(esp+0x1c), f32(esp+0x20), o.r32(esp+0x18), o.r32(esp+0x34)))
        if a==0x1000e7bb and obj==o16:
            ev.append(('v16', uc.reg_read(UC_X86_REG_EBX), uc.reg_read(UC_X86_REG_EDI)))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e6ce,end=0x1000e6cf)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e623,end=0x1000e624)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e7bb,end=0x1000e7bc)
    pcm=o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print("=== %s  pcm rms=%.2f"%(label,(sum(x*x for x in pcm)/640)**0.5))
    import math
    for e in ev:
        if e[0]=='cb':
            norm,gg,energy=e[1],e[2],e[3]
            print("  CB norm=%.6g gg=%.6g energy=%.6g  gg/ln: ln(gg)=%.6g"%(norm,gg,energy,math.log(abs(gg)) if gg else 0))
        elif e[0]=='nz':
            norm,amp,ofs,src=e[1],e[2],e[3],e[4]
            print("  NZ norm=%.6g amp=%.6g gain=%.6g ln(gain)=%.6g ofs=%d src[0..3]=%s"%(norm,amp,amp*norm,math.log(amp*norm) if amp*norm>0 else 0,ofs,["%.6g"%x for x in fl(src+ofs,4)]))
        else:
            print("  v16 pfVar12[:6]=%s  pass2scratch[:6]=%s"%(["%.5g"%x for x in fl(e[1],6)],["%.5g"%x for x in fl(e[2],6)]))
probe(38,"frame 38")
probe(0,"frame 0")
