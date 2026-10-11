# `LOQUENDOTTS7` binary container (`.bin`) — `ELQBin*` layer of `LTTS7Util.dll`

Scope: the container that wraps every Loquendo TTS 7 voice database (`*.bin`) and is opened by the
`ELQBin*` API family in `LTTS7Util.dll`. Primary source: the **Jorge** build
`jorge/pf/Loquendo/LTTS7/bin/LTTS7Util.dll` (551 KiB) — decompiled to
`jorge_re/decomp_util_jorge.txt` (Ghidra headless, image base `0x10000000`) and disassembled with
`objdump -d -Mintel`. Where a claim comes from the **older** `engine_re/LTTS7Util.dll` (266 KiB,
`decomp_util.txt`) it is marked `[old build]`.

Evidence convention: `[decomp <fn> @ <addr>]` = quoted decompiled C, `[asm <addr>]` = quoted instruction
bytes, `[file]` = byte values observed in the shipped files, `[INFERENCE]` = a conclusion drawn from the
above but not directly printed by a tool.

Function-address map used below (Jorge build):

| Jorge | old build | name |
|---|---|---|
| `0x10001f80` | `0x10004ca0` | XOR-deobfuscate `(len, byteKey, ptr)`, reads global `BL` |
| `0x10001f60` | `0x10004c80` | read `u16` (LE) through a NULL-safe pointer |
| `0x10002160` | `0x10004de0` | header probe (`ELQBinaryHeaderIsPresent` workhorse) |
| `0x100022c0` | `0x10004ec0` | `ReadHeader` → `ELQDataDescriptor` |
| `0x10002550` | `0x10005100` | `FUN_10005100` wrapper (probe + version check + ReadHeader) |
| `0x10003510` | `0x10003ca0` | internal open (malloc handle, bind access type) |
| `0x10003960` | `0x100040c0` | exported `ELQBinOpen` (thunk, cache = 1) |
| `0x10003990` | `0x100040f0` | exported `ELQBinOpenNoCache` (thunk, cache = 0) |
| `0x100039c0` | `0x10004120` | `ELQBinClose` |
| `0x10003b00` | `0x10004240` | `ELQBinGetSize` |
| `0x10003b50` | `0x10004290` | `ELQBinInitSmartBuffer` |
| `0x10003b70` | `0x100042b0` | `ELQBinDeleteSmartBuffer` |
| `0x10003ba0` | `0x100042e0` | core get-buffer (`__fastcall`, unit size in `EAX`) |
| `0x10003f10` | `0x100046f0` | `ELQBinGetSmartBufferCore` |
| `0x10003f20` | `0x10004700` | `ELQBinGetSmartBuffer` |
| `0x10003f50` | `0x10004730` | `ELQBinResizeSmartBuffer` |
| `0x10003f90` | `0x10004770` | `ELQBinGetBuffer` |
| `0x10003fc0` | `0x100047a0` | `ELQBinSeek` |
| `0x10003110` | `0x10004820` | `ELQBinGetRawData` |
| `0x10003170` | `0x100048a0` | `ELQBinGetType` |
| `0x10003190` | `0x100048c0` | `ELQBinShell` |
| `0x10003220` | `0x10004930` | `ELQBinCloneEx` |
| `0x10003450` | `0x10004b90` | `ELQBinVirtualOpen` |
| `0x10002dd0` | `0x10003970` | `fopen` + size out-param |
| `0x10002e20` | `0x100039c0` | DiskCache init |
| `0x10002f40`/`0x10003020` | `0x10003ad0`/`0x10003bb0` | DiskCache block read |

The validity tag stored at handle `+0x00` is the address of `ELQBinOpen`, i.e. `0x10003960` in the Jorge
build `[asm 0x10003118: cmp DWORD PTR [eax],0x10003960]` (Ghidra prints it as the symbol `ELQBinOpen`).

---

## 1. File layout

```
file offset  size        content
0x00         1           key byte A          (consumed raw - not decoded first)
0x01         1           key byte B          (consumed raw, "keyish")
0x02         12          ASCII signature  ─┐
0x0E         2           u16 LE format_version ─┤ obfuscated with key K = A^B
0x10         2           u16 LE header_size  ─┤ (the reader XORs the whole [0,hs) block;
0x12         ...         TLV list              ─┘  A and B are read out before that)
header_size  ...         data region — NOT obfuscated (§4)
```

Note the self-consistency of the seed pair: the reader uses `raw[0]` and `raw[1]` as they appear on disk,
so even if the writer applied `K` to them the derived key would be unchanged
(`(a^K)^(b^K) == a^b`); nothing in the reader depends on the decoded values of bytes 0/1.

