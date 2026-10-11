# Codec 210 — the two upper sub-bands: the 16 kHz *coded* band (B16) and the 32 kHz *noise* band (B32)

Scope: port the two branches that stand between the (now exact) 8 kHz core and the PCM:
the **16 kHz coded band** (which produces `B16`) and the **32 kHz noise band** (which
produces `B32`), plus the exact re-combination of the four-QMF-level tree.
Everything below was measured by running the real `LTTS7Codec210.dll` under Unicorn
(`tools/codec210_oracle.py`) and by re-implementing the two functions in Python and
comparing buffers **exactly** (`tools/`-independent scripts under `/tmp/ub_*.py`).

Status: **CLOSED** — every stage of both bands reproduces the real DLL's own buffer with
correlation **1.000000** (frames 37/38/39: `exc16`, `o16[+0x34]`, `out16=2*(A16-B16)`,
`exc32`, `o32[+0x34]`, `B32`, `A32`).  Applying the patch of §6 verbatim to the current
`tools/codec210.py` gives, against the oracle producing the same 300 frames:
**frames 0..299 PCM corr = 0.997496, rms ratio 0.9910** (frames 37/38/39 =
0.999999/1.000000/1.000000, `exc16` corr = 1.000000).  The residual is (a) ±1 LSB int16
rounding (two independent implementations of the same formulas differ from each other and
from the DLL only in which side of the `(int16)(v+0.5)` boundary the sub-LSB float rounding
order lands) and (b) the 8 kHz chain's own residual on a few frames (e.g. frame 120, where
the *8 kHz* excitation itself is corr 0.922, `sig8` 0.636 — not an upper-band error; the
upper bands then track it at 0.9992/0.9994).  The near-silent frames 0..36 have max abs
sample difference = **1** LSB over all 640 samples.

---

## 1. Where the two bands live (measured object/buffer map)

The decoder instance for 32 kHz is a three-level object chain, built by `FUN_1000db20`:
`ctx+0x28 = o32`, `o32[+0x04] = o16`, `o16[+0x04] = o8`.  Each object is 0x74 bytes and owns
its own `calloc`'d buffers (addresses as observed for the Jorge DB, `ctx = 0x30000010`):

