#!/usr/bin/env python3
"""Find the wrap rule of the LTP window copy.

The real scratch (0x3000e0a4, read at the call's return) does not equal the plain slice
buf[h-(lag+1) : +120] of the excitation buffer, so the copy loop must wrap (linearisation of a
circular buffer).  Search a rotation (and a possible source-base shift) that makes the two
equal, per subframe.

Requires: unicorn + pefile.
Usage: /tmp/uv/bin/python tools/oracle_window_wrap.py [frame]
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

import math
import struct
import sys

sys.path.insert(0, _os.path.join(_ROOT, "tools"))
import codec210_oracle as O
from unicorn import UC_HOOK_CODE

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 38
RET, SCRATCH, HBASE = 0x10009C0F, 0x3000E0A4, 0x30012120
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (da * db + 1e-9) if da * db else 0.0


o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

snaps = []


def cb(uc, a, s, u):
    if a == RET:
        snaps.append((list(struct.unpack("<120f", bytes(uc.mem_read(SCRATCH, 480)))),
                      list(struct.unpack("<305f", bytes(uc.mem_read(HBASE, 305 * 4)))),
                      struct.unpack("<i", bytes(uc.mem_read(0x201FE4A4, 4)))[0]))


o.uc.hook_add(UC_HOOK_CODE, cb)
o.decode(ctx, frame)

for k, (S, buf, lag) in enumerate(snaps):
    p = 145 + 40 * k
    best = None
    for base in range(p - (lag + 1) - 8, p - (lag + 1) + 9):
        win = buf[base:base + 120]
        if len(win) < 120:
            continue
        for r in range(120):
            rot = win[r:] + win[:r]
            c = corr(S, rot)
            if best is None or c > best[0]:
                best = (c, base, r)
    print("sf%d lag=%2d: best corr %+.5f at base=%d (expected %d) rotation=%d"
          % (k, lag, best[0], best[1], p - (lag + 1), best[2]))
    # also: exact equality check for the best candidate
    c, base, r = best
    win = buf[base:base + 120]
    rot = win[r:] + win[:r]
    md = max(abs(a - b) for a, b in zip(S, rot))
    print("      max abs diff at best = %.6g" % md)