* 18-byte fixed prefix = bytes `0x00..0x11`; the probe reads exactly `0x12` bytes and only proceeds when
  the requested size was satisfied: `[decomp FUN_10002160 @ 0x10002160]`
  ```c
  if (*(int **)(param_1 + 9) ... )                       /* access type */
  in_EAX = (undefined1 *)FUN_10003ba0((int)param_1,0x12,0,&local_4,(uint *)0x0,&local_9);
  if ((in_EAX != (undefined1 *)0x0) && (local_4 == 0x12)) {
    bVar2 = in_EAX[1];                                   /* key byte B */
    if (unaff_ESI != (undefined1 *)0x0) { *unaff_ESI = *in_EAX; unaff_ESI[1] = bVar2; }
    FUN_10001f80(0x10,bVar2,in_EAX + 2);                 /* XOR 16 bytes: sig+fmt+hdr */
    iVar5 = _strncmp("LOQUENDOTTS7",in_EAX + 2,0xc);
    if (iVar5 == 0) {
      sVar3 = FUN_10001f60((undefined2 *)(in_EAX + 0xe));  /* u16 @0x0E = format_version */
      ...
      sVar4 = FUN_10001f60((undefined2 *)(in_EAX + 0x10)); /* u16 @0x10 = header_size */
  ```
  Note the argument order of the core reader in the Jorge build is `(bin, count, offset, outsize,
  smartbuf, outflag)`: `[asm 0x10002305: movsx edx,WORD PTR [esi+0x2]` (= header_size into `EDX` = count,
  `[asm 0x1000231b: mov eax,0x1` = unit size 1, `[asm 0x10002319: push 0x0` = offset 0.
* `format_version` must be `1`; anything else clears the info struct and the reader logs
  `"ReadHeader: Warning. Header format not supported."`
  `[decomp FUN_10002160]` `if (sVar3 != 1) { FUN_10001fb0(); }` and `[decomp FUN_10002550]`
  ```c
  if (local_10 == 1) { uVar1 = FUN_100022c0((int)unaff_EBX,unaff_EDI,param_1,local_14,param_2); return uVar1; }
  uVar1 = ELQLogWrite(8,param_2,"ReadHeader: Warning. Header format not supported.");
  ```
* Sanity gate: `header_size <= ELQBinGetSize(bin,1)` — `[decomp FUN_10002160]`
  `local_8 = *(undefined1 **)param_1[3];` … `if ((undefined1 *)(int)sVar4 <= local_8)`.

Measured prefixes (raw bytes at offset 0, and the decoded prefix):

| file | byte0 | byte1 | key | fmt | header_size |
|---|---|---|---|---|---|
| `Jorge.32000.LTTS7Codec210.44000.10.bin` | `0x2B` | `0x29` | `0x02` | 1 | 122 (`0x7A`) |
| `JorgeGildedPhrases.32000.…bin` | `0xFC` | `0x80` | `0x7C` | 1 | 148 (`0x94`) |
| `JorgeGildedParalinguistics.32000.…bin` | `0x8B` | `0x69` | `0xE2` | 1 | 164 (`0xA4`) |
| `payload/Ludoviko.16000.linear.256000.10.bin12` | `0xD0` | `0xE9` | `0x39` | 1 | 125 (`0x7D`) |

`[file]` e.g. Jorge raw `2b 29 4e 4d 53 57 47 4c 46 4d 56 56 51 35 03 02 78 02`:
`0x4E^0x02 = 0x4C ('L')` … `0x35^0x02 = 0x37 ('7')`, `0x03^0x02 = 0x01`, `0x02^0x02 = 0x00`,
`0x78^0x02 = 0x7A`, `0x02^0x02 = 0x00`.

---

## 2. Key derivation (settled: `key = file[0] ^ file[1]`)

`FUN_10001f80` really is `ptr[i] ^= <BL at entry> ^ param_2`, with the length in `ECX` and the second
byte-key in `DL` (System V/`__fastcall` register usage):

`[decomp FUN_10001f80 @ 0x10001f80]`
```c
undefined4 __fastcall FUN_10001f80(ushort param_1,byte param_2,byte *param_3)
{
  byte unaff_BL;
  uint uVar1;
  if (0 < (short)param_1) {
    uVar1 = (uint)param_1;
    do {
      *param_3 = *param_3 ^ unaff_BL ^ param_2;     /* key = BL ^ param_2 */
      param_3 = param_3 + 1;
      uVar1 = uVar1 - 1;
    } while (uVar1 != 0);
  }
  return 1;
}
```

**The instruction that supplies `BL` at the call site** — `[asm 0x100021fd..0x10002216]`, inside
`FUN_10002160` (the header probe), immediately around `call 0x10001f80`:

```
100021fd: 8a 07                mov    al,BYTE PTR [edi]        ; AL = file[0]      (EDI = 0x12-byte buffer)
100021ff: 8a 57 01             mov    dl,BYTE PTR [edi+0x1]    ; DL = file[1]
10002202: 3b f3                cmp    esi,ebx
10002204: 74 05                je     0x1000220b
10002206: 88 06                mov    BYTE PTR [esi],al        ; info[0] = file[0]
10002208: 88 56 01             mov    BYTE PTR [esi+0x1],dl    ; info[1] = file[1]
1000220b: 8d 6f 02             lea    ebp,[edi+0x2]            ; arg3 = buffer+2
1000220e: 55                   push   ebp
1000220f: b9 10 00 00 00       mov    ecx,0x10                 ; arg1 = 16 (sig + fmt + header_size)
10002214: 8a d8                mov    bl,al                    ; *** BL = file[0] ***
10002216: e8 65 fd ff ff       call   0x10001f80
```

So `BL = file[0]`, `param_2 = file[1]`, therefore **effective key `K = file[0] ^ file[1]`**, and the 16
bytes at `0x02..0x11` are decoded with `K`. The decompiler view of the same expression, in the *second*
(complete-header) reader, confirms the two key bytes come from the probed info struct
`[decomp FUN_100022c0 @ 0x100022c0]`:
```c
  bVar1 = param_4[1];                 /* key byte B (info struct, uint8 = file[1]) */
  local_10[0] = *param_4;             /* key byte A (info struct, uint8 = file[0]) */
  if (0 < (short)uVar2) {             /* uVar2 = header_size */
    uVar9 = (uint)uVar2;
    pbVar10 = local_4;                /* the 0..header_size buffer */
    do {
      uVar9 = uVar9 - 1;
      *pbVar10 = *pbVar10 ^ local_10[0] ^ bVar1;   /* f[i] ^= file[0] ^ file[1] */
      pbVar10 = pbVar10 + 1;
    } while (uVar9 != 0);
  }
```
and at instruction level `[asm 0x10002386..0x100023a7]`:
```
10002386: 8a 0e                mov    cl,BYTE PTR [esi]        ; CL = info[0] = file[0]
10002388: 88 4c 24 10          mov    BYTE PTR [esp+0x10],cl   ; spill file[0]
10002398: 8a 11                mov    dl,BYTE PTR [ecx]        ; loop body
1000239a: 32 54 24 10          xor    dl,BYTE PTR [esp+0x10]   ; ^= file[0]
1000239e: 41                   inc    ecx
1000239f: 32 d0                xor    dl,al                    ; ^= file[1]  (AL = [esi+1])
100023a4: 88 51 ff             mov    BYTE PTR [ecx-0x1],dl
100023a7: 75 ef                jne    0x10002398
```

Range: the whole header `[0, header_size)` is obfuscated, not only the 18-byte prefix — the TLV
tags/sizes/values decode to clean ASCII only when `K` is applied `[file]`, and the reader XORs
`header_size` bytes (`FUN_100022c0` loop above). Bytes `0x00`/`0x01` are read *before* the XOR and are used
as the seeds; whether they are themselves also XORed on disk is immaterial because they are consumed raw.

The older build expresses the same thing as a function call with a "global BL"
(`[old build decomp FUN_10004ca0 @ 0x10004ca0]` `byte unaff_BL; ... *param_3 = *param_3 ^ unaff_BL ^ param_2;`),
which is precisely the `unaff_BL` the ticket asks about: it is `file[0]` loaded into `BL` by the caller.

`[INFERENCE]` The two key bytes are just an obfuscation seed pair (A,B) — nothing derives them from the
filename or the content; `K = A^B` and the pairs differ per file (`0x02`, `0x7C`, `0xE2`, `0x39` observed).

---

## 3. TLV list (`0x12 .. header_size-1`)

Each entry is `u16 LE tag | u16 LE size | size bytes of payload`; strings are NUL-terminated ASCII
(counted in `size`). `[decomp FUN_100022c0 @ 0x100022c0]`:
```c
  while( true ) {
    if (pbVar10 == (byte *)0x0) { uVar3 = 0; } else { uVar3 = *(undefined2 *)pbVar10; }      /* tag   */
    if (pbVar10 + 2 == (byte *)0x0) { sVar6 = 0; } else { sVar6 = *(short *)(pbVar10 + 2); } /* size  */
    local_c = local_c + 4;
    _Size = (size_t)sVar6;
    pbVar10 = pbVar10 + 4;
    if ((int)uVar8 < (int)(pbVar10 + (_Size - (int)local_4))) break;   /* out of header -> fail */
    switch(uVar3) {
    case 1: pcVar7 = &DAT_10058634; break;     /* "Name"    (string in .rdata) */
    case 2: pcVar7 = "Label";       break;
    case 3: pcVar7 = "Comment";     break;
    case 4: pcVar7 = &DAT_1005864c; break;     /* "Freq"    */
    case 5: pcVar7 = "Coding";      break;
    case 6: pcVar7 = "BitRate";     break;
    case 7: pcVar7 = &DAT_10058664; break;     /* "Rank"    */
    case 8: pcVar7 = "Version";     break;
    default: goto switchD_1000243a_default;    /* unknown tag -> delete descriptor, fail */
    }
```

| tag | attribute name | data | notes |
|---|---|---|---|
| 1 | `Name` | ASCII | not used by the shipped voices |
| 2 | `Label` | ASCII | mirrors the filename stem |
| 3 | `Comment` | ASCII | `"Acoustic file <Label> of voice <voice>"` |
| 4 | `Freq` | ASCII integer | sample rate in Hz |
| 5 | `Coding` | ASCII | codec / voice-module tag (`LTTS7Codec210`, `linear`, …) |
| 6 | `BitRate` | ASCII integer | bit/s |
| 7 | `Rank` | ASCII integer | `10` in every shipped file |
| 8 | `Version` | ASCII `a.b.c` | container/voice version |

Observed TLV lists `[file]`:

**`Jorge.32000.LTTS7Codec210.44000.10.bin`** (header_size 122):
```
tag 2 "Jorge\0" (6)
tag 3 "Acoustic file Jorge of voice Jorge\0" (35)
tag 4 "32000\0" (6)
tag 5 "LTTS7Codec210\0" (14)
tag 6 "44000\0" (6)
tag 7 "10\0" (3)
tag 8 "7.1.0\0" (6)
```
(18 + Σ(4+size) = 18 + 10+39+10+18+10+7+10 = 122 ✔)

**`JorgeGildedPhrases.32000.LTTS7Codec210.44000.10.bin`** (header_size 148):
`2:"JorgeGildedPhrases"`, `3:"Acoustic file JorgeGildedPhrases of voice Jorge"`, `4:"32000"`,
`5:"LTTS7Codec210"`, `6:"44000"`, `7:"10"`, `8:"7.1.0"`.

**`JorgeGildedParalinguistics.32000.LTTS7Codec210.44000.10.bin`** (header_size 164):
`2:"JorgeGildedParalinguistics"`, `3:"Acoustic file JorgeGildedParalinguistics of voice Jorge"`,
`4:"32000"`, `5:"LTTS7Codec210"`, `6:"44000"`, `7:"10"`, `8:"7.1.0"`.

**`payload/Ludoviko.16000.linear.256000.10.bin12`** (header_size 125):
`2:"Ludoviko"`, `3:"Acoustic file Ludoviko of voice Ludoviko"`, `4:"16000"`, `5:"linear"`,
`6:"256000"`, `7:"10"`, `8:"7.3.0"`.

The consumers are `ELQBinaryHeader*`: `ELQBinaryHeaderGetValue` / `LoadInfo` copy these attributes into an
`ELQDataDescriptor` via `ELQDataDescriptorSetAttribute(...,ELQfree)`
`[decomp FUN_100022c0]`, and `ELQBinaryHeaderLoadInfo` walks the `*.bin` files found for a voice
`[decomp ELQBinaryHeaderLoadInfo @ 0x100026d0]` (`ELQBinOpenNoCache(&local_10,'d',...)` +
`FUN_10002550(pcVar4,param_3)` per file).

---

## 4. Data region (`header_size .. EOF`) — **raw, not obfuscated**

The container never transforms the data region: every read path copies straight out of the RAM image,
the memory mapping or the disk cache, with no XOR anywhere
(`[decomp FUN_10003ba0 @ 0x10003ba0]` `_memcpy((void *)*puVar5,(void *)(puVar6[2] + uVar4),_Size);`).
De-obfuscation is done *by the header layer* (`FUN_100022c0`, §2), never by the container. There is no
second key/period: scanning the first 64 KiB of the region against all 256 single-byte keys yields at most
2.8 % zeros (a real fixed-key XOR would concentrate ~100 %), `[file]`:
`Jorge 0xc6/1.9%`, `GildedPhrases 0xbe/1.7%`, `GildedParalinguistics 0x3a/2.8%`, `Ludoviko 0xff/14.6 %`
(the latter is raw 16-bit linear audio, whose samples are mostly `0x0000`/`0xFFFF`).

For all three **Jorge** databases the region starts with **seven big-endian `u32`** and then
`nframes` frames of `bpf` bytes (`[file]`, arithmetic verified exactly):

```
header_size + 28 + nframes*bpf == filesize
```

| field | Jorge value | meaning |
|---|---|---|
| 0 | `0x0000ABE0` = 44000 | BitRate (mirrors TLV 6) |
| 1 | `0x0000000A` = 10 | Rank (mirrors TLV 7) |
| 2 | `0x00000280` = 640 | samples per frame (20 ms @ 32 kHz) |
| 3 | `0x00007D00` = 32000 | Freq (mirrors TLV 4) |
| 4 | `0x0000006E` = 110 | bytes per frame (bpf) |
| 5 | `0x00040AF4` = 264948 | frame count |
| 6 | `0x1FE90B6D` | cookie / checksum-ish |

Observed first 24 bytes of the data region (raw):
`00 00 ab e0 ⋅ 00 00 00 0a ⋅ 00 00 02 80 ⋅ 00 00 7d 00 ⋅ 00 00 00 6e ⋅ [f0]` — `[file]`, identical for
all three 32 kHz codec210 files at bytes `0..20` even though their header keys differ (`0x02`/`0x7C`/
`0xE2`), which independently proves the region is not keyed by the header key.

| file | header_size | fs − hs | frames `bpf` | check |
|---|---|---|---|---|
| Jorge | 122 | 29 144 308 | 264948 × 110 = 29 144 280 | 122+28+29 144 280 = **29 144 430** ✔ |
| GildedPhrases | 148 | 977 818 | 8889 × 110 = 977 790 | 148+28+977 790 = **977 966** ✔ |
| GildedParalinguistics | 164 | 1 095 408 | 9958 × 110 = 1 095 380 | 164+28+1 095 380 = **1 095 572** ✔ |

So a frame *i* (0-based) lives at `file[header_size+28+i*110 : header_size+28+(i+1)*110]`, plain bytes,
110 B/frame = 640 samples = 20 ms @ 32 kHz @ 44 000 bit/s.

**Older/other variant (`linear`, `Version=7.3.0`)** — `payload/Ludoviko.16000.linear.256000.10.bin12`
(5 069 459 B; the `.bin12` suffix is a payload-extraction artefact of the name). The *container* parses
exactly like Jorge (key `0x39`, `"LOQUENDOTTS7"`, `fmt=1`, `header_size=125`, full TLV list above, region
**not** obfuscated), but the payload format after `header_size` differs completely:

* there is **no** 28-byte BE-u32 sub-header — the values `16000`, `256000`, `44000`/`640`/`110` do not
  appear in any endianness at/near offset 125, and the 7 hypothetical BE u32s are meaningless
  (`16842751, 4261349376, 1536, …`);
* the region is plain **signed 16-bit little-endian PCM**: `[file]` 5 069 334 bytes = 2 534 667 samples,
  `min −18469`, `max 31805`, `mean −25.5`, `stdev 2612`, with an amplitude ramp from `±12` at the start
  (`01 00 ff ff fd ff 08 00 …` = `1, −1, −3, 8, 0, 6, 9, −1, …`) to `±18000` in the middle;
  2 534 667 samples @ 16 kHz = 158.4 s, and 5 069 334 B / 158.4 s = 32 000 B/s = 256 000 bit/s, which
  matches TLV `Freq=16000` + `BitRate=256000` exactly.

So: same container, different codec payload. The container spec ends at `header_size`; for
`LTTS7Codec210` voices a 28-byte sub-header follows (verified only for `BitRate`/`Freq`/`bytes_per_frame`
series and the exact `header_size+28+nframes*bpf == filesize` identity), for `linear` voices the samples
start immediately. `tools/bin_dump.py` prints the first 256 data-region bytes for either case and flags
the "no codec sub-header" variant.
`[INFERENCE]` the `linear` payload has no self-describing header; a reader must take `Freq`/`BitRate`
from the TLV list.

---

## 5. `ELQBin*` API — access types and semantics (Jorge addresses)

Access type is a single char at handle `+0x09`: `'d'` = DiskCache, `'m'` = memory-mapped file (MMF),
`'r'` = read whole file into RAM, `'s'` = shell/virtual (no backing store).

### 5.1 Return-value summary

| API | returns | obfuscated? | offsets |
|---|---|---|---|
| `ELQBinGetBuffer(bin, offset, count, unit, outSize, outFlag)` `0x10003f90` | pointer to a buffer holding the bytes: the caller's smart buffer if one was supplied, else the access substruct's own destination buffer (`sub[3]` for `'r'`/`'d'`, `sub[4]` for `'m'`); `NULL` on error/zero size | **raw / de-obfuscated = no** | byte offset = `offset * unit` |
| `ELQBinGetSmartBuffer(bin, offset, count, unit, outSize, smartBuf, outFlag)` `0x10003f20` | same bytes, copied into the caller's smart buffer (realloc'd as needed) | raw | byte offset = `offset * unit` |
| `ELQBinGetSmartBufferCore(smartBuf)` `0x10003f10` | `*(uint*)smartBuf` = the current data pointer inside the smart buffer | raw | — |
| `ELQBinGetRawData(bin)` `0x10003110` | `bin[1]` = the whole-file image (MMF base pointer, or the RAM copy); **`0` for `'d'`** | raw | — |
| `ELQBinSeek(bin, delta, unit)` `0x10003fc0` | `0` on success, `8` on error (`unit == 0` or unknown type); **returns no buffer** | n/a | moves state by `delta * unit` bytes |
| `ELQBinInitSmartBuffer()` `0x10003b50` | a fresh 8-byte smart-buffer handle `{ptr=NULL, capacity=0}` (returns it in `EAX`) | — | — |
| `ELQBinGetSize(bin, div)` `0x10003b00` | `sub[0] / div` | raw byte size | — |
| `ELQBinResizeSmartBuffer(h, n)` `0x10003f50` | data pointer, grown to `n` bytes (no-op if capacity already ≥ n) | — | — |
| `ELQBinDeleteSmartBuffer(h)` `0x10003b70` | frees `h[0]` then `h` | — | — |

