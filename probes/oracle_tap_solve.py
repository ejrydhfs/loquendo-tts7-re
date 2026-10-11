#!/usr/bin/env python3
"""Solve the 8 kHz LTP tap indices empirically for the sub-frames whose windows are not exact.

For a given frame: for every pitch call capture the DLL's scratch window (0x3000e0a4 at the call's
return), the DLL's LTP output (buffer 0x30012364, value after the LTP writer) and the gains/idx from
the port's bit parser; then, for each output sample i, search the (a,b,c) tap indices into the
scratch that reproduce it, and print the index pattern as a function of i so the exact wrap rule can
be read off.

Requires: unicorn + pefile.
Usage: /tmp/uv/bin/python probes/oracle_tap_solve.py <frame>
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

import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import codec210 as C
import codec210_oracle as O
import render_bin as R
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 160
EXC8, RET, SCRATCH = 0x30012364, 0x10009C0F, 0x3000E0A4
PITCHW = 0x10009C0D
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]

o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

last = {"a": 0}
scratch, written = [], {}


def cb_code(uc, a, s, u):
    last["a"] = a
    if a == RET:
        scratch.append(list(struct.unpack("<120f", bytes(uc.mem_read(SCRATCH, 480)))))


def cb_w(uc, acc, addr, size, val, u):
    if size == 4 and EXC8 <= addr < EXC8 + 640 and last["a"] == PITCHW:
        i = (addr - EXC8) // 4
        written[i] = struct.unpack("<f", struct.pack("<I", val & 0xFFFFFFFF))[0]


o.uc.hook_add(UC_HOOK_CODE, cb_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb_w)
o.decode(ctx, frame)
print("calls=%d" % len(scratch))

c = R.read_container(O.BIN)
p = R.codec210_params(c)
dec = C.Codec210()
f = dec.parse_frame(frame, key=p["frame_xor"])
tbl = dec.pitch_tbl

for sf in range(min(4, len(scratch))):
    lag_d, idx, b3, cbi = f["sub8"][sf]
    lag = lag_d + 17
    g = [tbl[idx * 3 + k] / 64.0 + 0.5 for k in range(3)]
    dll = [written.get(sf * 40 + i) for i in range(40)]
    S = scratch[sf]
    if any(v is None for v in dll):
        print("sf%d: no capture" % sf)
        continue
    # per-sample index search
    pat = []
    for i in range(40):
        best = None
        for a in range(0, 80):
            for b in range(0, 80):
                for c2 in range(0, 80):
                    v = g[2] * S[a] + g[1] * S[b] + g[0] * S[c2]
                    e = abs(v - dll[i])
                    if best is None or e < best[0]:
                        best = (e, a, b, c2)
        pat.append((best[1], best[2], best[3], best[0]))
    print("\nsf%d lag=%d idx=%d gains=%s" % (sf, lag, idx, [round(x, 4) for x in g]))
    print("   solved (a,b,c,err) per i for i=0..7 and i=36..39:")
    for i in list(range(0, 8)) + list(range(36, 40)):
        a, b, c2, e = pat[i]
        print("     i=%2d -> (%3d,%3d,%3d) err=%.3g     naive=(%d,%d,%d)" % (i, a, b, c2, e, i, i + 1, i + 2))
