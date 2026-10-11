import sys, struct, json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
# hook the o8 cmd-100 dst AND the o32 noise store, plus the CB gain args, frame 0
info={}
def h(uc,a,s,u):
    if a==0x1000f550:
        esp=uc.reg_read(UC_X86_REG_ESP)
        info.setdefault('cmdcalls',[]).append((hex(o.r32(esp+4)),hex(o.r32(esp+8)),hex(o.r32(esp+0xc))))
o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000f550,end=0x1000f551)
pcm0=o.decode(ctx, d[BLOCK_OFFSET:BLOCK_OFFSET+BLOCK_SIZE])
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
print("cmdcalls:",info['cmdcalls'])
print("frame0: exc16[:8]",["%.5g"%x for x in fl(o.r32(o16+0x48),8)])
print("        exc32[:8]",["%.5g"%x for x in fl(o.r32(o32+0x48),8)])
print("        synth16[:8]",["%.5g"%x for x in fl(o.r32(o16+0x34),8)])
print("        synth32[:8]",["%.5g"%x for x in fl(o.r32(o32+0x34),8)])
print("        lsf16",["%.5g"%x for x in fl(o.r32(o16+0x4c),8)])
print("        lsf32",["%.5g"%x for x in fl(o.r32(o32+0x4c),8)])
print("        lpc16",["%.5g"%x for x in fl(o.r32(o16+0x58),8)])
print("        lpc32",["%.5g"%x for x in fl(o.r32(o32+0x58),8)])
print("        tilt16",["%.6g"%x for x in fl(o.r32(o16+0x60),4)])
print("        tilt32",["%.6g"%x for x in fl(o.r32(o32+0x60),4)])
print("        A16[:6]",["%.5g"%x for x in fl(o.r32(o16+0x38),6)])
print("        B16[:6]",["%.5g"%x for x in fl(o.r32(o16+0x3c),6)])
print("        A32[:6]",["%.5g"%x for x in fl(o.r32(o32+0x38),6)])
print("        B32[:6]",["%.5g"%x for x in fl(o.r32(o32+0x3c),6)])
print("        pcm[:8]",pcm0[:8])