Offset units — the core multiplies both size and offset by the unit size held in `EAX`
`[decomp FUN_10003ba0 @ 0x10003ba0]`:
```c
  if (in_EAX == 0) { ELQLogWrite(8,...,"ELQBinGetBuffer: cast value error.\n"); return 0; }
  if (param_2 == 0) { return 0; }
  _Size = param_2 * in_EAX;      /* param_2 = count (EDX) */
  uVar4 = param_3 * in_EAX;      /* param_3 = offset (1st stack arg) */
```
`[asm 0x10003bf0: imul edi,eax]` (count·unit) `[asm 0x10003bf3: imul ebx,eax]` (offset·unit) — so with
`unit = 1` (every call site in Util passes 1, e.g. `mov eax,0x1` at `0x1000231b`, `0x100021d7`) all
offsets/sizes are **byte units**. The wrapper proves `EAX` carries the 4th argument
`[asm 0x10003f9e: mov eax,DWORD PTR [esp+0x18]` inside `ELQBinGetBuffer`, i.e. arg #4 = unit size).

All access types return a copy/target buffer; for `'d'` when `smartBuf == NULL` the target is the
disk-cache's own destination buffer, which is *also* the buffer the container hands back to callers
(`*local_8 = *(uint*)(sub+0xc)` `[asm 0x10003e2b: lea eax,[ecx+0xc]`).

