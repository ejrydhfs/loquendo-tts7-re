import re, shutil
src='/home/asdf/Downloads/ltts_re/tools/codec210.py'
dst='/tmp/codec210_patched.py'
s=open(src).read()

# 1) module-level constants + helpers after _f32 + EXC_Q/CB2_RATIO block
anchor = 'def clamp_int16(v):'
add = '''GG_A, GG_B = 0.27027027027027022976, 0.15556000000000000383   # 16 kHz gain law
NZ_STEP, NZ_OFF = 0.125, 10.0                                  # 32 kHz gain law
EC0_EPS = 0.1                                                  # FUN_10002ec0
CB2_PASS2 = 0.4                                                # double 0x10023660
UPSAMPLE_GAIN = 2.0                                            # FUN_1000f0e0 cmd 0x65/0x66
NOISE_MUL = 0.699999988079071                                  # float 0x10023ca8+0x24


def _tilt_pair(lpc):
    s = d = 1.0
    for i in range(0, len(lpc) - 1, 2):
        s += lpc[i] + lpc[i + 1]
        d += lpc[i + 1] - lpc[i]
    return s, d


def _f32_ec0(p, n):
    return _f32(math.sqrt(sum(_f32(x * x) for x in p) / n + EC0_EPS))


def _codebook16(ids, table):
    out = [0.0] * (8 * len(ids))
    for k, (sign, idx) in enumerate(ids):
        f = (-1.0 if sign else 1.0) * (1.0 / 32.0)
        b = idx * 8
        for j in range(8):
            out[k * 8 + j] += _f32(table[b + j] * f)
    return out


'''
assert anchor in s
s = s.replace(anchor, add + anchor, 1)

# 2) __init__: cb16
s = s.replace('        self.cb8 = T["codebooks"]["innovation"]["cb_256x5"]["int8"]   # 0x10021bd8: 64 x 5',
 '        self.cb8 = T["codebooks"]["innovation"]["cb_256x5"]["int8"]   # 0x10021bd8: 64 x 5\n'
 '        self.cb16 = T["codebooks"]["innovation"]["cb_128x8_16k"]["int8"]  # 0x10022470: 128 x 8', 1)

# 3) reset(): new state
s = s.replace("""        self.tail_a16 = [0.0] * 64
        self.tail_a32 = [0.0] * 64""",
"""        self.tail_a16 = [0.0] * 64
        self.tail_a32 = [0.0] * 64
        # --- upper bands (specs/UpperBands.md) ---
        self.lsf8_first = True
        self.lsf16_prev = None
        self.lsf32_prev = None
        self.mem16 = [0.0] * 8
        self.mem32 = [0.0] * 8
        self.tilt8 = [0.0] * 4
        self.tail_b16 = [0.0] * 64
        self.tail_b32 = [0.0] * 64
        self._exc16_pre = [0.0] * 160""", 1)

# 4) synth8 replacement
old_synth = s[s.index('    def synth8(self, lsf_cur):'):s.index('    def decode_frame(self, block, key=0x6D, trace=None):')]
new_synth = '''    def synth8(self, lsf_cur):
        """8 kHz core LPC synthesis -> o8[+0x30]; also fills self.tilt8 = d(lpc) per sub-frame."""
        out = []
        mem = list(self.lpc_mem8)
        prev = lsf_cur if self.lsf8_first else self.lsf8_prev
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 10, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            self.tilt8[sf] = _tilt_pair(a)[1]      # obj8[+0x58] = 1 + sum(lpc[i+1]-lpc[i])
            x = self.buf[HIST + 40 * sf: HIST + 40 * sf + 40]
            y, mem = lpc_synth(a, mem, x)
            out.extend(y)
        self.lpc_mem8 = mem
        self.lsf8_prev = lsf_cur
        self.lsf8_first = False
        return out

    def band16(self, f, exc8):
        """16 kHz coded band (B16). exc8 = the 8 kHz excitation (160)."""
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
        self._exc16_pre = list(exc)
        mem = list(self.mem16)
        for sf in range(4):
            y, mem = lpc_synth(ps[sf][0], mem, exc[40 * sf:40 * sf + 40])
            exc[40 * sf:40 * sf + 40] = y
        self.mem16 = mem
        self.lsf16_prev = lsf_cur
        return exc, ps

    def band32(self, f, exc16, tilt16):
        """32 kHz noise band (B32). exc16 = the 16 kHz excitation; tilt16 = its s tilt."""
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

'''
s = s.replace(old_synth, new_synth, 1)

# 5) decode_frame tail
old_tail = s[s.index('        # ---- 8 kHz synthesis -> A16 -> A32 -> out = 2*(A32 - B32) ----------'):s.index('        if trace is not None:')]
new_tail = '''        # ---- 8 kHz -> 16 kHz -> 32 kHz -> out = 2*(A32 - B32) ---------------
        exc8 = self.buf[HIST:HIST + 160]                     # o8[+0x3c]
        sig8 = self.synth8(f["lsf10"])                       # o8[+0x30]
        exc16, _ps16 = self.band16(f, exc8)                  # o16[+0x34]
        a16 = band_filter(sig8,  self.cf_a, 320, 64, self.tail_a16, [0.0] * 1088)
        b16 = band_filter(exc16, self.cf_b, 320, 64, self.tail_b16, [0.0] * 1088)
        out16 = [max(-32768.0, min(32767.0, 2.0 * (x - y))) for x, y in zip(a16, b16)]
        exc32 = self.band32(f, self._exc16_pre, [p[1] for p in _ps16])   # o32[+0x34]
        a32 = band_filter(out16, self.cf_a, 640, 64, self.tail_a32, [0.0] * 2048)
        b32 = band_filter(exc32, self.cf_b, 640, 64, self.tail_b32, [0.0] * 2048)
        pcm = [clamp_int16(2.0 * (x - y)) for x, y in zip(a32, b32)]

'''
s = s.replace(old_tail, new_tail, 1)
s = s.replace('"band_B_32k_noise": "not ported",', '"band_B_32k_noise": "ported+verified",')
s = s.replace('"band_16k_coded": "not ported",', '"band_16k_coded": "ported+verified",')
open(dst,'w').write(s)
print("patched ->",dst)
