#!/usr/bin/env python3
"""Diff the port against the DLL, stage by stage, on the frames whose windows are not exactly 1.0.

Dumps, for one frame: the DLL's 8 kHz excitation (0x30012364+160*sf), the 8 kHz synthesis buffer,
the 16 kHz / 32 kHz exc and A/B buffers (discovered from the object pointers used by the running
decoder) and the final PCM; then the port's corresponding values.  Prints max abs diff / relative
error per stage and sub-frame so the first divergent stage is visible.

Requires: unicorn + pefile.
Usage: /tmp/uv/bin/python tools/../probes/oracle_stage_diff.py <frame>
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
import codec210 as C
import codec210_oracle as O
import render_bin as R
from unicorn import UC_HOOK_CODE

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 161
d = open(O.BIN, "rb").read()
frame = d[O.BLOCK_OFFSET + FRAME * O.BLOCK_SIZE:O.BLOCK_OFFSET + (FRAME + 1) * O.BLOCK_SIZE]
EXC8 = 0x30012364


def rf(a, n):
    return list(struct.unpack("<%df" % n, bytes(o.uc.mem_read(a, 4 * n))))


o = O.Oracle()
ctx = o.open_decoder(32000, 0x6D)
for i in range(FRAME):
    o.decode(ctx, d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE])

# capture the DLL's excitation per subframe during this frame (hook the 4 writers' store site)
last = {"a": 0}
stages = {}


def cb_code(uc, a, s, u):
    last["a"] = a


def cb_w(uc, acc, addr, size, val, u):
    if size == 4 and EXC8 <= addr < EXC8 + 640:
        i = (addr - EXC8) // 4
        sf, k = divmod(i, 40)
        stages.setdefault(sf, {})[k] = struct.unpack("<f", struct.pack("<I", val & 0xFFFFFFFF))[0]


from unicorn import UC_HOOK_MEM_WRITE
o.uc.hook_add(UC_HOOK_CODE, cb_code)
o.uc.hook_add(UC_HOOK_MEM_WRITE, cb_w)
pcm_dll = o.decode(ctx, frame)

# port side
c = R.read_container(O.BIN)
p = R.codec210_params(c)
dec = C.Codec210()
snaps = {}
orig_synth = dec.synth8


def synth8_cap(lsf_cur):
    out = orig_synth(lsf_cur)
    snaps["sig8"] = list(out)
    return out


dec.synth8 = synth8_cap
for i in range(FRAME):
    dec.decode_frame(d[O.BLOCK_OFFSET + i * O.BLOCK_SIZE:O.BLOCK_OFFSET + (i + 1) * O.BLOCK_SIZE],
                     key=p["frame_xor"])
pcm_port = dec.decode_frame(frame, key=p["frame_xor"])
exc8_port = list(dec.buf[C.HIST:C.HIST + 160])

print("frame %d" % FRAME)
for sf in range(4):
    dll = [stages.get(sf, {}).get(k) for k in range(40)]
    if any(v is None for v in dll):
        print("  sf%d: incomplete DLL capture" % sf)
        continue
    prt = exc8_port[40 * sf:40 * sf + 40]
    md = max(abs(a - b) for a, b in zip(dll, prt))
    rms = (sum(x * x for x in prt) / 40) ** 0.5
    print("  exc8 sf%d: max abs diff %.6g  (rms %.1f, rel %.3g)" % (sf, md, rms, md / (rms + 1e-9)))
d = list(pcm_dll)
pp = list(pcm_port)
print("  PCM: max abs diff %d  corr %.6f" %
      (max(abs(a - b) for a, b in zip(d, pp)),
       sum(x * y for x, y in zip(d, pp)) /
       (math.sqrt(sum(x * x for x in d)) * math.sqrt(sum(x * x for x in pp)) + 1e-9)))
