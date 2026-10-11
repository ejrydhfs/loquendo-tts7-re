# The exact 8 kHz innovation gain law of LTTS7Codec210 (Jorge build)

Scope: replace the fitted law `gain = 0.430 * 1.3305**g8 * q_fit[b3]` in
`tools/codec210.py::Codec210.exc_gain()` with the **exact** law measured from the shipped
`LTTS7Codec210.dll`. Target file: `tools/codec210.py` (function `exc_gain`, plus the CB2
factor in `decode_frame`). Everything below is measured against the real DLL running under
Unicorn (`tools/codec210_oracle.py`, interpreter `/tmp/uv/bin/python`).

---

## 1. Result

The 8 kHz core innovation gain is computed **once per sub-frame** as

```
X    = float32( exp( g8 / 3.5 ) )                       # g8 = 5-bit frame energy field
gain = float32( q[b3] * X )                             # b3 = 3-bit sub-frame field (the gain index)
gain_CB2 = float32( gain * 0.45454545454545453 )        # double 5/11 = 0x10023ee8
```

with

```
q = [0.06112999841570854, 0.16354599595069885, 0.3104130029678345,
     0.4282200038433075,  0.55588698387146,     0.7190549969673157,
     0.9386940002441406,  1.326874017715454]
```

* `q` **is** the 8-entry float32 table at VA `0x10023db8` (bytes
  `73637a3d 9a78273e 74ee9e3e a73fdb3e 9c4e0e3f fd13383f 404e703f 02d7a93f`).
* the divisor `3.5` **is** the double at VA `0x10023e70` (`0000000000000c40`); the exponentiation
  is the CRT `_exp` reached through the intrinsic dispatcher at VA `0x10011aec`, and its result is
  rounded to float32 (`fstp DWORD PTR [esp+0x5c]`, VA `0x100099b1`).
* `0.45454545454545453` **is** the double at VA `0x10023ee8` (`175d74d14517dd3f`), applied with
  `fmul QWORD PTR ds:0x10023ee8` at VA `0x10009fba`.
* there is **no** per-sub-frame LPC-tilt / normaliser factor on the coded innovation
  (the `gden` term the port used is wrong — see §7).
* the innovation is the *only* thing this law scales; the excitation is then
  `dst = LTP; dst += CB1*gain; dst += CB2*gain_CB2` accumulated in float32.

Only the `read(3)` branch is used by the Jorge DB: the mode descriptor's `+8` field is **3** in
every frame measured, so the 8-entry table at `0x10023db8` is selected. The `read(1)` branch
(two-entry float32 table at `0x10023ddc` = `0.7046899795532227, 1.0512700080871582`) is dead code
for this voice.

---

## 2. What was measured and how

### 2.1 Probe (method requested by the task)

For **frames 0..70** (71 frames = **284 sub-frames**), all inside the same streaming decoder
instance (state carried from frame 0):

1. Instrumented **write capture** on the 8 kHz excitation buffer
   `EXC = 0x30012364`, 160 floats (4 sub-frames × 40: sub-frame `sf` occupies
   `EXC + 40*sf`), with a global `UC_HOOK_CODE` hook that keeps the last executed address and a
   `UC_HOOK_MEM_WRITE` hook that stores the written bytes (from the hook's `val` argument —
   **the Unicorn write hook fires *before* the store, so `mem_read` inside it returns stale data**).
   The four writers of that buffer per sub-frame, in this fixed order:

   | stage | code address(es) | meaning |
   |---|---|---|
   | `clear` | `0x10009b6f` | `dst[i] = 0` (VA `0x10009b6d` `fldz`) |
   | `ltp` | `0x10006f94`, `0x10006fb2`, `0x10006fd4`, `0x10006ff7` (inside `FUN_10006bb0`), and `0x10009c0d` (the `call` itself) | the 3-tap LTP output stores |
   | `cb1` | `0x10009f3e` | `dst[i] = dst[i] + scratch[i]` (VA `0x10009d9f` scaled the scratch by `gain`) |
   | `cb2` | `0x10009ff1` | `dst[i] = dst[i] + scratch[i]` (VA `0x10009fd5` scaled by `gain*5/11`) |

   Coverage was **160/160 floats at every stage in every frame** for the run reported here.
   (Caveat for anyone re-running this: the LTP stores are attributed to the four
   `FUN_10006bb0` addresses above; whether they are also seen at `0x10009c0d` depends on the
   Unicorn translation-block cache, so whitelist *both*.)
