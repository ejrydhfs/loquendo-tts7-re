# Codec 210 — the output chain, bit-exact

Scope: the stages between the (8 kHz) excitation and the int16 PCM —
`FUN_100030e0` (LPC synthesis), `FUN_10003960` (QMF `band_filter`, x87 code),
`FUN_1000c290` (the `2*(A-B)` combine) and the final int16 conversion — plus the
`FUN_10005080` LSF→LPC conversion and the `FUN_10004af0` cosine the DLL uses there.

Every number below was measured by running the real `LTTS7Codec210.dll` under Unicorn
(`tools/codec210_oracle.py`) and comparing **bit-for-bit** (integer bit-pattern equality,
not correlation) with candidate Python implementations of the very same DLL function,
fed the DLL's *own* inputs.  Scripts: `/tmp/audit/{analyze,iso_*,capture_all,audit_table,
inject*,mkpatch*}.py` (throwaway; regenerate dumps with
`tools/venv/bin/python /tmp/audit/capture_all.py 0 170 /tmp/audit/cap170.npz`).

---

## 1. Result: the output chain is bit-exact

| stage | DLL fn | calls | samples | differing | max abs |
|---|---|---|---|---|---|
| 8 kHz LPC synthesis | `FUN_100030e0` | 1572 | 83840 | **0** | 0 |
| QMF band filter (16/32 kHz level) | `FUN_10003960` | 524 | 251520 | **0** | 0 |
| `2*(A-B)` combine | `FUN_1000c290` | 262 | 125760 | **0** | 0 |
| DLL cosine `FUN_10004af0` | `FUN_10004af0` | 4784 | 4784 | **0** | 0 |

Ranges: synthesizer/band/combine over **frames 40..170** (given the DLL's own LPC
coefficients, state, `src`/`cf`/`tail` and A/B inputs); cosine over frames 0..45 (every
call).  "0 differing" means the float32 bit patterns are identical.

End-to-end proof that the *whole* 8 kHz output path is exact: replaying the port with the
DLL's own excitation **and** its own 8 kHz LPC coefficients injected gives

| quantity | differing | max abs |
|---|---|---|
| `sig8` (0x30011ea0), frames 40..170 (131 frames) | **0 / 20960** | 0 |

(feed via `/tmp/audit/inject2.py`; the port's own LPC still drives the 16/32 kHz bands).

---

## 2. Do any *output-chain* operations need 80-bit emulation?  No.

**Scoped to the three stages below** (`FUN_100030e0`, `FUN_10003960`, `FUN_1000c290`).
This must **not** be generalised: the 8 kHz LTP `FUN_10006bb0` *does* need the 80-bit MAC
and a direct 80→32 store (sibling `ExactExcitationArith`, `specs/ExactArith.md`; a
double implementation leaves 2648/48000 excitation samples wrong on a float32-midpoint
tie), and the DLL's cosine `FUN_10004af0` (§4.1) also evaluates in 80-bit.  For the three
stages here, though, the measurement is unambiguous:

For each of the three arithmetic stages I implemented **both** a plain-`double` and a
`numpy.longdouble` (= x87 80-bit, 64-bit mantissa) variant and tested both against the DLL
over the full range.  Both variants give **0 differing samples** everywhere — i.e. the x87
80-bit intermediates do **not** change any result relative to IEEE double here; what the
port was missing is the **float32 rounding at the DLL's store points**, not register
precision.  (For the synthesizer and the band filter the `ld` and `d` counts are
*identical* — 0 differing either way; only the float32 variants diverge, and the
bare-double port is 46505/83840 off on the synthesizer and 174242/251520 on the band
filter.)

### 2.1 `FUN_100030e0` — what must be float32

Transposed direct-form II, x87 80-bit multiply-adds, **float32 stores** (`fstp dword`
after every state write and for every output sample).  The disassembly is
`fVar1 = x[i] + state[0]` in 80-bit, then `fVar2 = -fVar1`, then
`state[j] = a[j]*fVar2 + state[j+1]` (80-bit) stored to float memory, and finally
`out[i] = (float)fVar1`.  `fVar1` is rounded to float32 before it is reused for the state
update (the compiler stores it).  The old port kept `t` and the state in double.

### 2.2 `FUN_10003960` — the accumulators live in float32 **memory**

The four polyphase accumulators `s0..s3` are stack slots (`[esp+0x38]`, `[esp+0x44]`,
`[esp+0x10]`, `[esp+0x14]`) and are **rounded to float32 after every partial product-sum**
(`fstp dword [esp+…]`), while each individual product+add is done in the 80-bit register
stack.  Exact per-section formula (verified against the DLL's own accumulator store
trace, `/tmp/audit/trace_band.py`):

```
W = work[base+4m-2]   X = work[base+4m]   prev = work[base+4m-4]   (base = outcount-4k)
s0 = f32(s0 + c0*W); s0 = f32(s0 + c2*X)
s1 = f32(s1 + c1*W); s1 = f32(s1 + c3*X)      <-- DLL order: c1 term FIRST
s2 = f32(s2 + c0*prev); s2 = f32(s2 + c2*W)
s3 = f32(s3 + c1*prev); s3 = f32(s3 + c3*W)   <-- DLL order: c1 term FIRST
```

The two things the old transcription got wrong: (a) no per-partial-sum float32 rounding,
and (b) the `s1`/`s3` accumulation order — the DLL adds the **c1** term before the **c3**
term, the port had `c3*w0 + c1*wm2`.

### 2.3 `FUN_1000c290` — the combine

`out[i] = f32((A[i]-B[i]) * 2.0)` (the `fsub`/`fmul` are exact, one `fstp dword`), then
clamped in double: `if out > 32767.0 -> 32767.0f; elif out < -32767.0 -> -32767.0f`.
The lower clamp is **-32767**, not -32768 (constants `0x10023658=32767.0`,
`0x10023650=32767.0f`, `0x10023ed0=-32767.0`, `0x10023ec8=-32767.0f`; disasm 0x1000c290).
This reproduces the DLL exactly (0/125760) and the port already clamps at that value after
the patch; the old `-32768.0` lower bound was wrong.

### 2.4 int16 conversion

`FUN_1000f640`: `if v > (float)32767.0 -> 0x7fff; elif v < -32768.0f -> 0x8000;
else (short)(v + 0.5)` where the conversion is the CRT helper `0x10011c90` (x87,
round-to-nearest-even).  Main has already replaced `int(v+0.5)` with Python `round(v)`
in `clamp_int16`; that matches ties-to-even and is measurably closer (11874 -> 7814
differing samples over frames 100..125).

---

## 3. Patch for `tools/codec210.py`

### 3.1 `lpc_synth`

```python
def lpc_synth(a, mem, x):
    n = len(a)
    m = [_f32(v) for v in mem]
    out = []
    for xi in x:
        t = _f32(xi + m[0])
        fv2 = -t
        nm = list(m)
        for j in range(n - 1):
            nm[j] = _f32(a[j] * fv2 + m[j + 1])
        nm[n - 1] = _f32(a[n - 1] * fv2)
        m = nm
        out.append(t)
    return out, m
