# LTTS7Codec210.dll — codec 210 format & decoder specification

Scope: the Loquendo TTS 7 **codec 210** speech decoder plugin, as shipped in the voice package
`jorge/pf/Loquendo/LTTS7/`. Primary target is the **Jorge build**
`bin/LTTS7Codec210.dll` (198 656 B, PE32, ImageBase `0x10000000`, TimeDateStamp `0x4b8f966f`,
MD5 `c02f0bd4329fc8f860407180ea1383c4`).
Cross-reference: `LTTS7CodecMsx.dll` (see §9).

All addresses below are **VA** (ImageBase + RVA). File offsets for every table are in
`tools/codec210_tables.json`. The raw decompilation used is the Ghidra auto-decomp of the Jorge DLL
(`/tmp/c210/decomp_codec210_jorge.txt`, 439 functions) plus a forced disassembly of the small
entry-point thunks Ghidra did not create (`/tmp/c210/missing210.txt`).

**Ground truth.** Besides the decompilation, every claim about the *stream* was validated by running
the real DLL code under an x86 emulator (Unicorn, `tools/codec210_oracle.py`) and comparing with the
pure-Python re-implementation (`tools/codec210.py`). See §10 for the validation protocol.

---

## 1. The two binaries at a glance

| | Jorge `LTTS7Codec210.dll` | Jorge `LTTS7CodecMsx.dll` |
|---|---|---|
| size | 198 656 B | 112 128 B |
| single export | `LTTS7Codec210` @ RVA 0x4760 | `LTTS7CodecMsx` |
| imports | **KERNEL32 only** | KERNEL32 + … |
| Util symbols | bound at runtime via `LoadUtilSymbols` | same mechanism |

The Jorge 210 build is **statically linked** against the compact MSVC 2008 CRT. It imports *no*
Loquendo library; the five utility entry points it needs are handed to it by the engine through
`LoadUtilSymbols` (see §2.2). This is the whole reason that entry point exists — for the older
`engine_re` build, `LTTS7Util.dll` was a real import table dependency instead.

---

## 2. Plugin ABI

### 2.1 Dispatcher export

`LTTS7Codec210` (RVA `0x4760`, i.e. VA `0x10004760`) is a **name→function-pointer dispatcher**.
It is called as `void *LTTS7Codec210(const char *name)` and returns the address of one of the plugin
entry points, or `0`.

It implements the comparison inline: for `uVar5 = 0..7` it walks the table at **VA `0x1002e028`**
(8 entries, stride 8 = `{const char *name; void *func;}`) and byte-compares `name` with
`entry->name`; on a full match it returns `entry->func`. The literal `if (7 < uVar5) return 0;`
proves the table has **8** entries.

| idx | name | func VA | role |
|---|---|---|---|
| 0 | `LoadUtilSymbols` | `0x10004130` | bind ELQ* helpers from the host (not a decoder entry point) |
| 1 | `GetVersion` | `0x100041f0` | decoder version |
| 2 | `ELQOpenDecoder` | `0x100045e0` | create a decoder instance |
| 3 | `ELQCloseDecoder` | `0x10004730` | destroy it |
| 4 | `ELQGetDecodedFileSize` | `0x10004220` | — |
| 5 | `ELQGetDecoderDescription` | `0x100041c0` | — |
| 6 | `ELQDecoderFileChanged` | `0x100041d0` | notify "current stream changed" |
| 7 | `ELQDecode` | `0x10004530` | decode PCM |

The **7 entry points** the engine resolves by name (via `ELQPluginGetProc`) are indices 1..7.

### 2.2 `LoadUtilSymbols` (`0x10004130`) — runtime binding of the util API

Walks a 5-entry table at **VA `0x1002e000`**, stride 8 = `{const char *name; void **slot;}` and for
each entry calls the helper `FUN_10004100(moduleHandle)`, which does
`*slot = GetProcAddress(moduleHandle, name)`. It stops at the first failure and prints
`WARNING: Symbol "%s" not found in utility library`.

| name | slot VA | meaning |
|---|---|---|
| `ELQBinGetBuffer` | `0x1002f624` | map/read `size` bytes at `offset` from the shared `.bin` resource |
| `ELQLogWrite` | `0x1002f628` | logger |
| `ELQfree` | `0x1002f62c` | free |
| `ELQmalloc` | `0x1002f630` | alloc (used for the 0x11E8-byte context) |
| `ELQstricmp` | `0x1002f634` | case-insensitive compare (not used after the dispatcher) |

These 5 slots are zero in the file's `.data` and are filled at load time. `ELQstricmp` is what the
engine-build dispatcher used; the Jorge dispatcher open-codes the comparison instead.

### 2.3 Entry-point signatures

| entry | VA | signature | behaviour |
|---|---|---|---|
| `GetVersion` | `0x100041f0` | `int GetVersion(void *out7)` | writes the 7 bytes at `0x10022db8` = `"7.14.0"` (`37 2e 31 34 2e 30 00`) → `out7[0..2]` as dword+word+byte. Returns 0. |
| `ELQOpenDecoder` | `0x100045e0` | `int ELQOpenDecoder(void **pCtx, int sampleRate, int logHandle)` | allocates and initialises the 0x11E8-byte context. Returns 0 ok, 4 `SampleRate not supported`, 5 out-of-memory. |
| `ELQCloseDecoder` | `0x10004730` | `int ELQCloseDecoder(void *ctx)` | frees the bit-reader buffer, the decoder object and the context. Returns 0. |
| `ELQGetDecodedFileSize` | `0x10004220` | `int ELQGetDecodedFileSize(void *, int *pSize)` | `*pSize = -1` (size not known up-front — the codec is streamed). Returns 0. |
| `ELQGetDecoderDescription` | `0x100041c0` | `const char *ELQGetDecoderDescription(void)` | returns the literal `"Loq210"` (`0x10022db0`). |
| `ELQDecoderFileChanged` | `0x100041d0` | `int ELQDecoderFileChanged(void *ctx, int streamOffset)` | `if (ctx) { ctx[0x11E5] = 0; *(int*)(ctx+0x4C) = streamOffset; }`. Returns 0. |
| `ELQDecode` | `0x10004530` | `int ELQDecode(void *ctx, void *io, void *binHandle, int maxSamples, void *pcmOut)` | see §6.1. |

`ELQDecoderFileChanged` is the important one: it **invalidates the cached stream sub-header**
(`ctx+0x11E5 = 0`) and stores the byte offset of this stream inside the shared `.bin`
(`ctx+0x4C = streamOffset`). For the Jorge voice DB this offset is the 122-byte
`LOQUENDOTTS7` header size — which is exactly why frame *i* is read at
`streamOffset + 28 + i*bytesPerFrame`. The engine derives it from the container header.

---

## 3. Decoder context layout (size `0x11E8` = 4584 bytes)

Allocated by `ELQOpenDecoder` through `ELQmalloc(0x11E8)` and zeroed. Only the fields listed are
used; the rest are scratch float buffers (LPC states, codebooks) addressed by the decoder object.

| byte offset | type | set by | meaning |
|---|---|---|---|
| `+0x00` | `u8*` | `FUN_100012e0` | bit-reader input buffer (own copy, `_calloc(2000)`) |
| `+0x04` | `u32` | `FUN_10001040` | **total bits** available (= `8 * bytesPerFrame`) |
| `+0x08` | `u32` | bit reader | current byte index |
| `+0x0C` | `u32` | bit reader | current bit index inside the byte (0..7) |
| `+0x10` | `u32` | `FUN_100012e0` | "owns the buffer" flag (1) |
| `+0x14` | `u32` | bit reader | **error/overrun flag** (1 = past end) |
| `+0x18` | `u32` | `FUN_100012e0` | buffer capacity (2000) |
| `+0x24` | `void*` | `ELQOpenDecoder` | pointer to the per-rate **class descriptor / vtable** (32 kHz → `0x10023b2c`) |
| `+0x28` | `void*` | `FUN_10004230` | the decoder **instance object** (see §3.1), 0 until first decode |
| `+0x2C` | `int` | `ELQOpenDecoder` | `logHandle` (host logger) |
| `+0x30` | `int` | `ELQOpenDecoder` | `sampleRate` (32000) |
| `+0x34` | `int` | `ELQOpenDecoder` | 509 for 32 kHz (table/index stride constant, used as the sample-position step in `ELQDecode`) |
| `+0x38` | `int` | `ELQOpenDecoder` | 6 for 32 kHz (frames of "history" the streaming wrapper keeps) |
| `+0x3C`,`+0x40` | `int` | `FUN_100042f0` | sample window currently in the output buffer (first/last) |
| `+0x44`,`+0x48` | `int` | `FUN_100042f0` | same for the previous-frame buffer |
| `+0x4C` | `int` | `ELQDecoderFileChanged` | **byte offset of this stream in the `.bin`** (= 122 for Jorge) |
| `+0x11D0` | `u16` | `ELQDecode` | **bytes per frame** = `110` (read from sub-header byte `0x13`) — also the XOR length |
| `+0x11D2` | `u16` | `ELQOpenDecoder` | **samples per frame** = `640` (0x280) |
| `+0x11D4` | `void*` | `ELQOpenDecoder` | output PCM buffer (points at `ctx+0x410`) |
| `+0x11D8` | `void*` | `ELQOpenDecoder` | previous-frame PCM buffer (`ctx+0xCD0`) |
| `+0x11DC`,`+0x11E0` | `int` | streaming wrapper | current/previous frame indices (`-2` initially) |
| `+0x11E4` | `u8` | `ELQDecode` | **per-frame XOR key** = `0x6D` (sub-header byte `0x1B`) |
| `+0x11E5` | `u8` | `ELQDecode` | sub-header cache-valid flag |

### 3.1 Rates

`ELQOpenDecoder` switches on `sampleRate` (`0x100045e0`, disasm `0x10004617`):

