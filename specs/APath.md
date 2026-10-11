# specs/APath.md — the A path: `8 kHz synthesis → A16 → A32 → out = 2·(A32 − B32)`

Status: **measured against the real `LTTS7Codec210.dll` under Unicorn** (tools/codec210_oracle.py).
Verdict: `band_filter` (FUN_10003960) is **amplitude-correct (exact factor ½ per call)**; every real
band-filter call is reproduced with **corr 1.000000**. The port's quietness is **not** a filter-gain
bug — it is one **missing ×2** stage in the middle of the chain: the 16 kHz level's reconstruction
`out16 = 2·(A16 − B16)` is never formed, so the second `band_filter` is fed `A16` instead of `2·A16`.
With `B16 = B32 = 0` the port is **exactly 2× too small**; the non-constant end-to-end ratios
(1.8× / 2.4× / 5.7×) come from the port's own 8 kHz synthesis (upstream of this path), not from the
A path.

Also answered: **the 16 kHz coded branch does NOT contribute to the A16 input.** The A16 filter input
is *bit-for-bit the 8 kHz core LPC-synthesis output* (corr `+1.000000`, equal rms). The 16 kHz branch
feeds the **B16** (high-band) filter instead.

---

## 1. What was measured and how

Instrumentation: `tools/codec210_oracle.py`'s `Oracle`, plus `UC_HOOK_CODE` hooks on the exact `call`
opcodes (found with `objdump -d -M intel`). At a `call` instruction ESP still points at the first
stack argument. Call-site semantics (confirmed disassembly vs. observed values):

* `FUN_10003960` is **`__cdecl`**; at the call, `[ESP+0]=src  [ESP+4]=coef  [ESP+8]=dst
  [ESP+12]=outcount(int, = 2·len(src))  [ESP+16]=64 (ntaps)  [ESP+20]=tail  [ESP+24]=work`.
  (Ghidra's signature `FUN_10003960(int src,int coef,int dst,float outcount,int ntaps,int tail,
  undefined4 *work)`; `outcount` is an **int**, not a float.)
* `FUN_1000c290` is **`__fastcall`**: `ECX = out`, `EDX = A`, `[ESP+0] = B`;
  `out[i] = clamp(round(2·(A[i]−B[i])))` — the ×2 is the double constant `_DAT_10022e58 = 2.0`.

Hooked sites (all inside `FUN_1000e170`, the per-level band driver):

| site | role |
|---|---|
| `0x1000e87b` | A filter (`coef = 0x100240a8`) |
| `0x1000e898` | B filter (`coef = 0x100241a8`) |
| `0x1000e8ae` | combine `FUN_1000c290` |

`FUN_1000e170` is called **twice per frame**: first with the 16 kHz object (`esi=0x30007fe0`),
then with the 32 kHz object (`esi=0x300021a0`) — so **4 band-filter calls + 2 combines per frame**.
(The other two groups of identical call sites, `0x1000e118/…` in `FUN_1000def0` and `0x1000e300/…`
inside `FUN_1000e170`'s `mode==0` branch, **never fire** on frames 0–39; the live path is
`0x1000e87b/0x1000e898` only.)

Procedure: decode frames 0…39 with the oracle, and at the hooked sites capture the arguments, the
`tail` contents *before* the call, and a snapshot of the whole working heap
(`0x3000d000..0x30019000`). Frames 37/38/39 were then analysed as follows: (a) each real filter call
was replayed through the port's `band_filter()` with the real `src`+`tail`; (b) the port's
`Codec210` was instrumented (throwaway copy) to dump `sig8`, `a16`, `a32`.

## 2. Measured buffer wiring (frames 37–39)

Object fields read from `esi` at the combine calls (`+0x8` = outcount, `+0xc` = filter input len,
`+0x10` = sub-frame, `+0x14` = 4 sub-frames, `+0x20` = rate):

| 16 kHz object `0x30007fe0` (rate 16000, 320 out) | 32 kHz object `0x300021a0` (rate 32000, 640 out) |
|---|---|
| `+0x2c = 0x30012a30`  A input (= ring1 head) | `+0x28 = 0x30002220`  **ring = the 16 kHz combine output buffer** |
| `+0x34 = 0x30012f30`  B input (16 kHz LPC synth) | `+0x2c = 0x30014380`  A input (= copy of `ring[0:320]`) |
| `+0x38 = 0x30013430`  A out  (= **A16**) | `+0x34 = 0x30014d80`  B input (32 kHz LPC synth) |
| `+0x3c = 0x30013930`  B out  (= **B16**) | `+0x38 = 0x30015780`  A out (= **A32**) |
| `+0x40/+0x44 = 0x30013e30/0x30013f30` tails | `+0x3c = 0x30016180`  B out (= **B32**) |

At the top of `FUN_1000e170` the object copies `ring[0 : +0xc]` into `+0x2c`. For the 32 kHz object
`ring = 0x30002220`, which is exactly the buffer the **16 kHz combine wrote one step earlier**, so the
32 kHz A-filter input is the *current frame's* 16 kHz reconstruction (no delay).

Wiring verified (frames 37/38/39):

| relation | corr | rms ratio |
|---|---|---|
| `A16` input (`0x30012a30`) vs the 8 kHz core LPC-synthesis output (`o8+0x30 = 0x30011ea0`) | **+1.000000** | **1.000000** |
| `A16` input vs the 16 kHz branch synth `0x30012f30` | +0.107 / +0.064 / −0.077 | — |
| 32 kHz ring head `0x30002220[0:320]` vs `2·(A16−B16)` | **+1.00000000** | **1.000000** |
| `2·(A32−B32)` vs the oracle PCM | +0.99999997 / +1.0 / +1.0 (max abs diff **0**) | 1.000000 |

⇒ the chain is a **two-level QMF tree**, each level `out = 2·(A − B)` :

```
                    8 kHz core LPC synthesis (o8+0x30, 160)
                          │                       │  ── the 16 kHz coded branch ──┐
                    A16 = bf(cfA, 320)      B16 = bf(cfB, 320) ◄───────────────┘
                          └────────── out16 = 2·(A16 − B16)  (320, = ring[0:320]) ──┐
                    A32 = bf(cfA, 640)      B32 = bf(cfB, 640) ◄── 32 kHz branch ──┘
                          └────────── pcm  = 2·(A32 − B32)      (640)
