# The remaining 8 kHz drift frames — root cause and fix

Scope: the ~20 non-silent frames where the (otherwise exact) port drifted from the DLL
(worst: 118–130, 170–179, 68, 94–97).  Delivered for the parent's follow-up request.

**Result: the drift is in the 8 kHz adaptive-codebook (LTP) tap read, not in the
LSF/interpolation/stabilisation/LSF→LPC path.**  The DLL's tap window is a *cyclic* read of
the `lag` samples that end just before the current sub-block; for `lag <= 40` a plain
3-tap read from the (cleared) excitation buffer reaches into the current sub-block and is
wrong.  With the rule below applied, the port's numbers become:

| range | before | after |
|---|---|---|
| frames 0..299 PCM corr | 0.997496 | **0.999648** |
| rms ratio | 0.9910 | **1.0010** |
| frames 170..179 (10-frame window) | 0.9863..0.9999 | **1.000000** |
| frames 118..130 | 0.6538 (f120) | 0.995993 (window 120–129 = 0.9958) |
| non-silent 10-frame windows < 0.999 | 4 | **1** (only 120–129 = 0.9958) |

All measurements are `tools/codec210_oracle.py` (the real DLL under Unicorn) vs a throwaway
copy of `tools/codec210.py` (`/tmp/codec210_ring.py`, patched per §4); scripts under `/tmp`.

---

## 1. Which stage drifts — per-frame state table

For frames N the DLL's post-frame 8 kHz work arrays are compared with the corresponding
port state (same decoder state, frames 0..N replayed in both):

| DLL array | port state | what it is |
|---|---|---|
| `0x300128a0` | `lsf8_prev` | 5-stage VQ accumulator = the frame's LSF |
| `0x30012870` | LSF→LPC of the last sub-block | the LPC coefficients |
| `0x30012a20` | `tilt8` | per-sub-block tilt (`1+Σ(lpc[i+1]-lpc[i])`) |
| `0x30012930` | `lpc_mem8[:10]` | LPC synthesis state (delay line) |
| `0x30011ea0` | `synth8()` output | the level signal `sig8` |
| `0x30012364` | `buf[HIST:HIST+160]` | the excitation |

| frame | lsf | lpc | tilt | state | sig8 | exc |
|---|---|---|---|---|---|---|
| 37, 38 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 116, 117 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| 118 | 1.000000 | 1.000000 | 1.000000 | 0.968563 | 0.958879 | 0.974426 |
| 119 | 1.000000 | 1.000000 | 1.000000 | 0.984884 | 0.926021 | 0.947833 |
| 120 | 1.000000 | 1.000000 | 1.000000 | -0.670792 | 0.635583 | 0.922091 |
| 121 | 1.000000 | 1.000000 | 1.000000 | 0.985930 | 0.934315 | 0.926513 |
| 122 | 1.000000 | 1.000000 | 1.000000 | 0.999902 | 0.993853 | 0.999286 |
| 123 | 1.000000 | 1.000000 | 1.000000 | 0.998732 | 0.961643 | 0.988090 |
| 124 | 1.000000 | 1.000000 | 1.000000 | 0.999864 | 0.958588 | 0.991140 |
| 125..130 | 1.000000 | 1.000000 | 1.000000 | 0.9985..1.0 | 0.990..0.999 | 0.997..0.9996 |
| 170 | 1.000000 | 1.000000 | 1.000000 | 0.979304 | 0.989400 | 0.995176 |
| 171 | 1.000000 | 1.000000 | 1.000000 | 0.947077 | 0.990556 | 0.996511 |
| 172..179 | 1.000000 | 1.000000 | 1.000000 | 0.981..1.0 | 0.995..0.9998 | 0.998..0.9995 |

So: **lsf, lpc and tilt are identical to the DLL on every frame** (the LSF VQ, the
interpolation, the stabiliser, LSF→LPC and the VQ ramps are all exact, and nothing is
re-seeded or reset wrongly); the first quantity to leave the rails is the **excitation**,
with the LPC *state* and `sig8` following it (a resonant LPC in these quiet passages
amplifies the excitation error).  This *disproves* the "sig8 worse than exc8 ⇒ LSF path"
inference: `sig8` is worse only because it is the *filtered* excitation.

