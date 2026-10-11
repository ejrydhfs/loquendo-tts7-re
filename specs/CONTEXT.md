# Shared context: Loquendo TTS 7 voice "Jorge" — DB/inventory formats

Working dir: `/home/asdf/Downloads/ltts_re` (use it as cwd; all relative paths below).

## Deliverable goal
Reverse-engineer the **vocal database (.bin)** and **unit inventory (.sde)** formats of Loquendo TTS 7
so another agent can reimplement the synthesizer binary-free and reproduce the *same voice* from the
shipped data files. Each sub-task writes its own spec under `specs/` and its own tools under `tools/`.
**Never edit `REPORT.md`** (the parent owns it). Do not run builds/lint/tests mid-flight.

## Authoritative inputs (the voice package, extracted with innoextract)
`jorge/pf/Loquendo/LTTS7/`
- `bin/LoqTTS7.dll` (746 KiB engine) — NEWER build than `engine_re/LoqTTS7.dll`.
- `bin/LTTS7Util.dll` (551 KiB) — NEWER than `engine_re/LTTS7Util.dll` (266 KiB).
- `bin/LTTS7Codec210.dll`, `bin/LTTS7CodecMsx.dll`, `bin/LTTS7Jorge.dll` (voice module), `bin/LTTS7DB.dll`,
  `bin/LTTS7GPR.dll`, `bin/LTTS7SAPI5.dll`, `bin/TTSDiag.exe`
- `data/Jorge.vcf`, `data/voices/Jorge/Jorge.vde`, `JorgeGilded.gde`,
  `Jorge.sde` (1 511 129 B), `Jorge.32000.LTTS7Codec210.44000.10.bin` (29 144 430 B),
  `JorgeGildedPhrases.sde/.bin`, `JorgeGildedParalinguistics.sde/.bin`

Existing Ghidra dumps (from the OLDER `engine_re/` build — good as a fast index, but **verify against the
jorge DLLs**): `decomp_util.txt`, `decomp_loqtts.txt`, `decomp_codec210.txt`, `decomp_codecmsx.txt`,
`decomp_db.txt`, `decomp_ludoviko.txt`, `decomp_director.txt`.

Ghidra headless (test it first; ~minutes per DLL):
```
/opt/ghidra/support/analyzeHeadless /tmp/ghproj_<tag> proj -import jorge/pf/Loquendo/LTTS7/bin/LTTS7Util.dll \
  -postScript DumpAll.java /home/asdf/Downloads/ltts_re/jorge_re/decomp_util_jorge.txt \
  -scriptPath /home/asdf/Downloads/ltts_re/ghidra_scripts
```
(`ghidra_scripts/DumpAll.java` decompiles all functions; pass the output path as script arg.)

## Already-established facts (do NOT re-derive; build on them)

### A. `.bin` container = `LOQUENDOTTS7` binary header (from `LTTS7Util.dll`, `decomp_util.txt`)
- `ELQBin*` API in Util: `ELQBinOpen`, `ELQBinOpenNoCache`, `ELQBinClose`, `ELQBinGetSize`, `ELQBinSeek`,
  `ELQBinGetBuffer`, `ELQBinGetRawData`, `ELQBinInitSmartBuffer`, `ELQBinGetSmartBuffer(Core)`,
  `ELQBinResizeSmartBuffer`, `ELQBinClone(Ex)`, `ELQBinVirtualOpen`, `ELQBinGetFilename/Type/Exclusive/LogHandle`,
  plus `ELQBinaryHeaderIsPresent/LoadInfo/UnLoadInfo/CheckCondition/CheckMultipleConditions/GetValue/CopyInMemory`.
- Access types: memory-mapped file ("MMF") and DiskCache (`ELQBinClone: bin access type <%c> unknown`).
- Recovered `ReadHeader` logic (`FUN_10004de0` + `FUN_10004ec0` in `decomp_util.txt`):
  * 18-byte fixed prefix read at offset 0 (`ELQBinGetBuffer(bin,0,0x12,1,…)`):
    `u8 [0]`, `u8 keyish [1]`, then 12 bytes = signature XORed → `"LOQUENDOTTS7"` (strncmp 12), then
    `u16 format_version` (== 1), `u16 header_size`.
  * De-obfuscation: `FUN_10004ca0(len, byteKey, ptr)` = `for i<len: ptr[i] ^= unaff_BL ^ byteKey` —
    i.e. effective key = (BL register at entry, a global/constant the caller loads) XOR byteKey.
    Empirically, on the real file, XOR **0x02** turns the header text/values into coherent form:
    offline decode of `Jorge.…bin` with `b ^ 0x02` yields
    `29 2b 4c 4f 51 55 45 4e 44 4f 54 54 53 37 01 00 7a 00 02 00 06 00 "Jorge\0" …`
    i.e. `format_version=1`, `header_size=0x7A=122`.
  * After the 18-byte prefix (from offset 0x12) comes a **TLV list until header_size**:
    `u16 tag, u16 size, u8 data[size]` (little-endian u16s), tags (verified against the contiguous .rdata
    string table `Name/Label/Comment/Freq/Coding/BitRate/Rank/Version`):
    `1=Name, 2=Label, 3=Comment, 4=Freq, 5=Coding, 6=BitRate, 7=Rank, 8=Version`.
    Observed on the real file: `2=Label:"Jorge"`, `3=Comment:"Acoustic file Jorge of voice Jorge"`,
    `4=Freq:"32000"`, `5=Coding:"LTTS7Codec210"`, `6=BitRate:"44000"`, `7=Rank:"10"`, `8=Version:"7.1.0"`.
    The DB filename mirrors these: `<Label>.<Freq>.<Coding>.<BitRate>.<Rank>.bin`.
  * Data region begins at `header_size` (122). Its first bytes (raw) are
    `00 00 ab e0 00 00 00 0a 00 00 02 80 00 00 7d 00 00 00 00 6e 00 04 0a f4 …` = 7 big-endian u32
    [BitRate, Rank, samples_per_frame(640), Freq, bytes_per_frame(110), nframes, cookie]; the
    sub-header is stored plain (not obfuscated) and `header_size + 28 + nframes*bpf == filesize`.
    RESOLVED: the FRAMES that follow ARE obfuscated - each 110-byte frame is byte-XORed with the
    single key = sub-header byte 27 (last byte of the cookie); verified by EngineBind and re-verified
    independently: three files with keys 0x6D/0x15/0x91 all normalise frame[0] to {0x38..0x3F}.
