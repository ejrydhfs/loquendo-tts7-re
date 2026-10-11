#!/usr/bin/env python3
"""Closed-loop codec verification harness (run it after every patch).

Compares the pure-Python decoder (`tools/codec210.py`) with the emulator's ground truth
(`tools/codec210_oracle.py`) and prints correlation / rms / amplitude tables, plus - with
`--excitation` - the per-subframe correlation of the 8k excitation against the emulator's
buffer, which is the earliest stage where a mistake shows up.

Usage:
    # ground truth (once):
    tools/venv/bin/python tools/codec210_oracle.py 0 120 0x6d jorge_re/ref_pcm_f0_119.raw
    # then:
    python3 tools/verify_codec.py jorge_re/ref_pcm_f0_119.raw [nframes]

Requires only stdlib for the port side; the oracle half needs unicorn+pefile.
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

sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import codec210 as C
import render_bin as R


BIN = _p("LTTS7_BIN", "voice", "data", "voices", "Jorge",
         "Jorge.32000.LTTS7Codec210.44000.10.bin")


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (da * db + 1e-9) if da * db else 0.0


def rms(v):
    return (sum(x * x for x in v) / len(v)) ** 0.5


def main():
    ref_path = sys.argv[1] if len(sys.argv) > 1 else "jorge_re/ref_pcm_f0_119.raw"
    nframes = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    ref = list(struct.unpack("<%dh" % (len(open(ref_path, "rb").read()) // 2), open(ref_path, "rb").read()))
    c = R.read_container(BIN)
    p = R.codec210_params(c)
    dec = C.Codec210()
    mine = []
    for i in range(nframes):
        mine.extend(dec.decode_frame(R.frame_bytes(c, p, i), key=p["frame_xor"]))
    n = min(len(mine), len(ref))
    print("frames %d, samples %d" % (nframes, n))
    print("GLOBAL corr %+.4f   rms mine %8.1f  ref %8.1f  (ratio %.3f)"
          % (corr(mine[:n], ref[:n]), rms(mine[:n]), rms(ref[:n]),
             rms(mine[:n]) / (rms(ref[:n]) + 1e-9)))
    print("%-12s %-9s %10s %10s" % ("frames", "corr", "mine", "ref"))
    for k in range(0, nframes, 10):
        a = mine[k * 640:(k + 1) * 640]
        b = ref[k * 640:(k + 1) * 640]
        print("%3d-%3d     %+.4f   %10.1f %10.1f" % (k, k + 9, corr(a, b), rms(a), rms(b)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
