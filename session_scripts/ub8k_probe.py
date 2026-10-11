"""Dump the 8 kHz LSF/interp/LPC/synthesis chain of the DLL for one frame (drift analysis)."""
import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBX, UC_X86_REG_EDI
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")

def run(N):
    d=open(DEFAULT,'rb').read()
    o=Oracle(); ctx=o.open_decoder(32000,0x6D)
    for i in range(N):
        o.decode(ctx, d[BLOCK_OFFSET+i*BLOCK_SIZE:BLOCK_OFFSET+(i+1)*BLOCK_SIZE])
    o32=o.r32(ctx+0x28); o16=o.r32(o32+4); o8=o.r32(o16+4)
    def fl(a,n): return list(struct.unpack("<%df"%n, bytes(o.uc.mem_read(a,4*n))))
    def f32(a): return struct.unpack("<f", bytes(o.uc.mem_read(a,4)))[0]
    log=[]
    def h(uc,a,s,u):
        esp=uc.reg_read(UC_X86_REG_ESP)
        if a==0x10005520:      # lsf_interp(dst, cur, prev, order, sf, nsub)
            log.append(('interp_args', hex(o.r32(esp+4)), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)),
                        o.r32(esp+0x10), o.r32(esp+0x14), o.r32(esp+0x18)))
        if a==0x10005521 or a==0x10009a7d:  # just after the call
            pass
        if a==0x10005390:      # stabilise(lsf, order, margin)
            log.append(('stab', hex(o.r32(esp+4)), o.r32(esp+8), f32(esp+0xc)))
        if a==0x10005080:      # lsf2lpc(lsf, lpc, order, work)
            log.append(('l2l', hex(o.r32(esp+4)), hex(o.r32(esp+8)), o.r32(esp+0xc), hex(o.r32(esp+0x10))))
        if a==0x10002cc0:      # expand(factor, lpc, dst, order)
            log.append(('exp', f32(esp+4), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)), o.r32(esp+0x10)))
        if a==0x100030e0:
            log.append(('synth30e0', hex(o.r32(esp+4)), hex(o.r32(esp+8)), o.r32(esp+0x10), o.r32(esp+0x14), hex(o.r32(esp+0x18))))
        if a==0x10002f80:
            log.append(('synth2f80', hex(o.r32(esp+4)), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)),
                        hex(o.r32(esp+0x10)), o.r32(esp+0x14), o.r32(esp+0x18), hex(o.r32(esp+0x1c))))
        # sample the arrays after each interesting call
        if a==0x10009a7d: log.append(('interp_dst', ["%.7g"%x for x in fl(0x30012900,10)]))
        if a==0x10009a96+0: pass
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002cc0,end=0x10002cc1)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x100030e0,end=0x100030e1)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10002f80,end=0x10002f81)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10005520,end=0x10005521)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10005390,end=0x10005391)
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10005080,end=0x10005081)
    o.decode(ctx, d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE])
    print("=== frame %d  o8=%08x"%(N,o8))
    print("  work arrays after frame: 0x30012870(lpc?)=%s"%["%.6g"%x for x in fl(0x30012870,10)])
    print("  0x300128a0(vq/ramp)=%s"%["%.6g"%x for x in fl(0x300128a0,10)])
    print("  0x300128d0=%s"%["%.6g"%x for x in fl(0x300128d0,10)])
    print("  0x30012900=%s"%["%.6g"%x for x in fl(0x30012900,10)])
    print("  0x30012930(state?)=%s"%["%.6g"%x for x in fl(0x30012930,12)])
    print("  tilt 0x30012a20=%s"%["%.6g"%x for x in fl(0x30012a20,4)])
    print("  sig8 0x30011ea0[:8]=%s"%["%.6g"%x for x in fl(0x30011ea0,8)])
    for e in log: print("   ",e)
for N in (int(sys.argv[1]) if len(sys.argv)>1 else 120,):
    run(N)