```

### 3.2 `band_filter`

```python
def band_filter(src, cf, outcount, ntaps, tail, work):
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
            s0 = _f32(s0 + c0 * wm2); s0 = _f32(s0 + c2 * w0)
            s1 = _f32(s1 + c1 * wm2); s1 = _f32(s1 + c3 * w0)
            s2 = _f32(s2 + c0 * prev); s2 = _f32(s2 + c2 * wm2)
            s3 = _f32(s3 + c1 * prev); s3 = _f32(s3 + c3 * wm2)
            prev = w0
        dst[4 * k:4 * k + 4] = (s0, s1, s2, s3)
    for k in range(0, ntaps - 1, 2):
        tail[1 + k] = work[k]
    return dst
```

### 3.3 combine

In `decode_frame`, change the 16 kHz combine clamp from `-32768.0` to `-32767.0`:

```python
out16 = [max(-32767.0, min(32767.0, 2.0 * (x - y))) for x, y in zip(a16, b16)]
```

---

## 4. `FUN_10005080` (LSF→LPC) — the DLL's own cosine, and the cascade

The port's LSF→LPC error had two causes; only the first is closed.

### 4.1 `FUN_10004af0` is **not** libm `cos` (CLOSED)

The DLL calls its own helper at the `FUN_10005080` cos site (`0x100050ee`); the helper is
a degree-6 polynomial approximation (max error ≈ 7e-6 — see the measured `y` vs `cos(x)`
below), evaluated in x87 80-bit with **double** constants and float32 stores of `x*x`,
`(pi-x)**2` and the result:

```
A=0.04148774594068527  B=0.0012712094467133284  C=0.49991244077682495
D=0.9999933242797852   pi=3.141592653589793       pi/2=1.5707963268
cos(x) = ((A - B y) y - C) y + D ,  y = f32(x*x)            if x < pi/2
       = -(((A - B y) y - C) y + D), y = f32(t*t), t=f32(pi-x)  otherwise
