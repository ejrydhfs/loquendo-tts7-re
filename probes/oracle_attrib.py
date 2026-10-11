#!/usr/bin/env python3
"""Attribute writes into the 8k excitation region to the code that performs them.

The code hook is authoritative for the executing address; a write hook paired with
the last-seen code address gives reliable attribution (the EIP reported inside a
memory hook is not reliable in this Unicorn setup).
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

import collections
import struct
import sys

sys.path.insert(0, _os.path.join(_ROOT, "tools"))
import codec210_oracle as O
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_EIP

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 38
d = open(O.BIN, "rb").read()
o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

last = {"addr": 0}
hits = collections.Counter()
vals = collections.defaultdict(list)


def cb_code(uc, address, size, user):
    last["addr"] = address


def cb_write(uc, access, address, size, value, user):
    if 0x30000000 <= address < 0x30020000:
        hits[last["addr"]] += 1
        if len(vals[last["addr"]]) < 4:
            vals[last["addr"]].append((address, struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]))


o.uc.hook_add(UC_HOOK_CODE, cb_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb_write)
o.decode(ctx, d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE])
print("top code addresses writing into 0x3000xxxx/0x3001xxxx (frame %d):" % FRAME)
for a, n in hits.most_common(18):
    print("  %#010x  n=%5d  sample=%s" % (a, n, [(hex(x), round(v, 2)) for x, v in vals[a]]))
