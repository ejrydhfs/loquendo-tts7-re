#!/usr/bin/env python3
"""Render one unit of a Loquendo TTS 7 voice, binary-free.

    python3 tools/render_unit.py <voice.bin> <voice.sde> <unit-index> [out.wav]

Chain: container (render_bin) -> inventory (sde_parse) -> 10 us positions (pos*Fs/100000)
       -> samples (linear PCM cut, or Codec210 decode) -> WAV.

`Coding=linear` databases need no decoder. `LTTS7Codec210` databases need tools/codec210.py
(Codec210 work-package); frames are de-obfuscated with the key at sub-header byte 27.
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
import wave

import render_bin as R
import sde_parse as S


def samples_for_records(recs, freq):
    """recs: iterable of dicts with start/end in 10 us units (sde_parse records)."""
    spans = []
    for r in recs:
        a = r["start"] * freq // 100000
        b = r["end"] * freq // 100000
        if b > a:
            spans.append((a, b))
    spans.sort()
    if not spans:
        return []
    lo, hi = spans[0][0], max(b for _, b in spans)
    return [(a, b) for a, b in spans], lo, hi


def get_pcm(c, lo, hi):
    """Return PCM samples for the sample range [lo,hi) using the container's coding."""
    coding = c["fields"].get("Coding", "")
    if coding == "linear":
        pcm, freq = R.pcm_from_linear(c)
        return list(pcm[lo:hi]), freq
    if coding == "LTTS7Codec210":
        p = R.codec210_params(c)
        spf = p["samples_per_frame"]
        f0, f1 = lo // spf, (hi + spf - 1) // spf
        try:
            import codec210
        except ImportError:
            raise SystemExit("codec210 decoder missing (tools/codec210.py required for %s)" % coding)
        dec = codec210.Codec210()
        out = []
        for i in range(f0, f1):
            out.extend(dec.decode_frame(R.frame_bytes(c, p, i), key=p["frame_xor"]))
        return out[lo - f0 * spf: hi - f0 * spf], p["freq"]
    raise SystemExit("unknown Coding %r" % coding)


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    binp, sdep, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
    out = sys.argv[4] if len(sys.argv) > 4 else "unit%d.wav" % idx
    c = R.read_container(binp)
    hdr, units, _ = S.parse(sdep)
    u = units[idx]
    recs = u.lr if u.lr else u.d
    spans, lo, hi = samples_for_records(recs, int(c["fields"]["Freq"]))
    pcm, freq = get_pcm(c, lo, hi)
    seg = []
    for a, b in spans:
        # positions are absolute: shift into the fetched window
        seg.extend(pcm[a - lo:b - lo])
    print("unit %d tokens=%s records=%d" % (idx, u.tokens, len(recs)))
    print("  sample range %d..%d (%d) -> rendered %d samples (%.3f s)"
          % (lo, hi, hi - lo, len(seg), len(seg) / freq))
    rms = (sum(float(x) * x for x in seg) / max(1, len(seg))) ** 0.5
    print("  RMS %.1f" % rms)
    w = wave.open(out, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(freq)
    w.writeframes(struct.pack("<%dh" % len(seg), *seg))
    w.close()
    print("  wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