| rate (Hz) | samples/frame `+0x11D2` | `+0x34` | `+0x38` | class descriptor `+0x24` | out buf `+0x11D4` | prev buf `+0x11D8` |
|---|---|---|---|---|---|---|
| 8000 (`0x1f40`) | 160 (`0xa0`) | 110 | 3 | `0x1002393c` | `ctx+0x50` | `ctx+0x910` |
| 16000 (`0x3e80`) | 320 (`0x140`) | 224 | 3 | `0x10023ab4` | `ctx+0x190` | `ctx+0xa50` |
| 32000 (`0x7d00`) | **640 (`0x280`)** | 509 | 6 | **`0x10023b2c`** | `ctx+0x410` | `ctx+0xCD0` |
| other | — | — | — | — | — | returns 4, logs `Unable to create LoqCodec210 decoder (SampleRate not supported)` |

Every rate supports exactly 20 ms frames; the 32 kHz rate is the one used by the voice DBs
(`Freq=32000` TLV).

### 3.2 Decoder instance object (0x74 bytes)

Created lazily on the first decode by `FUN_10004230` (the "reset" routine) through
the virtual factory `FUN_1000f4f0(ctx+0x24)` → `ctx[+0x24][+0x20]` = **`FUN_1000db20`**
(the constructor). Destroyed by `FUN_1000f510(obj)` → `obj[0][+0x24]` = `FUN_1000de40`.

`FUN_1000db20(classDesc, ...)`:

```
obj = calloc(0x74); memset(obj, 0, 0x74)
obj[+0x28] = calloc(24000)                 ; scratch work area
obj[+0x00] = classDesc                     ; == 0x10023b2c for 32 kHz  (the object's vtable)
sub = *classDesc                           ; == 0x10023ca8 (32 kHz sub-descriptor)
obj[+0x68] = 1
obj[+0x04] = FUN_1000f4f0(sub[+0x00])      ; construct the synthesis/filter sub-object
obj[+0x08] = sub[+0x04] * 2    ; = 640     ; samples per FUN_1000e170 invocation
obj[+0x0C] = sub[+0x04]        ; = 320
obj[+0x10] = sub[+0x08]        ; = 80      ; samples per sub-block
obj[+0x14] = sub[+0x04]/sub[+0x08] ; = 4   ; number of sub-blocks per call
obj[+0x18] = sub[+0x0C]        ; = 8       ; **LPC order**
obj[+0x6C] = sub + 10 (dwords)             ; == 0x10023cd0 : mode pointer array
obj[+0x70] = sub[+0x12]        ; = 1       ; current mode index (overwritten by the bitstream)
... + a dozen calloc'd work buffers indexed by order/samples ...
obj[+0x19] = 1000
```

The **class descriptor** for 32 kHz, `0x10023b2c`, is a table of 24 function/field pointers:

| off | value | |
|---|---|---|
| `+0x00` | `0x10023ca8` | per-rate sub-descriptor (see below) |
| `+0x04` | `0x1000f5d0` | class query / name helper |
| `+0x08` | `0x10023d54` | string pool (`"ultra-wideband sub-band CELP"` etc.) |
| `+0x0C` | 2 | rate index |
| `+0x10` | 4 | sub-block count |
| `+0x14` | `0x1000c310` | per-band setup |
| `+0x18` | `0x1000cb20` | |
| `+0x1C` | `0x1000cc90` | 32 k analysis/quantiser helper |
| `+0x20` | `0x1000db20` | **constructor** (called by `FUN_1000f4f0`) |
| `+0x24` | `0x1000de40` | **destructor** (called by `FUN_1000f510`) |
| `+0x28` | `0x1000e170` | **per-call decode** (called by `FUN_1000f530`) |
| `+0x2C` | `0x1000e8f0` | |
| `+0x30` | `0x1000f0e0` | called by `FUN_1000f550` before each decode |
| `+0x44` | `0x1000bdd0` | band parameter decode |
| `+0x48` | `0x1000c0d0` | band parameter decode (LSF) |
| `+0x58` | `0x10001b60` | |
| `+0x5C` | `0x100029c0` | |

Sub-descriptor `0x10023ca8` (32 kHz): `+0x00 = 0x10023ab4` (16 kHz descriptor), `+0x04 = 320`,
`+0x08 = 80`, `+0x0C = 8` (LPC order), `+0x10 = 1280`, then float constants
`0.9, 0.6, 0.002, 0.0001, 0.7`, `+0x2C = 0x10023a70` (band descriptor, funcs
`FUN_1000bdd0`@+0x10, `FUN_1000c0d0`@+0x14), and at `+0x28..` the **mode pointer array**
(`0x10023cd0`) = `[0, 0x10023a70, 0, 0, 0, 0, 0, 0, 1, 0, 1, 2, 3, 4, …]`.
A mode index `m` is valid iff `modeArray[m] != 0`; for 32 kHz only **m = 1** is non-null
(m = 0 selects the special "no new data" path, any other non-zero m triggers
`"Invalid mode encountered: corrupted stream?"` and returns −2).

The virtual-call thunks are tiny `jmp` stubs:
`FUN_1000f4e0(x) = jmp [x+0x14]`, `FUN_1000f4f0(x) = jmp [x+0x20]`,
`FUN_1000f500/510/520/530/540/550(x) = jmp [[x]+0x18/0x24/0x1C/0x28/0x2C/0x30]`.

---

## 4. Container, stream sub-header and frame-size arithmetic

The `.bin` file is a `LOQUENDOTTS7` container (see `specs/ELQBinContainer.md`).
For `Jorge.32000.LTTS7Codec210.44000.10.bin` (29 144 430 bytes):

* header size `122` (TLV `Freq=32000`, `Coding=LTTS7Codec210`, `BitRate=44000`, `Rank=10`,
  `Version=7.1.0`);
* at offset 122 the codec expects a **28-byte stream sub-header** = **7 big-endian `u32`**
  (`ELQOpenDecoder` reads them via the `ELQBinGetBuffer` binding in `ELQDecode`, size `0x1C`):

| sub-header off | BE u32 | value (Jorge) | meaning | consumed by |
|---|---|---|---|---|
| 0x00 | BitRate | 44000 | nominal bit rate (bits/s) | — |
| 0x04 | Rank | 10 | rank/quality class from the TLV | — |
| 0x08 | samples/frame | **640** | PCM samples per frame | — |
| 0x0C | Freq | 32000 | sample rate (must match `ELQOpenDecoder`) | — |
| 0x10 | bytes/frame | **110** | stored bytes per frame | `ELQDecode`: `ctx+0x11D0 = (u16)(s8)seed[0x13]` |
| 0x14 | frame count | **264 948** | number of frames | — |
| 0x18 | cookie | `0x1FE90B6D` | per-file scramble cookie | `ELQDecode`: `ctx+0x11E4 = (u8)seed[0x1B]` |

Exact code (`ELQDecode`, VA `0x10004530`, disasm `0x1000457e`–`0x100045ac`):

```
; if ctx->cache_valid(0x11E5) == 0:
p = ELQBinGetBuffer(bin, ctx->streamOffset(0x4C), 0x1C, 1, 0, &flag)
ctx->bytesPerFrame(0x11D0) = (int16)(int8)p[0x13]    ; 110
ctx->xorKey(0x11E4)        = p[0x1B]                 ; 0x6D
ctx->cache_valid(0x11E5)   = 1
```

### 4.1 Frame-size derivation (exact sources)

* **samples/frame = 640** — `ELQOpenDecoder` `mov WORD PTR [esi+0x11d2],0x280` (`0x10004698`), and
  independently the sub-header word at offset 0x08 (`0x00000280`).
* **frame duration = 20 ms** — 640 samples / 32 000 Hz.
* **bytes/frame = 110** — sub-header word at offset 0x10 (`0x0000006E`) copied to `ctx+0x11D0` by
  `ELQDecode` (`0x10004594`); consistent with 44000 bit/s × 20 ms / 8 = 110.
* **frame count = 264 948** — sub-header word at offset 0x14 (`0x00040AF4`).
* **data region starts at 122; first frame at 122 + 28 = 150.**

Cross-check against the shipped DB size (29 144 430 B):

```
122 (header) + 28 (sub-header) + 264948 * 110 = 122 + 28 + 29144280 = 29144430   ✔ exact
```

The same identity holds for the other two shipped DBs
(`JorgeGildedPhrases`: 148 + 28 + 8889·110 = 977 966; `JorgeGildedParalinguistics`:
164 + 28 + 9958·110 = 1 095 572).

---

## 5. Per-block layout and the XOR key

A **block** (frame) is **110 bytes** at file offset `150 + 110*i`, `i < 264948`.
Frames are stored **scrambled**, and the decoder un-scrambles each block before bit-unpacking.

### 5.1 The XOR fields at `+0x474` / `+0x479`

In the decompiled code the context pointer is typed `int*`, so the Ghidra expressions `ctx[0x474]`
and `ctx[0x479]` are **pointer-scaled** and denote the byte offsets **`+0x11D0`** and **`+0x11E4`**:

```c
/* FUN_10004290 @ 0x10004290  (the decode driver; EDI = block buffer, ESI = ctx) */
if ((char)ctx[0x479] != 0 && 0 < (short)*(u16*)(ctx + 0x474)) {   /* key != 0 && len > 0 */
    len = *(u16*)(ctx + 0x474);                                   /* ctx+0x11D0 = 110 */
    do { *p ^= *(u8*)(ctx + 0x479); p++; } while (--len);         /* ^= ctx+0x11E4 = 0x6D */
}
FUN_10001020(ctx);                          /* reset bit reader                 */
FUN_10001040(ctx, buf, *(short*)(ctx+0x474));/* set input = 110 bytes           */
FUN_1000f640(ctx[10], ctx, ctx[0x475]);      /* decode -> ctx+0x11D4 (int16 PCM) */
```

So:

