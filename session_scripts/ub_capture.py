import sys, struct, json
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
NF=38
o = Oracle()
ctx = o.open_decoder(32000, 0x6D)
d=open(BIN,'rb').read()
def run(fr): return o.decode(ctx, d[BLOCK_OFFSET+fr*BLOCK_SIZE:BLOCK_OFFSET+(fr+1)*BLOCK_SIZE])
for i in range(NF): run(i)
o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
cap={}
tilt8={}
def h(uc,a,s,u):
    if a==0x1000f550:
        esp=uc.reg_read(UC_X86_REG_ESP)
        obj=o.r32(esp+4); cmd=o.r32(esp+8); dst=o.r32(esp+0xc)
        if obj==o8 and cmd==100:
            tilt8['dst']=dst
# install hook for the cmd-100 call and run frame 38 while capturing after the call
state_before={}
def h2(uc,a,s,u):
    pass
o.uc.hook_add(UC_HOOK_CODE, lambda uc,a,s,u: tilt8.update({'dst':o.r32(uc.reg_read(UC_X86_REG_ESP)+0xc)}) if (a==0x1000f550 and o.r32(uc.reg_read(UC_X86_REG_ESP)+4)==o8 and o.r32(uc.reg_read(UC_X86_REG_ESP)+8)==100) else None, begin=0x1000f550,end=0x1000f551)
# capture state at the very start of frame 38 decode: hook 0x1000e170 entry (first call for the frame)
order=[]
def h3(uc,a,s,u):
    if a==0x1000e170:
        esp=uc.reg_read(UC_X86_REG_ESP)
        order.append(('enter',esp,uc.reg_read(UC_X86_REG_ESI)))
    if a==0x1000f550 and o.r32(uc.reg_read(UC_X86_REG_ESP)+4)==o8 and o.r32(uc.reg_read(UC_X86_REG_ESP)+8)==100:
        pass
o.uc.hook_add(UC_HOOK_CODE,h3,begin=0x1000e170,end=0x1000e171)
pcm38=run(NF)
print("tilt8 dst:",hex(tilt8.get('dst',0)))
if tilt8.get('dst'): print("tilt8 values:",["%.6g"%x for x in fl(tilt8['dst'],4)])
print("tilts: o8[+0x60]=%08x o16[+0x60]=%08x o32[+0x60]=%08x"%(o.r32(o8+0x60),o.r32(o16+0x60),o.r32(o32+0x60)))
out={
 'pcm38':pcm38,
 'exc16':fl(o.r32(o16+0x48),160),'exc32':fl(o.r32(o32+0x48),320),
 'lpc16':fl(o.r32(o16+0x58),8),'lpc32':fl(o.r32(o32+0x58),8),
 'st16':fl(o.r32(o16+0x5c),16),'st32':fl(o.r32(o32+0x5c),16),
 'lsf16':fl(o.r32(o16+0x4c),8),'lsf32':fl(o.r32(o32+0x4c),8),
 'synth16':fl(o.r32(o16+0x34),160),'synth32':fl(o.r32(o32+0x34),320),
 'buf34_16_pre':fl(o.r32(o16+0x34),160),
 'A16':fl(o.r32(o16+0x38),320),'B16':fl(o.r32(o16+0x3c),320),
 'A32':fl(o.r32(o32+0x38),640),'B32':fl(o.r32(o32+0x3c),640),
 'ring32':fl(o.r32(o32+0x28),320),
 'o8synth':fl(o.r32(o8+0x30),160),
 'tailA16':fl(o.r32(o16+0x40),64),'tailB16':fl(o.r32(o16+0x44),64),
 'tailA32':fl(o.r32(o32+0x40),64),'tailB32':fl(o.r32(o32+0x44),64),
}
json.dump(out,open('/tmp/ub38.json','w'))
print("captured; pcm rms=%.1f"%((sum(x*x for x in pcm38)/640)**0.5))