```

Both branches (including the float32 store of `t` and the final `fchs`+`fstp`) are
verified **bit-exact** on 4784 calls.  Patch: replace `math.cos` in `lsf_to_lpc` with
`_cos_apx` (§4.3).  Effect: the LSF→LPC max error drops from **7.4e-5** (libm cos) to
**3.96e-6** with the old polynomial, and to **1.19e-7** with the cascade of §4.2.

### 4.2 The P/Q construction is a cascade of second-order FIR sections (model derived, 1 ULP residual)

`FUN_10005080` does not expand the product polynomial directly.  It runs a unit-impulse
response through two cascades of second-order **FIR** sections whose state lives in the
float32 work array (`work[4k..4k+3]` per section, `work[4h]`, `work[4h+1]` = the previous
output pair, `work[4h+2..]` = the cos buffer):

```
x = 1.0 if i == 0 else 0.0 ;  y = x
for k in 0..half-1:
    T = f32(x - f32(2*cos[2k]  )*S[4k]   + S[4k+1]); S[4k+1]=S[4k]; S[4k]=x; x=T
    U = f32(y - f32(2*cos[2k+1])*S[4k+2] + S[4k+3]); S[4k+3]=S[4k+2]; S[4k+2]=y; y=U
out[i] = f32( ( (y - prev_y) + (prev_x + x) ) * 0.5 ) ;  prev_x=x; prev_y=y   (i = 1..order)
```

Verified against the DLL's own `FUN_10005080` output on the DLL's own LSF inputs (frames
40..80, orders 8 and 10): **333 / 4264 coefficients differ, all by exactly 1 float32
ULP** (max abs 1.19e-7); the DLL's final state array is reproduced exactly (all-zero
section states, extra pair = (1,1) = leading P/Q coefficients, cos buffer = the DLL cos
values).  The residual is a rounding-control difference in the x87 cascade that I could
not close (double and 80-bit give the same count; the operation order was checked against
the store trace).

**This model is ≈40x closer than the port's polynomial *in isolation* but is NOT
bit-exact, and it is NOT recommended as a patch**: dropped into the full port it makes the
end-to-end *worse* — 52342 vs 49165 differing samples without the excitation fix, and
19969 vs 15578 with the sibling's bit-exact excitation.  The port's existing polynomial
`lsf_to_lpc` (with the §4.3 cosine) is the better end-to-end choice; the cascade is kept
here as the root-cause analysis of `FUN_10005080` and as the starting point for closing
the remaining 1-ULP residual.

### 4.3 `_cos_apx` patch (recommended) — replaces `math.cos` in `lsf_to_lpc`

```python
def _cos_apx(x):
    x = _f32(x)
    if x < 1.5707963268:
        y = _f32(x * x)
        return _f32((((0.04148774594068527 - 0.0012712094467133284 * y) * y
                      - 0.49991244077682495) * y + 0.9999933242797852))
    t = _f32(3.141592653589793 - x)
    y = _f32(t * t)
    return _f32(-(((0.04148774594068527 - 0.0012712094467133284 * y) * y
                   - 0.49991244077682495) * y + 0.9999933242797852))