| field | o32 (`0x300021a0`) | o16 (`0x30007fe0`) | o8 (`0x3000de20`) | meaning |
|---|---|---|---|---|
| `+0x08` | 640 | 320 | 0 | `2*samples/sub-block` |
| `+0x0c` | 320 | 160 | 160 | count (samples per object per frame) |
| `+0x10` | 80 | 40 | 40 | samples per sub-block |
| `+0x14` | 4 | 4 | 4 | sub-blocks per frame |
| `+0x18` | 8 | 8 | 10 | LPC order |
| `+0x24` | 0 | 0 | 8000 | rate (0 for the 16/32 kHz classes → **plain** LPC synthesis; the 8 kHz class has 8000 here → its expanded path) |
| `+0x28` | `0x30002220` | `0x30008060` | — | per-object scratch (24000 B): `[0..4*count) = child output mailbox`, then the child tilt / block2 / block3 |
| `+0x2c` | `0x30014380` | `0x30012a30` | — | copy of the child-output mailbox (= the child level's final signal) |
| `+0x34` | `0x30014d80` | `0x30012f30` | `0x30011ea0` | **this level's LPC synthesis output** (the B source) |
| `+0x38` | `0x30015780` | `0x30013430` | — | A output (band filter of `+0x2c` with coefA) |
| `+0x3c` | `0x30016180` | `0x30013930` | `0x30012364` (o8: excitation) | B output / excitation |
| `+0x40`,`+0x44` | `0x30016b80`,`0x30016c80` | `0x30013e30`,`0x30013f30` | — | QMF tails for A / B |
| `+0x48` | `0x30016d80` | `0x30014030` | `0x300128d0` | **this level's excitation** |
| `+0x4c`,`+0x50`,`+0x54` | `0x30017280`,`0x300172a0`,`0x300172c0` | `0x300142b0`,`+20`,`+40` | — | current LSF / previous LSF / interpolated LSF |
| `+0x58`,`+0x5c`,`+0x60` | `0x300172e0`,`0x30017310`,`0x30017300` | `0x30014310`,`0x30014340`,`0x30014330` | (o8: scalars / `0x30012a20` tilt) | LPC / LPC state / per-sub-frame tilt |
| `+0x68`,`+0x6c`,`+0x70` | 1, `0x10023cd0`, mode | 1, `0x10023c20`, mode | 1, …, mode | read-mode flag, mode array, current mode |

Mode arrays (only non-null entries listed):

* 32 kHz `0x10023cd0` = `[0, 0x10023a70, 0, …]` → the Jorge stream's 32 kHz mode is **1**
  → mode object `0x10023a70`, whose `+0x28 == 0` selects the **noise branch**;
* 16 kHz `0x10023c20` = `[0, 0x10023a70, 0x10023ae8, 0x10023b60, 0x10023bb0, 0,0,0]` →
  the Jorge stream's 16 kHz mode is **4** → mode object `0x10023bb0`
  (`+0x28 = FUN_100029c0`, `+0x2c = 0x10023a5c`, `+0xc = 1` → **two** codebook passes);
* 8 kHz mode array `0x100239ec/f0` → mode 7 → `0x100238f8`.

Both upper levels run the *same* function `FUN_1000e170` (`obj`, `ctx` = the bit reader,
`arg3` = the mailbox/out pointer).  It (1) recursively decodes its child
(`FUN_1000f530`, in the reverse order of the bit stream: 8 kHz → 16 kHz → 32 kHz),
(2) copies the child mailbox to `obj+0x2c`, (3) reads its flag+3-bit mode
(`read1`+`read(3)`, always 1/4 and 1/1 for this stream), (4) the 2-stage order-8 LSF VQ
(`modeObj[+0x14]` = `FUN_1000c0d0`), (5) a 4-sub-block loop, (6)
`A = band_filter(obj+0x2c, 0x100240a8, obj+0x38, outcount, 64, tail obj+0x40, work)`,
`B = band_filter(obj+0x34, 0x100241a8, obj+0x3c, outcount, 64, tail obj+0x44, work)`,
`FUN_1000c290(out, A, B)` = `out[i] = clamp_f32(2*(A[i]-B[i]))` (store instructions
`0x1000e87b`/`0x1000e898`/`0x1000e8ae`; writes to `+0x34` at `0x1000e7ca`, to `+0x48` at
`0x1000e65b` / `0x1000e7ab`).

### 1.1 The sub-object scratch/parameter protocol (`FUN_1000f550(sub, cmd, buf)`)

At the top of `FUN_1000e170` the parent asks its **child** for three buffers, placed into
the parent's own scratch (measured: `base = obj[+0x28] + 4*obj[+0xc]`):

| cmd | destination | handler (16/32 kHz class, `FUN_1000f0e0` @ `0x1000f34a/0x1000f374/0x1000f3b5`) | handler (8 kHz class, `0x1000a820` @ `0x1000a9da/0x1000aa04/0x1000aa27`) |
|---|---|---|---|
| 100 (`0x64`) | `base` | copy `obj[+0x60][0..3]` → the **child's tilt array** | copy `obj[+0x58][0..3]` → the 8 kHz tilt array |
| 101 (`0x65`) | `base+0x10` ("block2") | `dst[0..2*obj[+0xc]) = 0` then `dst[2i] = 2.0*obj[+0x48][i]` (×2, zero-interleaved upsample) | plain copy `dst[i] = obj[+0x3c][i]` (the **8 kHz excitation**, 160 floats, no ×2) |
| 102 (`0x66`) | `base+0x10+4*obj[+0xc]` ("block3") | same as 101 | plain copy `dst[i] = obj[+0x40][i]` |

The two class handlers are **different code** — this is the single most easily-missed fact
in the whole chain:

* the **16 kHz** level's own energy comes from **block2 = a plain copy of the 8 kHz
  excitation** (`o8+0x3c`), because the child is the *8 kHz* object;
* the **32 kHz** level's noise source comes from **block3 = `2 * o16[+0x48]`
  zero-interleaved** (320 floats), because the child is the *16 kHz* object.

Measured proof: `o32` scratch block2/block3 (`0x30002730`/`0x30002c30`) =
`[886.774, 0, 1232.832, 0, 724.559, 0, …]` = `2*[443.387, 616.416, 362.280, …]` = exactly
`2*exc16` at the even positions (`exc16 = [443.387, 616.416, 362.280, …]`), while the
16 kHz energy probe reads `p = 0x300082f0 + 160*sf` (a plain copy of `o8[+0x3c]`).

---

## 2. Bit fields consumed (already parsed by `tools/codec210.py`)

The frame layout (880/880 bits, verified) already exposes all four fields:

| band | field | width | `parse_frame` key |
|---|---|---|---|
| 16 kHz | flag + mode | 1 + 3 | `f["f16"]`, `f["mode16"]` (4 for Jorge) |
| 16 kHz | LSF 2 × 6 | 12 | `f["lsf16"]`, `f["lsf16_idx"]` |
| 16 kHz | per sub-block: gain, 10 × (sign, 7-bit index) | 4 + 10·8 | `f["sub16"][sf] = (g4, [(sign, idx)×10])` |
| 32 kHz | flag + mode | 1 + 3 | `f["f32"]`, `f["mode32"]` (1 for Jorge) |
| 32 kHz | LSF 2 × 6 | 12 | `f["lsf32"]`, `f["lsf32_idx"]` |
| 32 kHz | per sub-block: 5-bit noise index | 4 × 5 | `f["ref32"] = [idx5 × 4]` |

Order inside a frame: 8 kHz core (492 bits) → 16 kHz flag/mode/LSF/sub-blocks → 32 kHz
flag/mode/LSF/4×5 bits.  For the 16 kHz sub-blocks the **first 5 (sign,idx) pairs are the
first codebook pass and the last 5 the second pass** (`FUN_100029c0` reads them in order).

---

## 3. The 16 kHz coded band

Per sub-block `sf` (order 8, 40 samples):

1. **LSF**: `lsf = lsf_stabilise(lsf_interp(prev, cur, 8, sf, 4), 0.05)`,
   `lpc = lsf_to_lpc(lsf)` (both already in the port).  The frame's `prev` is the previous
   frame's `cur`; on the **first** frame `prev := cur` (the `obj[+0x1c]` copy at
   `0x1000e3e8`, *after* the LSF VQ) — measured: at frame 0 all four sub-blocks have the
   same LPC (`tilt16 = 1.54544` constant).