2. Increments: `inc1 = value_after_cb1 - value_after_ltp`, `inc2 = value_after_cb2 - value_after_cb1`.
3. Codebook vector: the port's own `Codec210().codebook(idx)` built from
   `Codec210().parse_frame(block)["sub8"][sf][3]` (first 8 six-bit indices for CB1, last 8 for CB2).
4. `gain_measured = <inc, v> / <v, v>` per sub-frame and per pass, plus the relative projection
   residual `||inc - gain*v|| / ||inc||`.
5. Independently: the **real gain argument** was read straight off the stack at the
   `FUN_10002da0` call sites — `float32 [esp+0x1c]` at VA `0x10009d94` (CB1) and
   `float32 [esp+0x30]` at VA `0x10009fb6` (CB2, pre-`5/11`) — and `X` at VA `0x10009d56`
   (`float32 [esp+0x5c]`), together with the branch taken (VA `0x10009d18`/`0x10009d38`/`0x10009d48`)
   and the index read (`eax` at those lookups).

`gain_measured` (from step 4, i.e. the emulator's own excitation buffer) and the real gain
argument (step 5) agree to ≤1e-7 in every one of the 284 sub-frames: the increment *is* the
scaled codebook vector.

### 2.2 The code path (disassembly, all VA)

```
10009993  push 5 / push <reader> / call read            ; g8 = read(5)   (frame level)
1000999f  fild  [esp+0x64]                              ; g8 as float
100099a6  fdiv  qword [0x10023e70]                      ; g8 / 3.5
100099ac  call  0x10011aec                              ; _exp
100099b1  fstp  dword [esp+0x5c]                        ; X = float32(exp(g8/3.5))
   ...  (LTP call at 10009c0d, scratch cleared at 10009ced)
10009d08  cmp   eax,3 ; jne 10009d28                    ; mode descriptor [+8] == 3 ?
10009d13  push 3 / push <reader> / call read            ; i = read(3)
10009d18  fld   dword [eax*4 + 0x10023db8]              ; q[i]
10009d1f  fmul  dword [esp+0x64]                        ; q[i] * X        (esp+0x64 == esp0+0x5c)
10009d23  add   esp,8 ; jmp 10009d4c
10009d38  fld   dword [eax*4 + 0x10023ddc] ;  (read(1) branch, unused)
10009d48  fld   dword [esp+0x5c]                        ; else branch (=X)
10009d52  fstp  dword [esp+0x1c]                        ; gain = float32(q[i]*X)
10009d9f  call  0x10002da0(scratch, scratch, gain, 40)  ; FUN_10002da0: dst[i] = src[i]*gain
10009f3e  dst[i] += scratch[i]                          ; CB1 accumulated into the excitation
10009fb4  call  <codebook #2>                           ; second FUN_100029c0 pass
10009fba  fmul  qword [0x10023ee8]                      ; gain * (5/11)
10009fd5  call  0x10002da0(scratch2, scratch2, gain*5/11, 40)
10009ff1  dst[i] += scratch2[i]                          ; CB2 accumulated
```

`FUN_10002da0(dst, src, k, n)` is a plain `dst[i] = src[i] * k` with `dst == src` here
(float32 store per sample). Because `dst == src`, the CB1/CB2 accumulations are
"rounded to float32 at every sample".

Mode note: the 8 kHz core object's mode index `[obj+0x80]` is **7** (mode array `0x10023a0c`,
descriptor `0x10023978`), so the `if (mode == 1)` noise-mixing branch in `FUN_10009520` is
**not** taken: the excitation is exactly `LTP + CB1 + CB2`, which is what the increments show.