### 5.2 Block granularity

* minimum destination buffer for every access type: **`0x2800` = 10240 bytes**
  `[decomp FUN_10003ba0]` `if (_Size < 0x2801) { local_8 = (uint *)0x2800; }` / `if (_Size < 0x2801) {
  uVar7 = 0x2800; }` and `[asm 0x10003e3c..0x10003e44: cmp edi,0x2800 / ja / mov esi,0x2800]`.
  The capacity field `sub[1]` is realloc'd up to `max(_Size, 0x2800)`; reads never grow in smaller steps.
* DiskCache read-ahead block: **`0x5000` = 20480 bytes**
  `[decomp FUN_10002e20 @ 0x10002e20]`
  ```c
  pvVar3 = _malloc(0x5000);  unaff_ESI[1] = pvVar3;          /* staging buffer */
  if (0x4fff < _Size) { _Size = 0x5000; }
  _memset((void *)unaff_ESI[1],0,_Size);
  unaff_ESI[4] = 0x5000;                                     /* staging block size */
  sVar4 = _fread((void *)unaff_ESI[1],1,_Size,unaff_EDI);
  ```
  The block reader serves a range from the staging buffer when it lies inside
  `[cached_off, cached_off+blocksize)` and otherwise `fseek`s to the absolute byte offset and reads a whole
  `blocksize` block `[decomp FUN_10003020 @ 0x10003020]`:
  ```c
  _File = *(FILE **)(unaff_ESI + 0x10);
  _Offset = param_1 + iVar1;                       /* iVar1 = *(int*)(ESI+8) = base offset */
  if ((*(uint *)(unaff_ESI + 0x18) <= _Offset) &&
     (_Offset + unaff_EDI <= *(int *)(unaff_ESI + 0x20) + *(uint *)(unaff_ESI + 0x18))) { ...cache hit... }
  _fseek(_File,_Offset,0);
  lVar2 = _ftell(_File);
  *(long *)(unaff_ESI + 0x18) = lVar2;
  ```
  `0x5000` is the *read granularity* only; the caller still gets exactly `_Size` bytes (a short read at
  EOF is zero-filled and the out-flag is set, see below).

