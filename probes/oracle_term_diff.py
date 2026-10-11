#!/usr/bin/env python3
"""Per-subframe term diff: DLL(excitation terms) vs port(excitation terms) for one frame.

Captures the DLL's values in the 8 kHz excitation buffer after each writer
(0x10009b6f clear -> 0x10009c0d LTP -> 0x10009f3e CB1 -> 0x10009ff1 CB2), so
LTP = val(ltp)-val(clear), CB1 = val(cb1)-val(ltp), CB2 = val(cb2)-val(cb1),
and compares each against the port's ltp / gain*cb1 / g2*cb2 term.

Requires: unicorn + pefile.
Usage: /tmp/uv/bin/python probes/oracle_term_diff.py <frame>
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

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 161
EXC8 = 0x30012364
CODES = {0x10009B6F: "clear", 0x10009C0D: "ltp", 0x10009F3E: "cb1", 0x10009FF1: "cb2"}
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]

o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

last = {"a": 0}
st = {}


def cb_code(uc, a, s, u):
    last["a"] = a


def cb_w(uc, acc, addr, size, val, u):
    if size == 4 and EXC8 <= addr < EXC8 + 640 and last["a"] in CODES:
        i = (addr - EXC8) // 4
        sf, k = divmod(i, 40)
        st.setdefault((sf, CODES[last["a"]]), [None] * 40)[k] = \
            struct.unpack("<f", struct.pack("<I", val & 0xFFFFFFFF))[0]


o.uc.hook_add(UC_HOOK_CODE, cb_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb_w)
o.decode(ctx, frame)

# port terms
c = R.read_container(O.BIN)
p = R.codec210_params(c)
dec = C.Codec210()
for i in range(FRAME):
    dec.decode_frame(d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE],
                     key=p["frame_xor"])
terms = {}
orig_ltp, orig_cb = dec.ltp, dec.codebook
f = dec.parse_frame(frame, key=p["frame_xor"])
g8 = f["energy8"]


def cap_ltp(pp, lag, idx):
    r = orig_ltp(pp, lag, idx)
    terms.setdefault(len(terms), {})["ltp"] = list(r)
    terms[len(terms) - 1]["lag"] = lag
    terms[len(terms) - 1]["idx"] = idx
    return r


dec.ltp = cap_ltp
dec.decode_frame(frame, key=p["frame_xor"])

for sf in range(4):
    print("sf%d  lag=%s idx=%s" % (sf, terms.get(sf, {}).get("lag"), terms.get(sf, {}).get("idx")))
    if (sf, "clear") not in st or (sf, "ltp") not in st:
        print("   DLL capture incomplete")
        continue
    dll_ltp = [a - b for a, b in zip(st[(sf, "ltp")], st[(sf, "clear")])]
    prt_ltp = terms.get(sf, {}).get("ltp")
    if prt_ltp:
        md = max(abs(a - b) for a, b in zip(dll_ltp, prt_ltp))
        r = max(abs(a) for a in dll_ltp)
        print("   LTP   maxdiff %.6g (peak %.1f, rel %.3g)" % (md, r, md / (r + 1e-9)))
    if (sf, "cb1") in st and (sf, "cb2") in st:
        dll_cb1 = [a - b for a, b in zip(st[(sf, "cb1")], st[(sf, "ltp")])]
        dll_cb2 = [a - b for a, b in zip(st[(sf, "cb2")], st[(sf, "cb1")])]
        print("   CB1   dll rms %.2f  CB2 dll rms %.2f" %
              ((sum(x * x for x in dll_cb1) / 40) ** .5, (sum(x * x for x in dll_cb2) / 40) ** .5))