---

## 3. Measured tables

### 3.1 `q` fixed by gain-law-independent ratios (within-frame, same `g8`)

Within one frame `g8` (and therefore `X`) is constant — verified for all 71 frames — so the ratio
of two sub-frame gains in the same frame is exactly `q[b3_a]/q[b3_b]`. Over all frames:

```
max | gain_measured(b3)/gain_measured(b3_0)  -  q[b3]/q[b3_0] | = 3.80e-07
```

i.e. the 8-value table §1 is confirmed without using the exponential at all.

### 3.2 The full `q` dependence (representative rows, 284 records total)

| frame | sf | g8 | b3 | gain_measured (from increments) | gain (real arg) | model from §1 | projection resid |
|---|---|---|---|---|---|---|---|
| 0  | 0 | 0  | 2 | 0.31041 | 0.31041 | 0.31041 | 4.9e-14 |
| 0  | 2 | 0  | 5 | 0.71906 | 0.71905 | 0.71905 | 2.4e-08 |
| 31 | 1 | 0  | 5 | 0.71906 | 0.71905 | 0.71905 | 3.9e-08 |
| 38 | 0 | 27 | 4 | 1245.25489 | 1245.25488 | 1245.25488 | 4.6e-08 |
| 38 | 1 | 27 | 1 |  366.36304 |  366.36304 |  366.36304 | 3.1e-08 |
| 38 | 2 | 27 | 7 | 2972.36011 | 2972.36011 | 2972.36011 | 2.8e-08 |
| 38 | 3 | 27 | 1 |  366.36303 |  366.36304 |  366.36304 | 3.4e-08 |
| 55 | 2 | 24 | 6 |  892.36655 |  892.36664 |  892.36664 | 1.1e-07 |
| 60 | 0 | 14 | 7 |   72.44486 |   72.44486 |   72.44486 | 3.3e-08 |

`f32(q[4] * f32(exp(27/3.5))) = 1245.25488` reproduces the 1245.3 the earlier work measured at
frame 38 sub-frame 0 — that number was already right; the fit's error was in `q_fit` and in the
base of the exponential, which only shows up when `g8` varies (the recursion in the port).

### 3.3 `C(g8) = exp(g8/3.5)` — exact table for `g8 = 0..31`

`float32(exp(g8/3.5))` computed with Python's `math.exp` is **bit-identical** for all 32 values to
the value produced by the DLL's own x87 `_exp` path (checked by calling `0x10011aec` from a
hand-written stub `fild [esp+4]; fdiv qword [3.5]; call 0x10011aec; fstp dword [scratch]`).
Column "fit" is the old `0.430*1.3305**g8`; the last column is the **shape** error of the fit,
`C(g8)/C(0) / 1.3305^g8 - 1`.

