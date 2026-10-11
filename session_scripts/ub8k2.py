"""Dump the 8 kHz chain (interp/stabilise/LSF2LPC/synthesis) of the DLL for one frame.
Single global code hook (multiple narrow hooks proved unreliable under Unicorn)."""
import sys, struct
sys.path.insert(0,'/home/asdf/Downloads/ltts_re/tools')
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from codec210_oracle import Oracle, BLOCK_OFFSET, BLOCK_SIZE
DEFAULT=("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
         "Jorge.32000.LTTS7Codec210.44000.10.bin")

def run(N, verbose=True):
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
        if a==0x10005520:      # interp(dst, cur, prev, order, sf, nsub)
            log.append(('INTERP', hex(o.r32(esp+4)), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)),
                        o.r32(esp+0x10), o.r32(esp+0x14), o.r32(esp+0x18),
                        ["%.7g"%x for x in fl(o.r32(esp+4),10)]))
        elif a==0x10005390:    # stabilise(lsf, order, margin)
            log.append(('STAB', hex(o.r32(esp+4)), o.r32(esp+8), f32(esp+0xc),
                        ["%.7g"%x for x in fl(o.r32(esp+4),10)]))
        elif a==0x10005080:    # lsf2lpc(lsf, lpc, order, work)
            log.append(('L2L', hex(o.r32(esp+4)), hex(o.r32(esp+8)), o.r32(esp+0xc),
                        ["%.7g"%x for x in fl(o.r32(esp+4),10)]))
        elif a==0x10005081+0x1f: pass
        elif a==0x10002cc0:    # expand(factor, lpc, dst, order)
            log.append(('EXP', f32(esp+4), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)), o.r32(esp+0x10)))
        elif a==0x100030e0:    # synth(dst, lpc, x, n, order, state)
            log.append(('SYNTH', hex(o.r32(esp+4)), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)),
                        o.r32(esp+0x10), o.r32(esp+0x14), hex(o.r32(esp+0x18)),
                        ["%.6g"%x for x in fl(o.r32(esp+4),8)],
                        ["%.6g"%x for x in fl(o.r32(esp+0x18),12)]))
        elif a==0x10002f80:
            log.append(('SYNTH2F80', hex(o.r32(esp+4)), hex(o.r32(esp+8)), hex(o.r32(esp+0xc)),
                        hex(o.r32(esp+0x10)), o.r32(esp+0x14), o.r32(esp+0x18), hex(o.r32(esp+0x1c))))
    # capture arrays right after the interp / l2l / synth calls
    AFTER={0x10009a7d:('interp_dst 0x30012900',0x30012900,10),
           0x10009aac:('lpc 0x30012870',0x30012870,10),
           0x1000a14f:('synth_out 0x30011ea0',0x30011ea0,8),
           0x1000a153:('state 0x30012930',0x30012930,12),
           0x1000a156:('state 0x3001293c',0x3001293c,8)}
    o.uc.hook_add(UC_HOOK_CODE,h,begin=0x10000000,end=0x10040000)
    o.decode(ctx, d[BLOCK_OFFSET+N*BLOCK_SIZE:BLOCK_OFFSET+(N+1)*BLOCK_SIZE])
    if verbose:
        print("=== frame %d"%N)
        for e in log: print("   ",e)
    return o,log,fl

if __name__=='__main__':
    run(int(sys.argv[1]) if len(sys.argv)>1 else 120)