* **length field** `+0x11D0` (`u16`) = 110 = the whole block; set by `ELQDecode` from
  sub-header byte `0x13` (sign-extended).
* **key field** `+0x11E4` (`u8`) = `0x6D`; set by `ELQDecode` from sub-header byte `0x1B`.
* The mask is applied to the **whole 110-byte block, in place**, before bit-unpacking.

**Empirically confirmed**: decoding any block with key `0x6D` yields well-formed speech, while
key `0x00` or `0xFF` makes the decoder read a malformed mode/field and crash
(§10). `0x6D` is just `cookie & 0xFF` for this file, so the whole DB uses one constant key.

Consequence: a re-implementation must do `block[i] ^= 0x6D` for `i in range(110)` (or XOR with
`(cookie & 0xFF)` for a generic file) before parsing.

---

## 6. Decode pipeline

### 6.1 `ELQDecode` and the streaming wrapper

`ELQDecode(ctx, io, binHandle, maxSamples, pcmOut)` (VA `0x10004530`):

1. validate args;
2. if the sub-header cache is invalid, read it (see §4) and set the XOR fields;
3. else `io += ctx->0x34` (509 for 32 kHz);
4. loop calling `FUN_10004340(ctx, &outPtr, &samplePos, maxSamples, binHandle)` until it reports
   nothing left to do.