| g8 | C(g8) | fit | fit shape err | g8 | C(g8) | fit | fit shape err |
|---|---|---|---|---|---|---|---|
| 0  | 1.0                | 0.43        | 0           | 16 | 96.68212890625     | 41.4673725  | +0.256% |
| 1  | 1.3307121992111206 | 0.572115    | +0.016%     | 17 | 128.6560821533203  | 55.1723391  | +0.272% |
| 2  | 1.7707949876785278 | 0.761199    | +0.032%     | 18 | 171.2042236328125  | 73.4067971  | +0.287% |
| 3  | 2.3564183712005615 | 1.01277528  | +0.048%     | 19 | 227.82354736328125 | 97.6677436  | +0.304% |
| 4  | 3.1357147693634033 | 1.34749751  | +0.064%     | 20 | 303.1675720214844  | 129.946933  | +0.320% |
| 5  | 4.172733783721924  | 1.79284544  | +0.080%     | 21 | 403.4288024902344  | 172.894394  | +0.336% |
| 6  | 5.552707672119141  | 2.38538085  | +0.096%     | 22 | 536.8475952148438  | 230.035991  | +0.352% |
| 7  | 7.389056205749512  | 3.17374922  | **+0.112%** | 23 | 714.3896484375     | 306.062887  | +0.368% |
| 8  | 9.832707405090332  | 4.22267334  | +0.128%     | 24 | 950.6470336914062  | 407.216671  | +0.384% |
| 9  | 13.084503173828125 | 5.61826688  | +0.144%     | 25 | 1265.03759765625   | 541.80178   | +0.400% |
| 10 | 17.41170883178711  | 7.47510409  | +0.160%     | 26 | 1683.4010009765625 | 720.867269  | +0.416% |
| 11 | 23.169971466064453 | 9.94562599  | +0.176%     | 27 | 2240.122314453125  | 959.113901  | +0.432% |
| 12 | 30.832565307617188 | 13.2326554  | +0.192%     | 28 | 2980.9580078125    | 1276.10105  | +0.448% |
| 13 | 41.02927017211914  | 17.606048   | +0.208%     | 29 | 3966.797119140625  | 1697.85244  | +0.464% |
| 14 | 54.598148345947266 | 23.4248468  | +0.224%     | 30 | 5278.66552734375   | 2258.99267  | +0.480% |
| 15 | 72.65442657470703  | 31.1667587  | +0.240%     | 31 | 7024.38427734375   | 3005.58975  | +0.496% |

**Does `C(g8) = 0.430*1.3305**g8` match within 0.1%? NO.** Two independent failures:

* the base: `exp(1/3.5) = 1.3307121992111206` vs `1.3305` → `-0.016%` **per step**, i.e.
  `-0.016·g8 %`; the fit's shape error exceeds 0.1% from `g8 = 7` and reaches **+0.50% at
  `g8 = 31`**;
* the scale: `0.430` is off by a factor **2.3256** — it absorbed the old `q_fit[3] = 1.0`
  (`0.430 ≈ q_true[3] = 0.428220`). The old `q_fit` was therefore `gain/C_fit(g8)` and is wrong
  by up to 9% per entry (`q_fit/q_true` = 2.405, 2.336, 2.223, 2.335, 2.338, 2.335, 2.546, 2.335).

Because the innovation feeds the adaptive-codebook history, `g8`-dependent errors are the ones
that accumulate in the port's recursive loop — use the table/formula in §1.

### 3.4 Coverage

`g8` observed in frames 0..70 (284 sub-frames): 0×144, 1×4, 12×4, 14×4, 15×4, 17×4, 18×4, 20×4,
21×4, 22×8, 23×12, 24×8, 25×48, 26×12, 27×16, 28×4. `b3` observed: 1×25, 2×27, 3×25, 4×30,
5×127, 6×39, 7×11 (b3 = 0 never occurred in this range but is a legal value of `read(3)`).
`X` and `g8` are constant across the 4 sub-frames of a frame in **all 71** frames (0 exceptions).

The frames asked for in the task, **30..70**, are a strict subset of the run: **164 sub-frames**,
`g8 ∈ {0,1,12,14,15,17,18,20,21,22,23,24,25,26,27,28}`, worst
`|gain_model - gain_measured|/gain_measured = 9.82e-08` — the same worst case as the full run
(it occurs at frame 55, inside 30..70).

### 3.5 `g8 == 0` is **not** gated

