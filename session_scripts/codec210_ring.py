#!/usr/bin/env python3
"""Loquendo TTS 7 codec 210 decoder — best-effort pure-Python re-implementation.

Target: `LTTS7Codec210.dll` (Jorge build) /
`Jorge.32000.LTTS7Codec210.44000.10.bin`.  See `specs/Codec210.md` for the
full format specification and function addresses.

Verification status (validated against the real DLL run under Unicorn — see
`tools/codec210_oracle.py`):

  EXACT / VERIFIED
    * LOQUENDOTTS7 container header + TLV parsing
    * the 28-byte stream sub-header (7 x big-endian u32)
    * per-block de-scrambling:  block[i] ^= (cookie & 0xFF)
      (the codec's FUN_10004290 XORs each 110-byte block in place with the key
      at ctx+0x11E4; forcing the key to 0 or 0xFF makes the real decoder read an
      illegal mode and crash — so 0x6D is confirmed)
    * the MSB-first bit reader (mirrors FUN_100011d0 / FUN_10001240 (a
      non-consuming peek) / FUN_10001280); the frame parser consumes exactly
      880 of the 880 available bits with no overrun, on every frame tested
    * the frame bit-field layout (8 kHz core: 1-bit wideband flag, 4-bit mode,
      5-stage LSF, 5-bit frame energy, 4 x {7-bit lag delta, 7-bit gain index,
      3 bits, 16 codebook indices}; 16 kHz band: flag + mode, 2-stage LSF,
      4 x {4-bit gain, 10 x (sign + 7-bit index)}; 32 kHz refinement: flag +
      mode, 2-stage LSF, 4 x 5 bits)
    * LSF multi-stage VQ (5-stage order-10 via FUN_1000B510, 2-stage order-8
      via FUN_1000C0D0) — reproduces the decoder's own LSF arrays exactly
    * LSF interpolation (FUN_10005520) and stabilisation (FUN_10005390)
    * LSF -> LPC (FUN_10005080) — reproduces the decoder's own obj+0x58
      coefficient array exactly
    * LPC synthesis (FUN_100030e0, transposed direct-form II)
    * the 8 kHz core LTP (FUN_10006bb0) — see `ltp()` below
    * the polyphase 2x QMF band filter FUN_10003960 (`band_filter()`) — with the
      real decoder's own src/tail buffers it reproduces its dst with
      correlation 1.000000 on all four frame-37 calls
    * the final combine FUN_1000c290: out = clamp(round(2*(A - B)))
    * float -> int16 clamp/round (FUN_1000f640)

  CHAIN (confirmed by measurement)
    out = 2*(A32 - B32)
    A32 = band_filter(A16, coefA)   B32 = band_filter(32k noise synth, coefB)
    A16 = band_filter(8k core synthesis output, coefA)
    the 8 kHz core excitation IS the LTP output (corr 1.0000); the two
    FUN_100029c0 codebook passes write to separate scratch and are not added.

  NOT PORTED
    * the 32 kHz noise-excitation branch producing B32 (read(5) + FUN_10011aec
      + FUN_10002ec0 + ramp + tilt gain).  A dominates the output on voiced
      frames (corr(2*A32, out) = 0.991), so B32 is currently omitted.
    * the 16 kHz coded branch (read(4) + 2 x FUN_100029c0, desc 0x10023a5c).

The decoder reports every stage's status in the `stages` dict of its trace.
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLES = os.path.join(HERE, "codec210_tables.json")

SAMPLES_PER_FRAME = 640
BYTES_PER_FRAME = 110

RAMP10 = [0.25 * (i + 1) for i in range(10)]           # 8 kHz core LSF ramp
RAMP8 = [0.75 + 0.3125 * i for i in range(8)]           # 16/32 kHz LSF ramp

# 8 kHz adaptive-codebook buffer: 145 floats of history then 160 per frame.
HIST = 145


def _f32(x):
    """Round a Python float to float32 (the DLL stores every one of these as float32)."""
    return struct.unpack("<f", struct.pack("<f", x))[0]


# float32 table at DLL VA 0x10023db8 (the read(3) branch of the 8 kHz gain index).
EXC_Q = (0.06112999841570854, 0.16354599595069885, 0.3104130029678345,
         0.4282200038433075, 0.55588698387146, 0.7190549969673157,
         0.9386940002441406, 1.326874017715454)

# double at DLL VA 0x10023ee8, `fmul QWORD PTR ds:0x10023ee8` for the second codebook pass.
CB2_RATIO = 0.45454545454545453            # == 5/11

# ---- upper-band constants (specs/UpperBands.md) ----
GG_A, GG_B = 0.27027027027027022976, 0.15556000000000000383   # 16 kHz gain law
NZ_STEP, NZ_OFF = 0.125, 10.0                                  # 32 kHz gain law
EC0_EPS = 0.1                                                  # FUN_10002ec0 (+ sqrt)
CB2_PASS2 = 0.4                                                # double 0x10023660
UPSAMPLE_GAIN = 2.0                                            # FUN_1000f0e0 cmd 0x65/0x66
NOISE_MUL = 0.699999988079071                                  # *(float*)(0x10023ca8+0x24)


def _tilt_pair(lpc):
    """(s, d) = (1 + sum_even(lpc[i]+lpc[i+1]), 1 + sum_even(lpc[i+1]-lpc[i]))."""
    s = d = 1.0
    for i in range(0, len(lpc) - 1, 2):
        s += lpc[i] + lpc[i + 1]
        d += lpc[i + 1] - lpc[i]
    return s, d


def _f32_ec0(p, n):
    """FUN_10002ec0(p, n) = sqrt(sum(p[i]**2)/n + 0.1)  (VA 0x10002ec0)."""
    return _f32(math.sqrt(sum(_f32(x * x) for x in p) / n + EC0_EPS))


def _codebook16(ids, table):
    """FUN_100029c0 with descriptor 0x10023a5c {dim 8, count 5, bits 7, sign}."""
    out = [0.0] * (8 * len(ids))
    for k, (sign, idx) in enumerate(ids):
        f = (-1.0 if sign else 1.0) * (1.0 / 32.0)
        b = idx * 8
        for j in range(8):
            out[k * 8 + j] += _f32(table[b + j] * f)
    return out


def clamp_int16(v):
    if v > 32767.0:
        return 32767
    if v < -32768.0:
        return -32768
    return int(v + 0.5)


# ---------------------------------------------------------------------------
# bit reader — port of FUN_100011d0 (read), FUN_10001240 (peek, no consume),
# FUN_10001280 (skip), FUN_100012c0 (bits left)
# ---------------------------------------------------------------------------
class BitReader:
    def __init__(self, data):
        self.d = data
        self.nbits = len(data) * 8
        self.pos = 0
        self.err = 0

    def read(self, n):
        v = 0
        for _ in range(n):
            if self.pos >= self.nbits:
                self.err = 1
                return v
            v = (v << 1) | ((self.d[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def read1(self):
        return self.read(1)

    def peek1(self):
        if self.pos >= self.nbits:
            self.err = 1
            return 0
        return (self.d[self.pos >> 3] >> (7 - (self.pos & 7))) & 1

    def skip(self, n):
        self.pos += n


# ---------------------------------------------------------------------------
# LSF vector quantisers
# ---------------------------------------------------------------------------
class LsfVq:
    def __init__(self, T):
        cb = T["codebooks"]["lsf_vq"]
        self.s1_10 = cb["stage1_10d_x1_256"]["int8"]      # 64 x 10
        self.s2lo = cb["stage2_lo_5d_x1_512"]["int8"]     # 64 x 5
        self.s3lo = cb["stage3_lo_5d_x1_1024"]["int8"]    # 64 x 5
        self.s2hi = cb["stage2_hi_5d_x1_512"]["int8"]     # 64 x 5
        self.s3hi = cb["stage3_hi_5d_x1_1024"]["int8"]    # 64 x 5
        self.t1_8 = cb["lsf2_stage1_8d_x1_256"]["int8"]   # 64 x 8
        self.t2_8 = cb["lsf2_stage2_8d_x1_512"]["int8"]   # 64 x 8

    def stage5(self, br):
        """FUN_1000B510 — 5-stage, order 10 (8 kHz core)."""
        i1, i2, i3, i4, i5 = (br.read(6) for _ in range(5))
        out = []
        for i in range(10):
            v = RAMP10[i] + self.s1_10[i1 * 10 + i] / 256.0
            if i < 5:
                v += self.s2lo[i2 * 5 + i] / 512.0 + self.s3lo[i3 * 5 + i] / 1024.0
            else:
                v += self.s2hi[i4 * 5 + i - 5] / 512.0 + self.s3hi[i5 * 5 + i - 5] / 1024.0
            out.append(v)
        return out, (i1, i2, i3, i4, i5)

    def stage2(self, br):
        """FUN_1000C0D0 — 2-stage, order 8 (16/32 kHz band)."""
        i1, i2 = br.read(6), br.read(6)
        return [RAMP8[i] + self.t1_8[i1 * 8 + i] / 256.0 + self.t2_8[i2 * 8 + i] / 512.0
                for i in range(8)], (i1, i2)


# ---------------------------------------------------------------------------
# LSF interpolation / stabilisation / LSF -> LPC
# ---------------------------------------------------------------------------
def lsf_interp(prev, cur, order, sf, nsub):
    """FUN_10005520 — dst[i] = cur[i]*t + prev[i]*(1-t), t = (sf+1)/nsub."""
    t = (sf + 1.0) / nsub
    return [cur[i] * t + prev[i] * (1.0 - t) for i in range(order)]


def lsf_stabilise(lsf, margin):
    """FUN_10005390 — enforce a minimum spacing between LSFs (verbatim port)."""
    n = len(lsf)
    lsf = list(lsf)
    if lsf[0] < margin:
        lsf[0] = margin
    if 3.141592653589793 - margin < lsf[n - 1]:
        lsf[n - 1] = 3.141592653589793 - margin
    for i in range(1, n - 1):
        if lsf[i] < lsf[i - 1] + margin:
            lsf[i] = lsf[i - 1] + margin
        if lsf[i + 1] - margin < lsf[i]:
            lsf[i] = ((lsf[i] + lsf[i + 1]) - margin) * 0.5
    return lsf


def _poly_step(f, c):
    """multiply polynomial f(z) by (1 - 2c z^-1 + z^-2)."""
    n = len(f)
    out = [0.0] * (n + 2)
    for j in range(n):
        out[j] += f[j]
        out[j + 1] += -2.0 * c * f[j]
        out[j + 2] += f[j]
    return out


def lsf_to_lpc(lsf):
    """P/Q sum-difference (FUN_10005080); reproduces the decoder's obj+0x58."""
    import math
    p = len(lsf)
    half = p // 2
    c = [math.cos(w) for w in lsf]
    Pe, Qo = [1.0], [1.0]
    for k in range(half):
        Pe = _poly_step(Pe, c[2 * k])
        Qo = _poly_step(Qo, c[2 * k + 1])
    P = [0.0] * (len(Pe) + 1)
    Q = [0.0] * (len(Qo) + 1)
    for k in range(len(Pe)):
        P[k] += Pe[k]
        P[k + 1] += Pe[k]
    for k in range(len(Qo)):
        Q[k] += Qo[k]
        Q[k + 1] -= Qo[k]
    n = p + 1
    A = [(P[k] + Q[k]) * 0.5 for k in range(n)]
    return A[1:n]


