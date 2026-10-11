#!/usr/bin/env python3
"""Snapshot the heap region at the end of each level (the combine call), and
capture the tail state before every band-filter call, frames 36..39."""
import sys, struct, json
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210_oracle as O
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EDX

LO, HI = 0x3000d000, 0x30019000
o = O.Oracle()
r32 = o.r32
mem = o.uc.mem_read
frame_no = [0]
recs = {'bf': [], 'comb': []}
BF = {0x1000e87b: 'A', 0x1000e898: 'B'}

def snap():
    raw = bytes(mem(LO, HI - LO))
    return struct.unpack("<%df" % ((HI - LO)//4), raw)

def hook(uc, addr, size, user):
    sp = uc.reg_read(UC_X86_REG_ESP); esi = uc.reg_read(UC_X86_REG_ESI); f = frame_no[0]
    lvl = 'L1' if esi == 0x30007fe0 else ('L2' if esi == 0x300021a0 else hex(esi))
    if addr in BF:
        a = [r32(sp + 4*k) for k in range(8)]
        recs['bf'].append(dict(frame=f, lvl=lvl, filt=BF[addr], src=a[0], cf=a[1], dst=a[2],
                               oc=a[3], ntaps=a[4], tail=a[5], work=a[6],
                               tail_pre=list(struct.unpack("<64f", bytes(mem(a[5], 256))))))
    elif addr == 0x1000e8ae:
        recs['comb'].append(dict(frame=f, lvl=lvl, out=uc.reg_read(UC_X86_REG_ECX),
                                 A=uc.reg_read(UC_X86_REG_EDX), B=r32(sp), snap=snap()))

for a in list(BF) + [0x1000e8ae]:
    o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a+1)

d = open(O.BIN, "rb").read()
ctx = o.open_decoder(32000, 0x6D)
pcm = []
for i in range(40):
    frame_no[0] = i
    pcm.append(o.decode(ctx, d[O.BLOCK_OFFSET + i*O.BLOCK_SIZE: O.BLOCK_OFFSET + (i+1)*O.BLOCK_SIZE]))

keep_bf = [r for r in recs['bf'] if 36 <= r['frame'] <= 39]
keep_cb = [r for r in recs['comb'] if 36 <= r['frame'] <= 39]
json.dump({'lo': LO, 'bf': keep_bf, 'comb': keep_cb,
           'pcm_rms': {i: (sum(x*x for x in pcm[i])/640)**0.5 for i in range(36, 40)}},
          open('/tmp/snaps2.json', 'w'))
print("bf calls:", len(keep_bf), "comb calls:", len(keep_cb))
for r in keep_cb:
    print(r['frame'], r['lvl'], 'A=%08x B=%08x out=%08x' % (r['A'], r['B'], r['out']))
