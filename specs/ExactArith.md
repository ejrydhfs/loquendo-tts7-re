# Exact 8 kHz excitation arithmetic of LTTS7Codec210 (Jorge build)

Scope: make the recursive 8 kHz excitation of the pure-Python port (`tools/codec210.py`)
**bit-identical** to the real DLL running under Unicorn, and give the integrator the minimal
patch.  Everything below is *measured*: the DLL trace with `tools/codec210_oracle.py`
(Unicorn + pefile), the window/read capture with `/tmp/win_dump.py` / `/tmp/win_reads.py`,
the FIR isolation with `/tmp/fir_test.py`, the frame gate with `/tmp/frame_gate.py` and the
acceptance table with `/tmp/verify_p.py` (all throwaway scripts under `/tmp`).

---

## 1. Result

| check | before | after |
|---|---|---|
| 8 kHz excitation, 300 frames (48000 samples) vs DLL `0x30012364` | 12112 differing, worst frame 105 = 159/160 | **0 differing** |
| gate frames 150..170 (3360 samples) | sum 2010, max 141/160 | **all 0/160** |
| harness `verify_codec.py ... 300` global corr | +0.999648 | **+0.999999** |
| harness rms ratio | 1.00106 | **0.99993** |
| harness speech windows with corr 1.000000 | 20/30 | **27/30** |

The patch is **one function** (`Codec210.ltp`) plus four module-level helpers/constants; it
changes only the LTP arithmetic.  All other stages (bit unpack, gains, codebooks, LSF/LPC,
band filters) are untouched.

---

## 2. What the DLL actually does (8 kHz excitation)

Per sub-frame `sf` (0..3), the 8 kHz object writes its 40-sample excitation to
`0x30012364 + 160*sf`, in this order (addresses from `specs/GainLaw.md`):

1. `0x10009b6f` — clear the sub-frame: `dst[i] = 0`.
2. `0x10009c0d` — `call *%edx` with `edx = *(reader+0x1c)`: the **LTP** function
   (`FUN_10006bb0` for all 644 calls of frames 0..160, measured with `/tmp/ltp_dispatch.py`;
   frames 161..299 are covered indirectly by the bit-exact gate of §4.2).
3. `0x10009f3e` — `dst[i] += scratch[i]` where `scratch[i] = float32(cb1[i] * gain)`.
4. `0x10009ff1` — `dst[i] += scratch[i]` where `scratch[i] = float32(cb2[i] * gain*5/11)`.

The gains and the codebook scale are already exact in the port (`specs/GainLaw.md`); the two
accumulations are plain float32 adds (`FUN_10002da0` is `flds src; fmul st(1); fstps dst`).

### 2.1 `FUN_10006bb0` — the tap window

The function materialises **three 40-float windows** at

```
W2 = 0x3000e0a4   W1 = 0x3000e144   W0 = 0x3000e1e4      (40 floats apart, contiguous 120)
```

and runs a 4x-unrolled FIR reading `W0[i]`, `W1[i]`, `W2[i]` per output `i`
(measured: hook the 12 `flds` sites of the FIR loop, `/tmp/win_reads.py`).

Dumping the three windows in memory (`/tmp/win_dump.py`) shows that they are the **same
sequence shifted**:

```
W2[i] = R[i]      W1[i] = R[i+1]      W0[i] = R[i+2]
```

with `R[0..41]` the cyclic read of the `lag` samples ending just before the sub-block:

```
w0      = p - (lag + 1)                     p = HIST + 40*sf   (HIST = 145)
ring(j) = j                                 if j <= lag
          1 + ((j-1) % lag)                 if j >  lag
R[j]    = buf[w0 + ring(j)]                 if j <= 2*lag
          0.0                               if j >  2*lag      <-- NEW
```

The **`R[j] = 0` tail is the part the old port was missing**.  Measured example (frame 27
sf2, `lag_d = 2`, `lag = 19`, so `2*lag = 38`):

```
 i  DLL W0,W1,W2                      port ring (old)
 0  -0.531467  0.184759  1.78146      1.78146  0.184759 -0.531467     (same set)
...
36  0.145588  0.113651  0.473697     0.473697 0.113651 0.145588
37  0        0.145588  0.113651     0.113651 0.145588 0.184759      <-- old non-zero
38  0        0        0.145588      0.145588 0.184759 -0.531467      <-- old non-zero
39  0        0        0              0.184759 -0.531467 -0.0838768   <-- old non-zero
```