2. **tilt**: `s(lpc) = 1 + Σ_{i even<8}(lpc[i]+lpc[i+1])`,
   `d(lpc) = 1 + Σ_{i even<8}(lpc[i+1]-lpc[i])`.
   `s` is stored in `obj[+0x60]` (the child tilt for the 32 kHz level); the 8 kHz level's
   own tilt array (`obj8[+0x58]`, seen by cmd 100) is `d(lpc8)` — the loop at
   `0x10009b30..0x10009b65` computes `1 + Σ(lpc[i+1]-lpc[i])`.
3. **energy** (`FUN_10002ec0(p, n)`, VA `0x10002ec0`):
   `E = sqrt( Σ_{i<n} p[i]² / n + 0.1 )` (the `0.1` is the double at `0x10022120`;
   the plain `Σx²` reading in the old §10.4 was incomplete — the function also divides by
   `n`, adds 0.1 and takes a square root at `0x100105c0`).
   `p = block2 + 4*obj[+0x10]*sf` = **the 8 kHz excitation at that sub-block**
   (`o8[+0x3c]`, 40 samples), `n = 40`.
4. **gain**: `gg = exp(g4 * 0.27027027027 - 0.15556)` (doubles at `0x100242b0`/`0x100242c0`;
   the library call `FUN_10011aec` on that argument returns `exp` — measured: the four
   frame-38 gains reproduce the DLL's internal ones to ≤0.05 %),
   `norm16 = (d_tilt8[sf] + 0.01) / (0.01 + d(lpc16_sf))`,
   `gain = (E + 1.0) * (gg / norm16)`.
5. **codebook** (`FUN_100029c0` with descriptor `0x10023a5c` = `{dim 8, count 5,
   table VA 0x10022470, bits 7, sign 1}`, scale `0.03125` (double `0x10021260`),
   sign multiplier `-1.0` (float `0x10021268`)):
   pass 1 = `v1 = 5 vectors` (40 samples, `v1[j*8+i] += ±table[idx*8+i]/32`),
   pass 2 = `v2` from the last 5 pairs (the mode object's `+0xc = 1` enables it), scaled by
   `0.4` (double `0x10023660`):
   `exc16 = v1*gain + v2*(gain*0.4)`.
   The table row 43 is **all zeros** — the encoder's silence codeword (frame 0, first three
   sub-blocks).
6. **synthesis**: plain `FUN_100030e0(lpc, state, x, 40, 8)` in place (because
   `obj[+0x24] == 0`; the `FUN_10002f80` 3-filter path is *not* taken for the upper bands);
   `state = obj[+0x5c]` is 8 floats and carries across sub-blocks and frames.
   Output `o16[+0x34]`.

Measured table (frame 38, `tools/codec210_oracle.py` vs the Python re-implementation):

| sf | g4 | `E` (mine) | `gg` | `norm16` | gain (mine) | gain (measured in the DLL) |
|---|---|---|---|---|---|---|
| 0 | 0 | 1272.7 | 0.855936 | 2.52055 | 432.526 | **432.573** |
| 1 | 1 | 431.24 | 1.12155 | 3.95995 | 122.42 | **122.42** |
| 2 | 0 | 3429.07 | 0.855936 | 6.79812 | 431.872 | **432.02** |
| 3 | 2 | 601.52 | 1.46959 | 13.2961 | 66.595 | **66.6155** |

The gains were read *inside the DLL* at the `FUN_10002da0` call site (`0x1000e70a`,
`param_3`); the residual ≤0.05 % is float32-vs-double rounding.
For frames 37/38/39, feeding the DLL's own 8 kHz excitation/tilt/LPC state into the Python
code gives `exc16`, `o16[+0x34]`, `B16`, `out16` and the DFT `A16` at **corr 1.000000**.

---

## 4. The 32 kHz noise band

Per sub-block `sf` (order 8, 80 samples):

1. LSF/LPC exactly as above but with the 32 kHz LSF fields (`prev`/`cur` per frame, first
   frame `prev := cur`).
2. `norm32 = (s(lpc16_sf) + 0.01) / (0.01 + d(lpc32_sf))` — the *numerator* is the
   **16 kHz** level's `s` tilt (the value the 16 kHz level stored in `obj[+0x60]` and that
   its parent read via cmd 100).
