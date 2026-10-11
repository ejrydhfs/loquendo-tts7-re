#!/usr/bin/env python3
"""Dump the two band-level objects' fields and the L1 combine output, frames 37..39."""
import sys, struct, json
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210_oracle as O
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EDX

o = O.Oracle(); r32 = o.r32; mem = o.uc.mem_read
frame_no = [0]; recs = []

def fields(p, n=0x30):
    return {hex(0x4*k): r32(p + 4*k) for k in range(n)}

def hook(uc, addr, size, user):
    sp = uc.reg_read(UC_X86_REG_ESP); esi = uc.reg_read(UC_X86_REG_ESI); f = frame_no[0]
    if addr == 0x1000e170:
        recs.append(dict(k='entry', f=f, ret=r32(sp), esi=esi))
    elif addr == 0x1000e8ae:
        recs.append(dict(k='comb', f=f, esi=esi, A=uc.reg_read(UC_X86_REG_EDX),
                         B=r32(sp), out=uc.reg_read(UC_X86_REG_ECX),
                         fields=fields(esi, 0x20),
                         ring=list(struct.unpack("<24f", bytes(mem(r32(esi+0x28), 96))))))
    elif addr == 0x1000e87b:
        recs.append(dict(k='bfA', f=f, esi=esi, src=r32(sp+4), dst=r32(sp+12)))

for a in (0x1000e170, 0x1000e8ae, 0x1000e87b):
    o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a+1)

d = open(O.BIN, "rb").read()
ctx = o.open_decoder(32000, 0x6D)
for i in range(40):
    frame_no[0] = i
    o.decode(ctx, d[O.BLOCK_OFFSET + i*O.BLOCK_SIZE: O.BLOCK_OFFSET + (i+1)*O.BLOCK_SIZE])

print("entries (return addresses of FUN_1000e170):")
for r in recs:
    if r['k'] == 'entry' and 37 <= r['f'] <= 38:
        print("  f%d ret=%08x esi=%08x" % (r['f'], r['ret'], r['esi']))
print()
for r in recs:
    if r['k'] == 'comb' and 37 <= r['f'] <= 38:
        print("f%d comb esi=%08x A=%08x B=%08x out=%08x" % (r['f'], r['esi'], r['A'], r['B'], r['out']))
        print("   fields:", r['fields'])
        print("   ring[0:24]:", ["%.1f" % v for v in r['ring'][:12]])