Boundary behaviour: a read that runs past the end is clamped to the remaining bytes and/or zero-filled,
with `*outFlag = 1` and `"ELQBinGetBuffer: Out of boundaries.\n"` logged
`[decomp FUN_10003ba0]` `if (param_6 != (undefined1 *)0x0) { *param_6 = 1; } ... _memset(...0,_Size);`.
`0x2801`-style checks and the `0x2800` floor make every access type behave identically for boundary reads.

### 5.3 What each access type returns from its substruct

```c
/* 'm' (MMF) — [decomp FUN_10003ba0] */
puVar6 = *(uint **)(param_1 + 0xc);
if (param_5 == (uint *)0x0) { puVar5 = puVar6 + 4; param_5 = puVar6; }   /* dst = sub[4], cap = sub[1] */
...
_memcpy((void *)*puVar5,(void *)(puVar6[2] + uVar4),_Size);              /* from mapped base sub[2] */
/* 'r' (whole file in RAM) */
if (param_5 == (uint *)0x0) { puVar5 = puVar6 + 3; param_5 = puVar6; }   /* dst = sub[3] */
_memcpy((void *)*puVar5,(void *)(puVar6[2] + uVar4),_Size);              /* from RAM image  sub[2] */
/* 'd' (DiskCache) */
local_8 = puVar6 + 3;  param_5 = puVar6;  param_5 = param_5 + 1;         /* dst = sub[3], cap = sub[1] */
```