## 2. Which excitation component — decomposition at frame 118

For frame 118 the DLL's writes to the excitation buffer (`0x30012364`) were attributed by
code address (cache-clear at `0x10009b6f`, LTP output at `0x10009c0d`, CB1 accumulate at
`0x10009f3e`, CB2 at `0x10009ff1`), giving the DLL's LTP / CB1 / CB2 separately; the port's
single-pass components are computed on the same state (the state before frame 118 is exact,
frames ≤ 117 were exact):

| sf | lag | source | DLL rms | port rms | corr |
|---|---|---|---|---|---|
| 0 | 60 | LTP | 62.444 | 62.447 | 1.000000 |
| 0 | 60 | CB1 / CB2 | 119.518 / 57.897 | identical | 1.000000 |
| 1 | 20 | LTP | 55.952 | 40.952 | 0.705 |
| 1 | 20 | CB1 / CB2 | 55.328 / 27.271 | identical | 1.000000 |
| 2 | 109 | LTP | 45.817 | 45.818 | 1.000000 |
| 3 | 32 | LTP | 28.653 | 26.521 | 0.924 |
| 3 | 32 | CB1 / CB2 | 41.127 / 24.565 | identical | 1.000000 |

**CB1/CB2 (the innovation codebooks and their gains) are exact in every sub-frame; only the
LTP is wrong — and only when `lag <= 40`.**  (The taps span indices `w0 .. w0+41` with
`w0 = p-(lag+1)`, so they reach the current sub-block iff `w0+41 >= p` ⟺ `lag <= 40`.)

## 3. The rule: the tap window is a cyclic read of the previous `lag` samples

The LTP call's argument 10 is a 120-float scratch (`0x3000e0a4`) that the DLL fills with the
three 40-float tap windows before the FIR.  Reading it at the call's return gives the DLL's
*tap values* directly.  Comparing window 0 with the port's buffer `b[w0+k]` (frame 118,
sf1, `lag=20`, `w0 = p-21`):

| k | DLL `S[k]` | port `b[w0+k]` | match |
|---|---|---|---|
| 0 | 203.17763 | 203.17886 | ✓ |
| 1 | 173.39688 | 173.39948 | ✓ |
| … | … | … | ✓ |
| 20 | -109.34928 | -109.37252 | ✓ |
| **21** | **173.39688** | **-272.98111** | **✗ = `b[w0+1]`** |
| **22** | **121.79175** | **-274.10583** | **✗ = `b[w0+2]`** |
| … | … | (port has the cleared/stale values) | |
| 40 | 173.39688 | -272.98111 | ✗ (a second wrap) |

i.e. the DLL's window is **periodic with period `lag`** once it passes the end of the valid
history: it *wraps back* instead of entering the current sub-block.  The equivalent
statement for the taps (`w0 = p-(lag+1)`, tap index `k`):

```
RING[k] = buf[w0+k]                    if k <= lag
RING[k] = buf[w0 + 1 + ((k-1) % lag)]  if k >  lag
out[i]  = g2*RING[i] + g1*RING[i+1] + g0*RING[i+2]
```

Verification (frame 118 sf1, `lag=20`): the port's ring LTP vs the DLL's LTP recomputed from
its *own* scratch window, all 40 samples, max |difference| = **0.014** (≈1e-4 relative, the
float32 accumulation order); per-sub-frame correlations vs the DLL's written LTP output
(state exact):

| frame | sf | lag | current port (3-tap from the cleared buffer) | ring rule |
|---|---|---|---|---|
| 117 | 0..3 | 144,144,43,108 | 1.000000 | 1.000000 |
| 118 | 0,2 | 60,109 | 1.000000 | 1.000000 |
| 118 | 1 | 20 | 0.705330 | **0.990723** |
| 118 | 3 | 32 | 0.923512 | **1.000000** |
| 119 | 1 | 21 | 0.691752 | **1.000000** |
| 119 | 2 | 39 | 0.996394 | **1.000000** |
| 121 | 0 | 21 | 0.560543 | **1.000000** |
| frame total (excitation) | 118 | | 0.910706 | **0.997013** |
| frame total (excitation) | 119 | | 0.891144 | **1.000000** |