3. `gain5 = exp((idx5 - 10) * 0.125)` (`idx5 = f["ref32"][sf]`, doubles `0x10022e10 = 10.0`
   and `0x10024300 = 0.125`; `ln(gain5)` measured exactly `0.125, 1.75, -1, 2` for frame 38
   → `idx5 = 11, 24, 2, 26`).  `amp = gain5 / norm32`.
4. source: `src = block3` = `2 * exc16` zero-interleaved (320 floats, `src[2i] = 2*exc16[i]`).
5. per sample `i = 0..79`:
   `exc32[80*sf+i] = ((ramp*amp) * 0.7) * src[80*sf+i]`, `ramp *= -1.0`
   (`ramp` starts at `1.0` for every sub-block; the factor `0.7` is `*(float*)(0x10023ca8+0x24)`
   = `0.699999988079071`; the ramp constant is the double `-1.0` at `0x100242f8`).
   (So the "noise" is a sign-alternating, per-sub-block-gain-scaled band replication of the
   16 kHz excitation — this is what fills the 16–32 kHz band and provides the silence
   noise floor: in silence `exc16` is zero except for the sub-blocks with a real codeword.)
6. synthesis: plain `FUN_100030e0` in place, state `obj[+0x5c]`.

Measured table (frame 38; the norms were read inside the DLL at `0x1000e623` as
`[esp+0x1c]`, the gains at `0x1000e602`):