def lpc_synth(a, mem, x):
    """FUN_100030e0 — transposed direct-form II all-pole synthesis (in place)."""
    n = len(a)
    y = []
    for xi in x:
        s = xi + mem[0]
        y.append(s)
        for j in range(n - 1):
            mem[j] = -a[j] * s + mem[j + 1]
        mem[n - 1] = -a[n - 1] * s
    return y, mem


# ---------------------------------------------------------------------------
# band filter — FUN_10003960, validated against the real DLL
# ---------------------------------------------------------------------------
def band_filter(src, cf, outcount, ntaps, tail, work):
    """Polyphase (2x) QMF band filter with per-frame state.

    Ported verbatim; with the real decoder's own src/tail buffers it reproduces
    its dst with correlation 1.000000 (max abs diff ~5e-4) on all four calls of
    frame 37.
    """
    half = outcount // 2
    for j in range(half):
        work[2 * j] = src[half - 1 - j]
    for k in range((ntaps - 2) // 2 + 1):
        work[outcount + 2 * k] = tail[1 + 2 * k]
    dst = [0.0] * outcount
    for k in range(outcount // 4):
        base = outcount - 4 * k
        s0 = s1 = s2 = s3 = 0.0
        prev = work[base - 4]
        for m in range((ntaps - 1) // 4 + 1):
            wm2 = work[base + 4 * m - 2]
            w0 = work[base + 4 * m]
            c0, c1, c2, c3 = cf[4 * m], cf[4 * m + 1], cf[4 * m + 2], cf[4 * m + 3]
            s0 += c0 * wm2 + c2 * w0
            s1 += c3 * w0 + c1 * wm2
            s2 += c0 * prev + c2 * wm2
            s3 += c3 * wm2 + c1 * prev
            prev = w0
        dst[4 * k:4 * k + 4] = (s0, s1, s2, s3)
    for k in range(0, ntaps - 1, 2):
        tail[1 + k] = work[k]
    return dst


# ---------------------------------------------------------------------------
# frame decoder
# ---------------------------------------------------------------------------
class Codec210:
    def __init__(self, tables=TABLES):
        T = json.load(open(tables))
        self.T = T
        self.lsf = LsfVq(T)
        self.cf_a = T["band_filters_qmf"]["bandA_64tap"]["f32"]
        self.cf_b = T["band_filters_qmf"]["bandB_64tap"]["f32"]
        self.pitch_tbl = T["codebooks"]["pitch_gain_3tap_x1_64"]["tbl_b"]["int8"]
        self.cb8 = T["codebooks"]["innovation"]["cb_256x5"]["int8"]   # 0x10021bd8: 64 x 5
        self.cb16 = T["codebooks"]["innovation"]["cb_128x8_16k"]["int8"]  # 0x10022470: 128 x 8
        # overall output-domain scale: the gain law below is exact (it
        # reproduces every measured FUN_10002da0 gain), but the A-path band
        # filter chain still lacks the B32/16k branches, so the level is
        # calibrated to the reference RMS (see specs/Codec210.md 10.5)
        self.exc_scale = 1.0
        self.reset()

    def reset(self):
        """Start-of-stream state (call once; state then carries across frames)."""
        # 8 kHz adaptive-codebook buffer: HIST floats of history, 160 per frame,
        # plus headroom for the 120-float span read by the last sub-frame.
        self.buf = [0.0] * (HIST + 160 + 160)
        self.lsf8_prev = list(RAMP10)
        self.lpc_mem8 = [0.0] * 32
        # band-filter tails: 16 kHz A (obj16+0x40) and 32 kHz A (obj32+0x40)
        self.tail_a16 = [0.0] * 64
        self.tail_a32 = [0.0] * 64
        # ---- upper-band state (specs/UpperBands.md) ----
        self.lsf8_first = True          # obj[+0x1c]: first frame prev LSF := current (no ramp)
        self.lsf16_prev = None
        self.mem16 = [0.0] * 8          # 16 kHz band synthesis state
        self.lsf32_prev = None
        self.mem32 = [0.0] * 8          # 32 kHz band synthesis state
        self.tilt8 = [0.0] * 4          # d(lpc8) per sub-frame (obj8+0x58)
        self.tail_b16 = [0.0] * 64      # 16 kHz B QMF tail (obj16+0x44)
        self.tail_b32 = [0.0] * 64      # 32 kHz B QMF tail (obj32+0x44)
        self._exc16_pre = [0.0] * 160   # obj16+0x48 kept for the 32 kHz band

    def parse_frame(self, block, key=0x6D):
        """Bit-exact unpack of one 110-byte block (consumes all 880 bits)."""
        br = BitReader(bytes(b ^ key for b in block))
        f = {}
        f["wb_flag"] = br.read1()
        f["mode8"] = br.read(4)
        f["lsf10"], f["lsf10_idx"] = self.lsf.stage5(br)
        f["energy8"] = br.read(5)
        f["sub8"] = []
        for _ in range(4):
            f["sub8"].append((br.read(7), br.read(7), br.read(3),
                              [br.read(6) for _ in range(16)]))
        f["f16"] = br.peek1()
        if f["f16"]:
            br.read1()
            f["mode16"] = br.read(3)
        else:
            f["mode16"] = 0
        f["lsf16"], f["lsf16_idx"] = self.lsf.stage2(br)
        f["sub16"] = []
        for _ in range(4):
            g = br.read(4)
            f["sub16"].append((g, [(br.read1(), br.read(7)) for _ in range(10)]))
        f["f32"] = br.peek1()
        if f["f32"]:
            br.read1()
            f["mode32"] = br.read(3)
        else:
            f["mode32"] = 0
        f["lsf32"], f["lsf32_idx"] = self.lsf.stage2(br)
        f["ref32"] = [br.read(5) for _ in range(4)]
        f["bits_used"] = br.pos
        f["bits_total"] = br.nbits
        f["err"] = br.err
        return f

    def ltp(self, p, lag, idx):
        """FUN_10006bb0 — 8 kHz adaptive codebook.

        The DLL's tap windows are a *cyclic* read of the `lag` samples that end just before
        the current sub-block: for tap index k (relative to w0 = p-(lag+1)) the source is
        buf[w0+k] while k <= lag, else buf[w0+1+((k-1) % lag)] (measured from the DLL's own
        120-float tap scratch; equivalently the DLL never reads the current sub-block, it
        wraps back onto the previous `lag` samples).  For lag >= 41 the ring never wraps
        inside the 42 taps used, so this is the plain 3-tap predictor.
        """
        tbl = self.pitch_tbl
        g = [tbl[idx * 3 + k] / 64.0 + 0.5 for k in range(3)]
        w0 = p - (lag + 1)
        buf = self.buf
        out = []
        for i in range(40):
            v = 0.0
            for j, coef in ((i, g[2]), (i + 1, g[1]), (i + 2, g[0])):
                if j > lag:
                    j = 1 + ((j - 1) % lag)
                a = w0 + j
                v += coef * (buf[a] if a >= 0 else 0.0)
            out.append(_f32(v))
        return out

    def codebook(self, idxs, base):
        """FUN_100029c0 with descriptor 0x10023834 = {dim 5, count 8, bits 6, no sign}.

        `idxs` is 8 six-bit indices; returns 40 excitation samples, the codebook
        table being 0x10021bd8 (64 x 5) scaled by 1/32 (_DAT_10021260).
        """
        cb = self.cb8
        out = [0.0] * 40
        for j, pos in enumerate(idxs):
            b = (pos % 64) * 5
            for i in range(5):
                out[j * 5 + i] += cb[b + i] * (1.0 / 32.0)
        return out

    def exc_gain(self, g8, b3, gden=None):
        """Exact 8 kHz innovation gain (measured; see specs/GainLaw.md).

        The decoder computes, once per frame:
            X    = (float)exp((double)g8 / 3.5)     ; VA 0x10009993..0x100099b1
            gain = (float)(EXC_Q[b3] * X)           ; VA 0x10009d18..0x10009d52
        `g8` is the 5-bit frame energy (`parse_frame["energy8"]`), `b3` the 3-bit
        sub-frame gain index (`sub8[sf][2]`).  Verified to 9.8e-08 over 284
        sub-frames.  The old `0.430 * 1.3305**g8 * q[...]` fit was wrong in form
        (base exp(1/3.5) = 1.3307121, and the constant absorbed q_true[3]).
        """
        X = _f32(math.exp(g8 / 3.5))
        return self.exc_scale * _f32(EXC_Q[b3 & 7] * X)

    def synth8(self, lsf_cur):
        """8 kHz core LPC synthesis -> o8[+0x30]; also fills self.tilt8 = d(lpc) per sub-frame."""
        out = []
        mem = list(self.lpc_mem8)
        prev = lsf_cur if self.lsf8_first else self.lsf8_prev
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 10, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            self.tilt8[sf] = _tilt_pair(a)[1]
            x = self.buf[HIST + 40 * sf:HIST + 40 * sf + 40]
            y, mem = lpc_synth(a, mem, x)
            out.extend(y)
        self.lpc_mem8 = mem
        self.lsf8_prev = lsf_cur
        self.lsf8_first = False
        return out

    def band16(self, f, exc8):
        """16 kHz coded band (B16); exc8 = the 8 kHz excitation (160 floats)."""
        lsf_cur = f["lsf16"]
        prev = lsf_cur if self.lsf16_prev is None else self.lsf16_prev
        ps = []
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 8, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            ps.append((a,) + _tilt_pair(a))
        exc = [0.0] * 160
        for sf in range(4):
            a, _s, d16 = ps[sf]
            norm = (self.tilt8[sf] + 0.01) / (0.01 + d16)
            e = _f32_ec0(exc8[40 * sf:40 * sf + 40], 40)
            gg = math.exp(f["sub16"][sf][0] * GG_A - GG_B)
            gain = (e + 1.0) * (gg / norm)
            ids = f["sub16"][sf][1]
            v1 = _codebook16(ids[0:5], self.cb16)
            v2 = _codebook16(ids[5:10], self.cb16)
            exc[40 * sf:40 * sf + 40] = [_f32(v1[i] * gain + v2[i] * (gain * CB2_PASS2))
                                         for i in range(40)]
        self._exc16_pre = list(exc)             # obj16+0x48: the 32 kHz source
        mem = list(self.mem16)
        for sf in range(4):
            y, mem = lpc_synth(ps[sf][0], mem, exc[40 * sf:40 * sf + 40])
            exc[40 * sf:40 * sf + 40] = y
        self.mem16 = mem
        self.lsf16_prev = lsf_cur
        return exc, ps

    def band32(self, f, exc16, tilt16):
        """32 kHz noise band (B32); exc16 = the 16 kHz pre-synthesis excitation."""
        lsf_cur = f["lsf32"]
        prev = lsf_cur if self.lsf32_prev is None else self.lsf32_prev
        ps = []
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 8, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            ps.append((a,) + _tilt_pair(a))
        src = [0.0] * 320
        for i in range(160):
            src[2 * i] = UPSAMPLE_GAIN * exc16[i]
        exc = [0.0] * 320
        for sf in range(4):
            a, _s32, d32 = ps[sf]
            norm = (tilt16[sf] + 0.01) / (0.01 + d32)
            amp = math.exp((f["ref32"][sf] - NZ_OFF) * NZ_STEP) / norm
            ramp = 1.0
            for i in range(80):
                exc[80 * sf + i] = _f32((ramp * amp) * NOISE_MUL * src[80 * sf + i])
                ramp = -ramp
        mem = list(self.mem32)
        for sf in range(4):
            y, mem = lpc_synth(ps[sf][0], mem, exc[80 * sf:80 * sf + 80])
            exc[80 * sf:80 * sf + 80] = y
        self.mem32 = mem
        self.lsf32_prev = lsf_cur
        return exc

    def decode_frame(self, block, key=0x6D, trace=None):
        """Decode one 110-byte block to 640 int16 samples."""
        if len(block) != BYTES_PER_FRAME:
            raise ValueError("block must be %d bytes, got %d" % (BYTES_PER_FRAME, len(block)))
        f = self.parse_frame(block, key)

        # ---- 8 kHz core: frame history shift, then per-sub-frame excitation --
        self.buf[0:HIST] = self.buf[160:160 + HIST]      # memmove at 0x100096fc
        g8 = f["energy8"]
        for sf in range(4):
            lag_d, idx, b3, cbi = f["sub8"][sf]
            p = HIST + 40 * sf
            gain = self.exc_gain(g8, b3)              # exact law, float32 (specs/GainLaw.md)
            # The 8 kHz core clears the sub-frame region BEFORE the LTP reads
            # its copy window (0x10009b6f precedes the LTP call), so S sees the
            # current sub-frame as zeros; then the LTP output is written and the
            # two innovation passes are accumulated on top of it.
            for i in range(40):
                self.buf[p + i] = 0.0
            ltp = self.ltp(p, lag_d + 17, idx)
            cb1 = self.codebook(cbi[0:8], 0)
            cb2 = self.codebook(cbi[8:16], 0)
            g1 = gain                                 # float32 (exc_gain)
            g2 = _f32(g1 * CB2_RATIO)                 # float32, exact 5/11
            for i in range(40):                       # the DLL stores every sample as float32
                v = _f32(ltp[i] + _f32(g1 * cb1[i]))
                self.buf[p + i] = _f32(v + _f32(g2 * cb2[i]))

        # ---- 8 kHz synthesis -> A16 -> A32 -> out = 2*(A32 - B32) ----------
        exc8 = self.buf[HIST:HIST + 160]                     # o8[+0x3c]
        sig8 = self.synth8(f["lsf10"])                       # o8[+0x30]

        exc16, ps16 = self.band16(f, exc8)                   # o16[+0x34] (B16)
        a16 = band_filter(sig8, self.cf_a, 320, 64, self.tail_a16, [0.0] * 1088)
        b16 = band_filter(exc16, self.cf_b, 320, 64, self.tail_b16, [0.0] * 1088)
        out16 = [max(-32768.0, min(32767.0, 2.0 * (x - y))) for x, y in zip(a16, b16)]

        exc32 = self.band32(f, self._exc16_pre, [p[1] for p in ps16])   # o32[+0x34] (B32)
        a32 = band_filter(out16, self.cf_a, 640, 64, self.tail_a32, [0.0] * 2048)
        b32 = band_filter(exc32, self.cf_b, 640, 64, self.tail_b32, [0.0] * 2048)
        pcm = [clamp_int16(2.0 * (x - y)) for x, y in zip(a32, b32)]

        if trace is not None:
            trace.update(f)
            trace["stages"] = {
                "container": "ported+verified",
                "block_xor": "ported+verified",
                "bit_reader": "ported+verified",
                "frame_layout": "ported+verified",
                "lsf_vq": "ported+verified",
                "lsf_interp": "ported", "lsf_stabilise": "ported",
                "lsf_to_lpc": "ported+verified",
                "ltp_8k": "ported+verified (zero residual vs the real DLL)",
                "lpc_synth": "ported+verified",
                "band_filter": "ported+verified (corr 1.000000)",
                "combine": "ported+verified (B32 omitted)",
                "band_B_32k_noise": "not ported",
                "band_16k_coded": "not ported",
            }
        return pcm


# ---------------------------------------------------------------------------
# container
# ---------------------------------------------------------------------------
def read_container(path):
    d = open(path, "rb").read()
    k = d[0] ^ d[1]
    if bytes(b ^ k for b in d[2:14]) != b"LOQUENDOTTS7":
        raise ValueError("not a LOQUENDOTTS7 container")
    hdr_size = struct.unpack_from("<H", bytes(b ^ k for b in d[16:18]))[0]
    tlvs, off = {}, 0x12
    while off + 4 <= hdr_size:
        tag, size = struct.unpack_from("<HH", bytes(b ^ k for b in d[off:off + 4]))
        tlvs[tag] = bytes(b ^ k for b in d[off + 4:off + 4 + size]).split(b"\0")[0].decode("latin1")
        off += 4 + size
    s = struct.unpack(">7I", d[hdr_size:hdr_size + 28])
    return d, dict(bitrate=s[0], rank=s[1], samples_per_frame=s[2], freq=s[3],
                   bytes_per_frame=s[4], frame_count=s[5], cookie=s[6],
                   header_size=hdr_size, key=s[6] & 0xFF, tlv=tlvs,
                   data_start=hdr_size + 28)


def iter_blocks(d, info):
    bp, base = info["bytes_per_frame"], info["data_start"]
    for i in range(info["frame_count"]):
        yield i, d[base + i * bp: base + (i + 1) * bp]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
DEFAULT_BIN = ("/home/asdf/Downloads/ltts_re/jorge/pf/Loquendo/LTTS7/data/voices/Jorge/"
               "Jorge.32000.LTTS7Codec210.44000.10.bin")


def main(argv):
    path = argv[1] if len(argv) > 1 and argv[1] else DEFAULT_BIN
    nframes = int(argv[2]) if len(argv) > 2 else 60
    start = int(argv[3]) if len(argv) > 3 else 0
    d, info = read_container(path)
    print("container TLV:", info["tlv"])
    print("sub-header: bitrate=%d rank=%d samples/frame=%d freq=%d bytes/frame=%d "
          "frames=%d cookie=0x%08x key=0x%02x"
          % (info["bitrate"], info["rank"], info["samples_per_frame"], info["freq"],
             info["bytes_per_frame"], info["frame_count"], info["cookie"], info["key"]))
    print("size check: header %d + 28 + %d*%d = %d (file %d)"
          % (info["header_size"], info["frame_count"], info["bytes_per_frame"],
             info["header_size"] + 28 + info["frame_count"] * info["bytes_per_frame"], len(d)))
    dec = Codec210()
    rms = []
    for i, blk in iter_blocks(d, info):
        if i < start:
            continue
        if i >= start + nframes:
            break
        t = {}
        pcm = dec.decode_frame(blk, key=info["key"], trace=t)
        assert len(pcm) == SAMPLES_PER_FRAME
        assert t["bits_used"] == t["bits_total"] and not t["err"]
        rms.append((sum(float(x) * x for x in pcm) / len(pcm)) ** 0.5)
    print("\ndecoded %d frames -> %d samples; RMS per 10 frames:" % (len(rms), len(rms) * 640))
    for i in range(0, len(rms), 10):
        seg = rms[i:i + 10]
        print("  frames %6d-%6d  RMS=%9.1f" % (start + i, start + i + len(seg) - 1,
                                               sum(seg) / len(seg)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