```

**The port's assumption "A32 = band_filter(A16)" is wrong**: the 32 kHz A-filter input is the
*combined 16 kHz signal* `out16 = 2·(A16 − B16)`, not `A16` itself. (This also corrects the framing
in the task: the "16 kHz object's `+0x38`" is `A16` = the low-band filter output; the actual input of
the 32 kHz band filter is `out16 = 2·(A16−B16)`, i.e. the 32 kHz object's `+0x28/+0x2c`.)

## 3. Per-stage tables (real DLL, frames 37/38/39)

RMS of every stage (from the heap snapshots):

| f | sig8 (A16 in) | A16 | B16 | synth16 | out16 | A32 | B32 | synth32 | pcm |
|---|---|---|---|---|---|---|---|---|---|
| 37 | 2775.82 | 605.85 | 178.79 | 442.51 | 1262.11 | 617.50 | 83.24 | 181.78 | 1246.60 |
| 38 | 4088.00 | 2384.16 | 159.41 | 184.30 | 4779.32 | 2381.98 | 53.31 | 82.38 | 4765.15 |
| 39 | 5111.09 | 2549.55 | 92.30 | 184.48 | 5102.34 | 2539.10 | 30.64 | 54.90 | 5078.49 |

Per-call gain `rms(dst)/rms(src)`:

| call | f37 | f38 | f39 |
|---|---|---|---|
| A16 ← sig8 | 0.2183 | 0.5832 | 0.4988 |
| B16 ← synth16 | 0.4040 | 0.8649 | 0.5003 |
| A32 ← out16 | 0.4893 | 0.4984 | 0.4976 |
| B32 ← synth32 | 0.4579 | 0.6471 | 0.5581 |

Net level gains: `pcm/A16` = 2.058 / 1.999 / 1.992 ; `A32/A16` = 1.019 / 0.999 / 0.996.
The A16 ratio varies per frame (0.22 at the frame-37 silence→speech transient) because the filter
spreads an in-frame transient across the frame boundary (energy is conserved over *contiguous*
frames, not per window); the average over frames 37–39 is √((0.2183²+0.5832²+0.4988²)/3) = 0.460.

Shape (already known, re-confirmed): every one of the 4 real calls is reproduced by the port's
`band_filter()` with the real `src`+`tail` at **corr 1.000000** (max abs diff 8e-5 … 3e-3).

## 4. The exact gain of one `FUN_10003960` call

Fed the port's `band_filter()` with long (N=2048…4096) stationary inputs and `tail=0`, using the real
coefficient tables `0x100240a8` (=A) and `0x100241a8` (=B):

* `|H_A| = |H_B| = 0.4979 … 0.5015` for **every** input frequency swept (f/fs = 0.0005 … 0.4995;
  measured with cosines, steady-state rms ratio);
* DC input: `A → 0.49998`, `B → 0.00000` (Σh_A = 0.999967, Σh_B = 0.000000, Σ|h_A| = Σ|h_B| =
  1.982200);
* the A and B tables are the same 64-tap prototype with alternating taps negated.

**⇒ the exact factor of one call is ½** (flat amplitude response; the ÷2 is the polyphase
upsampling factor). The level combine `×2` is what restores the level's amplitude, so **each QMF
level is amplitude-preserving** and the two-level A path is amplitude-transparent:
`pcm/A16 ≈ 2.0` (measured 2.058 / 1.999 / 1.992).

Therefore a correct A path must contain **two** `×2` factors (one per level). `tools/codec210.py`
currently contains only the final one → **its output is exactly 2× too small** whenever
`B16 = B32 = 0` and the upstream 8 kHz synthesis is right.

## 5. Does the 16 kHz coded branch contribute to the A16 input?

**No.** The 16 kHz object's A-filter input (`0x30012a30`) is bit-for-bit the 8 kHz core
LPC-synthesis output (`0x30011ea0`): corr **+1.000000**, rms 605.85/2384.16/2549.55 identical to
7 digits, and it is uncorrelated with the 16 kHz branch synth (`0x30012f30`). The 16 kHz coded
branch is the **B16** input (high band), which the combine *subtracts*.

## 6. Minimal patch for `tools/codec210.py`

Function `Codec210.decode_frame`, the A-path block (currently the last ~7 lines). **Only insertion:
form `out16 = 2·a16` before the second `band_filter`.** Nothing else changes (the final
`2.0 * a32` already supplies the second ×2).

```python
        # ---- 8 kHz synthesis -> A16 -> out16 -> A32 -> out = 2*(A32 - B32) ----
        sig8 = self.synth8(f["lsf10"])
        a16 = band_filter(sig8, self.cf_a, 320, 64, self.tail_a16, [0.0] * 1088)
        # 16 kHz QMF reconstruction: out16 = 2*(A16 - B16).  B16 (the 16 kHz coded
        # branch) is not ported yet -> 0.  Skipping this factor made the output
        # exactly 2x too small (see specs/APath.md).
        out16 = [2.0 * v for v in a16]
        a32 = band_filter(out16, self.cf_a, 640, 64, self.tail_a32, [0.0] * 2048)

        # B32 (the 32 kHz noise branch) is not ported; A dominates the output.
        pcm = [clamp_int16(2.0 * v) for v in a32]
