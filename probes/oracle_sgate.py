#!/usr/bin/env python3
"""S gate: compare the port's adaptive-codebook window with the real decoder's, per subframe.

The real window is the 120-float copy the pitch call leaves in its scratch buffer
(0x3000e0a4, read at the call's RETURN 0x10009c0f - reading it before the call returns stale
data, and the EIP inside memory hooks is unreliable in this Unicorn setup).  The port's window
is captured by monkey-patching Codec210.ltp.

Requires: unicorn + pefile (e.g. tools/venv/bin/python, see tools/oracle_attrib.py).

Usage: tools/venv/bin/python tools/oracle_sgate.py [frame] [exc_scale]
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
SCALE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
RET, SCRATCH = 0x10009C0F, 0x3000E0A4
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]


def rms(v):
    return (sum(x * x for x in v) / len(v)) ** 0.5


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (da * db + 1e-9) if da * db else 0.0


# --- real windows ---
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])
real_S = []


def cb(uc, a, s, u):
    if a == RET:
        real_S.append(list(struct.unpack("<120f", bytes(uc.mem_read(SCRATCH, 480)))))


o.uc.hook_add(UC_HOOK_CODE, cb)
o.decode(ctx, frame)

# --- port windows ---
c = R.read_container(O.BIN)
p = R.codec210_params(c)
dec = C.Codec210()
dec.exc_scale = SCALE
for i in range(FRAME):
    dec.decode_frame(d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE],
                     key=p["frame_xor"])
mine_S = []
orig = dec.ltp


def patched(pp, lag, idx):
    # the real scratch is three 40-float windows of the same region shifted by 0, 1, 2 samples
    w0 = pp - (lag + 1)
    S = [dec.buf[w0 + i] if w0 + i >= 0 else 0.0 for i in range(40)]
    S += [dec.buf[w0 + 1 + i] if w0 + 1 + i >= 0 else 0.0 for i in range(40)]
    S += [dec.buf[w0 + 2 + i] if w0 + 2 + i >= 0 else 0.0 for i in range(40)]
    mine_S.append(list(S))
    return orig(pp, lag, idx)


dec.ltp = patched
dec.decode_frame(frame, key=p["frame_xor"])
print("real S rms %s" % [round(rms(s), 1) for s in real_S])
print("port S rms %s" % [round(rms(s), 1) for s in mine_S])
for k in range(min(len(real_S), len(mine_S))):
    print("  sf%d corr %+.4f   real[:4] %s  port[:4] %s" %
          (k, corr(real_S[k], mine_S[k]),
           [round(x, 1) for x in real_S[k][:4]], [round(x, 1) for x in mine_S[k][:4]]))