("current port" = the materialised 3-tap read after the clear; checked alternative
hypotheses — pre-clear/stale values, live in-place outputs, tap-base offsets ±160 —
are all *worse*: 0.02–0.85, and the offset scan peaks at offset 0.)

## 4. Minimal patch for `tools/codec210.py`

Replace the body of `Codec210.ltp` (the signature and the rest of the class are unchanged):

```python
    def ltp(self, p, lag, idx):
        """FUN_10006bb0 — 8 kHz adaptive codebook (lag-periodic tap window).

        The DLL's tap windows are a cyclic read of the `lag` samples ending just before the
        current sub-block: tap index k (relative to w0 = p-(lag+1)) reads buf[w0+k] while
        k <= lag, else buf[w0 + 1 + ((k-1) % lag)] — the current sub-block is never read.
        For lag >= 41 the ring does not wrap inside the 42 taps used, so this reduces to the
        plain 3-tap predictor.
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
```

To apply it programmatically to a copy (as done for the numbers here):

```python
s = open('tools/codec210.py').read()
i = s.index('    def ltp(self, p, lag, idx):')
j = s.index('    def codebook(self, idxs, base):')
s = s[:i] + <the function above> + s[j:]
```

## 5. Candidates checked and ruled out

| candidate | verdict |
|---|---|
| `lsf_interp` weights (is the first weight 0 or (sf+1)/nsub?) | **exact** — the port's interpolated LSF/LPC reproduce the DLL's LPC array `0x30012870` at corr 1.000000 on every frame incl. all drift frames |
| stabilisation margin (port uses 0.05, double `0x10023ec4`) | **exact** (same evidence; the margin is also confirmed in the disassembly at `0x10009a91`) |
| VQ ramp re-seeding per frame (RAMP10) | **exact** — the LSF array (`0x300128a0`) matches on every frame |
| LSF history reset on frame/mode boundaries | **exact** — ditto |
| LPC synthesis state initialisation / layout | **exact** — with the DLL's own state the port's `sig8` matches at corr 1.000000 (frames 37/38/39) and the state evolves identically once the excitation is right |
| the interpolation/`FUN_10002cc0`/`FUN_10002f80` band-expansion path | **not used** for 8 kHz per-frame synthesis (`obj8[+0x24] == 8000` selects it in the *parent* code, but the 8 kHz object uses its own path; all evidence comes from the LPC/state arrays themselves) |
| the **LTP tap read** | **wrong for lag ≤ 40** — this is the drift; see §3 |

## 6. Closed / unclosed

* **Root cause: CLOSED.** The 8 kHz LTP tap window is a cyclic read of the last `lag`
  samples (`RING` rule, §3), verified against the DLL's own 120-float tap scratch to
  ≈1e-4 (float32) and against the written LTP output per sub-frame (0.99–1.000 on the
  previously failing sub-frames; the residual 0.99 at frame 118 sf1 is float32 ordering in
  the near-cancelling 3-term sum).
* **End-to-end: frames 0..299 corr 0.999648, rms ratio 1.0010** (was 0.997496 / 0.9910).
  All non-silent 10-frame windows are ≥ 0.999 except **120–129 = 0.9958** (and 160–169 =
  0.9996); frames 170..179 are now exactly 1.000000.  The silent frames 0..36 are the
  ±1-LSB int16 rounding floor (unchanged; max abs sample diff = 1).
* **Not fully closed:** the window 120–129 (0.9958) still has a small residual — the same
  LTP rule with the exact float32 operation order and, possibly, the exact wrap boundary
  (`k > lag` vs `k >= lag+1`) should close it; everything else in that window traces back
  to the state error accrued at frames 118–119 by the previous (pre-fix) code path.