```

Equivalent one-liner (the filter is linear and its tail state is scaled consistently):
`a32 = band_filter([2.0 * v for v in a16], self.cf_a, 640, 64, self.tail_a32, [0.0] * 2048)`.

Do **not** compensate this missing ×2 with `exc_scale`: the ×2 belongs to the synthesis path and does
not exist in the excitation, so scaling `exc_scale` would corrupt the adaptive-codebook history
(`self.buf`) and change the waveform. Keep `exc_scale = 1.0` (the measured excitation amplitudes are
already the real decoder's; see §10.6 of `Codec210.md`).

`__init__`/`reset` can stay as-is (only the two A tails are needed while `B16 = B32 = 0`). When the
upper bands are ported, add `self.cf_b = T["band_filters_qmf"]["bandB_64tap"]["f32"]`,
`self.tail_b16`/`self.tail_b32` and the two lines
`b16 = band_filter(synth16, self.cf_b, 320, 64, self.tail_b16, work)` /
`b32 = band_filter(synth32, self.cf_b, 640, 64, self.tail_b32, work)`, then use
`out16 = [2.0*(x-y) for x, y in zip(a16, b16)]` and `pcm = [clamp_int16(2.0*(x-y)) for x, y in
zip(a32, b32)]`.

## 7. Acceptance

**(a) Stage-local, port's A path fed the real 8 kHz synthesis output** (isolates the A path):

| stage | corr(port, real) | rms ratio |
|---|---|---|
| `a16` vs real `A16` (f37/38/39) | **+1.000000** | **1.000000** |
| `a32` old (`bf(a16)`) vs real `A32` | +0.9578 / +0.9963 / +0.9952 (identical to the patched corr: the difference is a pure 2× scale) | 0.479 / 0.498 / 0.498 |
| `a32` **patched** (`bf(2·a16)`, B16=0) vs real `A32` | +0.9578 / +0.9963 / +0.9952 | 0.958 / 0.996 / 0.995 |
| `a32` patched fed the real `out16` (= with B16) vs real `A32` | **+1.00000000** | **1.000000** |

The residual at f37 is entirely the **unported B16** (`2·bf(B16)`, B16 rms 179 vs A16 606); with B16
supplied the A32 is exact.

**`rms(2·A32)` after the patch vs the real PCM:**

| f | patched `rms(2·A32)` | real `rms(pcm)` | ratio | corr vs real PCM |
|---|---|---|---|---|
| 37 | 1183.02 | 1246.60 | 0.949 | +0.9493 |
| 38 | 4745.85 | 4765.15 | 0.996 | +0.9961 |
| 39 | 5053.62 | 5078.49 | 0.995 | +0.9951 |

(fed the *emulator's* 8 kHz synthesis; `B16 = B32 = 0`)

**(b) End-to-end port** (its own, still-imperfect 8 kHz synthesis; frames 0…39 carried):

| f | port `rms(pcm)` OLD | port `rms(pcm)` PATCHED | real `rms(pcm)` | real/OLD | real/PATCHED |
|---|---|---|---|---|---|
| 37 | 675.92 | 1352.27 | 1246.60 | 1.844 | 0.922 |
| 38 | 1954.43 | 3909.15 | 4765.15 | 2.438 | 1.219 |
| 39 | 890.91 | 1782.16 | 5078.49 | 5.700 | 2.850 |

The pre-patch ratios reproduce the ticket's **1.8× / 2.4× / 5.7×** exactly. After the patch the
remaining error is dominated by the port's 8 kHz synthesis, not the A path: with the port's own
`sig8`, `corr(a16_port, A16_real)` = 0.746 / 0.709 / 0.330 and `rms(sig8_port)/rms(sig8_real)` =
0.922 / 0.808 / 0.338 — i.e. the 8 kHz chain (LTP/excitation history, §10.9 of `Codec210.md`) is the
next blocker, together with `B16`/`B32`.

## 8. Remaining A-path gap (not this task)

`B16 = band_filter(synth16, 0x100241a8, …)` and `B32 = band_filter(synth32, 0x100241a8, …)` are the
only unportable inputs; they need the 16 kHz coded branch and the 32 kHz branch syntheses
(inputs `0x30012f30` = `esi(16k)+0x34`, outcount 320, and `0x30014d80` = `esi(32k)+0x34`, outcount
640). With them the A path closes at corr 1.000000 / max-diff 0 (verified end to end above).

## 9. Reproduce

* `/tmp/measure4.py` — oracle hooks, heap snapshots + tail capture → `/tmp/snaps2.json`
* `/tmp/measure3.py` — L1-call snapshot of the 8 kHz synth → `/tmp/snaps_apath.json`
* `/tmp/analyze2.py`, `/tmp/analyze4.py` — per-call replay, wiring correlations, stage tables
* `/tmp/run_port.py` — runs `tools/codec210.py` and `/tmp/codec210_patched.py`, dumps
  `sig8/a16/a32/pcm` per frame
* `/tmp/verify_combine.py` — `out = clamp(round(2·(A32−B32)))` vs the oracle PCM (max diff 0)

(Run all of them with `/tmp/uv/bin/python`.)
