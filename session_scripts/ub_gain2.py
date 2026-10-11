import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBX, UC_X86_REG_EAX
from codec210_oracle import Oracle, BIN, BLOCK_OFFSET, BLOCK_SIZE
def run(NF,label):
    o = Oracle(); ctx=o.open_decoder(32000,0x6D); d=open(BIN,'rb').read()
    for i in range(NF): o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    ev=[]
    def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP)
        obj=uc.reg_read(UC_X86_REG_ESI)
        if a==0x1000e6f7 and obj==o16:
            ev.append(('cb', f32(esp+0x28), f32(esp+0x10), f32(esp+0x1c), o.r32(esp+0x18), f32(esp+0x30)))
        if a==0x1000e623 and obj==o32:
            ev.append(('noise', f32(esp+0x1c), f32(esp+0x20), f32(esp+0x10), o.r32(esp+0x18)))
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e6f7,end=0x1000e6f8)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x1000e623,end=0x1000e624)
    o.decode(ctx, d[BLOCK_OFFSET+NF*BLOCK_SIZE:BLOCK_OFFSET+(NF+1)*BLOCK_SIZE])
    print("=== %s"%label)
    for e in ev:
        if e[0]=='cb':  print("  CB sf: energy=%.6g gg=%.6g norm=%.6g g4=%d gain=%.6g"%(e[1],e[2],e[3],e[4],e[5]))
        else:           print("  NOISE sf: norm=%.6g amp=%.6g ramp=%.6g ofs=%d -> gain=%.6g"%(e[1],e[2],e[3],e[4],e[2]*e[1]))
for fr in (38,0,50):
    run(fr,"frame %d"%fr)
