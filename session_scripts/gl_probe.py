#!/usr/bin/env python3
"""Measure the exact 8k innovation gain law from the real DLL.

Captures, per sub-frame:
  * the gain local the codec passes to FUN_10002da0 (CB1) and the CB2 gain,
  * X = the exp() term (stack local esp+0x5c),
  * the gain index read path (read(3) / read(1) / else),
  * the excitation-buffer increments (clear -> ltp -> CB1 -> CB2),
  * the parsed (g8, b3) from the port.
"""
import sys, struct, json, collections
sys.path.insert(0, "/home/asdf/Downloads/ltts_re/tools")
import codec210_oracle as O
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ESI

START = int(sys.argv[1]) if len(sys.argv) > 1 else 30
END = int(sys.argv[2]) if len(sys.argv) > 2 else 70
OUT = sys.argv[3] if len(sys.argv) > 3 else "/tmp/gl_meas.json"

EXC = 0x30012364
CODES = {0x10009B6F: "clear", 0x10009C0D: "ltp", 0x10009F3E: "cb1", 0x10009FF1: "cb2"}

d = open(O.BIN, "rb").read()
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
blocks = [d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE]
          for i in range(END + 1)]
for i in range(START):
    o.decode(ctx, blocks[i])


def f32(a):
    return struct.unpack("<f", bytes(o.uc.mem_read(a, 4)))[0]


last = {"a": 0}
stages = {}
recs = []
ALL = []
sites = collections.Counter()
cur = {}
grab = {}


def h_code(uc, a, s, u):
    last["a"] = a
    if a == 0x10009D56:
        esp = uc.reg_read(UC_X86_REG_ESP)
        cur["gain"] = f32(esp + 0x1C)
        cur["X"] = f32(esp + 0x5C)
        cur["sf"] = o.r32(esp + 0x24)
        cur["reader"] = o.r32(esp + 0x60)
    elif a == 0x10009D94:
        esp = uc.reg_read(UC_X86_REG_ESP)
        cur["cb1_gain"] = f32(esp + 0x1C)
    elif a == 0x10009FB6:
        esp = uc.reg_read(UC_X86_REG_ESP)
        cur["cb2_gain_pre"] = f32(esp + 0x30)
        cur["cb2_gain"] = cur["cb2_gain_pre"] * struct.unpack(
            "<d", bytes(uc.mem_read(0x10023EE8, 8)))[0]
        recs.append(dict(cur))
        cur.clear()
    elif a == 0x10009D18:
        cur["path"] = "read3"
        cur["idx"] = uc.reg_read(UC_X86_REG_EAX)
    elif a == 0x10009D38:
        cur["path"] = "read1"
        cur["idx"] = uc.reg_read(UC_X86_REG_EAX)
    elif a == 0x10009D48:
        cur["path"] = "else"
        cur["idx"] = None
    elif a == 0x10009D08:
        cur["desc8"] = uc.reg_read(UC_X86_REG_EAX)
    elif a == 0x10009CF7:
        esi = uc.reg_read(UC_X86_REG_ESI)
        ma, mode = o.r32(esi + 0x7C), o.r32(esi + 0x80)
        desc = o.r32(ma + 4 * mode)
        cur["modedesc"] = (ma, mode, desc,
                           [o.r32(desc + 4 * k) for k in range(0, 12)])


def h_write(uc, acc, addr, size, val, u):
    a = last["a"]
    if size == 4 and EXC <= addr < EXC + 160:
        sites[a] += 1
        if a in CODES:
            i = addr - EXC
            sf, k = divmod(i, 40)
            stages.setdefault((sf, CODES[a]), [None] * 40)[k] = struct.unpack(
                "<f", struct.pack("<I", val & 0xFFFFFFFF))[0]


o.uc.hook_add(UC_HOOK_CODE, h_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, h_write)

for fr in range(START, END + 1):
    stages = {}
    recs = []
    o.decode(ctx, blocks[fr])
    sfs = sorted(set(sf for sf, _ in stages))
    for pos, r in enumerate(recs):
        r["sf"] = pos
        sf = pos
        if sf in sfs and None not in stages[(sf, "ltp")] + stages[(sf, "cb1")] \
                and None not in stages[(sf, "cb2")]:
            r["inc1"] = [b - a for a, b in zip(stages[(sf, "ltp")], stages[(sf, "cb1")])]
            r["inc2"] = [b - a for a, b in zip(stages[(sf, "cb1")], stages[(sf, "cb2")])]
            r["ltp"] = stages[(sf, "ltp")]
        ALL.append(dict(r, frame=fr))
    if fr == START:
        print("write sites into EXC..EXC+160:", dict(sites))
        print("modedesc:", recs[0].get("modedesc"))
        print("per-frame law-records:", len(recs), "stage sfs:", sfs)

json.dump(ALL, open(OUT, "w"))
print("done", len(ALL))
