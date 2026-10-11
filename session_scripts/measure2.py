#!/usr/bin/env python3
"""Dump the real A-path stage buffers from LTTS7Codec210.dll under Unicorn.

Call-site semantics (verified from the disassembly):
  * FUN_10003960 is __cdecl: at the `call` instruction ESP points at arg1.
      arg1=src  arg2=coef  arg3=dst  arg4=outcount  arg5=ntaps  arg6=tail  arg7=work
  * FUN_1000c290 is __fastcall: ECX=out, EDX=A, [ESP]=B.
"""
import sys, struct, json
sys.path.insert(0, '/home/asdf/Downloads/ltts_re/tools')
import codec210_oracle as O
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_ESP,
                               UC_X86_REG_ECX, UC_X86_REG_EDX)

BF_SITES = [0x1000e118, 0x1000e135, 0x1000e300, 0x1000e31d, 0x1000e87b, 0x1000e898]
COMB_SITES = [0x1000e148, 0x1000e336, 0x1000e8ae]
SYNTH_SITES = [0x1000e0f4, 0x1000e2e3, 0x1000e849, 0x1000a14a]

o = O.Oracle()
events = []
frame_no = [0]
r32 = o.r32
def rfloats(a, n):
    return struct.unpack("<%df" % n, bytes(o.uc.mem_read(a, 4 * n)))

def hook(uc, addr, size, user):
    sp = uc.reg_read(UC_X86_REG_ESP)
    if addr in BF_SITES:
        a = [r32(sp + 4 * k) for k in range(8)]
        events.append(dict(ev='bf', frame=frame_no[0], site=hex(addr), esp=sp,
                           esi=uc.reg_read(UC_X86_REG_ESI),
                           src=a[0], cf=a[1], dst=a[2], outcount=a[3], ntaps=a[4],
                           tail=a[5], work=a[6]))
    elif addr in COMB_SITES:
        events.append(dict(ev='combine', frame=frame_no[0], site=hex(addr), esp=sp,
                           esi=uc.reg_read(UC_X86_REG_ESI),
                           out=uc.reg_read(UC_X86_REG_ECX), A=uc.reg_read(UC_X86_REG_EDX),
                           B=r32(sp)))
    elif addr in SYNTH_SITES:
        a = [r32(sp + 4 * k) for k in range(7)]
        events.append(dict(ev='synth', frame=frame_no[0], site=hex(addr),
                           esi=uc.reg_read(UC_X86_REG_ESI),
                           edi=uc.reg_read(UC_X86_REG_EDI), args=a))

for a in BF_SITES + COMB_SITES + SYNTH_SITES:
    o.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a + 1)

d = open(O.BIN, "rb").read()
ctx = o.open_decoder(32000, 0x6D)
allpcm = []
for i in range(40):
    frame_no[0] = i
    blk = d[O.BLOCK_OFFSET + i*O.BLOCK_SIZE: O.BLOCK_OFFSET + (i+1)*O.BLOCK_SIZE]
    allpcm.append(o.decode(ctx, blk))
print("decoded 40 frames, events:", len(events))

dump = {}
byf = {}
for e in events:
    byf.setdefault(e['frame'], []).append(e)

for f in range(30, 40):
    rec = {'pcm_rms': (sum(x*x for x in allpcm[f]) / 640) ** 0.5, 'ev': []}
    for e in byf.get(f, []):
        r = dict(e)
        if e['ev'] == 'bf':
            n = e['outcount']
            r['src_vals'] = list(rfloats(e['src'], 640))  # generous
            r['dst_vals'] = list(rfloats(e['dst'], n))
        elif e['ev'] == 'combine':
            r['A_vals'] = list(rfloats(e['A'], 640))
            r['B_vals'] = list(rfloats(e['B'], 640))
        elif e['ev'] == 'synth':
            r['edi_vals'] = list(rfloats(e['edi'], 200))
        rec['ev'].append(r)
    dump[f] = rec

json.dump(dump, open('/tmp/real_apath.json', 'w'))
print("wrote /tmp/real_apath.json")
for f in (37, 38, 39):
    print("=== frame", f, "pcm_rms=%.1f" % dump[f]['pcm_rms'])
    for e in dump[f]['ev']:
        if e['ev'] == 'bf':
            print("  bf  site=%s esi=%08x src=%08x cf=%08x dst=%08x oc=%d ntaps=%d tail=%08x work=%08x"
                  % (e['site'], e['esi'], e['src'], e['cf'], e['dst'], e['outcount'], e['ntaps'], e['tail'], e['work']))
        elif e['ev'] == 'combine':
            print("  comb site=%s esi=%08x out=%08x A=%08x B=%08x" % (e['site'], e['esi'], e['out'], e['A'], e['B']))
        else:
            print("  synth site=%s esi=%08x edi=%08x" % (e['site'], e['esi'], e['edi']))