| sf | idx5 | ln(gain5) | gain5 (mine) | gain5 (DLL) | norm32 (mine) | norm32 (DLL) |
|---|---|---|---|---|---|---|
| 0 | 11 | 0.125 | 1.133148 | **1.13315** | 6.51341 | 6.51323 |
| 1 | 24 | 1.75 | 5.754603 | **5.7546** | 6.83603 | 6.83571 |
| 2 | 2 | −1.0 | 0.367879 | **0.367879** | 7.10982 | 7.10934 |
| 3 | 26 | 2.0 | 7.389056 | **7.38906** | 7.30798 | 7.3074 |

With the DLL's own `exc16` injected, the Python code reproduces `exc32` (`o32[+0x48]`),
`o32[+0x34]` and `B32` at **corr 1.000000** on frames 37/38/39.

---

## 5. The recombined chain (all four levels)

```
o8: exc8 = LTP + CB1 + CB2                      (now exact in tools/codec210.py)
    sig8 = LPC_order10(exc8)                    = o8[+0x30]
o16: exc16 = gain16*(v1 + 0.4*v2)               (section 3)
    b16  = LPC_order8(exc16)                    = o16[+0x34]
    A16  = band_filter(sig8, coefA, 320, 64, tail o16[+0x40], work)
    B16  = band_filter(b16 , coefB, 320, 64, tail o16[+0x44], work)
    out16 = clamp_f32(2*(A16 - B16))            = the 32 kHz level's mailbox (32k obj+0x2c)
o32: exc32 = noise branch (section 4)
    b32  = LPC_order8(exc32)                    = o32[+0x34]
    A32  = band_filter(out16, coefA, 640, 64, tail o32[+0x40], work)
    B32  = band_filter(b32  , coefB, 640, 64, tail o32[+0x44], work)
    pcm  = int16(clamp_f32(2*(A32 - B32)))      (FUN_1000f640: (int16)(v+0.5), ±32767/-32768)
```

Verified facts (oracle, frames 37/38/39): `pcm == clamp(2*(A32-B32))` corr 1.000000;
`o32[+0x2c] == clamp(2*(A16-B16))` corr 1.000000; `o16[+0x2c] == o8[+0x30]` corr 1.000000.
`band_filter`'s intrinsic gain is a flat 1/2 per call, so each level's `×2` is real.

---

## 6. Patch instructions for `tools/codec210.py`

### 6.1 New module-level helpers (place next to `_f32`)

```python
# doubles at DLL VA 0x100242b0 / 0x100242c0 / 0x10024300 / 0x10022e10 / 0x10022120
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
        f = (-1.0 if sign else 1.0) * (1.0 / 32.0)      # _DAT_10021260 / _DAT_10021268
        b = idx * 8
        for j in range(8):
            out[k * 8 + j] += _f32(table[b + j] * f)
    return out
```

The 128×8 int8 table is already extracted: `T["codebooks"]["innovation"]["cb_128x8_16k"]["int8"]`
(VA `0x10022470`, file offset `0x21870`, 1024 bytes).  In `__init__` add
`self.cb16 = T["codebooks"]["innovation"]["cb_128x8_16k"]["int8"]`.

### 6.2 New state in `Codec210.reset()`

