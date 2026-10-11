#!/usr/bin/env python3
"""Verify the exact LTP model on several frames:

    out[i] = g[2]*S[i] + g[1]*S[40+i] + g[0]*S[80+i]
    S = 120-float window copied from buf[h-(lag+1)], g = gains at 0x201fe4b8..4c0
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

import struct
import sys

sys.path.insert(0, _os.path.join(_ROOT, "tools"))
import codec210_oracle as O
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP

CALL, RET = 0x10009C0D, 0x10009C0F
FRAMES = [int(x) for x in sys.argv[1:]] or [20, 38, 60]
d = open(O.BIN, "rb").read()
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
pend = {}
snaps = []


def rdf(a, n):
    return list(struct.unpack("<%df" % n, bytes(o.uc.mem_read(a, 4 * n))))


def rdint(a):
    return struct.unpack("<i", bytes(o.uc.mem_read(a, 4)))[0]


def cb(uc, a, s, u):
    if a == CALL:
        esp = uc.reg_read(UC_X86_REG_ESP)
        st = struct.unpack("<14I", bytes(uc.mem_read(esp, 56)))
        pend["h"] = st[0]
    elif a == RET and pend:
        snaps.append((pend["h"], rdf(pend["h"], 40), rdf(0x3000E0A4, 120),
                      rdf(0x201FE4B8, 3), rdint(0x201FE4A4)))


o.uc.hook_add(UC_HOOK_CODE, cb)
prev = 0
for fr in FRAMES:
    for i in range(prev, fr):
        o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])
    snaps.clear()
    o.decode(ctx, d[O.BLOCK_OFFSET + fr * O.BLOCK_SIZE:O.BLOCK_OFFSET + (fr + 1) * O.BLOCK_SIZE])
    print("== frame %d: %d calls" % (fr, len(snaps)))
    for n, (h, out, S, g, lag) in enumerate(snaps):
        err = 0.0
        sig = sum(x * x for x in out)
        for i in range(40):
            pred = g[2] * S[i] + g[1] * S[40 + i] + g[0] * S[80 + i]
            err += (pred - out[i]) ** 2
        rel = 100.0 * err / sig if sig else 0.0
        print("   call %d h=%#x lag=%3d gains=%-28s err=%.3f (%.4f%%)" %
              (n, h, lag, [round(x, 5) for x in g], err, rel))
    prev = fr + 1
