#!/usr/bin/env python3
"""Find the provenance of the LTP window: search emulator memory for the 120-float scratch
content (and its rotations/reversal) right after a pitch call, then report every address where
it is found - that identifies the buffer the copy reads from.

Requires: unicorn + pefile.
Usage: /tmp/uv/bin/python tools/oracle_find_window.py [frame] [subframe]
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

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 38
RET, SCRATCH = 0x10009C0F, 0x3000E0A4
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

snaps = []


def cb(uc, a, s, u):
    if a == RET:
        snaps.append(bytes(uc.mem_read(SCRATCH, 480)))


o.uc.hook_add(UC_HOOK_CODE, cb)
o.decode(ctx, frame)

REGIONS = [("image", 0x10000000, 0x10040000), ("stack", 0x20000000, 0x20200000),
           ("heap", 0x30000000, 0x30040000), ("stub", 0x71000000, 0x71001000)]
for k, raw in enumerate(snaps):
    vals = struct.unpack("<120f", raw)
    probes = {
        "as-is": list(vals),
        "reversed": list(vals[::-1]),
        "rot60": list(vals[60:] + vals[:60]),
        "rot90": list(vals[90:] + vals[:90]),
    }
    print("=== subframe %d" % k)
    for label, seq in probes.items():
        pat = struct.pack("<24f", *seq[:24])       # first 24 floats are enough
        found = []
        for name, lo, hi in REGIONS:
            try:
                blob = bytes(o.uc.mem_read(lo, hi - lo))
            except Exception:
                continue
            i = blob.find(pat)
            while i >= 0 and len(found) < 6:
                found.append((name, lo + i))
                i = blob.find(pat, i + 1)
        print("   %-9s -> %s" % (label, [(n, hex(a)) for n, a in found]))