```python
        self.lsf8_first = True          # obj[+0x1c]: on the first frame prev LSF := current
        self.lsf16_prev = None; self.mem16 = [0.0] * 8     # 16 kHz band
        self.lsf32_prev = None; self.mem32 = [0.0] * 8     # 32 kHz band
        self.tilt8 = [0.0] * 4          # d(lpc8) per sub-frame (the 8 kHz obj[+0x58])
        self.tail_b16 = [0.0] * 64     # 16 kHz B QMF tail (obj16+0x44)
        self.tail_b32 = [0.0] * 64     # 32 kHz B QMF tail (obj32+0x44)
        self._exc16_pre = [0.0] * 160   # obj16+0x48 kept for band32
```

### 6.3 `synth8` must also record the 8 kHz tilt and use the first-frame LSF rule

Replace the body of `synth8` (keep the signature) by:

```python
    def synth8(self, lsf_cur):
        """8 kHz core LPC synthesis -> o8[+0x30]; also fills self.tilt8 = d(lpc) per sub-frame.

        obj[+0x1c] ("first frame") makes the LSF history equal the current LSF, so frame 0
        does not interpolate (measured: tilt16/tilt8 constant over the 4 sub-blocks of f0).
        """
        out = []
        mem = list(self.lpc_mem8)
        prev = lsf_cur if self.lsf8_first else self.lsf8_prev
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 10, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            self.tilt8[sf] = _tilt_pair(a)[1]          # obj8[+0x58] = 1 + sum(lpc[i+1]-lpc[i])
            x = self.buf[HIST + 40 * sf: HIST + 40 * sf + 40]
            y, mem = lpc_synth(a, mem, x)
            out.extend(y)
        self.lpc_mem8 = mem
        self.lsf8_prev = lsf_cur
        self.lsf8_first = False
        return out
```

with `self.lsf8_first = True` added in `reset()` (the port currently starts
`lsf8_prev = RAMP10`; the DLL starts from the current LSF, which is a 1-frame-only
difference).

### 6.4 The two new band methods

```python
    def band16(self, f, exc8):
        """16 kHz coded band (B16).  exc8 = the 8 kHz excitation (160)."""
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
            norm = (self.tilt8[sf] + 0.01) / (0.01 + d16)     # child(=8k) d-tilt / own d
            e = _f32_ec0(exc8[40 * sf:40 * sf + 40], 40)       # block2 = plain copy of exc8
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
        self.mem16 = mem; self.lsf16_prev = lsf_cur
        return exc, ps

    def band32(self, f, exc16, tilt16):
        """32 kHz noise band (B32).

        `exc16`  = the 16 kHz *excitation* (pre-synthesis), block3 source;
        `tilt16` = the 16 kHz level's per-sub-block `s` tilt (obj16+0x60, read by cmd 100).
        """
        lsf_cur = f["lsf32"]
        prev = lsf_cur if self.lsf32_prev is None else self.lsf32_prev
        ps = []
        for sf in range(4):
            lsf_i = lsf_stabilise(lsf_interp(prev, lsf_cur, 8, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            ps.append((a,) + _tilt_pair(a))
        src = [0.0] * 320
        for i in range(160):
            src[2 * i] = UPSAMPLE_GAIN * exc16[i]        # FUN_1000f0e0 cmd 0x66
        exc = [0.0] * 320
        for sf in range(4):
            a, _s32, d32 = ps[sf]
            norm = (tilt16[sf] + 0.01) / (0.01 + d32)    # 16k s-tilt / own d-tilt
            amp = math.exp((f["ref32"][sf] - NZ_OFF) * NZ_STEP) / norm
            ramp = 1.0
            for i in range(80):
                exc[80 * sf + i] = _f32((ramp * amp) * NOISE_MUL * src[80 * sf + i])
                ramp = -ramp                              # double -1.0 at 0x100242f8
        mem = list(self.mem32)
        for sf in range(4):
            y, mem = lpc_synth(ps[sf][0], mem, exc[80 * sf:80 * sf + 80])
            exc[80 * sf:80 * sf + 80] = y
        self.mem32 = mem; self.lsf32_prev = lsf_cur
        return exc
```