### 5.4 `ELQBinSeek` semantics

`[decomp FUN_10003fc0]` + `[asm 0x1000401b..0x1000402a]`:
```
1000401b: mov ecx,DWORD PTR [esp+0x8]   ; delta          (param_2)
1000401f: mov eax,DWORD PTR [eax+0xc]   ; sub = bin->sub
10004022: imul ecx,edx                  ; n = delta * unit (EDX = param_3)
10004025: add DWORD PTR [eax+0x8],ecx   ; sub[2] += n
10004028: sub DWORD PTR [eax],ecx       ; sub[0] -= n
1000402a: xor eax,eax ; ret             ; return 0
```
i.e. it re-bases the view window: `base += delta*unit`, `size -= delta*unit`. It does **not** move a
file cursor by itself. `[INFERENCE]` because the same two fields are the read base for `'m'`/`'r'`
(`sub[2]` = mapped/RAM base pointer) and the file-offset base for `'d'`, seeking is meaningful for `'d'`
and would corrupt the base pointer for `'m'`/`'r'` — consistent with the leftover log strings
`"ELQBinAssign: bin access type <%c> unknown."` / `"ELQBinAssign: cast value error."` (the code was
clearly factored out of an `ELQBinAssign` that no longer exists in this build).

### 5.5 `ELQBinGetSize(bin, 1)`

Returns the **total size of the bin in bytes** (file size), i.e. the value of the substruct's first dword
divided by the divisor argument. `[decomp ELQBinGetSize @ 0x10003b00]`
```c
  if (((param_2 != 0) && (((cVar1 = *(char *)((int)param_1 + 9), cVar1 == 'd' || (cVar1 == 'm')) || (cVar1 == 'r'))))
     && ((uint *)param_1[3] != (uint *)0x0)) {
    return *(uint *)param_1[3] / param_2;
  }
```
`[asm 0x10003b2b..0x10003b36: mov eax,[eax+0xc] / mov eax,[eax] / div esi]`.

The field is filled with the file length measured at open time for all three access types:
* `'d'`: `[decomp FUN_10003510 @ 0x10003510]` `psVar3[2] = sVar5; *psVar3 = local_10;` where `local_10`
  is the size produced by `FUN_10002dd0` (`_fseek(f,0,2); lVar1 = _ftell(f); … *unaff_EDI = size;`).
* `'r'`: `psVar3[0] = local_10` then `_fread(_Dst[1],1,local_10,_File)` reads exactly that many bytes.
* `'m'`: `*psVar3 = local_10` after `ELQMemoryMappedFileOpen(...)`.

Therefore `ELQBinGetSize(bin,1)` = byte length of the whole file (29144430 for the Jorge DB, confirmed by
`ls -l` `[file]`), and the header probe uses it to bound `header_size`
(`if ((undefined1 *)(int)sVar4 <= local_8)`). The second argument is a plain divisor: the function is
`sub[0] / div` (integer), so `ELQBinGetSize(bin,110)` = 29144430/110 = **264949** — deliberately *not* the
frame count (264948), because the divisor applies to the file size including the 150-byte
header+sub-header prefix. After an `ELQBinSeek` the returned value is the *remaining* size (`sub[0]` was
decremented) `[INFERENCE]`.

---

## 6. `ELQBin` handle layout

`ELQBinOpen` / `ELQBinOpenNoCache` are thin thunks that call the internal open with a cache flag
`[asm 0x10003960: push 0x1 / call 0x10003510]`, `[asm 0x10003990: push 0x0 / call 0x10003510]`.
The internal open allocates and zeroes **`0x214`** bytes in the Jorge build
`[asm 0x10003596: push 0x214 / push 0x0 / push ebx / call 0x1004b1b0]` (= `memset(handle,0,0x214)`), and
`ELQBinShell` (`0x10003190`) and `ELQBinVirtualOpen` (`0x10003450`) allocate the same `0x214`
`[decomp ELQBinShell @ 0x10003190] _Dst = _malloc(0x214); _memset(_Dst,0,0x214);`.