`g8 = 0` gives `X = 1.0` and a **non-zero** gain `q[b3]` (frames 0, 1, 2, 31 measured:
`gain = q[5] = 0.719055` for `b3 = 5`, `q[2] = 0.310413` for `b3 = 2`). The CB1/CB2 increments are
non-zero and match the codebook vector exactly (frame 0 sub-frame 0: the captured LTP stage is
`0.0` on every sample — the stream starts on a zero history, the codec's `+1e-15` floor aside —
`inc1[:6] = [-0.029101, -0.0097, 0.019401, 0.019401, 0.0, -0.029101]`,
`gain_measured = 0.310413 = q[2]`, projection residual 4.9e-14). So the innovation is emitted for
`g8 = 0`; the near-silence of frames 0..29 comes from the LTP/lower-band path, not from gating
this gain.

---

## 4. Stage-local acceptance result (emulator = ground truth)

All 284 sub-frames of frames 0..70:

| check | worst case |
|---|---|
| `\|gain_model - gain_measured\| / gain_measured` (CB1, model = §1) | **9.82e-08** (frame 55 sf 2, g8=24 b3=6) — criterion ≤1e-3 ⇒ PASS |
| `\|gain_model - gain_(real stack arg)\| / gain` (CB1) | **0.000e+00** (bit-identical float32) |
| `\|gain_model*5/11 - gain_measured(CB2)\| / gain_measured(CB2)` | 8.0e-08 |
| codebook projection residual `\|\|inc1 - gain*v1\|\|/\|\|inc1\|\|` | 1.15e-07 |
| codebook projection residual `\|\|inc2 - gain_CB2*v2\|\|/\|\|inc2\|\|` | 2.87e-07 |
| `\|gain_measured(CB1) - gain_(real stack arg)\| / gain` | 9.8e-08 |
| `\|gain_measured(CB2) - gain_(real stack arg)\| / gain` | 9.6e-08 |

Every residual is at the float32 rounding level, i.e. the excitation increments are exactly
`gain × (port codebook vector)` and `gain·5/11 × (port codebook vector)` — which also
re-confirms the port's codebook scale (the port's `codebook()` output equals the decoder's own
scratch, scale included, to ~1e-7).

---

## 5. Upper bands (16 kHz / 32 kHz): the same C/q machinery does **not** apply

Checked once, on frame 38, at the upper-band scale site `0x1000e70a`
(`call 0x10002da0`, block length 40, 4 sub-frames, object `0x30007fe0`):

```
1000e671  push 4 / call read(4)                ; i4 = the upper band's 4-bit energy field
1000e68c  call 0x10002ec0(codebook, 40)        ; Σ x²  -> the codebook energy
1000e695  fild  i4                             ; (the 4-bit field, as int)
1000e69c  fmul  qword [0x100242b0]             ; i4 * 0.27027027027027023
1000e6a2  fsub  qword [0x100242c0]             ; - 0.15556
1000e6a8  call  0x10011aec                     ; _exp
1000e6b4  cmp   [esi+0x10],0x50 ; jne ...      ; if block length == 80 (32 kHz): 
1000e6bd    fmul qword [0x100242a8]            ;    * 1.4142
1000e6ce  fdiv  [esp+0x1c]                     ; / codebook energy   (D2)
1000e6e7  fld   [esp+0x24] ; fadd 1.0          ; * (adaptive energy + 1.0)
1000e70a  call  0x10002da0(scratch, scratch, gain, 40)
```

Measured gains vs the model
`gain = exp(i4*0.27027027027027023 - 0.15556) * (E_adapt + 1.0) / E_codebook`
(frame 38, `E_adapt` = `[esp0+0x24]`, `E_codebook` = `[esp0+0x1c]`):

| sf | i4 | E_codebook | E_adapt | real gain | model | rel |
|---|---|---|---|---|---|---|
| 0 | 3 | 1.02654 | 638.397 | 1199.412354 | 1199.412299 | 4.5e-08 |
| 1 | 1 | 1.23648 | 606.470 |  551.004333 |  551.004327 | 1.1e-08 |
| 2 | 0 | 1.46465 | 585.227 |  342.588776 |  342.588774 | 6.2e-09 |
| 3 | 0 | 1.71094 | 2312.065 | 1157.161377 | 1157.161361 | 1.4e-08 |