i.e. only `2*lag+1` taps exist; for `lag >= 21` the tail is beyond the 42 taps used, which is
why only small-lag sub-frames drifted.

### 2.2 `FUN_10006bb0` — the FIR (x87, 80-bit)

Disassembly of the unrolled loop (VA `0x10006f6b`..`0x10006ff7`):

```
flds  S0            ; S0 = W0[i]
fmul  st(2)         ;   * g0        (product exact: two float32 -> 48-bit significand)
fadd  st(1)         ;   + 1e-15     (the double at 0x10023618, on the x87 stack)
flds  S1            ; S1 = W1[i]
fmul  st(4)         ;   * g1
faddp
flds  S2            ; S2 = W2[i]
fmul  st(5)         ;   * g2
faddp
fstps dst[i]        ; ONE float32 store
```

so, with every product and every add rounded to the x87 **64-bit significand** and only the
final value rounded to float32:

```
out[i] = f32( ((g0*R[i+2] + 1e-15) + g1*R[i+1]) + g2*R[i] )
```

* `g[k] = float32(tap[k]/64 + 0.5)`, `tap[k]` the k-th signed byte of the pitch triple at
  `pitch_tbl + 3*idx` (constants: double `1/64` at `0x100235e8`, double `0.5` at `0x10021270`;
  the value is exactly representable, so the port's `tbl/64.0 + 0.5` is bit-identical).
* the floor is the **double `1.0000000036274937e-15`** (`0x3CD203AFA0000000`) at VA
  `0x10023618`, loaded by `fldl` before the loop; it is *unconditional*, so a silent window
  yields `out[i] = 1e-15`, not 0 (verified at frame 0, `sf0`/`sf1`, where all three gains are
  0 and the DLL writes exactly `1e-15` into every sample).
* the port's old formula (`g2*buf[w0+i] + g1*buf[w0+i+1] + g0*buf[w0+i+2]`, no floor, no
  tail, double arithmetic) is ordering-equivalent to the DLL's sum, which is why it matched
  most frames.

**Two rounding details matter** (both measured, `/tmp/fir_test.py` with the DLL's own
windows):

1. the **80-bit intermediates** — a double sum is not enough.  Frame 39 sf0 i=12 is a
   textbook case: the exact sum of the three `float32*float32` products is
   `-233.37169647216797`, which is *exactly* the midpoint between the two neighbouring
   float32 values `0xc3695f28` and `0xc3695f27`.  The DLL returns `0xc3695f27` because its
   80-bit accumulator is the exact sum **plus the 1e-15 floor**, i.e. above the midpoint;
   a double accumulator rounds the tie to even (`0xc3695f28`) and a double *conversion* of
   the 80-bit result also loses the floor bits and gives `0xc3695f28`.
2. the final conversion must be **80-bit → float32 in one step** (`fstps`), not via double.
   `struct.pack("<f", float(v))` double-rounds; `numpy.float32(longdouble)` is the direct
   `fstps` and reproduces `0xc3695f27`.

---

## 3. Minimal patch for `tools/codec210.py`

Nothing else in the file changes.

### 3.1 Module level

Add next to the other module constants (the file already imports `math` and `struct`):

```python
import numpy as _np

_LD = _np.longdouble

# double at DLL VA 0x10023618, added to the first LTP product (x87 `fldl`).
EXC_FLOOR = 1.0000000036274937e-15


def _EXC_ADD(coef, s, eps):
    """v = coef*s + eps, in x87 80-bit extended precision."""
    return _LD(coef) * _LD(s) + _LD(eps)


def _EXC_ACC(v, coef, s):
    """v += coef*s, in x87 80-bit extended precision."""
    return v + _LD(coef) * _LD(s)


def _LD32(v):
    """x87 `fstps`: round an 80-bit value DIRECTLY to float32 (never via double)."""
    return float(_np.float32(v))
```

### 3.2 Replace `Codec210.ltp`

Replace the whole body of `def ltp(self, p, lag, idx):` (currently the ring rule of
`specs/DriftFrames.md`) with:

```python
    def ltp(self, p, lag, idx):
        """FUN_10006bb0 — 8 kHz adaptive codebook.

        Measured structure (specs/ExactArith.md): the DLL materialises ONE 42-float tap
        sequence R[] and the FIR is
            out[i] = ((g0*R[i+2] + 1e-15) + g1*R[i+1]) + g2*R[i]
        with every product/sum in x87 80-bit extended precision and a single float32 store
        of the result.  R is the cyclic read of the `lag` samples ending just before the
        current sub-block, R[j] = buf[w0 + ring(j)] with w0 = p-(lag+1) and
            ring(j) = j                       for j <= lag
                     1 + ((j-1) % lag)        for j >  lag
        but only the first 2*lag+1 entries are filled: R[j] = 0 for j > 2*lag (the DLL's
        window fill copies 2*lag+1 samples and zero-fills the rest).  The +1e-15 floor is
        the double at DLL VA 0x10023618, added to the R[i+2] product.
        """
        tbl = self.pitch_tbl
        g = [tbl[idx * 3 + k] / 64.0 + 0.5 for k in range(3)]
        w0 = p - (lag + 1)
        buf = self.buf
        r = []
        for j in range(42):
            if j > 2 * lag:
                r.append(0.0)
                continue
            jj = j
            if jj > lag:
                jj = 1 + ((jj - 1) % lag)
            a = w0 + jj
            r.append(buf[a] if a >= 0 else 0.0)
        out = []
        for i in range(40):
            v = _EXC_ADD(g[0], r[i + 2], EXC_FLOOR)
            v = _EXC_ACC(v, g[1], r[i + 1])
            v = _EXC_ACC(v, g[2], r[i])
            out.append(_LD32(v))
        return out
```

The rest of `decode_frame` (clear → `ltp` → `+= f32(gain*cb1)` → `+= f32(g2*cb2)`) is already
exact and must not change.

Reference implementation used for the numbers below: `/tmp/codec210_ld.py` (generated by
`/tmp/mkport.py` from the current `tools/codec210.py`).

---

## 4. Verification

### 4.1 Isolated LTP / FIR (the DLL's own window)

`/tmp/win_dump.py` + `/tmp/fir_test.py` (frames 0..59, every sub-frame): with the DLL's own
`W0/W1/W2` values, the model `f32_80(((g0*W0 + 1e-15) + g1*W1) + g2*W2)` matches the DLL's
written LTP **40/40 in every sub-frame**, while the double/no-floor variants mismatch on
0.5-10 samples per sub-frame (1 f32 ULP each).

### 4.2 Per-frame gate (DLL `0x30012364` vs port `buf[HIST:HIST+160]`, bitwise)

`/tmp/frame_gate.py <module> 300` (a difference is a differing *sample*, i.e. differing
float32 bytes):

| frames | `tools/codec210.py` (before) | `/tmp/codec210_eps.py` (floor+tail, double) | `/tmp/codec210_ld.py` (patch) |
|---|---|---|---|
| total (48000 samples) | 12112 | 2648 | **0** |
| worst frame | 105 (159/160) | 159 (51/160) | **none** |
| frames fully exact | 7/300 | 57/300 | **300/300** |
| first divergent frame | 0 (17/160) | 0 | — |
| gate 150..170 | `[37,45,52,64,77,60,90,101,109,122,100,122,127,141,127,120,111,100,104,91,110]` sum 2010 | same shape, much smaller | **all 0** (sum 0) |

(Note: the ticket's premise "frames 55-65 are bit-exact (0/160)" does **not** hold for the
unpatched port — measured 13/160 at 55, 17/160 at 60, 3/160 at 65 with the same buffer.)

The same numbers are reproduced by a port built **only** from the two code blocks of §3
(extracted from this file by text surgery, `/tmp/verify_spec.py`): frames 0..170 give
0/27360 differing and the 150..170 gate is all zeros — i.e. the patch text below is exactly
what was measured.

### 4.3 Acceptance harness

`python3 /tmp/verify_p.py <module> jorge_re/ref_pcm_f0_299.raw 300` (DLL reference PCM):

```
                     before        after (patch)
global corr          +0.999648     +0.999999
rms ratio             1.00106       0.99993
windows at corr 1.000000  20/30     27/30
sample-exact windows  0-9, 20-29, 30-39   (unchanged)
```