(The `s16` in `band32` is the *16 kHz* `s` tilt from `band16`'s `ps`, i.e. the value the
16 kHz level stores in `obj[+0x60]` and its parent reads by cmd 100.  `band32` must be
called with `self._exc16_pre`, the pre-synthesis 16 kHz excitation, **not** `band16`'s
return value — that one is the synthesized `o16[+0x34]`.)

### 6.5 `decode_frame`: replace the tail from `sig8` onwards

```python
        exc8 = self.buf[HIST:HIST + 160]                     # o8[+0x3c]
        sig8 = self.synth8(f["lsf10"])                       # o8[+0x30]

        exc16, ps16 = self.band16(f, exc8)                   # o16[+0x34] (B16)
        a16 = band_filter(sig8,  self.cf_a, 320, 64, self.tail_a16, [0.0] * 1088)
        b16 = band_filter(exc16, self.cf_b, 320, 64, self.tail_b16, [0.0] * 1088)
        out16 = [max(-32768.0, min(32767.0, 2.0 * (x - y))) for x, y in zip(a16, b16)]

        exc32 = self.band32(f, self._exc16_pre, [p[1] for p in ps16])   # o32[+0x34] (B32)
        a32 = band_filter(out16, self.cf_a, 640, 64, self.tail_a32, [0.0] * 2048)
        b32 = band_filter(exc32, self.cf_b, 640, 64, self.tail_b32, [0.0] * 2048)
        pcm = [clamp_int16(2.0 * (x - y)) for x, y in zip(a32, b32)]
```

`self.exc_scale` stays where it is (it is only used by the 8 kHz gain); with both bands
ported no output-domain calibration is needed (measured rms ratio 0.9910 over 0..299).
Update the `stages` dict: `band_B_32k_noise` / `band_16k_coded` → `"ported+verified"`.

---

## 7. Validation

Scripts (throwaway, in `/tmp`): `ub_stage.py` (stage-local, DLL buffers injected),
`ub_chk2.py`, `apply_patch.py` (applies the §6 patch to a copy of `tools/codec210.py`),
`e2e_patched.py`, `e2e_ranges.py` (end-to-end vs `/tmp/oracle_pcm_0_299.json`, produced by
`tools/codec210_oracle.py`).  All correlations are over the buffers themselves (float) /
the decoded int16 PCM.

**(a) Stage-local with the DLL's own inputs injected** (the DLL's 8 kHz excitation, its
`o8[+0x58]` tilt array, its LPC states and QMF tails are read out of the emulator and fed to
the Python code, so only the newly ported stages are under test):

| frame | exc16 | o16[+0x34] | A16 | B16 | out16 | exc32 | o32[+0x34] | A32 | B32 |
|---|---|---|---|---|---|---|---|---|---|
| 37 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 38 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 39 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

The frame-38 energies `E = [1272.7, 431.24, 3429.07, 601.52]` reproduce the DLL's own
`FUN_10002ec0` results `[1272.877, 431.233, 3429.84, 601.521]` read at `0x1000e691`.

**(a2) The patch generated *directly* from the §6 code blocks**
(`/tmp/gen_from_spec.py` stitches the spec's five code blocks into a copy of
`tools/codec210.py` → `/tmp/codec210_specpatch.py`) has every buffer of the running port
compared against the DLL's own buffers, frames 37/38/39 (no injected inputs — this is the
whole port, 8 kHz chain included):

| frame | exc8 | sig8 | tilt8 | exc16 | o16[+0x34] | A16 | B16 | o32[+0x34] | A32 | B32 | PCM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 37 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.999999 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.999999 |
| 38 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 39 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |

**(b) The patched port end-to-end** (`/tmp/codec210_specpatch.py`, i.e. the patch generated
from the §6 code blocks as in (a2); the module is imported directly, no subclassing):

| range | corr | rms / reference | ratio |
|---|---|---|---|
| 0..299 | **0.997496** | 2805.2 / 2830.35 | 0.9910 |
| 37..299 | 0.997496 | | 0.9910 |
| 40..299 | 0.997443 | | 0.9908 |
| 100..299 | 0.997039 | | 0.9922 |