and the four 4-bit values are *exactly* the port's `f["sub16"][sf][0]`
(frame 37 `[3,1,0,0]`, 38 `[0,1,0,2]`, 39 `[0,2,0,0]`, 40 `[2,0,0,0]` — all four frames match).

Conclusions:

* the upper bands use an **exponential energy dequantiser + codebook-energy normalisation**
  (`exp(i4*A - B)`, per-step base `exp(0.27027027027027023) = 1.3103185430275461`), with **no
  8-entry `q` table** and **no `g8/3.5`** — so `C(g8)`/`q[b3]` must not be reused there;
* the same code handles 80-sample blocks (the 32 kHz path) via the `*1.4142` branch at
  `0x1000e6b4`; in frames 37..40 the site was only reached with block length 40 (the 16 kHz band);
* the 32 kHz band's other energy fields (`read(5)`, the port's `ref32`) belong to its noise
  branch (ramp constant at `0x100242f8` = double `-1.0`), not to this site.

---

## 6. Minimal patch for `tools/codec210.py`

### 6.1 Module level (once)

`struct` is already imported; add `math` and the two constants + helper next to the other
module constants:

```python
import math
import struct

def _f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]

# float32 table at DLL VA 0x10023db8 (the read(3) branch of the 8 kHz gain index)
EXC_Q = (0.06112999841570854, 0.16354599595069885, 0.3104130029678345,
         0.4282200038433075, 0.55588698387146, 0.7190549969673157,
         0.9386940002441406, 1.326874017715454)

# double at DLL VA 0x10023ee8, used as `fmul QWORD PTR ds:0x10023ee8` for the 2nd pass
CB2_RATIO = 0.45454545454545453          # == 5/11
```

### 6.2 Replace `Codec210.exc_gain` (currently lines ~353-366)

```python
    def exc_gain(self, g8, b3, gden=None):
        """Exact 8 kHz innovation gain (measured; see specs/GainLaw.md).

        The decoder computes, once per frame:
            X    = (float)exp((double)g8 / 3.5)     ; VA 0x10009993..0x100099b1
            gain = (float)(EXC_Q[b3] * X)           ; VA 0x10009d18..0x10009d52
        `g8` is the 5-bit frame energy (`parse_frame["energy8"]`), `b3` the 3-bit
        sub-frame field (`sub8[sf][2]`, == the decoder's read(3) gain index).
        The `gden` LPC-tilt factor does not exist for this stage and is ignored.
        """
        X = _f32(math.exp(g8 / 3.5))
        return self.exc_scale * _f32(EXC_Q[b3 & 7] * X)
```

### 6.3 `Codec210.decode_frame` — one verbatim hunk

Delete these 8 lines (they compute the bogus `gden`; the comment is stale):

```python
            # LPC tilt terms used by the innovation gain (FUN_10009520)
            lsf_i = lsf_stabilise(lsf_interp(self.lsf8_prev, f["lsf10"], 10, sf, 4), 0.05)
            a = lsf_to_lpc(lsf_i)
            sump = sum(a[i] + a[i + 1] for i in range(0, len(a) - 1, 2))
            sumd = sum(a[i + 1] - a[i] for i in range(0, len(a) - 1, 2))
            gden = (sump + 0.01) / (0.01 + sumd) if sumd else 1.0
            gain = self.exc_gain(g8, b3, gden)
```

and put in their place

```python
            gain = self.exc_gain(g8, b3)              # exact law, float32
```

then replace

```python
            exc = [ltp[i] + gain * cb1[i] + (gain / 2.2) * cb2[i] for i in range(40)]
            self.buf[p:p + 40] = exc
```

with