- `ELQBinaryHeaderGetValue` / `LoadInfo` read these fields into an `ELQDataDescriptor` (Util).

### B. `.sde` = unit inventory (descriptor with bit-7-set ASCII)
Offline transform: clear bit 7 (`b & 0x7f`) turns `Jorge.sde` into printable text, 153 223 lines, e.g.:
```
10,4
LTTSComponentVersion=7.0.0
N=3647,82007
U=# # @ @
L# !'E #-% "
R# #>E "
U=# `a #
L# !*Jz #:< x
R# #T) #G
…
  R3 =t q
  L4 YR q
```
(the fields after `U=`/`L<n>`/`R<n>` are space-separated printable bytes; the numeric encoding of those
fields is still unknown — find it in the reader code.)

### C. Codec 210 (from `decomp_codec210.txt`)
- 7-entry ABI plugin (`LTTS7Codec210.dll` export = single dispatcher at RVA 0x4760).
- `FUN_100010c0(esi, edi)`: `len = *(u16*)(esi+0x474); key = *(u8*)(esi+0x479); for i<len: buf[i] ^= key;`
  then `FUN_10001810(esi,buf,len)`, `FUN_10001720(esi[10], esi, esi[0x475])`.
- 32000 Hz-specific init: `FUN_10001b00(32000)`.

### D. Engine ↔ plugin binding (from `decomp_loqtts.txt`)
- `FUN_10024ff0(voiceDescriptor, session)`: loops i=0..15 over `VocalDBName[i]` / `VocalDBPath[i]`;
  tag `LinkedSde[ALL]`/`LinkedSde[i]` = 'y' selects the **linked SDE plugin** path → `FUN_10024ba0`,
  which does `ELQPluginIni(slot, engine, desc, *piVar3+0x400, "SdeDllMain", 0)` then looks up
  `GetVersion`, `CatVoiceVersion`, `CatSdeData`, `GetSdeData` (log: `"Error loading dbunita from %s"`).
  No shipped module exports `SdeDllMain`; the Jorge descriptors have **no** `LinkedSde` tag → Jorge uses
  the fallback path.
- Fallback path: builds a path from `VocalDBPath[i]`/`VoicePath` + `DataPath`, appends the suffix built
  from `DAT_1008eec0/1008eec4` (likely `".bin"`), then `FUN_10024ad0(desc)` →
  `ELQDataDescriptorGetAttribute(desc,<tag at DAT_10088a0c>,&name,0)`, `ELQFileFullName`,
  `ELQFileResolveSymbolicName(buf,0x200,full, name,0,0)`, `ELQSharedResourceAdd(engine, &h, path, 0,0,0)`
  → handle stored at `session+0x14+i*4`, `session[i+0x94]=1`.
- `.bin` files are registered as a shared-resource type via pattern `*.bin` in `LTTS7Util.dll`.
- `ELQTagsDescriptor*` (Util) = the tags-descriptor parser; Util also has `ELQDataDescriptor*`,
  `ELQFileSearch*`, `ELQBuffer*`, `ELQMA*`.

### E. Voice module `LTTS7Jorge.dll`
Single PE export (dispatcher, RVA 0x1170). Its internal name table (strings) includes
`GetVersion, ELQGetPhonemes, ELQVoiceChannelOpen/Close, FonVidAllofonoAnalisi, FonVidAllofonoVoce,
FonVidAnalisi2Sintesi, FonVidMetaFonema, ELQLogWrite, ELQmalloc, ELQfree, ELQSharedResourceIni/Delete`.
The engine resolves procedures with `ELQPluginGetProc(handle,"<name>",&ptr)`, which goes through the
dispatcher (name string compared in the DLL).