| frame | 0 | 37 | 38 | 39 | 120 |
|---|---|---|---|---|---|
| PCM corr | 0.8975 | 0.999999 | 1.000000 | 1.000000 | 0.6538 |
| PCM rms | 0.401 / 0.659 | 1245.8 / 1246.6 | 4764.0 / 4765.1 | 5077.6 / 5078.5 | 123.3 / 137.4 |
| `exc16` corr | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.9992 |

Frame 0 (0.8975) and frames 0..36 are the near-silent floor: the port and the DLL differ by
at most **1** int16 LSB on every one of the 640 samples, so the correlation number there is
quantisation noise, not a modelling error.  Frame 120 is an 8 kHz-chain residual (`exc8`
corr 0.922, `sig8` 0.636), not the upper bands.

**(c) Every remaining low-correlation frame traced to the *8 kHz* chain, not the upper
bands.**  56 of the 299 frames score < 0.99; 36 of them are the silent frames 0..36 above,
the other 20 (68, 87, 118–124, 148, 170, 171, 193, 208, 209, 225, 228, 241, 254, 271) are
low-amplitude passages where the 8 kHz excitation itself drifts from the DLL.  Stage trace
on four of them (my buffers vs the DLL's own, same run):

| frame | `exc8` | `sig8` | `tilt8` | `exc16` | `o32[+0x34]` | PCM |
|---|---|---|---|---|---|---|
| 38 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 68 | 0.998471 | 0.992588 | 1.000000 | 0.999332 | 0.998147 | 0.985652 |
| 119 | 0.947833 | 0.926021 | 1.000000 | 0.999526 | 0.999031 | 0.927798 |
| 241 | 0.967982 | 0.968961 | 1.000000 | 0.999790 | 0.999944 | 0.968775 |

i.e. the 16/32 kHz stages track whatever the 8 kHz chain hands them at 0.999+ even when the
8 kHz excitation is only 0.95–0.97 correlated; the PCM loss is inherited, not generated.

**(d) Rounding sensitivity:** the same patch with the three `_f32` helpers in the new code
removed (every intermediate kept in Python double) scores *identically*
(0.997496 / 0.9910 over 0..299, 0.999999/1.000000/1.000000 at frames 37/38/39).  So the
explicit `_f32` calls in §6 only document the DLL's float32 storage; nothing in the metric
depends on them.

Per-frame PCM correlation over frames 37..298: mean **0.995918**, median 1.000000 (the
low frames are exactly those listed in (c)).

## 8. Closed / unclosed

* **16 kHz coded band (B16): CLOSED.** `exc16`, `o16[+0x34]`, `B16`, `out16` reproduce the
  DLL's own buffers at corr **1.000000** (frames 37/38/39); the four frame-38 gains match
  the DLL's internal values to ≤0.05 %; the norm/energy identities are exact.
* **32 kHz noise band (B32): CLOSED.** `exc32`, `o32[+0x34]`, `B32` at corr **1.000000**;
  the four frame-38 `gain5 = exp((idx5-10)/8)` values match the DLL's measured gains exactly
  (1.133148/5.754603/0.367879/7.389056) and the four norms to ≤3e-5.
* **Chain/combine: CLOSED** (`out16 = clamp(2*(A16-B16))`, `pcm = clamp(2*(A32-B32))`,
  corr 1.000000).
* **End-to-end with the current 8 kHz chain: corr 0.997496, rms ratio 0.9910 over frames
  0..299 for the §6 patch verbatim** (the reference port without these two bands scores
  0.9894 with ratio 0.983 on the same basis, so the two bands account for essentially the
  whole remaining gap).  The remaining error is the ±1 LSB int16 rounding on the silent
  frames plus the 8 kHz chain's own residual on a few frames (frame 120: `exc8` 0.922,
  `sig8` 0.636), not the upper bands.