Remaining: windows **10-19 = 0.999684** and **120-129 = 0.999999**.  These are *not*
excitation: the excitation is bit-exact for all 300 frames (§4.2), so what is left is in the
output chain (LPC synthesis / band filters / QMF combine / int16), i.e. outside this task.

---

### 4.4 The tilt / energy sums (`FUN_10002ec0`, `_tilt_pair`)

`FUN_10002ec0` (0x10002ec0) computes `sqrt(sum(x²)/n + 0.1)` for the 16 kHz band gain.  Its
accumulator is a **sequential float32 sum**: the unrolled loop is
`fld x; fmul st,st; fadds 0x8(%esp); fstps 0x8(%esp)` per element (products exact in x87, the
running sum rounded to float32 after every add), then `fidivl n`, `faddl 0.1`
(`0x10022120`), `call 0x100105c0` (sqrt), `fstps`.  The port accumulates the same sum in
double and rounds once.

Measured: over the 300-frame harness the port's values differ from the float32-sequential
accumulator on **524 of 1200** sub-frame energies (max relative difference 2.9e-07, i.e.
1 f32 ulp), yet the harness output is **bit-identical** with either accumulator (all
correlations and rms rows unchanged) — the energy only scales the 16 kHz excitation, whose
own float32 rounding absorbs it.  So the intermediate rounding of `FUN_10002ec0` does **not**
matter and the port's `_f32_ec0` is left alone.  (If it is ever needed, the exact version is
`acc = _LD32(acc + _LD(x)*_LD(x))` per element, then
`_LD32(sqrt(_LD(acc)/n + _LD(0.1)))`.)

## 5. The `exp` worker (item 1 of the task) — measured, and why no patch is needed

### 5.1 The real code path (the ticket's premise is wrong)

`_exp` is reached from the decoder at `0x100099ac` (`call 0x10011aec`).  `FUN_10011aec` is a
thunk:

```
10011aec  cmpl $0,0x100300cc        ; "use SSE2 math" flag  -> measured == 0 under Unicorn
10011b31  mov  $0x1002e7da,%edx     ; dispatch block
10011b36  jmp  0x10017ade           ; __cintrindisp1 wrapper
10017ade  ... fstcw -0xa4(%ebp) ; set CW=0x133f ; call 0x10012fe0 ; call 0x10017b6a ; restore
10012fe0  fxam ST0 ; jump table at 0x1002e7ea indexed by the FXAM class
100178a1  (ordinary argument) ...
100179ee  helper: frndint / fsub / f2xm1
```

`0x10017b6a` — the address named in the task — is **`__87except`, the `__matherr`/exception
handler**, not the worker: it is entered after the computation, tests `DAT_1002f638`
(measured 0) and immediately falls through to `fldcw -0xa4(%ebp); ret`.  It never contributes
to the result (its `__87except` call is only reached on an unmasked FP exception).

### 5.2 The algorithm (x87, 80-bit, then one double store)

```
y = x * log2(e)              ; `fldl2e` = 0xB8AA3B295C17F0BC x 2^1 (10 bytes
                             ;  bc f0 17 5c 29 3b aa b8 ff 3f, measured by executing
                             ;  `fldl2e; fstpt` under Unicorn), `fmulp`
n = rint(y)                  ; `frndint` (CW=0x133f: PC=extended, RC=nearest)
f = y - n                    ; `fsub`
r = f2xm1(|f|) + 1           ; `fabs; f2xm1; fld1; faddp`  -> 2^|f|
if (f < 0) r = 1 / r         ; `fld1; fdivp`  (FPSW C0 from the FTST of f)
if (n != 0) r = r * 2^n      ; `fscale`      (FPSW C3 from the FTST of n)
return (double)r             ; shared epilogue 0x100130d8: `fstp qword`
```

### 5.3 Measurement: `math.exp` vs the emulated CRT `exp`

Calling the emulated routine directly (arg in ST0, entry `0x10011aec`) and comparing
bit-for-bit (`/tmp/exp_verify.py`, `/tmp/exp_round.py`):