```

i.e. `c = [_cos_apx(w) for w in lsf]` instead of `c = [math.cos(w) for w in lsf]`.
Do **not** also swap `lsf_to_lpc` for the §4.2 cascade (§4.2).

### 4.4 Two further LSF-path mismatches found (open)

While tracing why the port's `sig8` is not exact given the DLL excitation I compared the
port's LSF at the `FUN_10005080` call with the DLL's (`/tmp/audit/lsf_cmp.py`,
`/tmp/audit/vq_cmp.py`):

* **the frame LSF itself (the 5-stage VQ output, DLL `0x300128a0`) is not bit-exact**:
  frames 40..60, 198/200 coefficients differ, max abs **4.05e-6** (frame 40: port
  `[0.31835938, 0.5390625, 0.69140625, …]` vs DLL `[0.31835774, 0.53906256, 0.69140685, …]`).
  This propagates straight into the interpolated LSF (port vs DLL: 1579/1600 differ, max
  5.16e-6) and hence into the LPC.  Fix would be float32 stores / x87 semantics in the VQ
  stages.
* **the 8 kHz stabilisation margin is wrong**: the DLL passes `0.002` (float at VA
  `0x10023ec0`, disasm `0x10009a80`) for the 8 kHz level and `0.05` (float at
  `0x10023ec4`, disasm `0x1000e4ad`) for the 16/32 kHz levels; the port uses `0.05` for
  both.  On frames 40..80 the LSF spacing never reaches either value so the difference is
  currently inert (forcing `0.002` changes no LSF), but it is a latent bug.

The interpolation itself is `dst[i] = cur[i]*t + prev[i]*(1-t)` with `t = f32((sf+1)/nsub)`
(the DLL's `FUN_10005520`), which is what the port does; the DLL passes prev/cur in
`(0x300128d0, 0x300128a0)` order.

---

## 5. End-to-end audit and acceptance

Harness: `python3 tools/verify_codec.py jorge_re/ref_pcm_f0_299.raw 300`, ground truth
`jorge_re/ref_pcm_f0_299.raw` (real DLL, frames 0..299).

| build | global corr | differing samples (of 192000) | max abs | k-window < 1.00000 (6 dp) |
|---|---|---|---|---|
| current `tools/codec210.py` | 0.999648 | 71565 | 2556 | 8 (worst k=160 = 0.99911) |
| + §3 patches + §4.3 cos (`/tmp/audit/codec210_out.py`) | 0.999647 | 49165 | 2556 | 8 (worst k=160) |
| + §3 + full cascade LSF→LPC (`codec210_out2.py`) | 0.999647 | 52342 | 2556 | 8 (worst k=160) |
| + §3/§4.3 patches **on top of the sibling's bit-exact excitation** (`/tmp/codec210_ld.py` → `/tmp/audit/comb_ld.py`) | **0.9999990** | **15578** | **186** | **1** (k=10 = 0.999684) |

(`verify_codec.py`'s table compares only frame `k` of each "k..k+9" row, so "k-window" above
is the correlation of frame `k` — the same convention the harness and REPORT use.)

The last row is the informative one — with the bit-exact excitation and the output-chain
patches together, **29 / 30 rows print `1.000000`** and only **frame 10 = 0.999684** is
below it; the vast majority of the 15578 differing samples are **±1 int16 LSB**, but the
error is **not** purely ±1: frames **294, 295, 296** still carry a localised residual
(frame 295: 627/640 samples differ, max 186).  The global correlation is **0.9999990**,
not 1.000000 — the acceptance target is **not** met.

Per-stage audit with the DLL's own `exc8` injected (`/tmp/audit/audit_table.py
codec210_out 40 171`):

| stage | differing | first divergence |
|---|---|---|
| exc8 (injected) | 0 / 20960 | — |
| sig8 | 20942 / 20960 | frame 40, sample 0 |
| exc16 | 20237 / 20960 | frame 40, sample 0 |
| b16 | 20957 / 20960 | frame 40, sample 0 |
| a16 | 41879 / 41920 | frame 40, sample 0 |
| B16 | 41910 / 41920 | frame 40, sample 0 |
| exc32 | 41920 / 41920 | frame 40, sample 0 |
| a32 | 83786 / 83840 | frame 40, sample 0 |
| B32 | 83836 / 83840 | frame 40, sample 0 |
| pcm | 9102 / 83840 | frame 40, sample 639 |

With the DLL's `exc8` supplied, the **first** stage to diverge is `sig8` (the 8 kHz LPC
synthesis) — i.e. the upper bands are all downstream of an already-wrong 8 kHz signal, and
the cause is the **LPC coefficients** (the synthesizer itself is exact given them, §1).
Feeding the DLL's `exc8` **and** its 8 kHz LPC removes that divergence entirely
(`sig8` 0/20960, §1).

### Acceptance: NOT yet reached (0.999999 with the sibling's current excitation)

As the harness stands (`tools/codec210.py`) it reports **global correlation 0.9996**.  With
this spec's §3/§4.3 patches **plus** the sibling's bit-exact excitation (`/tmp/codec210_ld.py`)
the harness reports **global 0.9999990**: 29/30 rows print exactly `1.000000`, only frame 10
is 0.999684, but the global correlation is still not 1.000000 and frames 294-296 carry a
localised residual (frame 295: max 186, 627/640 samples).  That is the honest number: the
target (all windows 1.00000, global 1.000000) is **not** met yet.

Remaining blockers, in order of effect:

1. **The 8 kHz excitation recursion** (closed by the sibling) — `ExactExcitationArith`
   reports it bit-exact (0/48000 samples, frames 0..299); with its `/tmp/codec210_ld.py`
   the end-to-end PCM drops to 15578/192000 differing with max 186.  What is left is
   *downstream* of the 8 kHz core, i.e. blocker 2 plus the still-inexact 16/32 kHz paths.
2. **The LSF chain: the 5-stage VQ, then `FUN_10005080`** — the *frame LSF itself* (the VQ
   output at DLL `0x300128a0`) is not bit-exact (198/200 coefficients, max 4.05e-6, §4.4),
   and `FUN_10005080`'s cascade lands 1 float32 ULP off on ≈7.8% of coefficients (§4.2).
   Both feed the LPC and a 1-ULP LPC error is amplified by the resonant synthesis.  Only
   §4.3's cosine is closed there so far.
3. The 16/32 kHz band LPC uses the same VQ/`FUN_10005080`, so it inherits blocker 2.

Integration note: apply these patches **on top of** the sibling's excitation model
(`tools/codec210.py::Codec210.ltp` + its `numpy.longdouble` MAC, `EXC_FLOOR` and `_LD32`),
and do not "simplify" that model to plain double — unlike the three output-chain stages it
genuinely needs 80-bit (§2); `/tmp/audit/mkcombined.py` does this stacking.
