#!/usr/bin/env python3
"""Locate the true window offset: slide the real 120-float LTP window over (a) the emulator's
excitation buffer and (b) the port's buffer, and report the best offset + correlation.

If the emulator's best offset is h-(lag+1) (expected) but the port's best offset differs, the
port's window assembly is shifted; if the port's buffer is simply wrong, no offset will fit.

Requires: unicorn + pefile.
Usage: tools/venv/bin/python tools/oracle_window_offset.py [frame]
"""

import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)                      # repo root (tools/ or probes/ are one level down)
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

sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "tools"))
import codec210 as C
import codec210_oracle as O
import render_bin as R
from unicorn import UC_HOOK_CODE


FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 38
RET, SCRATCH = 0x10009C0F, 0x3000E0A4
HISTBASE = 0x30012120          # 145 floats of history, then the frame at 0x30012364
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
        S = list(struct.unpack("<120f", bytes(uc.mem_read(SCRATCH, 480))))
        buf = list(struct.unpack("<305f", bytes(uc.mem_read(HISTBASE, 305 * 4))))
        lag = struct.unpack("<i", bytes(uc.mem_read(0x201FE4A4, 4)))[0]
        snaps.append((S, buf, lag))


o.uc.hook_add(UC_HOOK_CODE, cb)
o.decode(ctx, frame)

c = R.read_container(O.BIN)
p = R.codec210_params(c)
dec = C.Codec210()
for i in range(FRAME):
    dec.decode_frame(d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE],
                     key=p["frame_xor"])


def best_offset(S, buf, lo=-10, hi=200):
    best = None
    for off in range(lo, hi):
        seg = buf[off:off + 120] if off >= 0 else ([0.0] * (-off) + buf[0:off + 120])
        if len(seg) < 120:
            continue
        c2 = corr(S, seg)
        if best is None or c2 > best[0]:
            best = (c2, off)
    return best


for k, (S, buf, lag) in enumerate(snaps):
    exp = HIST = 145 + 40 * k - (lag + 1)
    print("sf%d lag=%2d expected offset %3d" % (k, lag, exp))
    print("   emulator buffer best: corr %+.4f at offset %d" % best_offset(S, buf))
    # port window for the same subframe (recomputed exactly as the port does, before writes)
    sp = 145 + 40 * k - (lag + 1)
    pw = dec.buf[sp:sp + 120]
    print("   port window at %d: corr(real S, port window) %+.4f   port buffer best: corr %+.4f at offset %d"
          % (sp, corr(S, pw), *best_offset(S, list(dec.buf)[:305])))