| input set | double mismatches | float32 mismatches |
|---|---|---|
| 100000 uniform draws in [-1.3, 32] | **20177 (20.18 %)** | **0** |
| reachable set: 32 x `g8/3.5` | 4 | **0** |
| reachable set: 16 x `i4*0.27027027027027023 - 0.15556` | 1 | **0** |
| reachable set: 32 x `(ref32-10)*0.125` | 3 | **0** |

So `math.exp` is the correctly-rounded glibc `exp` (which is within 0.52 ulp) while the CRT
routine differs from it by exactly 1 ulp on ~20 % of arbitrary doubles.  **Every one of those
differences vanishes at float32**, which is the only domain the 8 kHz gain law uses
(`X = float32(exp(g8/3.5))`, then `gain = float32(q[b3]*X)`), and the *gain* was already
verified bit-identical on 284 sub-frames (`specs/GainLaw.md`).

**Does the residual double difference matter for the 16 kHz / 32 kHz bands, which use the
double value directly?**  No — measured: replacing the port's `math.exp` with the *emulated*
values for all 80 reachable arguments (`/tmp/mkexp.py` → `/tmp/codec210_ldx.py`) changes
**not a single PCM sample** of the 300-frame harness (all correlations identical).  The band
gains are rounded to float32 in the excitation accumulation, which absorbs the 1-ulp double
difference.

### 5.4 Why a general bit-exact `exp` port is not attempted

The x87 chain cannot be reproduced by an 80-bit `2^f-1` evaluation: the emulator's `f2xm1`
(measured through an inline `fldt/f2xm1/fstpt; ret` stub called via `Oracle.call`) is **~5 ulp
away from the correctly-rounded `2^x - 1`** — e.g. `f2xm1(0.125) = 0.090507732665257689675` vs
the correct `0.090507732665257661919` (80-bit ulp there is ~5.4e-21).  Reproducing it needs
QEMU's exact polynomial; a numpy-`exp2l` model therefore mismatches ~76 % of arbitrary
doubles (measured, `/tmp/exp_x87.py`).  Since the *codec* only ever calls `exp` on the 80
arguments listed above, and all 80 agree at float32 (and the exact doubles change nothing),
the port keeps `math.exp`.

---

## 6. Measurement notes / caveats

* **Unicorn code hooks added after emulation has started do not fire for already translated
  blocks.**  All probes here install the hook *before* the first `decode`, otherwise they
  silently capture nothing (this cost several wrong intermediate conclusions).  Use
  `tools/oracle_stage_diff.py` / `/tmp/frame_gate.py` for the stage values.
* Ground truth is the DLL under Unicorn (`tools/codec210_oracle.py`), i.e. the same binary
  that produced `jorge_re/ref_pcm_f0_299.raw`; the x87 results were cross-checked with real
  80-bit arithmetic (numpy `longdouble`, 64-bit mantissa).
* `_f32()` in the port `struct.pack`s through a double; it is correct for *double* inputs
  (`float32*float32` products and `float32+float32` sums are exact in double) but must not be
  used on an 80-bit value — use `_LD32` for the LTP result.
* numpy is required for the 80-bit MAC.  Without it the port cannot represent the tie cases
  of §4.1/2.2 (`numpy.longdouble` on this platform is the x87 format: `itemsize 16`, 64-bit
  mantissa, checked at runtime).

## 7. Files

| file | role |
|---|---|
| `/tmp/mkport.py` | generates the patched port copies from `tools/codec210.py` |
| `/tmp/codec210_ld.py` | patched port used for all "after" numbers (**the patch of §3**) |
| `/tmp/codec210_eps.py` | intermediate variant (floor only, double) — shown for the table |
| `/tmp/frame_gate.py` | per-frame bitwise excitation gate (DLL vs module) |
| `/tmp/verify_p.py` | `verify_codec.py` with a selectable module |
| `/tmp/win_dump.py`, `/tmp/win_reads.py`, `/tmp/fir_test.py`, `/tmp/fir_reads.py` | window/FIR isolation |
| `/tmp/ltp_dispatch.py` | LTP vtable dispatch target per sub-frame (`edx` at `0x10009c0d`) |
| `/tmp/exp_verify.py`, `/tmp/exp_round.py`, `/tmp/exp_x87.py`, `/tmp/exp_model.py`, `/tmp/mkexp.py` | exp measurements |