`FUN_10004340` is the frame-streaming wrapper (analogue of the older build's `FUN_10001170`).
For frame index `n = samplePos / samplesPerFrame`:

* `n == ctx->curFrame(0x11DC)` → copy the remaining samples out of the cached output buffer;
* `n == ctx->curFrame + 1` → advance (`FUN_100042f0` = copy output→previous), read the block with
  `ELQBinGetBuffer(bin, bytesPerFrame*n + 28 + ctx->streamOffset, bytesPerFrame, 1, 0, &flag)`,
  run `FUN_10004290` (XOR + decode) and cache it; if `flag` says out of range, emit zeros;
* otherwise (random seek) → `FUN_10004230` (reset), then decode blocks
  `max(0, n-6) .. n` in order so the codec state (LPC memory, adaptive codebook) matches the
  target, then copy the requested samples.

This is why the decoder is *stateful*: a block cannot be decoded in isolation unless the previous
~6 blocks were decoded first (mode + filter memory).

### 6.2 `FUN_1000f640` — top of the DSP, float→int16

`FUN_1000f640(decObj, ctx, int16 *out)`:

```c
FUN_1000f550(decObj);                       /* decObj->vtbl[+0x30] = FUN_1000f0e0, pre-frame init */
r = (*(decObj->vtbl[+0x28]))(decObj, ctx, floatbuf, 3, ...);   /* FUN_1000e170 */
for (i = 0; i < count; i++) {                /* count is returned in a stack slot */
    double v = floatbuf[i];
    if (v >  32767.0) out[i] =  32767;                 /* _DAT_10023658 = 32767.0 */
    else if (v < -32768.0) out[i] = -32768;            /* _DAT_1002364c = -32768.0 */
    else out[i] = (int16)(v + 0.5);                    /* rounds via a CRT float->int helper */
}
```

Constants: `_DAT_10023658` = `32767.0` and `_DAT_1002364c` = `-32768.0` are **doubles**
(`0x10023658`, `0x1002364c`).

### 6.3 Bit reader (MSB-first)

Ported verbatim:

| VA | function | semantics |
|---|---|---|
| `0x10001020` | reset | `buf[0]=0; total=byte=bit=err=0` |
| `0x10001040` | set input | copies `n` bytes into the internal buffer, `total_bits = 8n`, `byte=bit=0` |
| `0x100011d0` | `read(n)` | MSB-first read of `n` bits; sets `err` on overrun and returns 0 |
| `0x10001240` | `peek1()` | one bit **without consuming it** (it only tests availability) |
| `0x10001280` | `skip(n)` | advance `n` bits |
| `0x100012c0` | `bits_left()` | `total_bits - 8*byte - bit` (or −1 on error) |

### 6.4 Frame header / mode

Cross-references: this is a **layered sub-band CELP**. `FUN_1000f640` calls
`decObj->vtbl[+0x28]` = `FUN_1000e170` for the 32 kHz object; `FUN_1000e170` in turn drives the
16 kHz object (`decObj[+0x04]`) and, below it, the 8 kHz core `FUN_10009520`. Bit order is
therefore **8 kHz core first, then the 16 kHz band, then the 32 kHz refinement**.

**Mode selection.** The 8 kHz core (`FUN_10009520`) reads

```
wideband_flag = read1()          ; observed 0 in every Jorge frame
mode8         = read(4)          ; observed 7 in every Jorge frame
```

The 16/32 kHz driver `FUN_1000e170` reads

```
f = read1(); if (f) { skip(1); m = read(3) }   /* 32 kHz: m = 1 (band table 0x10023cd0) */
if (m != 0 && modeArray[m] == 0) log("Invalid mode encountered: corrupted stream?"); return -2
```

`modeArray` for 32 kHz is `0x10023cd0` = `[0, 0x10023a70, 0, 0, …]`, so **m = 1** is the only
valid coded mode; m = 0 selects the "no new data" concealment path.
The 8 kHz mode table (indexed by `mode8` = 7) is the 8-entry array at `0x100239ec/0x100239f0`
whose mode-7 object is `0x100238f8` (5-stage LSF decoder `0x1000b510`, 3-tap pitch `0x10006bb0`
with descriptor `0x100237e4`, segmented codebook `0x100029c0` with descriptor `0x10023834`).

### 6.4.1 Exact bit-field layout (verified)

A live trace of the real decoder's bit-reader calls for one frame gives the complete sequence of
field widths below.  The parser in `tools/codec210.py` reproduces this and consumes **all 880
bits** of the 110-byte block with no overrun, for every frame tested.

| # | field | width | call site | meaning |
|---|---|---|---|---|
| 8 kHz core (`FUN_10009520`) | | | | |
| 1 | wideband flag | 1 | `0x100095aa` | 0 = narrowband core |
| 2 | mode8 | 4 | `0x10009677` | 7 |
| 3-7 | LSF stage indices | 5 × 6 | `0x1000b54e/b64a/b6d2/b75a/b7e4` | 5-stage order-10 VQ (`FUN_1000B510`) |
| 8 | **frame energy** | 5 | `0x1000999b` | drives the frame gain (§6.6) |
| 9-… | ×4 sub-frames: | | | |
| | pitch index | 7 | `0x10006bdd` | 3-tap LTP gain table index |
| | pitch lag | 7 | `0x10006bf1` | integer lag |
| | extra | 3 | `0x10009d18` | |
| | codebook indices | 16 × 6 | `0x10002a56` | segmented innovation (`FUN_100029C0`) |
| 16 kHz band (`FUN_1000e170` 16 kHz object) | | | | |
| | skip | 0 | `0x1000e228` | |
| | flag | 1 | `0x1000e237` | 1 |
| | mode | 3 | `0x1000e23f` | (3 or 4 observed) |
| | LSF indices | 2 × 6 | `0x1000c118/c1d5` | 2-stage order-8 VQ (`FUN_1000C0D0`) |
| | ×4 sub-frames: | | | |
| | sub-frame gain | 4 | `0x1000e679` | 4-bit gain index (0..15) |
| | innovation | 10 × (1 sign + 7 index) | `0x10002a33` / `0x10002a56` | 10 × 8-sample vectors = 80 samples |
| 32 kHz refinement | | | | |
| | skip | 0 | `0x1000e228` | |
| | flag | 1 | `0x1000e237` | 1 |
| | mode | 3 | `0x1000e23f` | 1 |
| | LSF indices | 2 × 6 | `0x1000c118/c1d5` | 2-stage order-8 VQ |
| | refinement | 4 × 5 | `0x1000e5e6` | |

Total: 40 + 4·113 + 16 + 4·84 + 16 + 20 = **880 bits = 110 bytes exactly**.

### 6.5 Spectral (LPC/LSF) stage — verified

* **LPC order 8** at 32/16 kHz (`decObj[+0x18]`, from sub-descriptor `0x10023ca8[+0x0C]`;
  *not* the file-header `Rank=10`); order 10 in the 8 kHz core.
* **LSF dequantisers.** Two of them, both fully recovered and checked against the decoder's own
  LSF arrays:
  * 8 kHz core, `FUN_1000B510`, order 10, 5 stages:
    `lsf[i] = ramp10[i] + s1[i1][i]/256 + s2lo[i2][i]/512 + s3lo[i3][i]/1024` for `i < 5`, and
    `+ s2hi[i4][i-5]/512 + s3hi[i5][i-5]/1024` for `i >= 5`, with the table set
    `0x10022e60 (64×10), 0x100230e0, 0x10023220, 0x10023360, 0x100234a0 (64×5 each)` and
    `ramp10[i] = 0.25·(i+1)`.
  * 16/32 kHz band, `FUN_1000C0D0`, order 8, 2 stages:
    `lsf[i] = ramp8[i] + t1[i1][i]/256 + t2[i2][i]/512`, tables `0x10022870` / `0x10022a70`
    (64×8 each), `ramp8[i] = 0.75 + 0.3125·i`.
  The ramps were recovered by requiring the residual to be exactly linear; the reconstruction
  then matches the decoder's arrays to float precision on every frame tested.
* **LSF → LPC** (`FUN_10005080`) — standard P/Q sum/difference:
  `P(z) = (1+z⁻¹)·Π_{even i}(1 − 2cos(w_i)z⁻¹ + z⁻²)`, `Q(z) = (1−z⁻¹)·Π_{odd i}(…)`,
  `A(z) = ½(P(z)+Q(z))`. The LSF array holds **radians in (0,π)**; `FUN_10004af0` is literally
  `cos` (double constants `0x10022e18` = π, `0x10022e40` = π/2), and `2.0` at `0x10022e58` is
  the recurrence factor. **Verified**: the port reproduces the decoder's `obj+0x58` coefficient
  array (e.g. `[1.2427, 1.0604, 0.5535, 0.3029, 0.719, 0.723, 0.4204, 0.13]`) exactly.
* Between sub-frames the LSF is interpolated (`FUN_10005520`, `prev·(1−t) + cur·t`,
  `t = (sf+1)/nsubf`) and stabilised (`FUN_10005390`, minimum spacing `0.05`).
* Synthesis is a direct-form all-pole filter (`FUN_100030e0` / `FUN_10002f80`), with bandwidth
  expansion (`FUN_10002cc0`, factors `mode[0x30/0x34/0x38]`).

`FUN_100047c0` (Levinson-Durbin, regulariser `0.003`) and `FUN_10004a00` (autocorrelation, noise
floor `10.0`) belong to the encoder-side helpers; `FUN_10004b80`/`FUN_10004cb0` are the LPC→LSF
analysis direction.

### 6.6 Excitation / gains / synthesis

**Architecture.** Two 64-tap QMF/polyphase filters `FUN_10003960` (coefficient tables
`0x100240a8` and `0x100241a8`, an exact quadrature pair — identical magnitudes, sign-alternating
taps) split/recombine the signal.  **Verified** final combine (`FUN_1000c290`):
`out[i] = clamp(round(2·(A[i] − B[i])))` (factor `2.0` at `0x10022e58`; clamps `32767.0` /
`−32768.0` at `0x10023658` / `0x1002364c`) where `A` = the 32 kHz object's `obj+0x38` buffer and
`B` = `obj+0x3C`, each **640 floats**.  A direct read of those two buffers reproduces the real
decoder's 640 output samples with correlation **1.000000**.  The port cannot yet construct `A`/`B`
(§10.2), so it substitutes a direct wideband LPC synthesis of the 32 kHz band with 2×
interpolation.

**Frame energy.** The 5-bit field read at `0x1000999b` right after the 8 kHz LSF is the frame's
transmitted energy/gain index.  It correlates 1:1 with the reference decoder's output level
(`g8 = 0` → RMS ≈ 1.5; `g8 = 27` → RMS ≈ 4900), i.e. the log-gain quantiser is at the *frame*
level, while the 4-bit per-sub-frame index only moderates it.

**Adaptive codebook (pitch).** `FUN_10006bb0(hist, baseLag, _, _, pitchDesc, blockLen, pOutLag,
gains, bitreader, _, normFlag, normCond, normLimit, mul)`, blockLen = 40:

```
lagDelta = read(7)                     ; pitchDesc[2] = bits_lag
lag      = lagDelta + baseLag          ; baseLag = 0x11 (17) for the 8 kHz core
idx      = read(7)                     ; pitchDesc[1] = bits_idx
g0 = int8[tbl + 3*idx    ] / 64 + 0.5  ; tbl = pitchDesc[0] = 0x10022150, scale 1/64 = _DAT_100235e8
g1 = int8[tbl + 3*idx + 1] / 64 + 0.5
g2 = int8[tbl + 3*idx + 2] / 64 + 0.5
if normFlag and normCond < lag:        ; optional gain normalisation
    if normLimit > 0.95: normLimit = 0.95
    limit |g0|+|g1|+|g2| (negatives scaled by _DAT_10022148) to <= normLimit
outLag = lag
```

The synthesis is a **3-tap integer-lag LTP** applied in place over the history `h` (`param_1`),
reading the three samples behind the lag (zero outside the valid range):

```
for i in 0..blockLen-1:
    out[i] = g2*h[i-lag-1] + g1*h[i-lag] + g0*h[i-lag+1] + eps     ; eps = _DAT_10023618
```

i.e. `h[-lag-1..-lag+1]` are the three taps, so `h` points into a ring that already holds at least
`lag+1` samples of the previous synthesis output.  The three tap buffers are materialised
(`local_c[0..2]`) before the in-place write, which is why the function copies the history first.

**Fixed codebook.** `FUN_100029c0` — segmented vector codebook (see §6.4.1); the 8 kHz core calls it
**twice** per sub-frame with descriptor `0x10023834` = `{dim 5, count 8, table 0x10021bd8, bits 6,
sign 0}` (no sign bits → 8 indices of 6 bits per call, 16 total = 40 samples of excitation), each
followed by `FUN_10002da0` scaling.

**Gain.** The real per-sub-frame dequantiser is hidden behind MSVC floating-point helper mangling
in the decompilation (`FUN_10011aec` = the 4-bit/5-bit index dequantiser).  This is the one stage
that had to be **fitted** rather than ported: the port uses `gain = A·B^g8 · sub[gidx]` with
`A = 2.82843`, `B = 1.30` and a 16-entry `sub[]` refinement, obtained by least-squares fitting of
the port's output RMS to reference PCM from the real DLL over frames 0..199.

**Concealment / mode 0.** `FUN_1000def0` synthesises a whole frame of uniform noise
(`FUN_100072a0` = LCG `s = s·0x19660D + 0x3C6EF35F`) through the LPC and band filters; it is used
when the mode array entry is null ("no new data").  `FUN_1000e8f0` is the decoder control entry
(mode index, post-filter on/off, reset).


---

## 7. Tables

`tools/codec210_tables.json` (regenerate with `tools/codec210_extract.py`) contains, for every
entry, both its VA and its file offset:

* `plugin_dispatch_table` — the 8 `{name, func}` entries at `0x1002e028`;
* `util_symbols` — the 5 `{name, slot}` entries at `0x1002e000`;
* `vtables` — the 8/16/32 kHz class descriptors `0x1002393c`, `0x10023ab4`, `0x10023b2c`
  (24 pointer slots each) with the rate index and sub-block count;
* `class_substructures` — the sub-descriptors `0x10023ca8` / `0x10023bf8`, the band descriptors
  `0x10023a70` / `0x10023a90` and the mode arrays `0x10023cd0` / `0x10023c38`;
* `mode_table_32k` / `mode_objects` — the 8 mode objects `0x100236b8 … 0x10023970`;
* `codebooks` — every int8 DSP codebook with its full contents:
  * LSF VQ: `0x10022e60` (64×10, ×1/256), `0x100230e0` (64×5, ×1/512), `0x10023220` (64×5, ×1/1024),
    `0x10023360` (64×5, ×1/512), `0x100234a0` (64×5, ×1/1024), `0x10022870` / `0x10022a70` (64×8,
    ×1/256 and ×1/512);
  * innovation: `0x10021278` (16×10), `0x10021318` (32×10), `0x10021458` (32×20),
    `0x10021bd8` (64×5), `0x100216d8` (256×5), `0x10021d18` (256×8);
  * pitch 3-tap gains (×1/64, +0.5): `0x100222d0`, `0x10022150`, `0x10022330`, `0x10022470`;
* `band_filters_qmf` — the 64-float QMF pair `0x100240a8` / `0x100241a8`;
* `fixed_codebook_descriptors` (`0x10023708`, `0x1002376c`, `0x100237d0`, `0x10023834`,
  `0x1002388c`, `0x100238e4`) and `pitch_descriptors` (`0x100236fc`, `0x1002371c`,
  `0x100237c4`, `0x100237e4`), each 8 dwords `{dim, count, table, bits/index, sign-flag, …}`;
* `referenced_globals` — all 452 `_DAT_/DAT_` globals referenced by the codec, each given as
  `u32`/`i32`/`f32`/`f64`;
* `annotations` — the constants whose *type* matters (the `.rdata` block at
  `0x10022exx`/`0x1002127x` is **doubles**, at `0x10023exx`/`0x10024xxx` **floats**).

There are **no runtime-generated DSP tables**: everything the decoder needs is static `.rdata`
(the mode arrays are static pointer tables into the class descriptors).  The only runtime-built
state is the 0x74-byte decoder instance (§3.2) and its `calloc`'d float buffers.

---

## 8. Msx comparison (summary)

`LTTS7CodecMsx.dll` (Jorge build, MD5 `bcb605086bbdc213a0a936823c73c54d`) has the **same plugin
shape** — a single named export that is a name→pointer dispatcher over an 8-entry `{name,func}`
table with the same eight names in the same order (`LoadUtilSymbols` first). Differences:

* dispatcher RVA `0x2A90` / table VA `0x10015ae0` (210: `0x4760` / `0x1002e028`);
* larger, different context; the streaming-header fields sit at different offsets
  (rate/byte/sample fields around `+0x11D0..+0x11D4`, XOR key at `+0x47A`, and a pointer to a
  separate bit-layout sub-object at `+0x11EC`);
* it exposes sub-band (narrow/wide/ultra-wideband) mode-query strings;
* it does **not** use the 28-byte 210 sub-header: its per-frame byte length comes from the main
  0x7C container header (`+0x10`) and its XOR key from `ctx+0x47A`.

Msx is therefore *not* bit-compatible with 210; both are independently addressable members of the
same plugin family. (Jorge `LTTS7CodecMsx.dll` is a *different, newer* binary than the older
`engine_re/LTTS7CodecMsx.dll`; the REPORT.md Msx column predates it.)

---

## 9. Validation protocol (oracle)

`tools/codec210_oracle.py` maps `LTTS7Codec210.dll` into Unicorn, fills the five Util slots with
Python implementations of `ELQmalloc`/`ELQfree`/`ELQLogWrite`/`ELQBinGetBuffer`/`ELQstricmp`, maps
a TEB/page 0 for the MSVC SEH prologues, replaces the CRT allocator entry points
(`0x100071e0`, `0x10011111`, `0x10011151`, `0x100071f0`, `0x1001136c`, `0x10007200`) with a Python
allocator (their SEH prologues do not emulate), and sets `FPCW = 0x037F` (Unicorn starts with all
x87 exceptions unmasked, which makes the MSVC math helpers raise). It then

1. calls `ELQOpenDecoder(&ctx, 32000, 0)`,
2. calls the reset routine `FUN_10004230(ctx)` to build the decoder object,
3. per frame: copies 110 raw bytes into a buffer and calls the register-based driver
   `FUN_10004290` with `ESI = ctx`, `EDI = buffer`,
4. reads 640 `int16` from `ctx+0x11D4`.

Reference RMS (Jorge DB, frames 0..199, per 10 frames): frames 0–29 ≈ 2 (silence), then
2 200–3 900 (speech) — a plausible envelope. Decoding the same block with the XOR key forced to
`0x00` or `0xFF` produces an illegal mode and crashes, confirming key `0x6D`.

---

## 10. Porting status of `tools/codec210.py`

| stage | status | evidence |
|---|---|---|
| container header + TLV parsing | **ported & verified** | matches ELQBinContainer facts; size identity exact |
| sub-header (7 BE u32) parse | **ported & verified** | vs `ELQDecode` disasm |
| block extraction (`150 + 110*i`) | **ported & verified** | `ELQBinGetBuffer` offset math |
| per-block XOR (`^ cookie&0xFF`) | **ported & verified** | oracle A/B: key `0x6D` decodes, `0x00`/`0xFF` crash |
| MSB-first bit reader (+ `peek1` = `FUN_10001240`) | **ported & verified** | 1:1 with `FUN_100011d0`/`0x10001240`/`0x10001280`/`0x100012c0` |
| frame bit-field layout (§6.4.1) | **ported & verified** | consumes 880/880 bits, `err == 0`, every frame |
| LSF VQ (order 10 / order 8) | **ported & verified** | reproduces the decoder's LSF arrays exactly |
| LSF interpolation / stabilisation (`FUN_10005520` / `0x10005390`) | **ported** | verbatim from the decompilation |
| LSF → LPC | **ported & verified** | reproduces the decoder's `obj+0x58` coefficients exactly |
| LPC synthesis (`FUN_100030e0`, transposed DF-II) | **ported** | verbatim from the decompilation |
| segmented fixed codebook (`FUN_100029c0`) | **ported** | descriptor `0x10023a5c` = {dim 8, count 5, bits 7, sign} for the 16 kHz band; `0x10023834` = {dim 5, count 8, bits 6, no sign} for the 8 kHz core |
| final combine (`FUN_1000c290`) | **verified** | `out = clamp(round(2·(A−B)))`, corr 1.000000 vs the real DLL |
| frame energy / sub-frame gain | **speculative (fitted)** | `A·B^g8` fitted to reference PCM; real dequantiser hidden behind FP-helper mangling |
| band filter `FUN_10003960` | **ported & verified** | polyphase 2× QMF; reproduces the real DLL's output with corr 1.000000 on all four calls of frame 37 |
| sub-band cascade / excitation wiring | **not ported** | ring window + noise/coded excitation of each level (§10.2) |
| 3-tap pitch / adaptive codebook | **not ported** | structure documented from `FUN_10006bb0` |

The decoder returns a `stages` dict in its trace marking each of these explicitly.

### 10.1 Prototype results (acceptance evidence)

`python3 tools/codec210.py` decodes real blocks from
`Jorge.32000.LTTS7Codec210.44000.10.bin`, returns exactly 640 int16 per block without exception,
and prints RMS per 10 frames.  Compared with reference PCM produced by the real DLL
(`tools/codec210_oracle.py`):

| frames | this port | reference DLL |
|---|---|---|
| 0–9 | 1.5 | 2.0 |
| 10–19 | 1.6 | 1.6 |
| 20–29 | 1.9 | 1.7 |
| 30–39 | 1428 | 2237 |
| 40–49 | 2865 | 2985 |
| 50–59 | 4200 | 2797 |
| 100000–100009 | 2384 | 2118 |
| 100010–100019 | 1854 | 2567 |

The silence→speech transition and the energy envelope are reproduced to within about 2×.

### 10.2 Waveform accuracy — correlation 0.51 (target 0.9 not yet reached)

After the 8 kHz chain was completed (exact LTP + the clear→LTP→CB1→CB2 accumulation with the
measured gain law `C(g8)·q[b3]`), the end-to-end correlation against the real DLL rose from **−0.05
to +0.51** over frames 0..119, with the energy envelope tracking the reference closely (port 1.5 /
1823 / 2223 / 3400 / 3556 / 2108 versus reference 1.8 / 1582 / 2893 / 3125 / 3163 / 2699 per
20-frame block).  The remaining gap is the two unported upper bands:

* **B32 — the 32 kHz noise branch** (`read(5)` + its dequantiser + noise source + ramp
  `_DAT_100242f8` + LPC-tilt gain): ≈13 % of A32 on voiced frames.
* **the 16 kHz coded branch** (`read(4)` + 2 × codebook, descriptor `0x10023a5c`).

`tools/codec210.py` currently computes `out = clamp(round(2·A32))` with B32 omitted, so those two
branches are the whole remaining error.  Everything below them is exact or measured (§10.3, §10.6);
the write-region map needed to port them is in §10.7.

(Historical note: before the 8 kHz chain was completed the port measured an overall correlation of 0.006 over frames 37..42; those numbers are superseded by the table in §10.6.)

### 10.3 Per-stage validation table (measured against the real DLL)

Every stage below was measured with the oracle, feeding **the real decoder's own buffers** into the
Python implementation where a stage is a pure function.  This localises exactly where the chain
breaks.

| stage | test | measured |
|---|---|---|
| bit reader + frame parse | bits consumed / error flag | 880/880, `err=0` — exact |
| LSF VQ (order 10 / 8) | vs the decoder's own LSF arrays | exact (float) |
| LSF → LPC | vs the decoder's own `obj+0x58` | exact (float) |
| **band filter `FUN_10003960`** | oracle `src`/`tail` → oracle `dst` | **corr 1.000000** (4/4 calls, max abs diff ~5e-4) |
| **output combine** | oracle `obj+0x38`/`obj+0x3C` → reference PCM | **corr 1.000000** |
| 16 kHz filter input | oracle `o16+0x2C[:160]` vs oracle `o8+0x30[:160]` | corr **1.0000** — the 16 kHz A-filter input *is* the 8 kHz core synthesis output |
| 32 kHz filter input | oracle `obj32+0x2C[:320]` vs oracle `A16` | corr 0.958 (f37) / 0.998 (f38) — the ring copy is near-exact |
| A-path contribution | `2·A32` vs reference PCM | corr 0.991 (f37) / 0.9997 (f38) — B is small on voiced frames |
| 8 kHz excitation (first unported stage) | oracle excitation vs oracle pitch-output buffer | corr **1.0000**, ratio 1.0 — **the 8 kHz excitation *is* the LTP (pitch) output**; the two `FUN_100029c0` passes write to separate scratch buffers and are not added to it |
| LTP reproduction | my 3-tap LTP from the buffer preceding `h` vs oracle pitch output | corr **0.39–0.69** |
| LTP free fit | optimal 3-tap least squares over all (lag, tap-offset) pairs | only **0.57–0.61** |
| LTP single-tap scan | best single delayed tap over ±1500 samples | only **0.69** |
| LTP window search | best-matching 40-sample window anywhere in `0x3000e000..0x30013000` | corr **0.58** |
| full port | my PCM vs reference PCM | corr **0.006** |

**Where the chain breaks.** The cascade is
`8 kHz core synthesis (o8+0x30) → A16 = band_filter(...) → A32 = band_filter(...) → out = 2·(A32 − B32)`
and everything from the 8 kHz synthesis output upwards is exact and validated.  The **first unported
stage is the 8 kHz core LTP** (`FUN_10006bb0`), characterised as follows:

* **the 8 kHz excitation *is* the LTP output** — the oracle's `LPCsynth` input (`0x30011ea0 + 40·sf`)
  equals the buffer the pitch writes (`o8+0x3C + 40·sf`) with correlation **1.0000** and ratio 1.0.
  The two `FUN_100029c0` passes (descriptor `0x10023834` = dim 5, count 8, bits 6, no sign, table
  `0x10021bd8`) write to *separate* scratch buffers and are **not** added to the excitation;
* complete argument list (frame 38, captured from the oracle):
  `(0x30012364+40·sf, 17, 144, 0, 0x100237e4, 40, &stack, &stack, ctx, 0x3000e0a4, 0, 40·sf,
  0x4002e000, 0)` — arg1 = history/output base, arg2 = base lag (17), arg5 = pitch descriptor,
  arg6 = block length (40), arg9 = bit reader, arg10 = 120-float scratch (inside `o8+0x2C`),
  arg13 = the normalisation limit (2.04, clamped to 0.95), arg14 = 0 (so the gain table base is
  exactly `0x10022150`);
* bit fields in order: `lagDelta = read(7)`, `idx = read(7)`; `lag = lagDelta + 17`;
  gains `g0,g1,g2 = int8[0x10022150 + 3·idx + k]/64 + 0.5` (the table is 128×3 = 384 bytes — the
  extractor originally truncated it to 96).  Normalisation (`Σ|g| ≤ 0.95`) is gated on
  `arg11 != 0`, which is **0 for every sub-frame**, so it never fires;
* the disassembly confirms the three taps: three delayed windows of `arg1` are copied into the
  scratch slots (`local_c[k] = arg10 + k·40` floats) and combined as
  `out[i] = g2·h[i−lag−1] + g1·h[i−lag] + g0·h[i−lag+1] + 1e-15`;
* **unresolved contradiction**: implementing exactly that (with `h` = the buffer immediately
  preceding `0x30012364`, i.e. `o8+0x38` + the earlier sub-frames' LTP output) gives only
  corr 0.39–0.69, and a *free* 3-tap least-squares fit over all (lag, tap-offset) pairs reaches
  only 0.57–0.61; a single-tap scan over ±1500 samples peaks at 0.69; and **no** 40-sample window
  anywhere in the 8 kHz object's heap region (`0x3000e000..0x30013000`) matches the LTP output
  (best |corr| 0.58).  Since the code's own formula is optimal-but-failing, the **history signal
  supplied to `arg1` is not the excitation/ring I am reading** — i.e. the buffer at `o8+0x38`
  (160 floats immediately before the LTP output) is not the running excitation history that the
  caller maintains.  Note that at frame 37 sub-frame 0 that region held only ~1-magnitude values
  while frames 30–36 were already voiced, which supports this.  Locating the true history buffer
  (and how the caller primes it at `o8+0x38`) is the single remaining unknown.

**Concrete remaining work to reach correlation ≥ 0.9**

1. Find and reproduce the **history buffer handed to `FUN_10006bb0` as arg1** (the LTP ring).  The
   scratch slots are known (`arg10 = o8+0x2C + 33` floats, 3×40), the taps and gains are known, so
   only the ring's memory and its per-frame priming are missing.  Validate against the oracle's
   LTP-output buffer (`o8+0x3C + 40·sf`, 40 floats) across frames 0..40 — target corr ≥ 0.99.
2. Then the **32 kHz noise excitation** (`read(5)`, `FUN_10011aec`, `FUN_10002ec0`, ramp
   `_DAT_100242f8`, `_DAT_100242a8 = √2`, tilt normaliser) which feeds B32.
3. Then the **16 kHz coded branch** (`read(4)` + `FUN_100029c0` twice, descriptor `0x10023a5c`).
4. Replace the fitted frame-energy map with the exact dequantiser; carry state from frame 0.

Because the A path is exact above the 8 kHz LTP and A dominates the output
(`corr(2·A32, out) = 0.991`), item 1 alone should lift the overall correlation to roughly the
0.9 threshold; items 2–4 close the rest.

### 10.4 The two "gain" helpers are not codec functions

Disassembling the two helpers that the decompilation attributes the innovation gain to:

* **`FUN_10002ec0(ptr, n)` IS a plain energy**: `fldz;` then `fld [p]; fmulp st,st; fadd` over `n`
  floats — i.e. `Σ p[i]²`.  It is exact and can be ported directly (`fadd [esp+8]` accumulates into
  a float, unrolled by 4).
* **`FUN_10011aec` is an MSVC CRT intrinsic dispatcher, not a dequantiser**: its body is
  `cmp ds:0x100300cc,0; stmxcsr; and eax,0x1f80; ... fnstcw ...; jmp 0x100175d0`
  (or `mov edx,0x1002e7da; jmp 0x10017ade/0x10017cb1`), i.e. the standard `__cintrindisp` wrapper
  that selects an x87/SSE path for an intrinsic (a conversion or math helper).  It therefore cannot
  be "ported" as a gain law; the gain arithmetic must be read from the **call site inside
  `FUN_10009520`** (the 8 kHz core), where the 5-bit/4-bit index is consumed.

Consequently the innovation gain in `tools/codec210.py` is still the fitted
`exc_scale * 0.431*1.3304^g8 * q[b3] / gden` (with the 8-entry `q` table measured from the
`FUN_10002da0` scale arguments and `gden` the LPC-tilt normaliser).  The exact replacement is:
read the gain arithmetic at the `FUN_10009520` call site, using `FUN_10002ec0` (now identified as
`Σ x²`) for the energy term, and delete the fitted constants.

### 10.5 Final state after implementing the exact 8 kHz LTP

`tools/codec210.py` now implements the decode chain end to end:

```
parse 880-bit frame -> 8 kHz excitation (LTP + innovation) -> 8 kHz LPC
synthesis -> A16 = band_filter(..., coefA) -> A32 = band_filter(..., coefA)
-> out = clamp(round(2*A32))            [B32, the 32 kHz noise branch, omitted]
```

* **8 kHz LTP — EXACT**: `buf[0:145] = buf[160:305]` per frame (the `0x100096fc`
  memmove), then per sub-frame `S = buf[p-(lag+1) : +120]`,
  `out[i] = g[2]*S[i] + g[1]*S[40+i] + g[0]*S[80+i]`,
  `lag = read(7)+17`, `g[k] = int8[0x10022150+3*idx+k]/64+0.5`, `idx = read(7)`.
  Verified by the project owner with zero residual on 12/12 calls.
* **8 kHz innovation — STRUCTURE ported, gains FITTED**: the excitation is
  `LTP + gain*CB1 + (gain/2.2)*CB2` with `CB1/CB2` = two `FUN_100029c0` passes
  (descriptor `0x10023834` = dim 5, count 8, bits 6, no sign, table
  `0x10021bd8`) — the two-block split of the 16 sub-frame indices is confirmed
  by the measured scale-call arguments (the ratio CB1:CB2 gain is exactly 2.200
  in every sub-frame of every frame measured).  The gain itself is
  `exc_scale * 0.431*1.3304^g8 * q[b3] / gden` with a fitted 8-entry `q` table
  and `exc_scale = 0.5`; `g8` is the 5-bit frame energy, `b3` the 3-bit field and
  `gden` the LPC-tilt normaliser `(Σ(lpc[i]+lpc[i+1]) + 0.01)/(0.01 + Σ(lpc[i+1]−lpc[i]))`.
  The real `FUN_10011aec` (index dequantiser) and `FUN_10002ec0` (energy) are
  **not ported**, so this is the one stage that remains fitted.
* Output RMS envelope (frames 0..59, per 10): `0.0, 0.0, 0.0, 5002, 2239, 1988`
  vs the reference `2.0, 1.6, 1.7, 2237, 2985, 2797` — the silence→speech
  transition and the steady-state level now match closely.
* **End-to-end correlation is still NOT reached**: −0.14 over frames 0..59
  (per-10-frame: −0.09, −0.07, 0.00, −0.08, −0.18, −0.48).  The waveform is not
  reproduced, so the fitted innovation gain is still the blocking stage.

Honest summary of what remains: `FUN_10011aec` (the 4/5-bit innovation index
dequantiser) and `FUN_10002ec0` (the per-sub-frame excitation energy feeding the
gain) must be ported to replace the fitted `q` table and `exc_scale`; then the
32 kHz noise branch (B32) and the 16 kHz coded branch close the chain.

### 10.6 Final state: gain law fixed, correlation 0.51

**Root cause of the divergence found**: the innovation gain is exactly
`gain = C(g8) · q[b3]` with `C(g8) = 0.430 · 1.3305^g8` and
`q = [0.147, 0.382, 0.69, 1.0, 1.30, 1.679, 2.39, 3.098]` — **no per-sub-frame LPC-tilt factor**.
My earlier `gden` term (from the 32 kHz band's decompilation) made the gain negative and 3–15× too
large, which is what blew the adaptive-codebook recursion up by 50×.  With `gden` removed the
codebook RMS comes out at **973 — exactly the measured `FUN_10002da0` result** for frame 38 sf0
(gain 1245.3 × unit codebook RMS 0.782 = 973), and the port's per-sub-frame codebook unit RMS
(0.78–1.12) matches the real one (0.78).

The excitation accumulation is also confirmed against the parent's write timeline: per sub-frame the
8 kHz core clears `buf[h:h+40]`, writes the LTP output, then accumulates CB1 and CB2 into the same
buffer (which doubles as the adaptive-codebook history for the next sub-frame), and the LPC
synthesis then filters it in place.  `tools/codec210.py` reproduces that sequence.

**Codebook mapping validated against the golden dataset** (`jorge_re/exc_stages_frame38.json`, the
per-sub-frame excitation after clear / after LTP / after CB1 / after CB2).  The measured increments
are *exactly* the port's codebook vector times the measured gain:

| sf | CB1 increment[:5] | port codebook[:5] | ratio | CB2 increment[:5] | port codebook[:5] | ratio |
|---|---|---|---|---|---|---|
| 0 | −116.74, −2646.17, 194.57, 1362.0, 272.4 | −0.09, −2.12, 0.16, 1.09, 0.22 | ≈1245 | 17.69, 88.44, −265.32, 866.73, −1167.4 | 0.03, 0.16, −0.47, 1.53, −2.06 | ≈566 |

i.e. the mapping **is** `8 six-bit indices → 8 concatenated 5-sample segments of table 0x10021bd8 ×
(1/32) × gain`, with `gain_CB1 = C(g8)·q[b3]` (1245.3 measured) and `gain_CB2 = gain_CB1/2.2`
(566.0 measured).  The port's own excitation matches the golden vectors at corr 0.66–0.70 (rms
1293 vs 1273 / 524 vs 431 / 3223 vs 3430) — the residual is in the **LTP history** (my per-sub-frame
state differs from the real one), not in the codebook or the gain.

**Output-path amplitude (measured with `exc_scale = 1.0`)** — the scale is exact in the excitation, so
the remaining factor is in the A-path.  Comparing the real 32 kHz buffers with the port:

| frame | rms(A32 real) | rms(B32 real) | rms(2·(A−B)) | rms(port pcm) |
|---|---|---|---|---|
| 37 | 617.5 | 83.2 | 1246.6 | 675.9 |
| 38 | 2382.0 | 53.3 | 4765.1 | 1954.4 |
| 39 | 2539.1 | 30.6 | 5078.5 | 890.9 |

`rms(2·(A−B))` matches the reference PCM (1246.6 vs 1259.7 at frame 37), confirming the combine is
exact, but the port is 1.8× / 2.4× / 5.7× too **small** and the ratio is *not constant* — so the
A-path differs in content, not merely by a gain.  Candidates: the 8 kHz LPC synthesis absolute gain,
a per-stage ½ polyphase gain in the two `band_filter` stages (which would give ¼), or the 16 kHz
branch feeding A16 (the port feeds the 8 kHz synthesis directly).  Because the port's excitation now
matches the golden vectors at corr 0.66–0.70, the residual is the **LTP history propagation** (per
sub-frame state) plus the two unported upper bands.

With `exc_scale = 1.0` the end-to-end correlation is **0.510** over frames 0..119 (identical to the
3.5-scaled run, as expected since the correlation is scale-invariant) with the per-20-frame values
0.39 / 0.55 / 0.47 / 0.59 / 0.48 / 0.47.

| frames | port RMS | reference RMS | correlation |
|---|---|---|---|
| 0–19 | 1.5 | 1.8 | **+0.513** |
| 20–39 | 1823 | 1582 | +0.510 |
| 40–59 | 2223 | 2893 | +0.457 |
| 60–79 | 3400 | 3125 | +0.566 |
| 80–99 | 3556 | 3163 | +0.549 |
| 100–119 | 2108 | 2699 | +0.459 |
| overall | — | — | **+0.513** |

So the energy envelope now tracks the reference closely (the one calibration left is a single global
output-domain factor, `exc_scale = 3.5`, which does not affect the correlation), and the waveform
correlation rose from −0.05 to **+0.51**.  It is still below the 0.9 target: the missing energy is
the **B32 band**, i.e. the 32 kHz noise branch (`read(5)` + dequantiser + ramp `_DAT_100242f8` +
tilt) and the 16 kHz coded branch (`read(4)` + 2 × codebook, descriptor `0x10023a5c`).  Those are the
only two stages left; every stage below them (bit layout, LSF VQ, LSF interp/stabilise, LSF→LPC, the
8 kHz LTP, the 8 kHz innovation and its gain, the LPC synthesis, the A-band QMF chain and the final
combine) is exact or measured.

### 10.7 Write-region map of the 8 kHz core (frame 38) and the path to the last two bands

**The final stage (exact and closed).** `out[i] = clamp(round(2·(A[i] − B[i])))` where `A` = the
32 kHz object's `obj+0x38` and `B` = `obj+0x3C`, both 640 floats — correlation with the reference
output is `1.000000`.  `FUN_10003960` is a polyphase (2×) QMF band filter, ported verbatim as
`band_filter()` and validated (fed the reference decoder's own `src`/`tail` it reproduces its `dst`
with correlation 1.000000, max abs diff ~5e-4, on all four calls of frame 37).  The calls in
`FUN_1000e170` are `A = FUN_10003960(obj+0x2C, 0x100240a8, obj+0x38, obj+8, 0x40, obj+0x40, work)`
and `B = FUN_10003960(obj+0x34, 0x100241a8, obj+0x3C, obj+8, 0x44, work)` with `work = obj+0x28+320`,
immediately followed by `FUN_1000c290(out, obj+0x38, obj+0x3C)`.  The chain is a dyadic
8 kHz → 16 kHz → 32 kHz cascade in which each level fills its `obj+0x2C` from its `obj+0x28` ring
(`obj+0x2C[i] = ring[i]`) and `obj+0x34` with its own band synthesis.

Per-frame write counts by (code address → 256-byte bucket), whole frame = 4 sub-frames × 40 samples:

| code address | buckets written | role |
|---|---|---|
| `0x10009b6f` | `0x30012300/400/500` | clear the excitation sub-block to 0 |
| `0x10009c0d` | same | the LTP call (writes the LTP output) |
| `0x10009f3e` | same | accumulate CB1 |
| `0x10009ff1` | same | accumulate CB2 |
| `0x10009ced` | `0x30012500/600/700` | codebook build: clears the scratch |
| `0x10009d7d` | `0x30012500/600` | codebook build: writes the unit-scale vector |
| `0x10009d9f` | `0x30012500/600` | scale/gain application (`FUN_10002da0`) |
| `0x10007210` | `0x30012100/200/300` | writes the LTP history region |
| `0x1000a075` | `0x30012000/100` | LPC-related |
| `0x1000a14a` | `0x30012000/100` | LPC synthesis call site |

First-writes at `0x10009ced` are 0.00 (clear), at `0x10009d7d` small (0.22, −0.09) and at `0x10009d9f`
the scaled ones (−116.74, 272.40): i.e. the innovation path is exactly
**build in scratch (`0x300125f0+0xa0·k`) → scale by `C(g8)·q[b3]` → accumulate into the excitation**,
with the scratch reused per sub-frame.

Only two stages remain to reach waveform exactness, and they are the whole remaining gap:

1. **32 kHz noise branch** (produces B32, ≈13 % of A32): `read(5)` index + its dequantiser + the noise
   source + the per-sample ramp `_DAT_100242f8` + the LPC-tilt gain (the ratio
   `(obj+0x60[sf] + 0.01)/(0.01 + Σ(lpc[i+1]−lpc[i]))`, the term that must NOT be applied to the
   8 kHz coded branch).
2. **16 kHz coded branch**: `read(4)` + two codebook passes with descriptor `0x10023a5c` =
   `{dim 8, count 5, table 0x10022470, bits 7, sign}` (the 10 (sign, index) pairs per sub-frame are
   already parsed by `codec210.py`).

Method to close each (as used for the 8 kHz core): hook the band's LPC-synthesis call opcode, read the
in-place buffer **before** the callee, and reproduce the per-sample writer sequence
(clear → excitation branch → scale → accumulate); then validate stage-locally (corr ≥ 0.999) and
re-measure end to end.

### 10.8 Superseded composition test (kept for the trail)

The excitation-buffer identification was tested directly.  At the 8 kHz `FUN_100030e0` call
(`0x1000a14f`, frame 38) the arguments are
`(0x30012870 = LPC order-10, 0x30011ea0 = synthesis output, 40, 10, 0x30012930, 0x300082e0,
0x30007fe0, ctx)`.  Solving `exc ≈ a·ltp + b·cb1 + c·cb2` per sub-frame (ltp = `0x30012364+40·k`,
cb1 = `0x300125f0+40·k`, cb2 = `0x3000e0a4`) gives:

| candidate | rms (sf0/1/2/3) | solved (a,b,c) sf0 | residual sf0 |
|---|---|---|---|
| `0x30012930` | 1818 / 341 / 109 / 452 | (−0.32, 0.36, 0.74) | 1.1e4 (vs rms 1818) |
| `0x30007fe0` | 55.6 constant | (−0.01, 0.01, 0.02) | 348 |

So **neither is the excitation**: `0x30012930` varies per sub-frame but is not a 3-term combination
of the LTP and the two codebook outputs (residual ≫ signal), and `0x30007fe0` does not vary at all.
`0x300082e0` is constant across sub-frames and therefore also not the excitation (this supersedes the
earlier note that used it).

The verified facts about this stage are therefore: the LTP formula and its gains (zero residual
against the LTP output buffer, project-owner verified), the two codebook passes and their gain ratio
(CB2/CB1 = 0.4545 = 1/2.2, measured), and `C(g8) = 0.430 · 1.3305^g8` with the 8-entry `q` table
(ratios match measured gains exactly).

**New and decisive measurement**: hooking the *actual* call instruction `call FUN_100030e0` at
`0x1000a14a` (the parent's `0x1000a14a` is the call opcode; the argument list is
`(edi, obj+0x50 = LPC, edi, obj+0x10 = 40, obj+0x18 = 10, obj+0x54 = state)` with `edi` the in-place
buffer) and reading `edi` **before the callee writes** shows that the buffer the LPC synthesis
consumes is **exactly the LTP output**:

| sf | rms(exc) | lstsq `exc = a·ltp + b·cb1 + c·cb2` | residual |
|---|---|---|---|
| 0 | 1272.9 | (1.0, 0, 0) | 3e-12 |
| 1 | 431.2 | (1.0, 0, 0) | 4e-13 |
| 2 | 3429.8 | (1.0, 0, 0) | 2e-11 |
| 3 | 601.5 | (1.0, 0, 0) | 2e-12 |

So the 8 kHz excitation **is** the LTP output, and the innovation is **not** added to it at the LPC
input.  The innovation must therefore prime the adaptive-codebook history *before* the LTP runs (that
is the only way the LTP can start from a zero state).  Locating that priming write is the one
remaining link; everything else in the 8 kHz chain is measured.

**S-comparison gate (the decisive stage-local test)**: comparing the 120-float adaptive-codebook
span `S = buf[h-(lag+1) : +120]` that my port maintains against the real decoder's own span at the
pitch call (frame 38):

| sf | lag | corr(myS, realS) | rms(myS) | rms(realS) |
|---|---|---|---|---|
| 0 | 71 | −0.003 | 70 057 | 1 365 |
| 1 | 66 | −0.045 | 70 779 | 1 530 |
| 2 | 94 | −0.049 | 70 926 | 1 509 |
| 3 | 93 | −0.041 | 119 547 | 2 010 |

My history is ~50× too large and uncorrelated from the very first sub-frame, which is exactly what
the missing innovation priming predicts: the real `S` sits at the excitation scale (1.4–2.0 k, the
same order as the excitation itself), because the innovation (scaled CB output, measured rms 973 at
gain 1245 ⇒ unit rms ≈ 0.78) is folded into the history that the LTP copies, whereas my port keeps a
pure LTP recursion.  A second contributing factor is that my codebook unit scale is larger than the
real 0.78, so even the fitted sum diverges.

**Write-sequence timeline (parent-supplied sites, frame 38)**: hooking the three sites
`0x10009b6f` / `0x10009f3e` / `0x10009ff1` (all with `ebx = 0x30012364`, the excitation base) shows
that `0x30012364` is **cleared sample by sample** at `0x10009b6f` before the passes run (rms 639 →
638 → … with the leading samples going to 0 one at a time), while `0x30011ea0` — the buffer the LPC
synthesis consumes — holds a constant 1458.7 RMS throughout those sites, i.e. it is written later, by
a copy from the excitation base.  Each site carries two gain arguments in its stack frame
(`0x0983…`-style values plus 215.763 at the clear site and 1245.3 / 566.02 / 2.7489 at the others),
so the 8 kHz core **clears the excitation region and then accumulates the codebook passes plus the
LTP into it more than once per sub-frame**.

That is the arrangement my port is missing, and it explains the S-gate failure quantitatively: my
port keeps a pure LTP recursion on its own history (rms ≈ 70 k) where the real history is refreshed
every sub-frame by the cleared-and-rebuilt excitation (rms 1.4–2.0 k).  The remaining work is to
reproduce that clear → CB1 → CB2 → LTP accumulation sequence with the measured gains
(215.763 / 1245.3 / 566.02 as applicable) and then to re-run the S gate; everything else in the 8 kHz
chain is exact.

Measured call-site facts now recorded for the next agent: the 8 kHz core calls `FUN_10002da0` at
`0x10009da4` (×4) and `0x10009fda` (×4) and `FUN_100030e0` at `0x1000a14f` (×4, dst `0x30011ea0`);
the 16 kHz band calls `FUN_10002da0` at `0x1000e70f` and `FUN_100030e0` at `0x1000e84e`
(dst `0x30012f30`).

### 10.9 Investigation trail for the 8 kHz LTP (hypothesis → measurement)

Every entry is a real experiment run against the oracle; none of them reproduced the real LTP.

| # | hypothesis | measured result |
|---|---|---|
| 1 | history = the flat buffer immediately preceding `arg1` (`o8+0x38` + earlier sub-frames' LTP output); taps `g2·h[i−lag−1] + g1·h[i−lag] + g0·h[i−lag+1] + 1e-15` | corr 0.39–0.69 per sub-frame |
| 2 | **free** 3-tap least squares over every (lag 20..380, tap-offset −3..+3, 4 tap patterns) | best 0.57–0.61 (optimal weights still fail ⇒ the input signal is wrong, not the weights) |
| 3 | single delayed tap, scanning lag over ±1500 samples | best 0.69 |
| 4 | any 40-sample window anywhere in the 8 kHz heap region `0x3000e000..0x30013000` | best \|corr\| 0.58 (no window matches ⇒ the LTP output is a genuine filtered signal, not a delayed copy) |
| 5 | running-buffer recursion: `R` = concatenation of **all** LTP outputs of frames 0..40 (160/frame), taps read backwards from the sub-frame start | mean corr 0.43 over 160 sub-frames |
| 6 | in-place recursion within the current sub-frame (parent's hypothesis: taps read already-written samples when `i ≥ lag`) — equivalent to reading the pre-write buffer, which is what experiments 1–2 captured | same as #1/#2; no improvement |
| 7 | history = the **synthesis** buffer (`o8+0x30 = 0x30011ea0`) instead of the LTP output | single tap at the declared lag: −0.14, 0.02, −0.12, −0.02 |

Interpretation: the taps/gains/bit-fields are certainly right (they come straight from the
disassembly and the 14-argument call site is captured in full), and the excitation *is* the LTP
output (corr 1.0000).  A memory-write watchpoint on the LTP history region
(`0x30012000..0x30012364`) during frame 37 shows who fills it:

| writer pc | writes/frame | belongs to |
|---|---|---|
| `0x1001145a` | 290 | CRT `_memcpy`/`_memmove` (bulk copy into the region) |
| `0x1000ab5c` | 144 | `FUN_1000AB30` |
| `0x1000af15` | 144 | `FUN_1000AD40` |

So the 145-float window immediately before the LTP output (`o8+0x38`, `0x30012120`) is **refilled
every frame**.  The ordered event log for frame 37 identifies the mechanism exactly:

```
memmove(dst = 0x30012120, src = 0x300123a0, len = 580)   ; called from 0x100096fc (inside FUN_10009520)
PITCH sf0 (h = 0x30012364)
PITCH sf1 (h = 0x30012404)
PITCH sf2 (h = 0x300124a4)
writes at 0x1000a075 (32) and 0x100031dc (32) into the history window
PITCH sf3 (h = 0x30012544)
writes at 0x1000a075 (40) and 0x100031dc (40)
```

i.e. at the start of every 8 kHz frame the code **shifts 145 floats of the previous frame's LTP
output down into the history window** (`0x300123a0 → 0x30012120`, 580 bytes = 145 floats), which is
exactly the "running excitation buffer with leading history" model: the history is the previous
frame's LTP tail, `maxLag + 1 = 145` samples of it.  `FUN_10009520` (the 8 kHz core, called at
`0x100096fc`) performs the shift, and the window is additionally updated between sub-frames by code
at `0x1000a075` (in the `FUN_1000A230` family) and `0x100031dc` (inside `FUN_100030E0`).

**Numeric gain solve (requested) — does NOT reproduce.**  Reading the three scratch windows the
copy loops fill (`arg10 + k·40`, `arg10 = 0x3000e0a4`) and solving the 40×3 least-squares system
`dest[i] = g0·w0[i] + g1·w1[i] + g2·w2[i]` against the destination `h[0..39]` gives, for frame 38:

| sf | solved (g0,g1,g2) | residual | rms(dest) | table `0x10022150[3·idx]` | table at the other read |
|---|---|---|---|---|---|
| 0 | (0.466, 0.416, −0.984) | 7431 | 1273 | (−0.313, 0.734, 0.750) | (−0.125, 0.766, 0.484) |
| 1 | (0.070, −0.203, 0.272) | 2582 | 431 | (−0.078, −0.047, −0.031) | (0.609, 0.250, 0.156) |
| 2 | (−0.394, −1.299, 0.179) | 21520 | 3430 | (0.609, 0.250, 0.156) | (−0.328, −0.375, −0.094) |
| 3 | (0.701, 0.575, 0.468) | 3121 | 602 | (0.219, 0.391, 0.438) | (−0.063, 0.875, 0.016) |

The residual **exceeds the signal RMS**, so the 3-tap combination of those three windows is not the
model, and none of the table candidates matches the solved gains.  Re-running the solve with the
scratch captured **immediately after each call** (at the next call's entry, so it cannot have been
reused) gives the same verdict — residual 7924 / 2476 / 17950 against signal RMS 1273 / 431 / 3430.
So this is not a measurement artefact: the destination is genuinely not a 3-term linear combination
of the three scratch blocks.

Combined with the read trace this means the **copy loops do not build three shifted tap windows**:
they read **120 consecutive floats** (`h−72 … h+47`, split 30 reads × 4 unrolled instructions) into
the scratch — the span is exactly three contiguous 40-blocks, `h[−72..−33]`, `h[−32..+7]`,
`h[+8..+47]`, i.e. a **linearisation of a circular buffer whose period is ≈120**, and the final FIR
then combines the linearised blocks at offsets that are *not* the `lag−1, lag, lag+1` triple.  The
disassembly of the FIR tail (`0x10006dc0`–`0x10006e20` + the loop after the copies) confirms the
structure (`fld [edx−8] / fstp [eax−0x18]` … block copies, then the 4-accumulator FIR writing
`param_1`), but the exact tap offsets inside the linearised buffer are still not pinned down.

That reframes the remaining unknown: the LTP reads a **circular adaptive-codebook buffer of period
≈120 samples** (the 145-float history shift plus the 160-float per-frame LTP area), linearises it into
three contiguous 40-blocks, and runs a 3-tap FIR over the *linearised* index — with the taps taken at
offsets inside those blocks rather than at `lag−1, lag, lag+1`.  The next step is to single-step the
FIR loop (`0x10006e20` onward) and log the (source address within the scratch, coefficient address)
pairs; that yields the offsets and the coefficient strides directly.

* the function issues **120 reads** into the history/destination region, at 4 instruction
  addresses (`0x10006dc0/0x10006dcf/0x10006dd5/0x10006ddb`), 30 each;
* the addresses start at **`0x30012244 = h − 72` floats** and advance by 4 bytes with a repeating
  +16-byte stride, spanning `h−72 … h+47` (120 floats);
* `h − (lag+1)` with the declared `lag = 54 + 17 = 71` is exactly `h − 72` — so **the lag and the
  three-tap window offsets are confirmed**: the reads are `h[i−lag−1] ... h[i−lag+1]`, i.e. the
  model in §10.3 is right;
* the reads are performed *by the copy loops* into the three scratch slots (`arg10 + k·40`), which is
  why they appear as three 40-sample windows.

So the tap geometry, the lag, the bit-fields and the memory region are all confirmed.  The only
quantity that does not fit is the **gain magnitude**: at `idx = 17` the table yields
`(−0.078, −0.047, −0.031)`, yet the observed output RMS is 431, and a free 3-tap least-squares fit
over those very windows still only reaches 0.57–0.61.  The next measurement (not done here) is to
hook the *exit* of `FUN_10006bb0` and read the three gain floats it stores through `arg8`
(`0x201fe4b8`) — the store instructions are `mov [eax+…],` at the end of the gain computation — and
compare them with `int8[0x10022150 + 3·idx + k]/64 + 0.5`; that single comparison decides whether the
gain index is the first or the second 7-bit read and whether the table base is right.

Candidate causes, in order of likelihood, given everything measured:
(a) the gain **index** is the *first* 7-bit read and the lag delta the second (the widths are both 7
bits, so only the gain values can distinguish them); (b) the gains are read from a shifted table
base; (c) the output buffer that the caller reads is not `h[0..39]` but starts further into the
120-float span (the measured reads reach `h+47`, i.e. past the 40-sample destination).

The per-frame call graph with arguments (captured from the oracle for frame 37) is the map for
this work: 4 sub-frames of `{LSFinterp → LSFstab → LSF2LPC → [pitch] → 2×fixedCB → 2×scale →
LPCsynth}` for the 8 kHz core (order 10, 40 samples/sub-frame), the same with a single fixed-CB
pair for the 16 kHz band (order 8, 40 samples, descriptor `0x10023a5c`), and
`{LSFinterp → LSFstab → LSF2LPC → LPCsynth}` only (order 8, 80 samples, band replication) for the
32 kHz band.