> The ticket's "0x218 bytes" is the **older** build (`engine_re/LTTS7Util.dll`): there the handle is `0x218`
> and a log-handle dword sits at `+0x10` (`[old build decomp FUN_10003ca0 @ 0x10003ca0] _Dst[4] = param_3;`),
> pushing the filename to `+0x14` and the extra dword to `+0x214`. In the Jorge build the log handle is
> **not** stored in the handle (every `ELQLogWrite` in the open path passes `0x0` or the caller's handle),
> so the fields shift down by 4 → `0x214`. Both layouts are listed below.

### Jorge build — `ELQBin` handle, `0x214` bytes

| off | type | content | evidence |
|---|---|---|---|
| `+0x00` | `void*` | type tag = address of `ELQBinOpen` (`0x10003960`), `0` = unusable | `[asm 0x10003118 cmp DWORD PTR [eax],0x10003960]`; `[asm 0x100035b6 mov DWORD PTR [ebx],0x0]` then `*_Dst = ELQBinOpen` |
| `+0x04` | `void*` | whole-file data pointer: MMF base (`'m'`), RAM image (`'r'`), `0` for `'d'` | `[decomp ELQBinGetRawData] return param_1[1];`; `[asm 0x10003126 mov eax,DWORD PTR [eax+0x4]]`; `[decomp FUN_10003510] _Dst[1] = pvVar4;` / `_Dst[1] = uVar6;` / `_Dst[1] = 0;` |
| `+0x08` | `u8` | "data is borrowed" flag (`1` for shell/clone, `0` for a real open); gates freeing/closing the backing store in `ELQBinClose` (`'r'`: `handle+4`; `'m'`: the MMF) | `[asm 0x100035b2 mov BYTE PTR [ebx+0x8],0x0]`; `[decomp ELQBinShell] *(undefined1 *)(_Dst + 2) = 1;` (`_Dst+2` = byte `+0x08`); `[decomp ELQBinCloneEx] *(undefined1 *)(param_1 + 2) = 1;` |
| `+0x09` | `char` | access type: `'d'`, `'m'`, `'r'`, (`'s'` shell) | `[asm 0x100035a6 mov BYTE PTR [ebx+0x9],al]`; `[asm 0x10003b19 mov cl,BYTE PTR [eax+0x9]]` |
| `+0x0C` | `void*` | access substruct (see §7), `NULL` if none | `[asm 0x10003b2b mov eax,DWORD PTR [eax+0xc]]`; `[asm 0x10003e0c mov ecx,DWORD PTR [ecx+0xc]]` |
| `+0x10` | `char[0x200]` | NUL-terminated full file name | `[asm 0x100035f4 lea edx,[ebx+0x10]` … copy loop `]; `[decomp ELQBinGetFilename] return param_1 + 4;` |
| `+0x210` | `u32` | 5th open argument, kept verbatim | `[asm 0x1000360d mov DWORD PTR [ebx+0x210],eax]` from `[ebp+0x18]` |
| `+0x214` | — | end of allocation (`0x10 + 0x200 + 4 = 0x214`) | `[asm 0x10003596 push 0x214]` |

Open sequence (`[asm 0x10003596..0x10003616]`): `memset(handle,0,0x214)` →
`handle[9] = access char` → `handle[8] = 0` → `handle[0] = 0` → `fopen`+size (`FUN_10002dd0`) →
`handle[0x10..] = filename` → `handle[0x210] = arg5` → per-type substruct setup → `handle[0] = ELQBinOpen`.
On any failure the handle is freed, `*out = 0` and an error code is returned (`3` NULL bin pointer,
`8` NULL filename / unknown access type, `5` out of memory / read error, `2` file open error, `0` OK).

### Compatibility — older build `0x218`

Same fields shifted by `+4` from `+0x10`: `+0x04` data, `+0x08` flag, `+0x09` type, `+0x0C` substruct,
`+0x10` log handle, `+0x14` `char[0x200]` filename, `+0x214` 5th arg. `[old build decomp FUN_10003ca0]`
`_Dst[4] = param_3;` / filename copy at `+0x14` / `_Dst[0x85] = param_5;` (`0x85*4 = 0x214`, +4 = `0x218`).
A reimplementation must therefore not assume either size; it should only rely on the field meanings.

---

## 7. Access substructs

All are allocated per handle and reachable at `handle+0x0C`.

### `'d'` — DiskCache, `0x24` bytes

```
+0x00 u32  total size in bytes                     (ELQBinGetSize / ELQBinSeek)
+0x04 u32  capacity of the destination buffer, always >= max(requested, 0x2800)
+0x08 u32  base file offset (advanced by ELQBinSeek)
+0x0C void* destination cache buffer (the pointer returned by ELQBinGetBuffer without a smart buffer)
+0x10 FILE* file handle
+0x14 void* staging buffer (malloc 0x5000, or a caller-supplied buffer)
+0x18 u32  cached file offset (last ftell), 0 at open
+0x1C u8   "staging buffer is external" flag
+0x20 u32  staging block size = 0x5000
```
Evidence: `[asm 0x10003e24 lea eax,[ecx+4] / 0x10003e2b lea eax,[ecx+0xc]]` (cap = `sub[1]`,
dst = `sub[3]`), `[asm 0x1000401f..0x10004028]` (size/base), `[decomp FUN_10003020]` (`+0x8` base,
`+0xc` dst, `+0x10` FILE\*, `+0x14` staging, `+0x18` cached offset, `+0x20` block size),
`[decomp FUN_10002e20]` (called with `ESI = sub+0x10`: `ESI[0]=FILE`, `ESI[1]=staging`,
`*(u8*)(ESI+0xc)=own-flag`, `ESI[2]=0`, `ESI[4]=0x5000`), `[decomp ELQBinClose case 0x64]` (frees
`sub[3]`, then `FUN_10002f00` which frees `ESI[1]` and `fclose(ESI[0])`).

### `'m'` — MMF, `0x14` bytes

```
+0x00 u32  total size in bytes
+0x04 u32  capacity of the destination buffer
+0x08 void* mapped base pointer        (== handle+0x04, ELQBinGetRawData)
+0x0C void* MMF handle                 (out-param of ELQMemoryMappedFileOpen, ELQMemoryMappedFileClose'd)
+0x10 void* destination buffer         (realloc'd on demand, freed with ELQfree)
```
Evidence: `[decomp FUN_10003510 'm'] *psVar3 = local_10; psVar3[4] = 0; psVar3[2] = uVar6 & (cVar1 == 'd') - 1;`
plus `uVar6 = ELQMemoryMappedFileOpen(param_4,'\0',1,psVar3 + 3,param_3); _Dst[1] = uVar6;`,
`[decomp FUN_10003ba0 'm'] puVar5 = puVar6 + 4;` (destination = `sub[4]`),
`[decomp ELQBinClose case 0x6d]` (frees `sub[4]`, `ELQMemoryMappedFileClose(sub[3])`).

### `'r'` — whole file in RAM, `0x10` bytes

```
+0x00 u32  total size in bytes
+0x04 u32  capacity of the destination buffer
+0x08 void* base pointer, == handle+0x04 (malloc'd file image)
+0x0C void* destination buffer
```
Evidence: `[decomp FUN_10003510 'r'] pvVar4 = _malloc(local_10); _Dst[1] = pvVar4; ... *psVar3 = local_10;
psVar3[2] = _Dst[1];`, `[decomp FUN_10003ba0 'r'] puVar5 = puVar6 + 3;`,
`[decomp ELQBinClose case 0x72]` (frees `handle+4` when the borrowed-flag is clear, then `sub[3]`).

`ELQBinCloneEx` copies filename/type/5th-arg and, per type, all fields except the buffers
(`[decomp ELQBinCloneEx @ 0x10003220]` `param_1[1] = param_2[1]; uVar4 = *puVar2; puVar7[3] = 0; *puVar7 = uVar4;
uVar4 = puVar2[2]; puVar7[1] = 0; puVar7[2] = uVar4;`) — a clone shares the `handle+0x04` data pointer but
must have the borrowed flag set (`*(undefined1 *)(param_1 + 2) = 1;`) so neither copy frees it twice.

---

## 8. Reader/consumer chain (context)

```
ELQBinOpen(&h, 'd'|'m'|'r', log, "voice.bin", 0)
  └─ FUN_10003510 (0x10003510)  ▸ malloc(0x214), fopen+size, substruct, handle[0]=ELQBinOpen
ELQBinaryHeaderIsPresent(bin, &hdr)      → FUN_10002160 (0x10002160)   [0x12 read, key, "LOQUENDOTTS7"]
FUN_10005100 / ELQBinaryHeaderLoadInfo   → FUN_10002550 / 0x100026d0  [version==1, then ReadHeader]
FUN_100022c0 (0x100022c0)                ▸ XOR whole header, parse TLVs into an ELQDataDescriptor
ELQBinGetBuffer/GetSmartBuffer           ▸ raw payload bytes (frames for codec210)
```

Known constants: signature `"LOQUENDOTTS7"` (`0x10058674`), tag names `"Label"…"Version"`
(`0x10058634`/`0x1005864c`/`0x10058664` are the `Name`/`Freq`/`Rank` strings), error strings
`"ELQBinOpen: NULL bin pointer error.\n"`, `"ELQBinOpen: Filename NULL.\n"`, `"ELQBinOpen: bin access type
<%c> unknown.\n"`, `"ELQBinOpen: Init DiskCache error.\n"`, `"ELQBinOpen: Error opening in MMF %s.\n"`,
`"ELQBinGetBuffer: cast value error.\n"`, `"ELQBinGetBuffer: Out of boundaries.\n"`,
`"ELQBinGetBuffer: Read error.\n"`, `"ELQBinGetBuffer: Out of memory.\n"`,
`"ReadHeader: Error creating HID."`,
`"ReadHeader: Warning. Header format not supported."`, `"ELQBinSeek: cast value error.\n"`,
`"ELQBinSeek: bin access type <%c> unknown.\n"`.

## 9. Reimplementation checklist

1. Read `b0 = f[0]`, `b1 = f[1]`; `k = b0 ^ b1`; decode `f[2:header_size]` with `k`.
2. Require `f[2:14] == b"LOQUENDOTTS7"`, `u16le(f,14) == 1`, `u16le(f,16) == header_size`,
   `0x12 <= header_size <= len(f)`.
3. Parse TLVs from `0x12` to `header_size`; unknown tag ⇒ reject the file.
4. Data region starts at `header_size`; **no** de-obfuscation. For `LTTS7Codec210` voices read the 7 BE
   `u32`s and then `nframes` × `bpf` frames (verify `header_size+28+nframes*bpf == len(f)`).
5. Never assume the handle size; the Jorge build uses `0x214`, the older one `0x218`.

Reference implementation of the read side: `tools/bin_dump.py` (standalone, stdlib only) —
`python3 tools/bin_dump.py` dumps the Jorge database by default, `--offset N --length M` dumps an
arbitrary file range, `--key N` overrides the derived key.
