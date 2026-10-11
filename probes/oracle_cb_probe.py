#!/usr/bin/env python3
"""Derive the 8k innovation codebook mapping directly from measurements.

For every 5-sample position of every subframe, search all 64 codebook segments for the one
that (up to a per-position scale) reproduces the measured CB1/CB2 increment, then compare the
derived segment order with the parsed 6-bit indices.

Requires: unicorn + pefile.
"""

import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)
def _p(env, *parts):
    """Path helper: $env wins, else <repo>/<parts...> (put your unpacked voice package under voice/)."""
    v = _os.environ.get(env)
    return v if v else _os.path.join(_ROOT, *parts)
VOICE = _os.environ.get("LTTS7_VOICE", _os.path.join(_ROOT, "voice"))
DLL = _p("LTTS7_DLL", "voice", "bin", "LTTS7Codec210.dll")
BIN = _p("LTTS7_BIN", "voice", "data", "voices", "Jorge",
         "Jorge.32000.LTTS7Codec210.44000.10.bin")

import json
import struct
import sys

sys.path.insert(0, _os.path.join(_ROOT, "tools"))
import codec210_oracle as O
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 38
EXC = 0x30012364
CODES = {0x10009B6F: "clear", 0x10009C0D: "ltp", 0x10009F3E: "cb1", 0x10009FF1: "cb2"}
d = open(O.BIN, "rb").read()
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

last = {"a": 0}
stages = {}


def cb_code(uc, a, s, u):
    last["a"] = a


def cb_w(uc, acc, addr, size, val, u):
    a = last["a"]
    if size == 4 and a in CODES and EXC <= addr < EXC + 640:
        i = (addr - EXC) // 4
        sf, k = divmod(i, 40)
        st = stages.setdefault((sf, CODES[a]), [None] * 40)
        st[k] = struct.unpack("<f", struct.pack("<I", val & 0xFFFFFFFF))[0]


o.uc.hook_add(UC_HOOK_CODE, cb_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb_w)
o.decode(ctx, d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE])

import codec210 as C
T = json.load(open(_os.path.join(_ROOT, "tools", "codec210_tables.json")))
CB = T["codebooks"]["innovation"]["cb_256x5"]["int8"]
NSEG = len(CB) // 5
dec = C.Codec210()
f = dec.parse_frame(d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE],
                    key=0x6D)


def best_seg(block):
    best = None
    for s in range(NSEG):
        seg = CB[s * 5:s * 5 + 5]
        k = sum(a * b for a, b in zip(seg, block)) / (sum(a * a for a in seg) + 1e-12)
        r = sum((b - k * a) ** 2 for a, b in zip(block, seg))
        sig = sum(b * b for b in block) + 1e-12
        if best is None or r / sig < best[0]:
            best = (r / sig, s, k)
    return best


for sf in range(4):
    if (sf, "clear") not in stages:
        continue
    lt, c1, c2 = (stages[(sf, k)] for k in ("ltp", "cb1", "cb2"))
    idxs = f["sub8"][sf][3]
    print("\n=== subframe %d   parsed 6-bit indices: %s" % (sf, idxs))
    for name, y0, y1 in (("cb1", lt, c1), ("cb2", c1, c2)):
        inc = [a - b for a, b in zip(y1, y0)]
        found, scales = [], []
        for j in range(8):
            block = inc[j * 5:j * 5 + 5]
            r, s, k = best_seg(block)
            found.append((s, round(k, 2), round(r, 3)))
        print("  %s: per-5-sample best segment (seg, scale, resid) = %s" % (name, found))
