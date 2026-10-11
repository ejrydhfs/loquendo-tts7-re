#!/usr/bin/env python3
"""Snapshot the codec's working heap region at the level-1 / level-2 band-filter
call sites, for frames 36..39, plus the final combine buffers."""
import sys, struct, json
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210_oracle as O
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESI, UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EDX

LO, HI = 0x3000d000, 0x30019000
r32 = None
snaps = []
o = O.Oracle()
r32 = o.r32
frame_no = [0]
mem = o.uc.mem_read

def snap(tag):
    raw = bytes(mem(LO, HI - LO))
    return {'tag': tag, 'lo': LO, 'data': list(struct.unpack("<%df" % ((HI - LO)//4), raw))}

def hook(uc, addr, size, user):
    sp = uc.reg_read(UC_X86_REG_ESP)
    esi = uc.reg_read(UC_X86_REG_ESI)
    f = frame_no[0]
    if addr == 0x1000e87b:
        lvl = 'L1' if esi == 0x30007fe0 else ('L2' if esi == 0x300021a0 else hex(esi))
        a = [r32(sp + 4*k) for k in range(8)]
        snaps.append(dict(frame=f, ev='bfA', lvl=lvl, esi=esi, src=a[0], cf=a[1], dst=a[2],
                          oc=a[3], ntaps=a[4], tail=a[5], work=a[6],
                          tailvals=list(struct.unpack("<64f", bytes(mem(a[5], 256)))),
                          snap=snap('bfA')))
    elif addr == 0x1000e8ae:
        snaps.append(dict(frame=f, ev='comb', esi=esi, out=uc.reg_read(UC_X86_REG_ECX),
                          A=uc.reg_read(UC_X86_REG_EDX), B=r32(sp), snap=snap('comb')))

for a in (0x1000e87b, 0x1000e8ae):
    o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a+1)

d = open(O.BIN, "rb").read()
ctx = o.open_decoder(32000, 0x6D)
for i in range(40):
    frame_no[0] = i
    o.decode(ctx, d[O.BLOCK_OFFSET + i*O.BLOCK_SIZE: O.BLOCK_OFFSET + (i+1)*O.BLOCK_SIZE])

keep = [s for s in snaps if 36 <= s['frame'] <= 39]
json.dump(keep, open('/tmp/snaps_apath.json', 'w'))
print("snapshots kept:", len(keep))
for s in keep:
    print(s['frame'], s['ev'], s['lvl'] if 'lvl' in s else '', hex(s.get('src', 0)), hex(s.get('dst', 0)),
          'oc=', s.get('oc'), 'tail=', hex(s.get('tail', 0)))