```python
            g1 = gain                                 # float32 (exc_gain)
            g2 = _f32(g1 * CB2_RATIO)                 # float32, exact 5/11
            for i in range(40):                       # float32 store per sample,
                v = _f32(ltp[i] + _f32(g1 * cb1[i]))
                self.buf[p + i] = _f32(v + _f32(g2 * cb2[i]))
```

(The scalar `2.2` was a fitted approximation of `1/0.45454545454545453`; it is right to
2e-16 in double, so that part is a correctness-of-form change. The float32 rounding *is*
significant: the excitation buffer is the adaptive-codebook history, and the DLL rounds every
stored sample to float32, which the old list-comprehension did not.)

`exc_scale` stays as-is (it is an output-domain calibration unrelated to this law).

One further fidelity note on the same recursion (not part of the gain law, but it costs one
`_f32` call): the DLL's LTP output is stored as float32 too (the four `fstp DWORD` stores at
`0x10006f94/0x10006fb2/0x10006fd4/0x10006ff7`), so returning
`[_f32(g[2]*S[i] + g[1]*S[40+i] + g[0]*S[80+i]) for i in range(40)]` from `Codec210.ltp()`
matches the emulator bit-for-bit where the current double-precision return matches only to
~1e-7. Since `self.buf` *is* the adaptive-codebook history for the next sub-frame (and the next
frame), that rounding is visible in long recursions.

### 6.4 Delete

* the old `q = (0.147, 0.382, 0.69, 1.0, 1.30, 1.679, 2.39, 3.098)` tuple in `exc_gain`,
  the `0.430 * 1.3305 ** g8` expression and the `gden` parameter's dead computation (superseded
  by `EXC_Q` / `_f32(math.exp(g8/3.5))`).

---

## 7. Notes / why the old fit drifted

* The 8 kHz innovation is the only consumer of `C(g8)`; both codebook passes use the *same*
  `gain` (the second scaled by the exact double `5/11`), so there is exactly one place to fix.
* The old `gden` normaliser was derived from the 32 kHz band's decompilation and does not exist
  in `FUN_10009520`. It was already removed from the value but is still computed in
  `decode_frame`; it can go.
* The fit failed in two independent ways (§3.3): base `1.3305` vs `exp(1/3.5) = 1.3307121992`
  (−0.016%/step, i.e. +0.5% by `g8 = 31`) and the constant `0.430` = `q_true[3]` (a 2.3256×
  scale error absorbed into the fitted `q`). At the three frames the fit was tuned on
  (`g8 = 27` over three frames, per `Codec210.md` §10.6/§10.8) both errors partly cancelled, and
  the ramp between `g8 = 27` and `g8 = 0` was never exercised — which is exactly the
  `g8`-dependent error that accumulates in the recursive excitation loop.
* No other hidden factor is applied to the coded innovation: the increment/codebook projection is
  exact to float32 (≤1.15e-07) for all 284 sub-frames, so the `if (obj[+8] != 0)` scaling block at
  `0x10009c12`, if it ever fires, only rescales the LTP output (it cancels out of the increment).

## 8. Reproduce

Probe (throwaway, uses the oracle): `/tmp/gl_measure.py <first> <last> <out.json>`
with `/tmp/uv/bin/python`; it installs the code/write hooks listed in §2.1 and writes one JSON
record per sub-frame (fields: `g8, b3, idx_read, path, gain (real arg), X, gain_meas_cb1,
gain_meas_cb2, resid_cb1, resid_cb2, ...`). The full run for frames 0..70 used here:
`/tmp/uv/bin/python /tmp/gl_measure.py 0 70 /tmp/gl_meas.json` (~60 s).
The `exp` table in §3.3 was read by calling VA `0x10011aec` from a stub
`fild dword [esp+4]; fdiv qword [0x10023e70]; call 0x10011aec; fstp dword [scratch]; ret`.
